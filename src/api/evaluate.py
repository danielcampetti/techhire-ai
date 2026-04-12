"""Evaluation endpoints — Claude as automated RAG quality judge.

POST /evaluate      — Grade a RAG response using 5 compliance criteria.
POST /test-pipeline — Run retrieval + Ollama generation + Claude evaluation in one call.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import List, Optional

import anthropic

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.config import settings
from src.llm import ollama_client
from src.retrieval.prompt_builder import build_prompt
from src.retrieval.query_engine import retrieve

router = APIRouter()

# ---------------------------------------------------------------------------
# Evaluation prompts
# ---------------------------------------------------------------------------

_EVAL_SYSTEM = """\
Você é um avaliador especialista em compliance regulatório financeiro brasileiro.
Avalie respostas de um sistema RAG sobre normativos do Banco Central do Brasil.
Seja rigoroso, preciso e justo."""

_EVAL_PROMPT = """\
## PERGUNTA
{pergunta}

## TRECHOS RECUPERADOS
{chunks}

## RESPOSTA GERADA
{resposta}

{esperada_section}
Avalie em 5 critérios (0-10 cada). JSON apenas, sem markdown:
{{
    "precisao_normativa": <0-10>,
    "completude": <0-10>,
    "relevancia_chunks": <0-10>,
    "coerencia": <0-10>,
    "alucinacao": <0-10>,
    "nota_geral": <média com 1 casa decimal>,
    "analise": "<parágrafo com pontos fortes e fracos>",
    "problemas_identificados": [],
    "sugestoes_melhoria": [],
    "veredicto": "<APROVADO se nota_geral >= 7.0, REPROVADO se < 7.0>"
}}"""


def _check_api_key() -> str:
    key = settings.anthropic_api_key
    if not key:
        raise HTTPException(
            status_code=503,
            detail="Sistema de avaliação indisponível. Configure a variável ANTHROPIC_API_KEY para usar este endpoint.",
        )
    return key


async def _grade(
    pergunta: str,
    resposta: str,
    chunks_text: list[str],
    resposta_esperada: Optional[str] = None,
) -> dict:
    """Call Claude to grade a RAG response. Returns parsed evaluation dict."""
    api_key = _check_api_key()

    chunks_block = "\n\n".join(
        f"[{i+1}] {text}" for i, text in enumerate(chunks_text)
    )

    if resposta_esperada:
        esperada_section = (
            f"## RESPOSTA ESPERADA\n{resposta_esperada}\n\n"
            "Compare a resposta gerada com a esperada. "
            "A resposta precisa conter as informações-chave da esperada para pontuar bem em Completude.\n\n"
        )
    else:
        esperada_section = ""

    prompt = _EVAL_PROMPT.format(
        pergunta=pergunta,
        chunks=chunks_block,
        resposta=resposta,
        esperada_section=esperada_section,
    )

    client = anthropic.AsyncAnthropic(api_key=api_key)
    response = await client.messages.create(
        model=settings.claude_model,
        max_tokens=1024,
        system=[{"type": "text", "text": _EVAL_SYSTEM, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"\s*```$", "", raw)

    try:
        return json.loads(raw.strip())
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            return json.loads(match.group())
        raise HTTPException(
            status_code=500,
            detail=f"Falha ao parsear avaliação do Claude: {raw[:200]}",
        )


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class EvaluateRequest(BaseModel):
    pergunta: str
    resposta_rag: str
    chunks_utilizados: List[str] = []  # raw text; re-fetches from ChromaDB if empty
    resposta_esperada: Optional[str] = None


class EvaluationScore(BaseModel):
    precisao_normativa: float
    completude: float
    relevancia_chunks: float
    coerencia: float
    alucinacao: float
    nota_geral: float
    analise: str
    problemas_identificados: List[str]
    sugestoes_melhoria: List[str]
    veredicto: str


class EvaluateResponse(BaseModel):
    pergunta: str
    avaliacao: EvaluationScore


class TestPipelineRequest(BaseModel):
    pergunta: str
    resposta_esperada: Optional[str] = None


class ChunkSummary(BaseModel):
    documento: str
    pagina: object
    texto_preview: str


class TestPipelineResponse(BaseModel):
    pergunta: str
    chunks_recuperados: List[ChunkSummary]
    resposta_ollama: str
    avaliacao: EvaluationScore
    tempo_resposta_segundos: float


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/evaluate",
    response_model=EvaluateResponse,
    summary="Avaliar resposta RAG com Claude como juiz",
)
async def evaluate(request: EvaluateRequest) -> EvaluateResponse:
    """Grade a RAG response using Claude with 5 compliance-specific criteria.

    Criteria: precisao_normativa, completude, relevancia_chunks, coerencia, alucinacao.
    Returns veredicto APROVADO (nota_geral >= 7.0) or REPROVADO.

    If chunks_utilizados is empty, re-fetches from ChromaDB using the pergunta.
    When resposta_esperada is provided, Claude uses it as reference for Completude.
    """
    _check_api_key()
    chunks_text = request.chunks_utilizados or [c.content for c in retrieve(request.pergunta)]
    scores = await _grade(
        request.pergunta, request.resposta_rag, chunks_text, request.resposta_esperada
    )
    return EvaluateResponse(pergunta=request.pergunta, avaliacao=EvaluationScore(**scores))


@router.post(
    "/test-pipeline",
    response_model=TestPipelineResponse,
    summary="Pipeline completo: RAG + Ollama + avaliação Claude",
)
async def test_pipeline(request: TestPipelineRequest) -> TestPipelineResponse:
    """Run retrieval, generate an Ollama response, then evaluate it with Claude.

    1. Retrieve top-K chunks.
    2. Generate a response using Ollama.
    3. Evaluate the response with Claude.
    4. Return everything with timing.
    """
    _check_api_key()

    chunks = retrieve(request.pergunta)
    if not chunks:
        raise HTTPException(
            status_code=404,
            detail="Nenhum chunk encontrado. Execute /ingest primeiro.",
        )

    t0 = time.monotonic()
    resposta = await ollama_client.generate(build_prompt(request.pergunta, chunks))
    elapsed = round(time.monotonic() - t0, 2)

    scores = await _grade(
        request.pergunta,
        resposta,
        [c.content for c in chunks],
        request.resposta_esperada,
    )

    return TestPipelineResponse(
        pergunta=request.pergunta,
        chunks_recuperados=[
            ChunkSummary(
                documento=Path(c.metadata.get("source", "desconhecido")).name,
                pagina=c.metadata.get("page", "?"),
                texto_preview=c.content[:200],
            )
            for c in chunks
        ],
        resposta_ollama=resposta,
        avaliacao=EvaluationScore(**scores),
        tempo_resposta_segundos=elapsed,
    )
