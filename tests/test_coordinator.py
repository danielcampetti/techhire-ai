"""Tests for the CoordinatorAgent routing logic."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from src.agents.coordinator import CoordinatorAgent, CoordinatorResponse, _heuristic_route, _is_conversational
from src.agents.base import AgentResponse


class TestHeuristicRoute:
    def test_routes_candidate_question_to_resume(self):
        assert _heuristic_route("Quais candidatos têm experiência com Python?") == "RESUME"

    def test_routes_ranking_question_to_match(self):
        assert _heuristic_route("Rankeie por score de aderência") == "MATCH"

    def test_routes_pipeline_request_to_pipeline(self):
        assert _heuristic_route("Mova o candidato para entrevista") == "PIPELINE"

    def test_routes_combined_to_resume_match(self):
        q = "Compare o perfil do candidato com o score de aderência para a vaga"
        assert _heuristic_route(q) == "RESUME+MATCH"


class TestEnhancedHeuristicRoute:
    """Tests for the accent-insensitive keyword classifier."""

    def test_resume_route_candidato(self):
        assert _heuristic_route("Quem é o candidato Lucas Mendes?") == "RESUME"

    def test_resume_route_curriculo(self):
        assert _heuristic_route("Mostre o currículo de Ana Beatriz") == "RESUME"

    def test_resume_route_habilidades(self):
        assert _heuristic_route("Quais são as habilidades do candidato?") == "RESUME"

    def test_resume_route_no_accent(self):
        assert _heuristic_route("Qual a formacao do candidato?") == "RESUME"

    def test_match_route_score(self):
        assert _heuristic_route("Qual o score para a vaga atual?") == "MATCH"

    def test_match_route_ranking(self):
        assert _heuristic_route("Rankeie os top 5 para a vaga de IA") == "MATCH"

    def test_match_route_comparar(self):
        assert _heuristic_route("Compare os scores para a vaga") == "MATCH"

    def test_pipeline_route_mover(self):
        assert _heuristic_route("Mova o candidato #3 para entrevista") == "PIPELINE"

    def test_pipeline_route_rejeitar(self):
        assert _heuristic_route("Rejeite o candidato com score baixo") == "PIPELINE"

    def test_pipeline_route_aprovar(self):
        assert _heuristic_route("Aprove o candidato #1 para a vaga") == "PIPELINE"

    def test_pipeline_route_funil(self):
        assert _heuristic_route("Qual o status do funil de contratação?") == "PIPELINE"

    def test_pipeline_route_email_feedback(self):
        assert _heuristic_route("Gere e-mail de feedback para o candidato") == "PIPELINE"

    def test_resume_default(self):
        assert _heuristic_route("O que é Python?") == "RESUME"


class TestClassifyNoLlm:
    """_classify() should never call llm_router.generate for routing."""

    @pytest.mark.asyncio
    async def test_classify_match_does_not_call_llm(self):
        from unittest.mock import patch, AsyncMock
        with patch("src.agents.coordinator.llm_router") as mock_router:
            mock_router.generate = AsyncMock(return_value="MATCH")
            coordinator = CoordinatorAgent.__new__(CoordinatorAgent)
            result = await coordinator._classify("Rankeie por score de aderência")
        mock_router.generate.assert_not_called()
        assert result == "MATCH"

    @pytest.mark.asyncio
    async def test_classify_resume_does_not_call_llm(self):
        from unittest.mock import patch, AsyncMock
        with patch("src.agents.coordinator.llm_router") as mock_router:
            mock_router.generate = AsyncMock(return_value="RESUME")
            coordinator = CoordinatorAgent.__new__(CoordinatorAgent)
            result = await coordinator._classify("Quais as habilidades do candidato?")
        mock_router.generate.assert_not_called()
        assert result == "RESUME"

    @pytest.mark.asyncio
    async def test_classify_pipeline_does_not_call_llm(self):
        from unittest.mock import patch, AsyncMock
        with patch("src.agents.coordinator.llm_router") as mock_router:
            mock_router.generate = AsyncMock(return_value="PIPELINE")
            coordinator = CoordinatorAgent.__new__(CoordinatorAgent)
            result = await coordinator._classify("Mova o candidato para entrevista")
        mock_router.generate.assert_not_called()
        assert result == "PIPELINE"

    @pytest.mark.asyncio
    async def test_classify_resume_match_does_not_call_llm(self):
        from unittest.mock import patch, AsyncMock
        with patch("src.agents.coordinator.llm_router") as mock_router:
            mock_router.generate = AsyncMock(return_value="RESUME+MATCH")
            coordinator = CoordinatorAgent.__new__(CoordinatorAgent)
            result = await coordinator._classify("Compare o currículo do candidato com o score de aderência")
        mock_router.generate.assert_not_called()
        assert result == "RESUME+MATCH"


class TestCoordinatorProcess:
    @pytest.fixture
    def db_tmp(self, tmp_path, monkeypatch):
        import src.database.connection as conn_mod
        monkeypatch.setattr(conn_mod.settings, "db_path", str(tmp_path / "test.db"))

    @pytest.mark.asyncio
    async def test_routes_to_resume_agent(self, db_tmp):
        mock_r_response = AgentResponse(
            agent_name="resume", answer="Lucas Mendes tem 5 anos de experiência em IA.", confidence=0.9
        )
        coord = CoordinatorAgent.__new__(CoordinatorAgent)
        coord.resume_agent = AsyncMock()
        coord.resume_agent.answer = AsyncMock(return_value=mock_r_response)
        coord.match_agent = AsyncMock()
        coord.pipeline_agent = AsyncMock()

        with patch("src.agents.coordinator.llm_router.generate",
                   new_callable=AsyncMock, return_value="RESUME"), \
             patch("src.agents.coordinator.init_db"), \
             patch("src.agents.coordinator.audit.log_interaction",
                   new_callable=AsyncMock, return_value=1):
            result = await coord.process("Quem tem experiência com Python?")

        assert isinstance(result, CoordinatorResponse)
        assert result.roteamento == "RESUME"
        assert "resume" in result.agentes_utilizados
        assert result.provider_utilizado == "ollama"

    @pytest.mark.asyncio
    async def test_routes_to_match_agent(self, db_tmp):
        mock_m_response = AgentResponse(
            agent_name="match", answer="Top 5 candidatos por score.", confidence=0.85,
            data={"sql": "SELECT * FROM matches ORDER BY overall_score DESC", "rows": [], "total": 5}
        )
        coord = CoordinatorAgent.__new__(CoordinatorAgent)
        coord.resume_agent = AsyncMock()
        coord.match_agent = AsyncMock()
        coord.match_agent.answer = AsyncMock(return_value=mock_m_response)
        coord.pipeline_agent = AsyncMock()

        with patch("src.agents.coordinator.llm_router.generate",
                   new_callable=AsyncMock, return_value="MATCH"), \
             patch("src.agents.coordinator.init_db"), \
             patch("src.agents.coordinator.audit.log_interaction",
                   new_callable=AsyncMock, return_value=2):
            result = await coord.process("Rankeie os top 5 por score")

        assert result.roteamento == "MATCH"
        assert "match" in result.agentes_utilizados
        assert result.detalhes_agentes[0]["dados"]["total"] == 5
        assert result.provider_utilizado == "ollama"
