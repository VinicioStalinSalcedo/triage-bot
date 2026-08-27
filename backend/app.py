"""API Flask del triage bot: RAG + Groq (openai/gpt-oss-120b) -> JSON estricto.

Este servicio es deliberadamente sin estado respecto a la base de datos: no
inserta nada en Postgres. La persistencia de cada caso la hace el nodo Postgres
nativo de n8n después de llamar a este endpoint, y el schema se crea al
levantar la base (db/init.sql). Ver ARCHITECTURE.md.

La inferencia ocurre en dos etapas: primero se traduce el relato del paciente a
terminología clínica para buscar en las guías, y después se genera el triage
sobre el contexto recuperado. Ver PROMPTS.md (incidente del 2026-08-25) para
por qué la búsqueda en una sola etapa no era suficiente.
"""
import json
import os

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from groq import Groq

from backend.prompts import (
    QUERY_REWRITE_PROMPT,
    RESPONSE_SCHEMA_KEYS,
    SYSTEM_PROMPT,
    build_rewrite_prompt,
    build_user_prompt,
)
from rag.query_rag import query_symptoms

load_dotenv()

MODEL = "openai/gpt-oss-120b"
VALID_COLORS = ("Rojo", "Amarillo", "Verde")
TOP_K = 4

# Un intento de inyección de prompt puede hacer que la etapa de reescritura
# responda con una negativa ("I'm sorry, but I can't comply...") en vez de
# términos clínicos. Sin este filtro, esa negativa se usaría como consulta de
# búsqueda vectorial. No decide nada clínico: solo descarta una consulta
# inservible y se vuelve al texto original del paciente.
_MARCADORES_DE_RECHAZO = (
    "i'm sorry", "i am sorry", "i can't", "i cannot", "as an ai",
    "lo siento", "no puedo", "como asistente", "no está permitido",
)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise SystemExit(
        "Falta GROQ_API_KEY. Copia .env.example a .env y coloca tu clave de Groq Cloud."
    )

app = Flask(__name__)
client = Groq(api_key=GROQ_API_KEY)


def _parse_patient(body: dict) -> dict:
    """Extrae los datos demográficos opcionales, tolerando ausencias y basura.

    Son opcionales a propósito: el paciente puede no querer darlos, y el triage
    debe seguir funcionando. Pero cuando están, mejoran mucho la inferencia —
    buena parte del corpus MSP disponible es obstétrico.
    """
    try:
        edad = int(body["edad"]) if body.get("edad") not in (None, "") else None
    except (TypeError, ValueError):
        edad = None

    gestante = body.get("gestante")
    if isinstance(gestante, str):
        gestante = gestante.strip().lower() in ("true", "sí", "si", "1", "yes")
    elif not isinstance(gestante, bool):
        gestante = None

    sexo = (body.get("sexo") or "").strip() or None

    return {"edad": edad, "sexo": sexo, "gestante": gestante}


# Signos vitales admitidos y su tipo. La validación es de formato, no clínica:
# aquí no se decide si una cifra es normal o alarmante — eso lo infiere el
# modelo contra las guías. Un umbral codificado en este punto convertiría la
# clasificación de gravedad en una regla fija.
_SIGNOS_VITALES = {
    "pa_sistolica": int,
    "pa_diastolica": int,
    "frecuencia_cardiaca": int,
    "frecuencia_respiratoria": int,
    "temperatura": float,
    "saturacion_oxigeno": int,
}


def _parse_vitals(body: dict) -> dict:
    """Extrae los signos vitales presentes, descartando valores no numéricos."""
    vitales: dict = {}
    for campo, tipo in _SIGNOS_VITALES.items():
        valor = body.get(campo)
        if valor in (None, ""):
            vitales[campo] = None
            continue
        try:
            vitales[campo] = tipo(valor)
        except (TypeError, ValueError):
            app.logger.warning("Signo vital ignorado por no ser numérico: %s=%r", campo, valor)
            vitales[campo] = None
    return vitales


def _to_clinical_query(symptoms_text: str, patient: dict) -> str:
    """Traduce el relato del paciente a términos clínicos de guía.

    Si falla, se degrada con gracia devolviendo cadena vacía: la búsqueda
    seguirá funcionando con el texto original del paciente.
    """
    try:
        completion = client.chat.completions.create(
            model=MODEL,
            temperature=0.0,
            # Sin tope de tokens: gpt-oss-120b es un modelo de razonamiento y
            # consume presupuesto pensando antes de emitir contenido. Con un
            # max_tokens ajustado (150) devolvía cadena vacía, y la reescritura
            # fallaba en silencio — ver PROMPTS.md, 2026-08-25.
            messages=[
                {"role": "system", "content": QUERY_REWRITE_PROMPT},
                {"role": "user", "content": build_rewrite_prompt(symptoms_text, patient)},
            ],
        )
        reescrita = (completion.choices[0].message.content or "").strip()
        if not reescrita:
            app.logger.warning("La reescritura clínica devolvió contenido vacío.")
            return ""

        minuscula = reescrita.lower()
        if len(reescrita) < 15 or any(m in minuscula for m in _MARCADORES_DE_RECHAZO):
            app.logger.warning("Reescritura clínica descartada por no ser clínica: %r", reescrita)
            return ""

        return reescrita
    except Exception as exc:  # noqa: BLE001 - la reescritura es una mejora, no un requisito
        # Nunca romper el triage por esto, pero tampoco fallar en silencio.
        app.logger.warning("Falló la reescritura clínica: %s", exc)
        return ""


def _retrieve(symptoms_text: str, clinical_query: str, k: int = TOP_K) -> list[dict]:
    """Busca con el texto del paciente y con su traducción clínica, y fusiona.

    Se conservan ambas porque cada una acierta en casos distintos: el relato
    original conserva matices que la traducción pierde, y la traducción alcanza
    secciones de guía que el lenguaje coloquial nunca recuperaría.
    """
    candidatos = query_symptoms(symptoms_text, k=k)
    if clinical_query:
        candidatos += query_symptoms(clinical_query, k=k)

    mejores: dict[tuple, dict] = {}
    for fragmento in candidatos:
        clave = (fragmento["guia"], fragmento["pagina"], fragmento["contenido"][:80])
        if clave not in mejores or fragmento["distancia"] < mejores[clave]["distancia"]:
            mejores[clave] = fragmento

    return sorted(mejores.values(), key=lambda f: f["distancia"])[:k]


@app.route("/api/triage", methods=["POST"])
def triage():
    body = request.get_json(silent=True) or {}
    symptoms_text = (body.get("symptoms") or "").strip()
    if not symptoms_text:
        return jsonify({"error": "El campo 'symptoms' es requerido."}), 400

    patient = _parse_patient(body)
    vitals = _parse_vitals(body)
    clinical_query = _to_clinical_query(symptoms_text, patient)
    rag_context = _retrieve(symptoms_text, clinical_query)

    try:
        completion = client.chat.completions.create(
            model=MODEL,
            # Temperatura 0: en una clasificación de seguridad clínica la
            # reproducibilidad pesa más que la variedad de la redacción. Con 0.2
            # el mismo caso de urgencia hipertensiva se clasificó Verde en una
            # ejecución y Amarillo en otra — varianza inaceptable en la frontera
            # entre niveles (ver PROMPTS.md, evaluación del 2026-08-25).
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_user_prompt(symptoms_text, rag_context, patient, vitals)},
            ],
        )
    except Exception as exc:  # noqa: BLE001 - la causa se reporta tal cual al cliente
        return jsonify({"error": f"Fallo al invocar el modelo: {exc}"}), 502

    raw = completion.choices[0].message.content
    try:
        triage_json = json.loads(raw)
    except json.JSONDecodeError:
        return jsonify({"error": "El LLM no devolvió un JSON válido.", "raw": raw}), 502

    missing = [key for key in RESPONSE_SCHEMA_KEYS if key not in triage_json]
    if missing:
        return jsonify({"error": f"Faltan claves en la respuesta del LLM: {missing}", "raw": triage_json}), 502

    if triage_json["color_triage"] not in VALID_COLORS:
        return jsonify({"error": f"color_triage inválido: {triage_json['color_triage']}", "raw": triage_json}), 502

    # Se devuelven la consulta clínica y las fuentes para que el panel del
    # médico muestre en qué se apoyó la IA, y para poder auditar el triage.
    triage_json["consulta_clinica"] = clinical_query
    triage_json["fuentes_rag"] = [
        {"guia": c["guia"], "pagina": c["pagina"], "distancia": c["distancia"]} for c in rag_context
    ]
    return jsonify(triage_json), 200


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=os.getenv("FLASK_DEBUG", "false").lower() == "true")
