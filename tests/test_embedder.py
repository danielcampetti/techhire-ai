"""Tests for embedding and ChromaDB indexing functionality."""
import pytest
from unittest.mock import MagicMock, patch

from src.ingestion.chunker import TextChunk
from src.ingestion.embedder import index_chunks, list_indexed_documents


def _make_chunk(content: str = "Artigo 1 de compliance.", filename: str = "norma.pdf") -> TextChunk:
    return TextChunk(
        content=content,
        filename=filename,
        page_number=1,
        title="Norma Teste",
        chunk_index=0,
        metadata={"source": filename, "page": 1, "title": "Norma Teste", "chunk_index": 0},
    )


def test_index_chunks_returns_count_of_indexed_items() -> None:
    chunks = [_make_chunk("Texto A"), _make_chunk("Texto B")]

    mock_collection = MagicMock()
    mock_model = MagicMock()
    mock_model.encode.return_value = [[0.1, 0.2]] * 2

    with patch("src.ingestion.embedder.SentenceTransformer", return_value=mock_model), \
         patch("src.ingestion.embedder.chromadb.PersistentClient") as mock_client:
        mock_client.return_value.get_or_create_collection.return_value = mock_collection

        count = index_chunks(chunks)

    assert count == 2
    mock_collection.add.assert_called_once()


def test_index_chunks_calls_collection_add_with_correct_structure() -> None:
    chunks = [_make_chunk("Norma de ciberseguranca.")]

    mock_collection = MagicMock()
    mock_model = MagicMock()
    mock_model.encode.return_value = [[0.3, 0.4, 0.5]]

    with patch("src.ingestion.embedder.SentenceTransformer", return_value=mock_model), \
         patch("src.ingestion.embedder.chromadb.PersistentClient") as mock_client:
        mock_client.return_value.get_or_create_collection.return_value = mock_collection

        index_chunks(chunks)

    call_kwargs = mock_collection.add.call_args.kwargs
    assert "ids" in call_kwargs
    assert "documents" in call_kwargs
    assert "embeddings" in call_kwargs
    assert "metadatas" in call_kwargs
    assert call_kwargs["documents"] == ["Norma de ciberseguranca."]


def test_list_indexed_documents_returns_unique_sources() -> None:
    mock_collection = MagicMock()
    mock_collection.get.return_value = {
        "metadatas": [
            {"source": "doc_a.pdf", "page": 1},
            {"source": "doc_a.pdf", "page": 2},
            {"source": "doc_b.pdf", "page": 1},
        ]
    }

    with patch("src.ingestion.embedder.chromadb.PersistentClient") as mock_client:
        mock_client.return_value.get_or_create_collection.return_value = mock_collection

        docs = list_indexed_documents()

    sources = {d["source"] for d in docs}
    assert sources == {"doc_a.pdf", "doc_b.pdf"}
