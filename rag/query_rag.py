"""Búsqueda de similitud semántica sobre las guías del MSP ya ingeridas por ingest.py.

Uso (dentro del contenedor backend):
    docker compose run --rm backend python rag/query_rag.py
"""
import os

from dotenv import load_dotenv
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

load_dotenv()

CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH", "./chroma_db")
EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

_vectorstore = None


def _get_vectorstore() -> Chroma:
    global _vectorstore
    if _vectorstore is None:
        embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
        _vectorstore = Chroma(
            persist_directory=CHROMA_DB_PATH,
            embedding_function=embeddings,
        )
    return _vectorstore


def query_symptoms(symptom_text: str, k: int = 4) -> list[dict]:
    """Devuelve los k fragmentos de guías MSP más relevantes para los síntomas dados."""
    results = _get_vectorstore().similarity_search_with_score(symptom_text, k=k)
    return [
        {
            "guia": doc.metadata.get("source_guide", "desconocida"),
            "pagina": doc.metadata.get("page", "?"),
            "contenido": doc.page_content,
            "distancia": score,
        }
        for doc, score in results
    ]


if __name__ == "__main__":
    ejemplos = [
        "Tengo la presión muy alta, dolor de cabeza fuerte y veo puntos negros",
        "Estoy embarazada, tengo hinchazón en piernas y cara, y la presión me salió alta",
        "Tengo granos en la cara desde hace meses, nada grave",
    ]
    for texto in ejemplos:
        print(f"\n--- Síntomas: {texto} ---")
        for r in query_symptoms(texto, k=2):
            print(f"  [{r['guia']} - pág. {r['pagina']}] (distancia={r['distancia']:.3f})")
            print(f"  {r['contenido'][:200]}...")
