"""Embedding generation and ChromaDB vector store management.

Generates dense embeddings from text chunks using Sentence Transformers
and persists them to local ChromaDB collections. Supports two collections:
- "resumes": indexed resume chunks
- "job_postings": indexed job posting chunks
"""
from __future__ import annotations

import uuid
from typing import List, Optional

import chromadb
from sentence_transformers import SentenceTransformer

from src.config import settings
from src.ingestion.chunker import TextChunk

# Keywords for document classification
_RESUME_KEYWORDS = (
    "experiência", "formação", "habilidades", "profissional", "currículo",
    "experience", "skills", "education", "professional", "resume",
    "bacharelado", "mestrado", "doutorado", "universidade", "graduação",
    "trabalhei", "atuei", "desenvolvi", "implementei", "liderei",
)
_JOB_KEYWORDS = (
    "requisitos", "responsabilidades", "vaga", "contratação", "benefícios",
    "requirements", "responsibilities", "job", "hiring", "benefits",
    "buscamos", "procuramos", "oferecemos", "remuneração", "salário",
    "candidate", "apply", "opportunity", "position",
)


def classify_document(text: str) -> str:
    """Classify a document as a resume or job posting based on keyword counts.

    Args:
        text: Full document text to classify.

    Returns:
        "resume" if resume keywords dominate, "job_posting" otherwise.
    """
    lower = text.lower()
    resume_hits = sum(1 for kw in _RESUME_KEYWORDS if kw in lower)
    job_hits = sum(1 for kw in _JOB_KEYWORDS if kw in lower)
    return "resume" if resume_hits >= job_hits else "job_posting"


def _get_client() -> chromadb.PersistentClient:
    return chromadb.PersistentClient(path=settings.chroma_db_path)


def _get_collection(
    client: chromadb.PersistentClient,
    collection_name: Optional[str] = None,
) -> chromadb.Collection:
    name = collection_name or settings.collection_name
    return client.get_or_create_collection(
        name=name,
        metadata={"hnsw:space": "cosine"},
    )


def index_chunks(
    chunks: List[TextChunk],
    collection_name: Optional[str] = None,
) -> int:
    """Embed a list of text chunks and store them in ChromaDB.

    Args:
        chunks: TextChunk objects to embed and index.
        collection_name: Target ChromaDB collection. Defaults to
            settings.collection_name ("resumes").

    Returns:
        Number of chunks successfully indexed.
    """
    model = SentenceTransformer(settings.embedding_model)
    client = _get_client()
    collection = _get_collection(client, collection_name)

    texts = [c.content for c in chunks]
    raw = model.encode(texts, show_progress_bar=True)
    embeddings = raw.tolist() if hasattr(raw, "tolist") else list(raw)
    ids = [str(uuid.uuid4()) for _ in chunks]
    metadatas = [c.metadata for c in chunks]

    collection.add(
        ids=ids,
        documents=texts,
        embeddings=embeddings,
        metadatas=metadatas,
    )
    return len(chunks)


def list_indexed_documents(
    client: Optional[chromadb.PersistentClient] = None,
    collection_name: Optional[str] = None,
) -> List[dict]:
    """Return one metadata record per unique source document in the collection.

    Args:
        client: Optional pre-existing ChromaDB client (creates new one if not provided).
        collection_name: Target collection. Defaults to settings.collection_name.

    Returns:
        List of metadata dicts, one per unique source file.
    """
    if client is None:
        client = _get_client()
    collection = _get_collection(client, collection_name)
    result = collection.get(include=["metadatas"])

    seen: dict[str, dict] = {}
    for meta in result["metadatas"]:
        source = meta.get("source", "desconhecido")
        if source not in seen:
            seen[source] = meta

    return list(seen.values())
