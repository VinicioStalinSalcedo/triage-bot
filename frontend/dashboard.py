"""Interfaz Streamlit del triage bot: vista del paciente y panel del médico.

Las dos vistas viven en una sola aplicación a propósito, pero consumen el
sistema por caminos distintos, y esa asimetría es intencional:

  - El paciente entra por el webhook de n8n y recibe ÚNICAMENTE su
    enrutamiento (a dónde ir y con qué urgencia). Nunca ve el diagnóstico
    presuntivo ni la receta borrador.
  - El médico lee directamente de PostgreSQL y ve el análisis completo, que
    puede editar y firmar. La IA propone; la persona decide.
"""
import os

import requests
import streamlit as st
from dotenv import load_dotenv

from backend.db import get_attended_cases, get_case, get_pending_cases, sign_case

load_dotenv()

N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL", "http://n8n:5678/webhook/triage")

COLOR_STYLE = {
    "Rojo": {"emoji": "🔴", "render": st.error},
    "Amarillo": {"emoji": "🟡", "render": st.warning},
    "Verde": {"emoji": "🟢", "render": st.success},
}

st.set_page_config(page_title="Triaje Preliminar - Dispensario EPN", page_icon="🏥", layout="wide")


def _fuentes(caso: dict) -> list[dict]:
    """Normaliza fuentes_rag: n8n la almacena envuelta en {"lista": [...]}."""
    valor = caso.get("fuentes_rag")
    if isinstance(valor, dict):
        valor = valor.get("lista", [])
    return valor or []


def vista_paciente() -> None:
    st.title("🏥 Consulta de síntomas")
    st.caption(
        "Describa lo que siente con sus propias palabras. Un profesional revisará su caso; "
        "esta herramienta no reemplaza una valoración médica."
    )

    with st.form("sintomas"):
        symptoms = st.text_area(
            "¿Qué siente?",
            placeholder="Ej.: desde ayer me duele mucho la cabeza, tengo náuseas y me molesta la luz",
            height=140,
        )
        col1, col2, col3 = st.columns(3)
        edad = col1.number_input("Edad", min_value=0, max_value=120, value=25)
        sexo = col2.selectbox("Sexo", ["", "femenino", "masculino"])
        gestante = col3.selectbox("¿Está embarazada?", ["No aplica", "Sí", "No"])
        enviar = st.form_submit_button("Enviar mi consulta", type="primary", use_container_width=True)

    if not enviar:
        return
    if not symptoms.strip():
        st.warning("Por favor describa sus síntomas antes de enviar.")
        return

    payload = {"symptoms": symptoms.strip(), "edad": int(edad), "sexo": sexo or None}
    if gestante != "No aplica":
        payload["gestante"] = gestante == "Sí"

    with st.spinner("Analizando sus síntomas..."):
        try:
            respuesta = requests.post(N8N_WEBHOOK_URL, json=payload, timeout=120)
            respuesta.raise_for_status()
            datos = respuesta.json()
        except requests.RequestException as exc:
            st.error(f"No se pudo procesar su consulta. Acérquese al dispensario. (Detalle: {exc})")
            return

    prioridad = datos.get("prioridad", "Verde")
    estilo = COLOR_STYLE.get(prioridad, COLOR_STYLE["Verde"])
    estilo["render"](f"{estilo['emoji']}  {datos.get('mensaje', 'Su caso fue registrado.')}")
    st.caption("Su caso quedó en la cola del médico de turno.")


def _tarjeta_analisis(caso: dict) -> None:
    estilo = COLOR_STYLE.get(caso["color_triage"], COLOR_STYLE["Verde"])
    estilo["render"](f"{estilo['emoji']}  Triaje **{caso['color_triage']}** · Caso #{caso['id']}")

    demograficos = [
        f"**Edad:** {caso['edad']}" if caso.get("edad") is not None else None,
        f"**Sexo:** {caso['sexo']}" if caso.get("sexo") else None,
        f"**Gestante:** {'sí' if caso['gestante'] else 'no'}" if caso.get("gestante") is not None else None,
    ]
    st.markdown(" · ".join(d for d in demograficos if d) or "_Sin datos demográficos_")

    st.subheader("Relato del paciente")
    st.info(caso["symptoms_text"])

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Diagnóstico presuntivo")
        st.write(caso.get("diagnostico_presuntivo") or "_No disponible_")
        st.subheader("Explicación para el paciente")
        st.write(caso.get("explicacion_feynman") or "_No disponible_")
    with col2:
        st.subheader("Contraindicaciones y alertas")
        st.write(caso.get("contraindicaciones_alertas") or "_No disponible_")
        st.subheader("Justificación clínica")
        st.write(caso.get("justificacion_clinica_rag") or "_No disponible_")

    fuentes = _fuentes(caso)
    with st.expander(f"Fuentes MSP recuperadas ({len(fuentes)})"):
        if not fuentes:
            st.write(
                "Ninguna guía del MSP superó el umbral de relevancia. El triaje se apoyó "
                "en criterio clínico general — revise con especial atención."
            )
        for fuente in fuentes:
            st.write(f"- `{fuente.get('guia')}` pág. {fuente.get('pagina')} (distancia {fuente.get('distancia')})")


def vista_medico() -> None:
    st.title("🩺 Panel del médico de turno")

    pendientes = get_pending_cases()
    conteo = {color: sum(1 for c in pendientes if c["color_triage"] == color) for color in COLOR_STYLE}
    col1, col2, col3 = st.columns(3)
    col1.metric("🔴 Rojo", conteo["Rojo"])
    col2.metric("🟡 Amarillo", conteo["Amarillo"])
    col3.metric("🟢 Verde", conteo["Verde"])

    if not pendientes:
        st.success("No hay casos pendientes en la cola.")
    else:
        st.caption("Cola ordenada por gravedad y, dentro de cada color, por orden de llegada.")
        opciones = {
            f"{COLOR_STYLE[c['color_triage']]['emoji']} #{c['id']} · {c['symptoms_text'][:60]}...": c["id"]
            for c in pendientes
        }
        etiqueta = st.selectbox("Caso a revisar", list(opciones))
        caso = get_case(opciones[etiqueta])

        _tarjeta_analisis(caso)

        st.divider()
        st.subheader("Plan definitivo")
        st.caption(
            "La IA propone el borrador siguiente. Edítelo según su criterio: lo que quede aquí "
            "es lo que se emite al paciente bajo su firma."
        )
        plan_final = st.text_area(
            "Receta o plan (editable)",
            value=caso.get("propuesta_ia") or "",
            height=260,
            key=f"plan_{caso['id']}",
        )
        medico = st.text_input("Profesional que autoriza", placeholder="Dr./Dra. Nombre Apellido")

        if st.button("✅ Autorizar, firmar y emitir", type="primary"):
            if not medico.strip():
                st.warning("Indique el nombre del profesional que autoriza.")
            elif not plan_final.strip():
                st.warning("El plan no puede quedar vacío.")
            else:
                sign_case(caso["id"], plan_final.strip(), medico.strip())
                st.success(f"Caso #{caso['id']} firmado y emitido.")
                st.rerun()

    with st.expander("Historial de casos atendidos"):
        atendidos = get_attended_cases()
        if not atendidos:
            st.write("_Todavía no hay casos atendidos._")
        for caso in atendidos:
            st.write(
                f"{COLOR_STYLE[caso['color_triage']]['emoji']} **#{caso['id']}** · "
                f"{caso['diagnostico_presuntivo']} · firmado por {caso['attended_by']}"
            )


vista = st.sidebar.radio("Vista", ["Paciente", "Médico"])
st.sidebar.caption(
    "Proyecto final AIE — Summer Camp 2026\n\n"
    "Triaje preliminar asistido por IA con guías del MSP Ecuador. "
    "Toda decisión clínica pasa por validación humana."
)

if vista == "Paciente":
    vista_paciente()
else:
    vista_medico()
