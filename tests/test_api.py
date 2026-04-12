"""Integration tests for the FastAPI endpoints."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient


def _get_client() -> TestClient:
    """Import app lazily to avoid side effects at module load time."""
    from src.api.main import app
    return TestClient(app)


def test_ingest_no_pdfs_returns_zero_count(tmp_path) -> None:
    with patch("src.api.main.settings") as mock_cfg, \
         patch("src.api.main.load_all_pdfs", return_value=[]):
        mock_cfg.data_raw_dir = tmp_path
        mock_cfg.chunk_size = 800
        mock_cfg.chunk_overlap = 100

        client = _get_client()
        response = client.post("/ingest")

    assert response.status_code == 200
    assert response.json()["chunks_indexados"] == 0


def test_ingest_with_pdfs_returns_chunk_count(tmp_path) -> None:
    from src.ingestion.pdf_loader import DocumentPage
    from src.ingestion.chunker import TextChunk

    mock_page = DocumentPage(
        content="Artigo 1.", filename="norma.pdf", page_number=1,
        title="Norma", metadata={"source": "norma.pdf", "page": 1, "title": "Norma"}
    )
    mock_chunk = TextChunk(
        content="Artigo 1.", filename="norma.pdf", page_number=1,
        title="Norma", chunk_index=0, metadata={}
    )

    with patch("src.api.main.settings") as mock_cfg, \
         patch("src.api.main.load_all_pdfs", return_value=[mock_page]), \
         patch("src.api.main.chunk_pages", return_value=[mock_chunk, mock_chunk]), \
         patch("src.api.main.index_chunks", return_value=2):
        mock_cfg.data_raw_dir = tmp_path
        mock_cfg.chunk_size = 800
        mock_cfg.chunk_overlap = 100

        client = _get_client()
        response = client.post("/ingest")

    assert response.status_code == 200
    assert response.json()["chunks_indexados"] == 2


def test_chat_returns_answer_with_sources() -> None:
    from src.retrieval.query_engine import RetrievedChunk

    mock_chunk = RetrievedChunk(
        content="Compliance e obrigatorio.",
        score=0.92,
        metadata={"source": "norma.pdf", "page": 3},
    )

    with patch("src.api.main.retrieve", return_value=[mock_chunk]), \
         patch("src.api.main.generate", new_callable=AsyncMock, return_value="O compliance e essencial."):
        client = _get_client()
        response = client.post("/chat", json={"pergunta": "O que e compliance?"})

    assert response.status_code == 200
    body = response.json()
    assert "resposta" in body
    assert "fontes" in body
    assert body["fontes"][0]["arquivo"] == "norma.pdf"
    assert body["fontes"][0]["pagina"] == 3


def test_chat_no_results_returns_not_found_message() -> None:
    with patch("src.api.main.retrieve", return_value=[]):
        client = _get_client()
        response = client.post("/chat", json={"pergunta": "pergunta sem resultado"})

    assert response.status_code == 200
    assert "nao foi encontrada" in response.json()["resposta"]


def test_list_documents_returns_document_list() -> None:
    with patch("src.api.main._get_chroma_client"), \
         patch("src.api.main.list_indexed_documents", return_value=[{"source": "norma.pdf", "title": "Norma"}]):
        client = _get_client()
        response = client.get("/documents")

    assert response.status_code == 200
    body = response.json()
    assert "documentos" in body
    assert body["total"] == 1
