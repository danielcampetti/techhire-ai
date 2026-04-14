"""Unit tests for all agent classes. LLM calls are mocked."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from src.agents.base import AgentResponse
from src.agents.resume_agent import ResumeAgent


# ── ResumeAgent ──────────────────────────────────────────────────────────────

class TestResumeAgentCanHandle:
    def test_high_confidence_for_candidate_question(self):
        agent = ResumeAgent()
        score = agent.can_handle("Quais candidatos têm experiência com Python e RAG?")
        assert score >= 0.4

    def test_high_confidence_for_profile_question(self):
        agent = ResumeAgent()
        score = agent.can_handle("Qual é o perfil do candidato Lucas Mendes?")
        assert score >= 0.2

    def test_low_confidence_for_score_question(self):
        agent = ResumeAgent()
        score = agent.can_handle("Qual o score de aderência para a vaga?")
        assert score < 0.3


class TestResumeAgentAnswer:
    @pytest.mark.asyncio
    async def test_returns_agent_response(self):
        from src.retrieval.query_engine import RetrievedChunk
        mock_chunks = [
            RetrievedChunk(content="Lucas Mendes: 5 anos de experiência em RAG e LLMs.", score=0.9,
                           metadata={"source": "lucas_mendes.pdf", "page": 1})
        ]
        with patch("src.agents.resume_agent.retrieve", return_value=mock_chunks), \
             patch("src.agents.resume_agent.llm_router.generate",
                   new_callable=AsyncMock, return_value="Lucas Mendes tem 5 anos de experiência em RAG."):
            agent = ResumeAgent()
            response = await agent.answer("Quem tem experiência com RAG?")

        assert isinstance(response, AgentResponse)
        assert response.agent_name == "resume"
        assert "RAG" in response.answer
        assert len(response.sources) == 1

    @pytest.mark.asyncio
    async def test_no_chunks_returns_not_found(self):
        with patch("src.agents.resume_agent.retrieve", return_value=[]):
            agent = ResumeAgent()
            response = await agent.answer("pergunta qualquer")

        assert response.confidence == 0.0
        assert "Nenhum" in response.answer


# ── MatchAgent ────────────────────────────────────────────────────────────────

from src.agents.match_agent import MatchAgent, _extract_sql, _SELECT_ONLY_RE


class TestMatchAgentHelpers:
    def test_extract_sql_strips_markdown(self):
        raw = "```sql\nSELECT * FROM matches\n```"
        assert _extract_sql(raw) == "SELECT * FROM matches"

    def test_extract_sql_plain(self):
        raw = "SELECT COUNT(*) FROM candidates"
        assert _extract_sql(raw) == "SELECT COUNT(*) FROM candidates"

    def test_select_only_regex_blocks_delete(self):
        assert not _SELECT_ONLY_RE.match("DELETE FROM candidates")

    def test_select_only_regex_allows_select(self):
        assert _SELECT_ONLY_RE.match("SELECT * FROM matches")


class TestMatchAgentCanHandle:
    def test_high_for_ranking_question(self):
        agent = MatchAgent()
        score = agent.can_handle("Rankeie os top 5 candidatos para a vaga de IA")
        assert score >= 0.4

    def test_high_for_score_question(self):
        agent = MatchAgent()
        score = agent.can_handle("Qual o score de aderência dos candidatos?")
        assert score >= 0.2

    def test_low_for_resume_question(self):
        agent = MatchAgent()
        score = agent.can_handle("O que o candidato Lucas fez nos últimos 3 anos?")
        assert score < 0.3


class TestMatchAgentAnswer:
    @pytest.mark.asyncio
    async def test_returns_agent_response_with_data(self, tmp_path, monkeypatch):
        import src.database.connection as conn_mod
        monkeypatch.setattr(conn_mod.settings, "db_path", str(tmp_path / "test.db"))

        with patch("src.agents.match_agent.llm_router.generate",
                   new_callable=AsyncMock) as mock_gen:
            mock_gen.side_effect = [
                "SELECT COUNT(*) FROM candidates",
                "Existem 20 candidatos no total.",
            ]
            agent = MatchAgent()
            response = await agent.answer("Quantos candidatos temos?")

        assert isinstance(response, AgentResponse)
        assert response.agent_name == "match"
        assert response.data is not None
        assert "sql" in response.data

    @pytest.mark.asyncio
    async def test_blocks_non_select_sql(self, tmp_path, monkeypatch):
        import src.database.connection as conn_mod
        monkeypatch.setattr(conn_mod.settings, "db_path", str(tmp_path / "test.db"))

        with patch("src.agents.match_agent.llm_router.generate",
                   new_callable=AsyncMock, return_value="DELETE FROM candidates"):
            agent = MatchAgent()
            response = await agent.answer("Apague tudo")

        assert response.confidence == 0.0
        assert "segura" in response.answer


# ── PipelineAgent ──────────────────────────────────────────────────────────────

from src.agents.pipeline_agent import PipelineAgent


class TestPipelineAgentCanHandle:
    def test_high_for_funnel_request(self):
        agent = PipelineAgent()
        score = agent.can_handle("Qual o status do funil de contratação?")
        assert score >= 0.5

    def test_high_for_move_request(self):
        agent = PipelineAgent()
        score = agent.can_handle("Mova o candidato para entrevista")
        assert score >= 0.5

    def test_low_for_resume_question(self):
        agent = PipelineAgent()
        score = agent.can_handle("O que é Python?")
        assert score == 0.0


class TestPipelineAgentAnswer:
    @pytest.fixture
    def db_tmp(self, tmp_path, monkeypatch):
        import src.database.connection as conn_mod
        monkeypatch.setattr(conn_mod.settings, "db_path", str(tmp_path / "test.db"))

    @pytest.mark.asyncio
    async def test_report_funnel(self, db_tmp):
        agent = PipelineAgent()
        response = await agent.answer("Qual o status do funil de contratação?")
        assert response.agent_name == "pipeline"
        assert "funil" in response.answer.lower() or "Nenhum" in response.answer
        assert len(response.actions_taken) == 1

    @pytest.mark.asyncio
    async def test_move_stage_without_candidate_id(self, db_tmp):
        agent = PipelineAgent()
        response = await agent.answer("Mova o candidato para entrevista")
        # Should ask for candidate ID
        assert response.confidence == 0.0
        assert "ID" in response.answer

    @pytest.mark.asyncio
    async def test_feedback_email_without_candidate_id(self, db_tmp):
        agent = PipelineAgent()
        response = await agent.answer("Gere um e-mail de feedback")
        # Should ask for candidate ID
        assert response.confidence == 0.0
        assert "ID" in response.answer

    @pytest.mark.asyncio
    async def test_unrecognized_action(self, db_tmp):
        agent = PipelineAgent()
        response = await agent.answer("Faça algo completamente novo")
        assert response.confidence == 0.0
