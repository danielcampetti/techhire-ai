"""Unit tests for all agent classes. LLM calls are mocked."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from src.agents.base import AgentResponse
from src.agents.knowledge_agent import KnowledgeAgent


# ── KnowledgeAgent ──────────────────────────────────────────────────────────

class TestKnowledgeAgentCanHandle:
    def test_high_confidence_for_resolution_question(self):
        agent = KnowledgeAgent()
        score = agent.can_handle("O que diz a Resolução CMN 5.274 sobre segurança cibernética?")
        assert score >= 0.4

    def test_low_confidence_for_data_question(self):
        agent = KnowledgeAgent()
        score = agent.can_handle("Quantas transações acima de R$50.000 temos?")
        assert score < 0.3


class TestKnowledgeAgentAnswer:
    @pytest.mark.asyncio
    async def test_returns_agent_response(self):
        from src.retrieval.query_engine import RetrievedChunk
        mock_chunks = [
            RetrievedChunk(content="Prazo: 1º de março de 2026.", score=0.9,
                           metadata={"source": "res_5274.pdf", "page": 3})
        ]
        with patch("src.agents.knowledge_agent.retrieve", return_value=mock_chunks), \
             patch("src.agents.knowledge_agent.ollama_client.generate",
                   new_callable=AsyncMock, return_value="O prazo é 1º de março de 2026."):
            agent = KnowledgeAgent()
            response = await agent.answer("Qual é o prazo da Resolução 5.274?")

        assert isinstance(response, AgentResponse)
        assert response.agent_name == "knowledge"
        assert "março" in response.answer
        assert len(response.sources) == 1

    @pytest.mark.asyncio
    async def test_no_chunks_returns_not_found(self):
        with patch("src.agents.knowledge_agent.retrieve", return_value=[]):
            agent = KnowledgeAgent()
            response = await agent.answer("pergunta qualquer")

        assert response.confidence == 0.0
        assert "Nenhum" in response.answer
