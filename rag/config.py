"""Configuración compartida del motor RAG (ingesta y consulta).

Vive en un solo lugar para que ingest.py y query_rag.py no puedan
desincronizarse: si el nombre de la colección o el modelo de embeddings
difieren entre ambos, las búsquedas fallan de forma silenciosa.
"""
import os

from dotenv import load_dotenv

load_dotenv()

CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH", "./chroma_db")
COLLECTION_NAME = "msp_guides"

# Multilingüe: el corpus y las consultas de los pacientes están en español.
# Un modelo mayormente inglés (all-MiniLM-L6-v2) hacía coincidencias léxicas
# en vez de semánticas — ver PROMPTS.md, depuración del 2026-08-24.
EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

# Distancia coseno: rango acotado [0, 2], donde 0 = idéntico.
# Se usa en vez de L2 (default de Chroma) porque permite fijar un umbral
# de relevancia interpretable y estable entre corpus de distinto tamaño.
DISTANCE_METRIC = "cosine"

# Fragmentos con distancia mayor a este umbral se descartan por irrelevantes.
# Es preferible entregarle al LLM "no hay contexto" que contexto equivocado:
# un fragmento de la guía de acné para un dolor abdominal contamina el
# razonamiento clínico.
#
# Calibrado empíricamente sobre este corpus (6 guías, 3.664 fragmentos):
#   0.32-0.49  recuperación correcta (preeclampsia 0.325, angina 0.424, acné 0.49)
#   0.59-0.62  ruido (esguince de tobillo -> vesícula biliar, técnica de punción)
#   0.74       fuera de dominio (control negativo "capital de Francia")
# El umbral se sitúa en el hueco entre el peor acierto (0.4913) y el mejor
# falso positivo (0.5892). Re-calibrar si cambia el corpus o el modelo.
MAX_DISTANCE = 0.55
