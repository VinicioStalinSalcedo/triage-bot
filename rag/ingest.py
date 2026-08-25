"""Ingesta las guías clínicas del MSP (PDF) hacia ChromaDB para el RAG del triage bot.

Implementado directamente sobre pypdf + sentence-transformers + chromadb, sin
LangChain: el proyecto solo necesita cuatro operaciones puntuales (leer PDF,
partir texto, embeber, persistir) y la capa de abstracción traía un árbol de
dependencias inestable — ver PROMPTS.md, depuración del 2026-08-25.

Uso (dentro del contenedor backend, donde están instaladas las dependencias):
    docker compose run --rm backend python rag/ingest.py
"""
import re
import shutil
from pathlib import Path

import chromadb
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer

from rag.config import (
    CHROMA_DB_PATH,
    COLLECTION_NAME,
    DISTANCE_METRIC,
    EMBEDDING_MODEL,
)

PDF_DIR = Path(__file__).resolve().parent.parent / "data" / "msp_guides"
CHUNK_SIZE = 500
CHUNK_OVERLAP = 100

# ChromaDB rechaza inserciones por encima de ~5.461 registros por llamada.
INSERT_BATCH_SIZE = 2000


def split_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Parte el texto en fragmentos solapados, cortando en límites de oración.

    El solapamiento evita que una recomendación clínica quede partida entre dos
    fragmentos y se pierda en la búsqueda. El tamaño (~500 caracteres) se ajusta
    a la ventana efectiva del modelo de embeddings: fragmentos mucho mayores se
    truncarían silenciosamente al vectorizar.
    """
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        if end < len(text):
            window = text[start:end]
            # Preferir un corte en fin de oración; si no hay, cortar en espacio.
            cut = max(window.rfind(". "), window.rfind("? "), window.rfind("! "))
            if cut < chunk_size // 2:
                cut = window.rfind(" ")
            if cut > 0:
                end = start + cut + 1

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break

        # El solapamiento nunca puede mover el cursor hacia atrás: un corte muy
        # temprano (tablas, texto mal extraído) haría que el bucle no avance.
        start = end - overlap if end - overlap > start else end

    return chunks


def load_chunks() -> tuple[list[str], list[dict]]:
    """Devuelve (textos, metadatos) de todos los PDFs del corpus."""
    texts: list[str] = []
    metadatas: list[dict] = []

    for pdf_path in sorted(PDF_DIR.glob("*.pdf")):
        reader = PdfReader(str(pdf_path))
        chunk_count = 0
        for page_number, page in enumerate(reader.pages, start=1):
            for chunk in split_text(page.extract_text() or ""):
                texts.append(chunk)
                # La fuente y la página viajan con cada fragmento para que el
                # LLM pueda citar de qué guía salió cada afirmación clínica.
                metadatas.append({"guia": pdf_path.stem, "pagina": page_number})
                chunk_count += 1
        marca = "  <-- SIN TEXTO EXTRAÍBLE" if chunk_count == 0 else ""
        print(f"  {pdf_path.name}: {len(reader.pages)} páginas -> {chunk_count} fragmentos{marca}")

    return texts, metadatas


def main() -> None:
    print(f"Leyendo PDFs desde {PDF_DIR} ...")
    texts, metadatas = load_chunks()
    if not texts:
        raise SystemExit(f"No se encontraron PDFs con texto extraíble en {PDF_DIR}")
    print(f"Total de fragmentos: {len(texts)}")

    print(f"Cargando modelo de embeddings ({EMBEDDING_MODEL}) ...")
    model = SentenceTransformer(EMBEDDING_MODEL)

    print("Generando embeddings ...")
    embeddings = model.encode(
        texts,
        batch_size=64,
        show_progress_bar=True,
        normalize_embeddings=True,
    ).tolist()

    # Se reconstruye desde cero: reingestar sobre una colección existente
    # dejaría fragmentos huérfanos de corridas anteriores.
    if Path(CHROMA_DB_PATH).exists():
        print(f"Eliminando base vectorial anterior en {CHROMA_DB_PATH} ...")
        shutil.rmtree(CHROMA_DB_PATH)

    print(f"Persistiendo en ChromaDB ({CHROMA_DB_PATH}, métrica={DISTANCE_METRIC}) ...")
    client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
    collection = client.create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": DISTANCE_METRIC},
    )
    for offset in range(0, len(texts), INSERT_BATCH_SIZE):
        fin = min(offset + INSERT_BATCH_SIZE, len(texts))
        collection.add(
            ids=[str(i) for i in range(offset, fin)],
            documents=texts[offset:fin],
            metadatas=metadatas[offset:fin],
            embeddings=embeddings[offset:fin],
        )
        print(f"  insertados {fin}/{len(texts)}")

    print(f"Listo: {collection.count()} fragmentos indexados.")


if __name__ == "__main__":
    main()
