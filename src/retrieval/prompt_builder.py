"""Prompt assembly for the TechHire AI recruitment assistant.

Builds structured Portuguese-language prompts that instruct the LLM to
answer based exclusively on retrieved resume/job-posting context and
cite candidates by name and document section.
"""
from __future__ import annotations

from typing import List, Optional

from src.retrieval.query_engine import RetrievedChunk

_SYSTEM_PROMPT = """\
Você é um assistente especializado em recrutamento e seleção.
Sua função é analisar currículos, comparar candidatos com vagas, e fornecer
insights para decisões de contratação.

REGRAS OBRIGATÓRIAS:
1. Base suas respostas EXCLUSIVAMENTE nos dados dos currículos e vagas fornecidos abaixo e no histórico da conversa quando disponível. NUNCA invente informações.
2. Nunca invente experiências, habilidades, empresas ou datas que não estejam explicitamente nos trechos.
3. Ao afirmar algo sobre um candidato, cite o nome do candidato e a seção do currículo. Exemplo: "Conforme o currículo de Lucas Mendes, seção Experiência..."
4. Ao comparar candidatos, seja objetivo e use critérios mensuráveis presentes nos documentos.
5. Mantenha confidencialidade — nunca exponha CPF ou dados pessoais sensíveis na resposta.
6. Se a informação não estiver nos currículos ou vagas fornecidos, diga claramente: "Esta informação não foi encontrada nos documentos disponíveis."
7. Se a pergunta se refere ao histórico desta conversa (ex: "qual foi a pergunta anterior?", "o que você disse antes?"), responda com base no histórico da conversa acima.\
"""

_CONTEXT_TEMPLATE = """\
## TRECHOS DOS CURRÍCULOS / VAGAS

{chunks}

---

## PERGUNTA DO RECRUTADOR

{question}

---

## INSTRUÇÕES

Responda à pergunta acima usando as informações dos trechos fornecidos ou do histórico da conversa quando relevante.
- Para perguntas sobre candidatos: cite o nome completo e a seção do currículo (ex: "Na seção Experiência do currículo de Ana Beatriz...")
- Para comparações: use critérios objetivos como anos de experiência, habilidades listadas, formação
- Para perguntas sobre a conversa anterior: use o histórico da conversa acima
- Se houver habilidades ou tecnologias nos trechos, transcreva-as exatamente
- Se a informação não estiver nos trechos nem no histórico, informe que não foi encontrada
- Seja direto, objetivo e profissional na resposta\
"""


def build_prompt(
    question: str,
    chunks: List[RetrievedChunk],
    conversation_history: Optional[List[dict]] = None,
) -> str:
    """Assemble the final LLM prompt from a question, retrieved chunks, and optional prior context.

    Args:
        question: The recruiter's question about candidates or job postings (in Portuguese).
        chunks: Retrieved and reranked resume/job-posting chunks with metadata.
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
