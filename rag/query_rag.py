"""Búsqueda semántica sobre las guías del MSP ya ingeridas por ingest.py.

Uso (dentro del contenedor backend):
    docker compose run --rm backend python rag/query_rag.py
"""
import chromadb
from sentence_transformers import SentenceTransformer

from rag.config import (
    CHROMA_DB_PATH,
    COLLECTION_NAME,
    EMBEDDING_MODEL,
    MAX_DISTANCE,
)

_model: SentenceTransformer | None = None
_collection = None


def _get_model() -> SentenceTransformer:
    # Cargar el modelo cuesta segundos y ~500MB: se cachea entre peticiones
    # para no pagarlo en cada llamada al endpoint de triage.
    global _model
    if _model is None:
        _model = SentenceTransformer(EMBEDDING_MODEL)
    return _model


def _get_collection():
    global _collection
    if _collection is None:
        client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
        _collection = client.get_collection(name=COLLECTION_NAME)
    return _collection


def query_symptoms(symptom_text: str, k: int = 4, max_distance: float = MAX_DISTANCE) -> list[dict]:
    """Devuelve los fragmentos de guías MSP relevantes para los síntomas dados.

    Descarta los que superen `max_distance`: es preferible devolver una lista
    vacía (y que el LLM lo declare) a inyectar contexto clínico equivocado.
    """
    embedding = _get_model().encode(symptom_text, normalize_embeddings=True).tolist()
    results = _get_collection().query(
        query_embeddings=[embedding],
        n_results=k,
        include=["documents", "metadatas", "distances"],
    )

    return [
        {
            "guia": meta.get("guia", "desconocida"),
            "pagina": meta.get("pagina", "?"),
            "contenido": document,
            "distancia": round(distance, 4),
        }
        for document, meta, distance in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        )
        if distance <= max_distance
    ]


if __name__ == "__main__":
    ejemplos = [
        "Tengo la presión muy alta, dolor de cabeza fuerte y veo puntos negros",
        "Estoy embarazada, tengo hinchazón en piernas y cara, y la presión me salió alta",
        "Tengo granos en la cara desde hace meses, nada grave",
        "Me duele mucho el pecho y me cuesta respirar desde hace una hora",
        "Me torcí el tobillo jugando fútbol y está hinchado",
        # Control negativo: debe devolver 0 fragmentos, no basura con confianza.
        "Quiero saber cuál es la capital de Francia",
    ]
    for texto in ejemplos:
        print(f"\n--- {texto}")
        encontrados = query_symptoms(texto)
        if not encontrados:
            print("  (sin contexto relevante por encima del umbral)")
        for r in encontrados:
            print(f"  [{r['guia']} p.{r['pagina']}] dist={r['distancia']}")
            print(f"    {r['contenido'][:160]}...")
