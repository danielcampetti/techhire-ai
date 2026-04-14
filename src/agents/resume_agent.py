"""Resume agent — answers questions about candidate resumes using RAG."""
from __future__ import annotations

from typing import Optional

from src.agents.base import AgentResponse
from src.llm import llm_router
from src.retrieval.prompt_builder import build_prompt
from src.retrieval.query_engine import retrieve

_RESUME_KEYWORDS = (
    "candidato", "candidata", "candidatos", "candidatas",
    "currículo", "curriculo", "currículos", "curriculos",
    "perfil", "perfis",
    "experiência", "experiencia", "experiências", "experiencias",
    "formação", "formacao", "formações", "formacoes",
    "habilidades", "skills", "competências", "competencias",
    "histórico", "historico",
    "educação", "educacao",
    "certificação", "certificacao", "certificações",
    "cargo", "função", "funcao",
    "trabalhou", "trabalha", "atuou", "atua",
    "conhece", "conhecimento",
    "senior", "sênior", "pleno", "junior", "júnior",
)


class ResumeAgent:
    """Agent specialized in answering questions about candidate resumes via RAG."""

    name = "resume"

    def can_handle(self, question: str) -> float:
        """Return confidence score (0–1) for handling this question."""
        q = question.lower()
        hits = sum(1 for kw in _RESUME_KEYWORDS if kw in q)
        return min(hits * 0.2, 1.0)

    async def answer(
        self,
        question: str,
        provider: str = "ollama",
        conversation_history: Optional[list[dict]] = None,
    ) -> AgentResponse:
        """Retrieve relevant resume chunks and generate an answer.

        Args:
            question: Natural language question in Portuguese.
            provider: LLM backend — "ollama" (default) or "claude".
            conversation_history: Optional prior messages for multi-turn context.

        Returns:
            AgentResponse with the answer text, sources, and confidence score.
        """
        chunks = retrieve(question)

        if not chunks:
            return AgentResponse(
                agent_name=self.name,
                answer="Nenhum currículo relevante encontrado para esta pergunta.",
                confidence=0.0,
            )

        prompt = build_prompt(question, chunks, conversation_history=conversation_history)
        answer_text = await llm_router.generate(prompt, provider=provider)

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

    async def prepare(
        self,
        question: str,
        conversation_history: Optional[list[dict]] = None,
    ) -> tuple[str | None, list]:
        """Retrieve resume chunks and build prompt without calling the LLM.

        Use this with the streaming endpoint: returns the assembled prompt and
        retrieved chunks so the caller can stream the LLM response itself.

        Args:
            question: Natural language question in Portuguese.
            conversation_history: Optional prior messages for multi-turn context.

        Returns:
            Tuple of (prompt_string, chunks). Returns (None, []) when no
            relevant chunks are found.
        """
        chunks = retrieve(question)
        if not chunks:
            return None, []
        prompt = build_prompt(question, chunks, conversation_history=conversation_history)
        return prompt, chunks
