"""Prompt assembly for the compliance RAG assistant.

Builds structured Portuguese-language prompts that instruct the LLM to
answer based exclusively on retrieved regulatory context and cite sources.
"""
from __future__ import annotations

from typing import List, Optional

from src.retrieval.query_engine import RetrievedChunk

_SYSTEM_PROMPT = """\
Você é um assistente especializado em regulamentação financeira brasileira.

REGRAS OBRIGATÓRIAS:
1. Responda com base nos trechos fornecidos abaixo e no histórico da conversa quando disponível. NUNCA invente informações.
2. Se a resposta está nos trechos, cite o artigo e normativo exato. Exemplo: "Conforme Art. 49 da Circular 3.978..."
3. Se a resposta NÃO está nos trechos NEM no histórico da conversa, diga: "Esta informação não foi encontrada nos documentos disponíveis."
4. NUNCA cite artigos, valores, prazos ou normativos que não apareçam explicitamente nos trechos.
5. Quando mencionar valores monetários, prazos ou percentuais, copie EXATAMENTE o que está nos trechos.
6. Antes de responder, releia os trechos e verifique se sua resposta é consistente com eles.
7. Se a pergunta se refere ao histórico desta conversa (ex: "qual foi a pergunta anterior?", "o que você disse antes?"), responda com base no histórico da conversa acima.\
"""

_CONTEXT_TEMPLATE = """\
## TRECHOS DOS DOCUMENTOS REGULATÓRIOS

{chunks}

---

## PERGUNTA DO USUÁRIO

{question}

---

## INSTRUÇÕES

Responda à pergunta acima usando as informações dos trechos fornecidos ou do histórico da conversa quando relevante.
- Para perguntas sobre regulamentação: cite o artigo e normativo específico (ex: "Art. 9º da Resolução CMN nº 4.893")
- Para perguntas sobre a própria conversa (ex: "qual foi a pergunta anterior?"): use o histórico da conversa acima
- Se houver valores, prazos ou percentuais nos trechos, transcreva-os exatamente
- Se a informação não estiver nos trechos nem no histórico, informe que não foi encontrada
- Seja direto e objetivo na resposta\
"""


def build_prompt(
    question: str,
    chunks: List[RetrievedChunk],
    conversation_history: Optional[List[dict]] = None,
) -> str:
    """Assemble the final LLM prompt from a question, retrieved chunks, and optional prior context.

    Args:
        question: The user's regulatory question (in Portuguese).
        chunks: Retrieved and reranked document chunks with metadata.
        conversation_history: Prior messages as [{"role": "user"|"assistant", "content": "..."}].
            Injected between system prompt and RAG chunks.

    Returns:
        Formatted prompt string ready for submission to the LLM.
    """
    chunk_parts: List[str] = []
    for i, chunk in enumerate(chunks, start=1):
        source = chunk.metadata.get("source", "Desconhecido")
        page = chunk.metadata.get("page", "?")
        chunk_parts.append(
            f"[Trecho {i}] Fonte: {source}, Página {page}\n{chunk.content}"
        )
    chunks_text = "\n\n---\n\n".join(chunk_parts)

    history_section = ""
    if conversation_history:
        lines = []
        for msg in conversation_history:
            label = "Usuário" if msg["role"] == "user" else "Assistente"
            lines.append(f"{label}: {msg['content'][:500]}")
        history_section = (
            "\n\n--- Histórico da conversa ---\n"
            + "\n".join(lines)
            + "\n--- Fim do histórico ---"
        )

    return (
        f"{_SYSTEM_PROMPT}{history_section}\n\n"
        + _CONTEXT_TEMPLATE.format(chunks=chunks_text, question=question)
    )
