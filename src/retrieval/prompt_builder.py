"""Prompt assembly for the compliance RAG assistant.

Builds structured Portuguese-language prompts that instruct the LLM to
answer based exclusively on retrieved regulatory context and cite sources.
"""
from __future__ import annotations

from typing import List

from src.retrieval.query_engine import RetrievedChunk

_SYSTEM_PROMPT = """\
Você é um assistente especializado em regulamentação financeira brasileira.

REGRAS OBRIGATÓRIAS:
1. Responda EXCLUSIVAMENTE com base nos trechos fornecidos abaixo. NUNCA invente informações.
2. Se a resposta está nos trechos, cite o artigo e normativo exato. Exemplo: "Conforme Art. 49 da Circular 3.978..."
3. Se a resposta NÃO está nos trechos, diga: "Esta informação não foi encontrada nos documentos disponíveis."
4. NUNCA cite artigos, valores, prazos ou normativos que não apareçam explicitamente nos trechos.
5. Quando mencionar valores monetários, prazos ou percentuais, copie EXATAMENTE o que está nos trechos.
6. Antes de responder, releia os trechos e verifique se sua resposta é consistente com eles.\
"""

_CONTEXT_TEMPLATE = """\
## TRECHOS DOS DOCUMENTOS REGULATÓRIOS

{chunks}

---

## PERGUNTA DO USUÁRIO

{question}

---

## INSTRUÇÕES

Responda à pergunta acima usando APENAS as informações dos trechos fornecidos.
- Cite o artigo e normativo específico (ex: "Art. 9º da Resolução CMN nº 4.893")
- Se houver valores, prazos ou percentuais nos trechos, transcreva-os exatamente
- Se a informação não estiver nos trechos, informe que não foi encontrada
- Seja direto e objetivo na resposta\
"""


def build_prompt(question: str, chunks: List[RetrievedChunk]) -> str:
    """Assemble the final LLM prompt from a question and retrieved chunks.

    Args:
        question: The user's regulatory question (in Portuguese).
        chunks: Retrieved and reranked document chunks with metadata.

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

    return (
        f"{_SYSTEM_PROMPT}\n\n"
        + _CONTEXT_TEMPLATE.format(chunks=chunks_text, question=question)
    )
