"""Prompt assembly for the compliance RAG assistant.

Builds structured Portuguese-language prompts that instruct the LLM to
answer based exclusively on retrieved regulatory context and cite sources.
"""
from __future__ import annotations

from typing import List

from src.retrieval.query_engine import RetrievedChunk

_SYSTEM_INSTRUCTIONS = """\
Voce e um assistente especializado em compliance e regulamentacao financeira brasileira.
Sua funcao e responder perguntas com base EXCLUSIVAMENTE nos documentos regulatorios fornecidos abaixo.

Regras obrigatorias:
1. Responda APENAS com informacoes presentes no contexto fornecido.
2. Cite a regulamentacao especifica (nome do documento, artigo ou secao) ao responder.
3. Se a informacao nao estiver no contexto, responda exatamente: \
"Esta informacao nao foi encontrada nos documentos disponiveis."
4. Use linguagem formal e tecnica adequada ao ambiente regulatorio brasileiro.
5. Seja objetivo e preciso - evite suposicoes ou informacoes externas.\
"""


def build_prompt(question: str, chunks: List[RetrievedChunk]) -> str:
    """Assemble the final LLM prompt from a question and retrieved chunks.

    Args:
        question: The user's regulatory question (in Portuguese).
        chunks: Retrieved and reranked document chunks with metadata.

    Returns:
        Formatted prompt string ready for submission to the LLM.
    """
    context_parts: List[str] = []
    for i, chunk in enumerate(chunks, start=1):
        source = chunk.metadata.get("source", "Desconhecido")
        page = chunk.metadata.get("page", "?")
        context_parts.append(f"[Fonte {i} - {source}, Pagina {page}]\n{chunk.content}")

    context = "\n\n---\n\n".join(context_parts)

    return (
        f"{_SYSTEM_INSTRUCTIONS}\n\n"
        f"CONTEXTO REGULATORIO:\n{context}\n\n"
        f"PERGUNTA: {question}\n\n"
        f"RESPOSTA:"
    )
