"""Ingesta las guías clínicas del MSP (PDF) hacia ChromaDB para el RAG del triage bot.

Uso (dentro del contenedor backend, donde están instaladas las dependencias):
    docker compose run --rm backend python rag/ingest.py
"""
import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

load_dotenv()

PDF_DIR = Path(__file__).resolve().parent.parent / "data" / "msp_guides"
CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH", "./chroma_db")
EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


def load_and_split_pdfs() -> list:
    documents = []
    for pdf_path in sorted(PDF_DIR.glob("*.pdf")):
        pages = PyPDFLoader(str(pdf_path)).load()
        for page in pages:
            page.metadata["source_guide"] = pdf_path.stem
        documents.extend(pages)
        print(f"  cargado: {pdf_path.name} ({len(pages)} páginas)")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=100,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    return splitter.split_documents(documents)


def main():
    print(f"Buscando PDFs en {PDF_DIR} ...")
    chunks = load_and_split_pdfs()
    print(f"Total de fragmentos generados: {len(chunks)}")

    print(f"Generando embeddings con {EMBEDDING_MODEL} (descarga el modelo la primera vez) ...")
    embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)

    print(f"Persistiendo en ChromaDB: {CHROMA_DB_PATH} ...")
    Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=CHROMA_DB_PATH,
    )
    print("Listo. La base vectorial quedó persistida.")


if __name__ == "__main__":
    main()
