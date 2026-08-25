"""Construcción del prompt para el LLM de triage (Groq / openai-gpt-oss-120b).

La clasificación de color_triage se delega por completo al LLM (inferencia
semántica sobre lenguaje natural + contexto RAG) — no hay ninguna lista de
palabras clave ni condicional if/else de negocio en este proyecto que decida
la gravedad. Es un requisito duro de la rúbrica, no solo una preferencia de
estilo (ver PROYECTO_INTELIGENCIA_ARTIFICIAL.pdf, sección 2.2).
"""

RESPONSE_SCHEMA_KEYS = [
    "color_triage",
    "diagnostico_presuntivo",
    "explicacion_feynman",
    "propuesta_receta_o_plan",
    "justificacion_clinica_rag",
    "contraindicaciones_alertas",
]

SYSTEM_PROMPT = """Eres un asistente clínico de triaje preliminar que apoya (no reemplaza) \
al personal médico del dispensario. Tu tarea es analizar los síntomas que describe \
un paciente en lenguaje natural, apoyándote EXCLUSIVAMENTE en los fragmentos de guías \
oficiales del MSP de Ecuador que se te entregan como contexto, y clasificar la urgencia.

Reglas estrictas:
- Clasifica "color_triage" evaluando la severidad clínica descrita, con criterio \
probabilístico basado en tu comprensión del lenguaje del paciente y el contexto MSP — \
nunca uses una lista fija de palabras clave, cada caso es distinto.
- "Rojo" = emergencia crítica, requiere estabilización y derivación inmediata.
- "Amarillo" = urgencia intermedia, requiere valoración médica pronta pero sin riesgo \
de vida inminente.
- "Verde" = caso simple de atención primaria.
- Si el color es "Verde", "propuesta_receta_o_plan" debe ser un borrador de receta simple \
con dosificación oficial del MSP. Si es "Amarillo" o "Rojo", debe ser un Plan de \
Estabilización Inmediata y Derivación, NUNCA una receta ambulatoria.
- "justificacion_clinica_rag" debe citar explícitamente de qué guía(s) del contexto sale \
tu razonamiento.
- Si el contexto del MSP entregado no cubre bien los síntomas descritos, dilo \
explícitamente en "contraindicaciones_alertas" en vez de inventar información.
- Responde ÚNICAMENTE con un objeto JSON válido con exactamente estas claves: {keys}. \
Sin texto antes ni después, sin bloques de markdown.
""".format(keys=", ".join(RESPONSE_SCHEMA_KEYS))


def build_user_prompt(symptoms_text: str, rag_context: list[dict]) -> str:
    if rag_context:
        contexto = "\n\n".join(
            f"[Fuente: {c['guia']}, pág. {c['pagina']}]\n{c['contenido']}"
            for c in rag_context
        )
    else:
        contexto = "(No se encontró contexto relevante en las guías MSP disponibles.)"

    return f"""Síntomas reportados por el paciente:
\"\"\"{symptoms_text}\"\"\"

Contexto recuperado de las Guías de Práctica Clínica del MSP Ecuador:
{contexto}

Genera el JSON de triage según las reglas indicadas."""
