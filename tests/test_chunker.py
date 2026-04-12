"""Tests for text chunking functionality."""
import pytest

from src.ingestion.pdf_loader import DocumentPage
from src.ingestion.chunker import chunk_pages, TextChunk


def _make_page(
    content: str,
    filename: str = "norma.pdf",
    page_number: int = 1,
) -> DocumentPage:
    return DocumentPage(
        content=content,
        filename=filename,
        page_number=page_number,
        title="Test Doc",
        metadata={"source": filename, "page": page_number, "title": "Test Doc"},
    )


def test_chunk_returns_text_chunk_instances() -> None:
    pages = [_make_page("Artigo 1. Compliance e obrigatorio para instituicoes financeiras.")]
    chunks = chunk_pages(pages)
    assert len(chunks) >= 1
    assert isinstance(chunks[0], TextChunk)


def test_chunk_carries_source_metadata() -> None:
    pages = [_make_page("Texto de teste.", filename="circ3978.pdf", page_number=5)]
    chunks = chunk_pages(pages)
    assert chunks[0].filename == "circ3978.pdf"
    assert chunks[0].page_number == 5
    assert chunks[0].metadata["page"] == 5
    assert chunks[0].metadata["source"] == "circ3978.pdf"


def test_long_text_produces_multiple_chunks() -> None:
    long_text = "Esta e uma norma regulatoria importante. " * 60
    pages = [_make_page(long_text)]
    chunks = chunk_pages(pages, chunk_size=200, chunk_overlap=20)
    assert len(chunks) > 1


def test_chunk_content_is_non_empty() -> None:
    pages = [_make_page("Artigo 2. Os bancos devem manter registros de conformidade.")]
    chunks = chunk_pages(pages)
    for chunk in chunks:
        assert chunk.content.strip() != ""


def test_chunk_index_increments_per_page() -> None:
    long_text = "Regulacao financeira e essencial. " * 80
    pages = [_make_page(long_text)]
    chunks = chunk_pages(pages, chunk_size=100, chunk_overlap=10)
    indices = [c.chunk_index for c in chunks]
    assert indices == list(range(len(chunks)))


def test_empty_pages_produce_no_chunks() -> None:
    chunks = chunk_pages([])
    assert chunks == []
