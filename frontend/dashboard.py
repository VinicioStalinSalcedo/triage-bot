"""Interfaz Streamlit del triage bot: recepción, consola clínica e indicadores.

Las vistas consumen el sistema por caminos distintos, y esa asimetría es el
human-in-the-loop hecho arquitectura:

  - RECEPCIÓN entra por el webhook de n8n y devuelve ÚNICAMENTE el
    enrutamiento. El paciente nunca ve el diagnóstico presuntivo ni la
    propuesta terapéutica.
  - CONSOLA lee PostgreSQL y muestra el análisis completo con sus fuentes.
    La IA propone; el profesional edita y firma.
  - INDICADORES expone la cobertura real del corpus, incluida la proporción
    de casos resueltos sin respaldo documental.
"""
import os

import requests
import streamlit as st
from dotenv import load_dotenv

from backend.db import (
    get_attended_cases,
    get_case,
    get_estadisticas,
    get_pending_cases,
    get_uso_de_guias,
    sign_case,
)

load_dotenv()

N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL", "http://n8n:5678/webhook/triage")

TRIAJE = {
    "Rojo":     {"color": "#DC2626", "fondo": "#FEF2F2", "icono": "🔴", "etiqueta": "Emergencia"},
    "Amarillo": {"color": "#D97706", "fondo": "#FFFBEB", "icono": "🟡", "etiqueta": "Urgencia"},
    "Verde":    {"color": "#16A34A", "fondo": "#F0FDF4", "icono": "🟢", "etiqueta": "Primaria"},
}

st.set_page_config(page_title="Triaje EPN", page_icon="🏥", layout="wide")


def inyectar_estilos() -> None:
    st.markdown("""
    <style>
      #MainMenu, footer {visibility: hidden;}
      .block-container {padding-top: 2.2rem; max-width: 1180px;}

      .marca {
        display:flex; align-items:baseline; gap:.65rem;
        border-bottom:1px solid #E2E8F0; padding-bottom:.9rem; margin-bottom:1.6rem;
      }
      .marca h1 {font-size:1.45rem; margin:0; color:#0F172A; letter-spacing:-.02em;}
      .marca span {font-size:.82rem; color:#64748B;}

      .tarjeta {
        background:#fff; border:1px solid #E2E8F0; border-radius:10px;
        padding:1.1rem 1.3rem; margin-bottom:.85rem;
      }
      .tarjeta h4 {
        margin:0 0 .5rem 0; font-size:.72rem; font-weight:700;
        text-transform:uppercase; letter-spacing:.07em; color:#64748B;
      }
      .tarjeta p {margin:0; color:#1E293B; line-height:1.6; font-size:.94rem;}

      .banda {
        border-left:5px solid var(--c); background:var(--bg);
        border-radius:8px; padding:1rem 1.25rem; margin-bottom:1.3rem;
      }
      .banda .nivel {font-size:1.1rem; font-weight:700; color:var(--c);}
      .banda .detalle {font-size:.88rem; color:#475569; margin-top:.15rem;}

      .relato {
        background:#F8FAFC; border-left:3px solid #94A3B8; border-radius:6px;
        padding:.85rem 1.1rem; font-style:italic; color:#334155; line-height:1.6;
      }

      .kpi {
        background:#fff; border:1px solid #E2E8F0; border-radius:10px;
        padding:1rem 1.2rem; text-align:center;
      }
      .kpi .n {font-size:2rem; font-weight:700; line-height:1.1;}
      .kpi .t {font-size:.74rem; text-transform:uppercase; letter-spacing:.06em; color:#64748B; margin-top:.2rem;}

      .aviso {
        background:#FFFBEB; border:1px solid #FDE68A; border-radius:8px;
        padding:.8rem 1rem; color:#92400E; font-size:.88rem;
      }
      .fuente {
        font-family:ui-monospace, monospace; font-size:.8rem; color:#475569;
        padding:.3rem 0; border-bottom:1px dashed #E2E8F0;
      }
    </style>
    """, unsafe_allow_html=True)


def cabecera(titulo: str, subtitulo: str) -> None:
    st.markdown(
        f'<div class="marca"><h1>{titulo}</h1><span>{subtitulo}</span></div>',
        unsafe_allow_html=True,
    )


def _fuentes(caso: dict) -> list[dict]:
    """Normaliza fuentes_rag: el orquestador la almacena envuelta en {"lista": [...]}."""
    valor = caso.get("fuentes_rag")
    if isinstance(valor, dict):
        valor = valor.get("lista", [])
    return valor or []


# --------------------------------------------------------------------------- #
#  Recepción del paciente
# --------------------------------------------------------------------------- #

def vista_recepcion() -> None:
    cabecera("Consulta de síntomas", "Dispensario médico · EPN")

    izquierda, derecha = st.columns([3, 2], gap="large")

    with izquierda:
        with st.form("sintomas"):
            sintomas = st.text_area(
                "Cuéntenos qué siente, con sus propias palabras",
                placeholder="Ej.: desde ayer me duele mucho la cabeza, tengo náuseas y me molesta la luz",
                height=170,
            )
            c1, c2, c3 = st.columns(3)
            edad = c1.number_input("Edad", min_value=0, max_value=120, value=25)
            sexo = c2.selectbox("Sexo", ["", "femenino", "masculino"])
            gestante = c3.selectbox("¿Embarazada?", ["No aplica", "Sí", "No"])

            st.markdown("**Signos vitales** · opcionales, los toma el personal de recepción")
            v1, v2, v3 = st.columns(3)
            sistolica = v1.number_input("PA sistólica (mmHg)", 0, 300, 0, help="0 = no tomada")
            diastolica = v2.number_input("PA diastólica (mmHg)", 0, 200, 0, help="0 = no tomada")
            frec_card = v3.number_input("Frec. cardíaca (lpm)", 0, 300, 0, help="0 = no tomada")
            v4, v5, v6 = st.columns(3)
            frec_resp = v4.number_input("Frec. respiratoria (rpm)", 0, 90, 0, help="0 = no tomada")
            temperatura = v5.number_input("Temperatura (°C)", 0.0, 45.0, 0.0, step=0.1, help="0 = no tomada")
            saturacion = v6.number_input("Saturación O₂ (%)", 0, 100, 0, help="0 = no tomada")

            enviar = st.form_submit_button("Enviar consulta", type="primary", use_container_width=True)

    with derecha:
        st.markdown("""
        <div class="tarjeta">
          <h4>Cómo funciona</h4>
          <p>Su relato se analiza contra las Guías de Práctica Clínica del Ministerio
          de Salud Pública. El sistema asigna una prioridad de atención y prepara un
          informe que <strong>revisa y firma un profesional</strong> antes de cualquier
          indicación.</p>
        </div>
        <div class="tarjeta">
          <h4>Importante</h4>
          <p>Esta herramienta <strong>no reemplaza</strong> una valoración médica.
          Si presenta dificultad para respirar, dolor en el pecho o pérdida de
          consciencia, acuda de inmediato a emergencias.</p>
        </div>
        """, unsafe_allow_html=True)

    if not enviar:
        return
    if not sintomas.strip():
        st.warning("Describa sus síntomas antes de enviar.")
        return

    carga = {"symptoms": sintomas.strip(), "edad": int(edad), "sexo": sexo or None}
    if gestante != "No aplica":
        carga["gestante"] = gestante == "Sí"

    # Cero significa "no tomado": se omite del envío en lugar de mandarse como
    # medición, para que el modelo distinga ausencia de dato de valor anómalo.
    for campo, valor in [
        ("pa_sistolica", sistolica), ("pa_diastolica", diastolica),
        ("frecuencia_cardiaca", frec_card), ("frecuencia_respiratoria", frec_resp),
        ("temperatura", temperatura), ("saturacion_oxigeno", saturacion),
    ]:
        if valor:
            carga[campo] = valor

    with st.spinner("Analizando su consulta contra las guías clínicas..."):
        try:
            respuesta = requests.post(N8N_WEBHOOK_URL, json=carga, timeout=180)
            respuesta.raise_for_status()
            datos = respuesta.json()
        except requests.RequestException as exc:
            st.error(f"No se pudo procesar su consulta. Acérquese al dispensario. ({exc})")
            return

    nivel = datos.get("prioridad", "Verde")
    estilo = TRIAJE.get(nivel, TRIAJE["Verde"])
    st.markdown(f"""
    <div class="banda" style="--c:{estilo['color']}; --bg:{estilo['fondo']};">
      <div class="nivel">{estilo['icono']} Prioridad {nivel} · {estilo['etiqueta']}</div>
      <div class="detalle">{datos.get('mensaje', 'Su caso fue registrado.')}</div>
    </div>
    """, unsafe_allow_html=True)
    st.caption("Su caso ingresó a la cola del médico de turno.")


# --------------------------------------------------------------------------- #
#  Consola clínica
# --------------------------------------------------------------------------- #

def _ficha(caso: dict) -> None:
    estilo = TRIAJE.get(caso["color_triage"], TRIAJE["Verde"])
    demografia = " · ".join(filter(None, [
        f"{caso['edad']} años" if caso.get("edad") is not None else None,
        caso.get("sexo"),
        "gestante" if caso.get("gestante") else None,
    ])) or "sin datos demográficos"

    st.markdown(f"""
    <div class="banda" style="--c:{estilo['color']}; --bg:{estilo['fondo']};">
      <div class="nivel">{estilo['icono']} {caso['color_triage']} · {estilo['etiqueta']}</div>
      <div class="detalle">Caso #{caso['id']} — {demografia}</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown(f'<div class="relato">“{caso["symptoms_text"]}”</div>', unsafe_allow_html=True)
    st.write("")

    constantes = [
        (f"{caso['pa_sistolica']}/{caso['pa_diastolica']}", "PA (mmHg)")
        if caso.get("pa_sistolica") and caso.get("pa_diastolica") else None,
        (caso.get("frecuencia_cardiaca"), "FC (lpm)"),
        (caso.get("frecuencia_respiratoria"), "FR (rpm)"),
        (caso.get("temperatura"), "Temp (°C)"),
        (caso.get("saturacion_oxigeno"), "SatO₂ (%)"),
    ]
    constantes = [c for c in constantes if c and c[0]]
    if constantes:
        for columna, (valor, titulo) in zip(st.columns(len(constantes)), constantes):
            columna.markdown(
                f'<div class="kpi"><div class="n" style="font-size:1.4rem">{valor}</div>'
                f'<div class="t">{titulo}</div></div>',
                unsafe_allow_html=True,
            )
    else:
        st.caption("Sin signos vitales registrados — la valoración se apoyó solo en el relato.")
    st.write("")

    col1, col2 = st.columns(2, gap="medium")
    bloques = [
        (col1, "Diagnóstico presuntivo", caso.get("diagnostico_presuntivo")),
        (col1, "Explicación para el paciente", caso.get("explicacion_feynman")),
        (col2, "Contraindicaciones y alertas", caso.get("contraindicaciones_alertas")),
        (col2, "Justificación clínica", caso.get("justificacion_clinica_rag")),
    ]
    for columna, titulo, contenido in bloques:
        with columna:
            st.markdown(
                f'<div class="tarjeta"><h4>{titulo}</h4><p>{contenido or "No disponible"}</p></div>',
                unsafe_allow_html=True,
            )

    fuentes = _fuentes(caso)
    if not fuentes:
        st.markdown(
            '<div class="aviso"><strong>Sin respaldo documental.</strong> Ninguna guía del MSP '
            'superó el umbral de relevancia para este cuadro; el triaje se apoyó en criterio '
            'clínico general. Revise con especial atención.</div>',
            unsafe_allow_html=True,
        )
    else:
        with st.expander(f"Fuentes MSP que sustentan el análisis ({len(fuentes)})"):
            for f in fuentes:
                st.markdown(
                    f'<div class="fuente">{f.get("guia")} · pág. {f.get("pagina")} '
                    f'· distancia {f.get("distancia")}</div>',
                    unsafe_allow_html=True,
                )


def vista_consola() -> None:
    cabecera("Consola clínica", "Validación profesional · human-in-the-loop")

    pendientes = get_pending_cases()
    conteo = {c: sum(1 for p in pendientes if p["color_triage"] == c) for c in TRIAJE}

    columnas = st.columns(3)
    for columna, (nivel, estilo) in zip(columnas, TRIAJE.items()):
        columna.markdown(
            f'<div class="kpi"><div class="n" style="color:{estilo["color"]}">{conteo[nivel]}</div>'
            f'<div class="t">{estilo["icono"]} {nivel}</div></div>',
            unsafe_allow_html=True,
        )
    st.write("")

    if not pendientes:
        st.success("No hay casos pendientes en la cola.")
    else:
        opciones = {
            f"{TRIAJE[c['color_triage']]['icono']}  #{c['id']} · {c['symptoms_text'][:64]}…": c["id"]
            for c in pendientes
        }
        etiqueta = st.selectbox(
            "Cola de atención — ordenada por gravedad y, dentro de cada nivel, por llegada",
            list(opciones),
        )
        caso = get_case(opciones[etiqueta])

        _ficha(caso)

        st.divider()
        st.markdown("#### Plan definitivo")
        st.caption(
            "La propuesta de la IA es un borrador. Lo que quede en este campo es lo que "
            "se emite bajo su firma; la propuesta original se conserva para auditoría."
        )
        plan = st.text_area(
            "Receta o plan", value=caso.get("propuesta_ia") or "",
            height=250, key=f"plan_{caso['id']}", label_visibility="collapsed",
        )
        col_a, col_b = st.columns([2, 1])
        profesional = col_a.text_input("Profesional que autoriza", placeholder="Dr./Dra. Nombre Apellido")
        col_b.write("")
        col_b.write("")
        if col_b.button("Autorizar y firmar", type="primary", use_container_width=True):
            if not profesional.strip():
                st.warning("Indique el profesional que autoriza.")
            elif not plan.strip():
                st.warning("El plan no puede quedar vacío.")
            else:
                sign_case(caso["id"], plan.strip(), profesional.strip())
                st.success(f"Caso #{caso['id']} firmado y emitido.")
                st.rerun()

    with st.expander("Historial de casos atendidos"):
        atendidos = get_attended_cases()
        if not atendidos:
            st.caption("Todavía no hay casos atendidos.")
        for caso in atendidos:
            st.markdown(
                f"{TRIAJE[caso['color_triage']]['icono']} **#{caso['id']}** · "
                f"{caso['diagnostico_presuntivo']} · _firmado por {caso['attended_by']}_"
            )


# --------------------------------------------------------------------------- #
#  Indicadores
# --------------------------------------------------------------------------- #

def vista_indicadores() -> None:
    cabecera("Indicadores de operación", "Cobertura del corpus y flujo de atención")

    est = get_estadisticas()
    if not est["total"]:
        st.info("Todavía no hay casos registrados.")
        return

    fila = st.columns(4)
    tarjetas = [
        (est["total"], "Casos totales", "#0F172A"),
        (est["pendientes"], "En cola", "#D97706"),
        (est["atendidos"], "Atendidos", "#16A34A"),
        (f"{est['minutos_promedio']:.0f} min" if est["minutos_promedio"] else "—",
         "Tiempo medio de atención", "#0F766E"),
    ]
    for columna, (valor, titulo, color) in zip(fila, tarjetas):
        columna.markdown(
            f'<div class="kpi"><div class="n" style="color:{color}">{valor}</div>'
            f'<div class="t">{titulo}</div></div>',
            unsafe_allow_html=True,
        )

    st.write("")
    izq, der = st.columns(2, gap="large")

    with izq:
        st.markdown("##### Distribución por nivel de triaje")
        st.bar_chart(
            {"Casos": {"Rojo": est["rojos"], "Amarillo": est["amarillos"], "Verde": est["verdes"]}},
            color="#0F766E", height=260,
        )

    with der:
        st.markdown("##### Guías del MSP que sustentaron los triajes")
        uso = get_uso_de_guias()
        if uso:
            st.bar_chart({"Usos": {u["guia"][:26]: u["usos"] for u in uso}},
                         color="#0F766E", height=260, horizontal=True)
        else:
            st.caption("Sin datos de recuperación registrados.")

    sin_respaldo = est["sin_respaldo"]
    proporcion = sin_respaldo / est["total"]
    st.markdown(f"""
    <div class="aviso">
      <strong>Cobertura documental: {sin_respaldo} de {est['total']} casos ({proporcion:.0%})
      se resolvieron sin respaldo del corpus.</strong><br>
      Son cuadros para los que ninguna guía del MSP indexada superó el umbral de relevancia.
      El sistema lo declara explícitamente en lugar de citar la fuente menos inadecuada.
      Una proporción alta indica que el corpus debe ampliarse hacia esos motivos de consulta.
    </div>
    """, unsafe_allow_html=True)


# --------------------------------------------------------------------------- #

inyectar_estilos()

with st.sidebar:
    st.markdown("### 🏥 Triaje EPN")
    st.caption("Sistema de triaje clínico preliminar asistido por IA")
    vista = st.radio("Vista", ["Recepción", "Consola clínica", "Indicadores"], label_visibility="collapsed")
    st.divider()
    st.caption(
        "**Proyecto final AIE — Summer Camp 2026**\n\n"
        "Escuela Politécnica Nacional · CyberMinds\n\n"
        "Clasificación mediante inferencia semántica anclada en Guías de Práctica "
        "Clínica del MSP. Toda decisión clínica pasa por validación humana."
    )

if vista == "Recepción":
    vista_recepcion()
elif vista == "Consola clínica":
    vista_consola()
else:
    vista_indicadores()
