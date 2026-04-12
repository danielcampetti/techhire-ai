"""Embedding generation and ChromaDB vector store management.

Generates dense embeddings from text chunks using Sentence Transformers
and persists them to a local ChromaDB collection with source metadata.
"""
from __future__ import annotations

import uuid
from typing import List, Optional

import chromadb
from sentence_transformers import SentenceTransformer

from src.config import settings
from src.ingestion.chunker import TextChunk


def _get_client() -> chromadb.PersistentClient:
    return chromadb.PersistentClient(path=settings.chroma_db_path)


def _get_collection(client: chromadb.PersistentClient) -> chromadb.Collection:
    return client.get_or_create_collection(
        name=settings.collection_name,
        metadata={"hnsw:space": "cosine"},
    )


def index_chunks(chunks: List[TextChunk]) -> int:
    """Embed a list of text chunks and store them in ChromaDB.

    Args:
        chunks: TextChunk objects to embed and index.

    Returns:
        Number of chunks successfully indexed.
    """
    model = SentenceTransformer(settings.embedding_model)
    client = _get_client()
    collection = _get_collection(client)

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


def list_indexed_documents(client: Optional[chromadb.PersistentClient] = None) -> List[dict]:
    """Return one metadata record per unique source document in the collection.

    Args:
        client: Optional pre-existing ChromaDB client (creates new one if not provided).

    Returns:
        List of metadata dicts, one per unique source file.
    """
    if client is None:
        client = _get_client()
    collection = _get_collection(client)
    result = collection.get(include=["metadatas"])

    seen: dict[str, dict] = {}
    for meta in result["metadatas"]:
        source = meta.get("source", "desconhecido")
        if source not in seen:
            seen[source] = meta

    return list(seen.values())
