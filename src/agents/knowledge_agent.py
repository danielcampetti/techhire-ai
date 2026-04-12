"""Knowledge agent — wraps the Phase 1 RAG pipeline."""
from __future__ import annotations

from src.agents.base import AgentResponse
from src.llm import ollama_client
from src.retrieval.prompt_builder import build_prompt
from src.retrieval.query_engine import retrieve

_KNOWLEDGE_KEYWORDS = (
    "resolução", "circular", "artigo", "normativo", "regulamentação",
    "lgpd", "compliance", "pld", "coaf", "bacen", "bcb", "cmn",
    "cibersegurança", "segurança cibernética", "prazo", "obrigação",
    "política", "disposição", "inciso", "parágrafo",
)


class KnowledgeAgent:
    """Agent specialized in regulatory document search and analysis."""

    name = "knowledge"

    def can_handle(self, question: str) -> float:
        """Return confidence score (0–1) for handling this question."""
        q = question.lower()
        hits = sum(1 for kw in _KNOWLEDGE_KEYWORDS if kw in q)
        return min(hits * 0.2, 1.0)

    async def answer(self, question: str) -> AgentResponse:
        """Retrieve relevant chunks and generate an answer using Ollama.

        Args:
            question: Natural language question in Portuguese.

        Returns:
            AgentResponse with the answer text, sources, and confidence score.
        """
        chunks = retrieve(question)

        if not chunks:
            return AgentResponse(
                agent_name=self.name,
                answer="Nenhum documento relevante encontrado para esta pergunta.",
                confidence=0.0,
            )

        prompt = build_prompt(question, chunks)
        answer_text = await ollama_client.generate(prompt)

        sources = list({
            f"{c.metadata.get('source', 'Desconhecido')}, p. {c.metadata.get('page', '?')}"
            for c in chunks
        })

        return AgentResponse(
            agent_name=self.name,
            answer=answer_text,
            sources=sources,
            confidence=0.9,
        )
