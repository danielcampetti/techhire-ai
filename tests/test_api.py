"""Integration tests for the FastAPI endpoints."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient


def _get_client() -> TestClient:
    """Import app lazily to avoid side effects at module load time."""
    from src.api.main import app
    return TestClient(app)


def _analyst_token() -> str:
    from src.api.auth import create_access_token
    return create_access_token(1, "analyst", "analyst")


def _manager_token() -> str:
    from src.api.auth import create_access_token
    return create_access_token(1, "manager", "manager")


def test_ingest_no_pdfs_returns_zero_count(tmp_path) -> None:
    with patch("src.api.main.settings") as mock_cfg, \
         patch("src.api.main.load_all_pdfs", return_value=[]):
        mock_cfg.data_raw_dir = tmp_path
        mock_cfg.collection_name = "resumes"
        mock_cfg.jobs_collection_name = "job_postings"

        client = _get_client()
        response = client.post("/ingest", headers={"Authorization": f"Bearer {_manager_token()}"})

    assert response.status_code == 200
    assert response.json()["chunks_indexados"] == 0


def test_ingest_with_pdfs_routes_to_correct_collection(tmp_path) -> None:
    from src.ingestion.pdf_loader import DocumentPage
    from src.ingestion.chunker import TextChunk

    mock_page = DocumentPage(
        content="Lucas Mendes — experiência em Python, RAG, LLMs. Formação em Computação.",
        filename="lucas_mendes.pdf", page_number=1,
        title="Lucas Mendes", metadata={"source": "lucas_mendes.pdf", "page": 1, "title": "Lucas Mendes"}
    )
    mock_chunk = TextChunk(
        content="Lucas Mendes — experiência em Python, RAG, LLMs.",
        filename="lucas_mendes.pdf", page_number=1,
        title="Lucas Mendes", chunk_index=0, metadata={}
    )

    with patch("src.api.main.settings") as mock_cfg, \
         patch("src.api.main.load_all_pdfs", return_value=[mock_page]), \
         patch("src.api.main.classify_document", return_value="resume"), \
         patch("src.api.main.chunk_pages", return_value=[mock_chunk, mock_chunk]), \
         patch("src.api.main.index_chunks", return_value=2):
        mock_cfg.data_raw_dir = tmp_path
        mock_cfg.collection_name = "resumes"
        mock_cfg.jobs_collection_name = "job_postings"

        client = _get_client()
        response = client.post("/ingest", headers={"Authorization": f"Bearer {_manager_token()}"})

    assert response.status_code == 200
    assert response.json()["chunks_indexados"] == 2
    assert response.json()["curriculos_indexados"] == 1


def test_chat_returns_answer_with_sources() -> None:
    from src.retrieval.query_engine import RetrievedChunk

    mock_chunk = RetrievedChunk(
        content="Lucas Mendes tem experiência com Python e RAG.",
        score=0.92,
        metadata={"source": "lucas_mendes.pdf", "page": 1},
    )

    with patch("src.api.main.retrieve", return_value=[mock_chunk]), \
         patch("src.api.main.ollama_client.generate", new_callable=AsyncMock, return_value="Lucas Mendes tem experiência com RAG."), \
         patch("src.api.main.settings") as mock_cfg:
        mock_cfg.llm_provider = "ollama"
        client = _get_client()
        response = client.post(
            "/chat",
            json={"pergunta": "Quem tem experiência com RAG?"},
            headers={"Authorization": f"Bearer {_analyst_token()}"},
        )

    assert response.status_code == 200
    body = response.json()
    assert "resposta" in body
    assert "fontes" in body
    assert body["fontes"][0]["arquivo"] == "lucas_mendes.pdf"
    assert body["fontes"][0]["pagina"] == 1


def test_chat_no_results_returns_not_found_message() -> None:
    with patch("src.api.main.retrieve", return_value=[]):
        client = _get_client()
        response = client.post(
            "/chat",
            json={"pergunta": "pergunta sem resultado"},
            headers={"Authorization": f"Bearer {_analyst_token()}"},
        )

    assert response.status_code == 200
    assert "nao foi encontrada" in response.json()["resposta"].replace("ã", "a").lower() \
        or "não foi encontrada" in response.json()["resposta"].lower()


def test_list_resumes_returns_document_list() -> None:
    with patch("src.api.main._get_chroma_client"), \
         patch("src.api.main.list_indexed_documents", return_value=[{"source": "lucas_mendes.pdf", "title": "Lucas Mendes"}]):
        client = _get_client()
        response = client.get("/resumes", headers={"Authorization": f"Bearer {_analyst_token()}"})

    assert response.status_code == 200
    body = response.json()
    assert "curriculos" in body
    assert body["total"] == 1


def _agent_token() -> str:
    from src.api.auth import create_access_token
    return create_access_token(2, "analyst", "analyst")


def test_agent_endpoint_passes_provider_to_coordinator() -> None:
    from src.agents.coordinator import CoordinatorResponse

    mock_response = CoordinatorResponse(
        pergunta="Quem tem experiência com RAG?",
        roteamento="RESUME",
        agentes_utilizados=["resume"],
        resposta_final="Lucas Mendes tem experiência com RAG.",
        detalhes_agentes=[],
        log_id=1,
        provider_utilizado="claude",
    )

    with patch("src.api.main.CoordinatorAgent") as MockCoordinator:
        instance = MockCoordinator.return_value
        instance.process = AsyncMock(return_value=mock_response)
        client = _get_client()
        response = client.post(
            "/agent",
            json={"pergunta": "Quem tem experiência com RAG?", "provider": "claude"},
            headers={"Authorization": f"Bearer {_agent_token()}"},
        )

    assert response.status_code == 200
    assert response.json()["provider_utilizado"] == "claude"


def test_agent_endpoint_returns_503_when_claude_key_missing() -> None:
    with patch("src.api.main.CoordinatorAgent") as MockCoordinator:
        instance = MockCoordinator.return_value
        instance.process = AsyncMock(side_effect=ValueError("ANTHROPIC_API_KEY não configurado"))
        client = _get_client()
        response = client.post(
            "/agent",
            json={"pergunta": "Quem tem experiência com RAG?", "provider": "claude"},
            headers={"Authorization": f"Bearer {_agent_token()}"},
        )

    assert response.status_code == 503
    assert "ANTHROPIC_API_KEY" in response.json()["detail"]


def test_chat_returns_503_when_claude_key_missing() -> None:
    from src.retrieval.query_engine import RetrievedChunk

    mock_chunk = RetrievedChunk(
        content="Lucas Mendes tem experiência com Python.",
        score=0.92,
        metadata={"source": "lucas_mendes.pdf", "page": 1},
    )

    with patch("src.api.main.retrieve", return_value=[mock_chunk]), \
         patch("src.api.main.claude_client.generate", new_callable=AsyncMock,
               side_effect=ValueError("ANTHROPIC_API_KEY não configurado")):
        client = _get_client()
        response = client.post(
            "/chat",
            json={"pergunta": "Quem tem experiência com Python?", "provider": "claude"},
            headers={"Authorization": f"Bearer {_analyst_token()}"},
        )

    assert response.status_code == 503
