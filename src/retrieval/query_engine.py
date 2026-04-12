"""Retrieval query engine with dense embedding search and cross-encoder reranking.

Pipeline:
1. Embed user query with Sentence Transformers
2. ANN search in ChromaDB (top-K candidates)
3. Rerank with cross-encoder (top-N final results)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

import chromadb
import numpy as np
from sentence_transformers import CrossEncoder, SentenceTransformer

from src.config import settings


@dataclass
class RetrievedChunk:
    """A retrieved text chunk with its relevance score and source metadata."""

    content: str
    score: float
    metadata: dict = field(default_factory=dict)


def retrieve(query: str) -> List[RetrievedChunk]:
    """Retrieve and rerank the most relevant chunks for a query.

    Args:
        query: Natural language query in Portuguese or English.

    Returns:
        List of RetrievedChunk objects sorted by reranking score (descending),
        limited to settings.rerank_top_k results.
    """
    # Step 1: Embed the query
    embedder = SentenceTransformer(settings.embedding_model)
    query_embedding: List[float] = embedder.encode(query).tolist()

    # Step 2: Vector search in ChromaDB
    client = chromadb.PersistentClient(path=settings.chroma_db_path)
    collection = client.get_or_create_collection(settings.collection_name)

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=settings.retrieval_top_k,
        include=["documents", "metadatas", "distances"],
    )

    documents: List[str] = results["documents"][0]
    metadatas: List[dict] = results["metadatas"][0]

    if not documents:
        return []

    # Step 3: Cross-encoder reranking
    reranker = CrossEncoder(settings.reranker_model)
    pairs = [[query, doc] for doc in documents]
    scores: np.ndarray = reranker.predict(pairs)

    ranked = sorted(
        zip(documents, metadatas, scores.tolist()),
        key=lambda x: x[2],
        reverse=True,
    )[: settings.rerank_top_k]

    return [
        RetrievedChunk(content=doc, score=float(score), metadata=meta)
        for doc, meta, score in ranked
    ]
