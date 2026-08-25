"""API Flask del triage bot: RAG + Groq (openai/gpt-oss-120b) -> JSON estricto.

Este servicio es intencionalmente sin estado respecto a la base de datos: no
inserta nada en Postgres. La persistencia de cada caso la hace el nodo Postgres
de n8n, después de llamar a este endpoint (ver backend/db.py y PROMPTS.md).
Aquí solo se garantiza que la tabla exista al arrancar.
"""
import json
import os

from flask import Flask, jsonify, request
from langchain_groq import ChatGroq

from backend.db import init_db
from backend.prompts import RESPONSE_SCHEMA_KEYS, SYSTEM_PROMPT, build_user_prompt
from rag.query_rag import query_symptoms

app = Flask(__name__)

llm = ChatGroq(
    model="openai/gpt-oss-120b",
    temperature=0.2,
    model_kwargs={"response_format": {"type": "json_object"}},
)


@app.route("/api/triage", methods=["POST"])
def triage():
    body = request.get_json(silent=True) or {}
    symptoms_text = (body.get("symptoms") or "").strip()
    if not symptoms_text:
        return jsonify({"error": "El campo 'symptoms' es requerido."}), 400

    rag_context = query_symptoms(symptoms_text, k=4)
    user_prompt = build_user_prompt(symptoms_text, rag_context)

    response = llm.invoke(
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]
    )

    try:
        triage_json = json.loads(response.content)
    except json.JSONDecodeError:
        return jsonify({"error": "El LLM no devolvió un JSON válido.", "raw": response.content}), 502

    missing = [k for k in RESPONSE_SCHEMA_KEYS if k not in triage_json]
    if missing:
        return jsonify({"error": f"Faltan claves en la respuesta del LLM: {missing}", "raw": triage_json}), 502

    if triage_json["color_triage"] not in ("Rojo", "Amarillo", "Verde"):
        return jsonify({"error": f"color_triage inválido: {triage_json['color_triage']}", "raw": triage_json}), 502

    return jsonify(triage_json), 200


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=os.getenv("FLASK_DEBUG", "false").lower() == "true")
