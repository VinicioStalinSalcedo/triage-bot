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

# Umbral de descarte de fragmentos por distancia.
#
# HISTORIA DE CALIBRACIÓN — el rol de este parámetro cambió al crecer el corpus.
#
# Con 6 guías (3.664 fragmentos) los grupos se separaban limpiamente y el umbral
# funcionaba como detector de cobertura: 0.32-0.49 acierto, 0.59-0.62 ruido,
# 0.74 fuera de dominio. Se fijó en 0.55, en el hueco entre ambos.
#
# Con 10 guías (5.933 fragmentos) esa separación desaparece. Medición sobre los
# 28 casos de eval/cases.json (evaluate.py --recuperacion):
#   Casos con respaldo esperado : 0.3107 - 0.5168
#   Casos sin respaldo esperado : 0.3533 - 0.7817
# Los rangos se solapan: ningún umbral los separa. La causa es la densificación
# del corpus — un resfriado queda a 0.44 de la guía de neumonía y una ansiedad
# situacional a 0.36 de la de depresión. Proximidad ya no implica pertinencia.
#
# DECISIÓN: el umbral deja de ser filtro de relevancia clínica y pasa a ser
# filtro de dominio. Se fija en 0.65, que descarta lo manifiestamente ajeno
# (control negativo no clínico: 0.7817) y admite todo lo clínicamente plausible.
# El juicio fino de pertinencia se delega al LLM, que sí dispone del cuadro
# completo para decidir — y que demostró hacerlo: ante contexto de
# envenenamientos para una preeclampsia, lo descartó y lo declaró (ver
# PROMPTS.md, incidente del 2026-08-25).
#
# Defensa en dos capas: umbral para lo grosero, inferencia para lo sutil.
# Recalibrar ante cualquier cambio de corpus o de modelo de embeddings.
MAX_DISTANCE = 0.65
