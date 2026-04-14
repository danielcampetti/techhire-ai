"""Coordinator agent — classifies intent and routes to specialized agents."""
from __future__ import annotations

import json
import unicodedata
from datetime import datetime
from typing import AsyncGenerator, Optional

from pydantic import BaseModel

from src.agents.base import AgentResponse
from src.agents.match_agent import MatchAgent
from src.agents.pipeline_agent import PipelineAgent
from src.agents.resume_agent import ResumeAgent
from src.database.connection import get_db
from src.database.seed import init_db
from src.governance import audit
from src.governance.pii_detector import detect_pii, has_pii
from src.llm import llm_router

_LGPD_FOOTER = (
    "\n\n---\n🔒 Esta resposta contém dados pessoais protegidos pela LGPD. "
    "Uso restrito a fins de recrutamento autorizado."
)


class CoordinatorResponse(BaseModel):
    """Full response from the coordinator including routing metadata."""

    pergunta: str
    roteamento: str
    agentes_utilizados: list[str]
    resposta_final: str
    detalhes_agentes: list[dict]
    log_id: int
    provider_utilizado: str
    pii_detected: bool = False
    data_classification: str = "public"
    session_id: str = ""


class CoordinatorAgent:
    """Routes questions to the appropriate specialized agent(s)."""

    def __init__(self) -> None:
        self.resume_agent = ResumeAgent()
        self.match_agent = MatchAgent()
        self.pipeline_agent = PipelineAgent()

    async def process(
        self,
        question: str,
        provider: str = "ollama",
        user_id: Optional[int] = None,
        username: Optional[str] = None,
        conversation_history: Optional[list[dict]] = None,
    ) -> CoordinatorResponse:
        """Classify and route a question to the appropriate agent(s).

        Args:
            question: Natural language question in Portuguese.
            provider: LLM backend — "ollama" (default) or "claude".
            user_id: Authenticated user ID for audit logging.
            username: Authenticated username for audit logging.
            conversation_history: Prior conversation messages for context.

        Returns:
            CoordinatorResponse with the final answer and routing metadata.
        """
        init_db()
        session_id = audit.generate_session_id()
        routing = await self._classify(question)
        details: list[dict] = []
        agents_used: list[str] = []
        model = "claude-sonnet-4-6" if provider == "claude" else "llama3:8b"

        if routing == "RESUME":
            response = await self.resume_agent.answer(
                question, provider=provider,
                conversation_history=conversation_history,
            )
            details.append(_to_detail(response))
            agents_used.append("resume")
            final = response.answer

            pii_found = bool(detect_pii(response.answer)) or has_pii(question)
            log_id = await audit.log_interaction(
                session_id=session_id, agent_name="resume", action="answer",
                input_text=question, output_text=response.answer,
                provider=provider, model=model, tokens_used=0,
                chunks_count=getattr(response, "chunks_count", 0),
                user_id=user_id, username=username,
            )
            classification = audit.classify_query("knowledge", pii_found, question)

        elif routing == "MATCH":
            response = await self.match_agent.answer(question, provider=provider)
            details.append(_to_detail(response))
            agents_used.append("match")
            final = response.answer

            pii_found = bool(detect_pii(response.answer)) or has_pii(question)
            if pii_found:
                final = final + _LGPD_FOOTER

            log_id = await audit.log_interaction(
                session_id=session_id, agent_name="match", action="answer",
                input_text=question, output_text=response.answer,
                provider=provider, model=model, tokens_used=0,
                chunks_count=getattr(response, "chunks_count", 0),
                user_id=user_id, username=username,
            )
            classification = audit.classify_query("data", pii_found, question)

        elif routing == "PIPELINE":
            response = await self.pipeline_agent.answer(question)
            details.append(_to_detail(response))
            agents_used.append("pipeline")
            final = response.answer

            pii_found = bool(detect_pii(response.answer)) or has_pii(question)
            log_id = await audit.log_interaction(
                session_id=session_id, agent_name="pipeline", action="answer",
                input_text=question, output_text=response.answer,
                provider=provider, model=model, tokens_used=0,
                chunks_count=getattr(response, "chunks_count", 0),
                user_id=user_id, username=username,
            )
            classification = audit.classify_query("action", pii_found, question)

        else:  # RESUME+MATCH
            r_resp = await self.resume_agent.answer(
                question, provider=provider,
                conversation_history=conversation_history,
            )
            m_resp = await self.match_agent.answer(
                question, extra_context=r_resp.answer, provider=provider
            )
            details.extend([_to_detail(r_resp), _to_detail(m_resp)])
            agents_used.extend(["resume", "match"])
            final = (
                f"**Análise de Currículos:**\n{r_resp.answer}\n\n"
                f"**Análise de Scores:**\n{m_resp.answer}"
            )

            pii_found = bool(detect_pii(final)) or has_pii(question)
            if pii_found:
                final = final + _LGPD_FOOTER

            await audit.log_interaction(
                session_id=session_id, agent_name="resume", action="answer",
                input_text=question, output_text=r_resp.answer,
                provider=provider, model=model, tokens_used=0,
                chunks_count=getattr(r_resp, "chunks_count", 0),
                user_id=user_id, username=username,
            )
            log_id = await audit.log_interaction(
                session_id=session_id, agent_name="match", action="answer",
                input_text=question, output_text=m_resp.answer,
                provider=provider, model=model, tokens_used=0,
                chunks_count=getattr(m_resp, "chunks_count", 0),
                user_id=user_id, username=username,
            )
            r_class = audit.classify_query("knowledge", pii_found, question)
            m_class = audit.classify_query("data", pii_found, question)
            _order = ["public", "internal", "confidential", "restricted"]
            classification = (
                r_class if _order.index(r_class) >= _order.index(m_class) else m_class
            )

        return CoordinatorResponse(
            pergunta=question,
            roteamento=routing,
            agentes_utilizados=agents_used,
            resposta_final=final,
            detalhes_agentes=details,
            log_id=log_id,
            provider_utilizado=provider,
            pii_detected=pii_found,
            data_classification=classification,
            session_id=session_id,
        )

    async def process_stream(
        self,
        question: str,
        provider: str = "ollama",
        user_id: Optional[int] = None,
        username: Optional[str] = None,
        conversation_history: Optional[list[dict]] = None,
    ) -> AsyncGenerator[str, None]:
        """Stream the agent response as SSE events.

        Yields SSE-formatted strings for each event:
        - metadata: routing info, sent first
        - sources: chunk references (RESUME routes only)
        - token: individual LLM tokens (RESUME streams one-by-one;
                 MATCH/PIPELINE send a single token with the full answer)
        - sql: SQL details (MATCH agent only)
        - actions: action list (PIPELINE agent only)
        - done: final metadata including full_response for persistence
        - error: on exception

        Args:
            question: Natural language question in Portuguese.
            provider: LLM backend — "ollama" (default) or "claude".
            user_id: Authenticated user ID for audit logging.
            username: Authenticated username for audit logging.
            conversation_history: Prior conversation messages for context injection.
        """
        init_db()
        session_id = audit.generate_session_id()
        routing = await self._classify(question)
        model = "claude-sonnet-4-6" if provider == "claude" else "llama3:8b"

        _route_agents = {
            "RESUME": ["resume"],
            "MATCH": ["match"],
            "PIPELINE": ["pipeline"],
            "RESUME+MATCH": ["resume", "match"],
        }
        agents_used = _route_agents.get(routing, ["resume"])

        yield f'data: {json.dumps({"type": "metadata", "roteamento": routing, "agentes_utilizados": agents_used})}\n\n'

        try:
            if routing == "RESUME":
                prompt, chunks = await self.resume_agent.prepare(
                    question, conversation_history=conversation_history
                )

                if prompt is None:
                    msg = "Nenhum currículo relevante encontrado para esta pergunta."
                    yield f'data: {json.dumps({"type": "token", "content": msg})}\n\n'
                    yield f'data: {json.dumps({"type": "done", "pii_detected": False, "data_classification": "public", "session_id": session_id, "full_response": msg})}\n\n'
                    return

                sources = list({
                    f"{c.metadata.get('source', 'Desconhecido')}, p. {c.metadata.get('page', '?')}"
                    for c in chunks
                })
                yield f'data: {json.dumps({"type": "sources", "chunks": sources})}\n\n'

                full_response = ""
                async for token in llm_router.generate_stream(prompt, provider=provider):
                    full_response += token
                    yield f'data: {json.dumps({"type": "token", "content": token})}\n\n'

                pii_found = bool(detect_pii(full_response)) or has_pii(question)
                await audit.log_interaction(
                    session_id=session_id, agent_name="resume",
                    action="stream_answer", input_text=question,
                    output_text=full_response, provider=provider, model=model,
                    tokens_used=0, chunks_count=len(chunks),
                    user_id=user_id, username=username,
                )
                classification = audit.classify_query("knowledge", pii_found, question)
                yield f'data: {json.dumps({"type": "done", "pii_detected": pii_found, "data_classification": classification, "session_id": session_id, "full_response": full_response})}\n\n'

            elif routing == "MATCH":
                response = await self.match_agent.answer(question, provider=provider)
                yield f'data: {json.dumps({"type": "token", "content": response.answer})}\n\n'

                if response.data and response.data.get("sql"):
                    yield f'data: {json.dumps({"type": "sql", "sql": response.data.get("sql"), "total": response.data.get("total")})}\n\n'

                pii_found = bool(detect_pii(response.answer)) or has_pii(question)
                await audit.log_interaction(
                    session_id=session_id, agent_name="match",
                    action="stream_answer", input_text=question,
                    output_text=response.answer, provider=provider, model=model,
                    tokens_used=0, chunks_count=0,
                    user_id=user_id, username=username,
                )
                classification = audit.classify_query("data", pii_found, question)
                yield f'data: {json.dumps({"type": "done", "pii_detected": pii_found, "data_classification": classification, "session_id": session_id, "full_response": response.answer})}\n\n'

            elif routing == "PIPELINE":
                response = await self.pipeline_agent.answer(question)
                yield f'data: {json.dumps({"type": "token", "content": response.answer})}\n\n'

                if response.actions_taken:
                    yield f'data: {json.dumps({"type": "actions", "acoes": response.actions_taken})}\n\n'

                pii_found = bool(detect_pii(response.answer)) or has_pii(question)
                await audit.log_interaction(
                    session_id=session_id, agent_name="pipeline",
                    action="stream_answer", input_text=question,
                    output_text=response.answer, provider=provider, model=model,
                    tokens_used=0, chunks_count=0,
                    user_id=user_id, username=username,
                )
                classification = audit.classify_query("action", pii_found, question)
                yield f'data: {json.dumps({"type": "done", "pii_detected": pii_found, "data_classification": classification, "session_id": session_id, "full_response": response.answer})}\n\n'

            else:  # RESUME+MATCH
                prompt, chunks = await self.resume_agent.prepare(
                    question, conversation_history=conversation_history
                )
                sources = list({
                    f"{c.metadata.get('source', 'Desconhecido')}, p. {c.metadata.get('page', '?')}"
                    for c in (chunks or [])
                })
                if sources:
                    yield f'data: {json.dumps({"type": "sources", "chunks": sources})}\n\n'

                _header_resume = "**Análise de Currículos:**\n"
                yield f'data: {json.dumps({"type": "token", "content": _header_resume})}\n\n'

                full_resume = ""
                if prompt:
                    async for token in llm_router.generate_stream(prompt, provider=provider):
                        full_resume += token
                        yield f'data: {json.dumps({"type": "token", "content": token})}\n\n'

                _header_match = "\n\n**Análise de Scores:**\n"
                yield f'data: {json.dumps({"type": "token", "content": _header_match})}\n\n'

                m_resp = await self.match_agent.answer(
                    question, extra_context=full_resume, provider=provider
                )
                yield f'data: {json.dumps({"type": "token", "content": m_resp.answer})}\n\n'

                if m_resp.data and m_resp.data.get("sql"):
                    yield f'data: {json.dumps({"type": "sql", "sql": m_resp.data.get("sql"), "total": m_resp.data.get("total")})}\n\n'

                full_response = (
                    f"**Análise de Currículos:**\n{full_resume}\n\n"
                    f"**Análise de Scores:**\n{m_resp.answer}"
                )
                pii_found = bool(detect_pii(full_response)) or has_pii(question)

                await audit.log_interaction(
                    session_id=session_id, agent_name="resume",
                    action="stream_answer", input_text=question,
                    output_text=full_resume, provider=provider, model=model,
                    tokens_used=0, chunks_count=len(chunks or []),
                    user_id=user_id, username=username,
                )
                await audit.log_interaction(
                    session_id=session_id, agent_name="match",
                    action="stream_answer", input_text=question,
                    output_text=m_resp.answer, provider=provider, model=model,
                    tokens_used=0, chunks_count=0,
                    user_id=user_id, username=username,
                )
                r_class = audit.classify_query("knowledge", pii_found, question)
                m_class = audit.classify_query("data", pii_found, question)
                _order = ["public", "internal", "confidential", "restricted"]
                classification = r_class if _order.index(r_class) >= _order.index(m_class) else m_class

                yield f'data: {json.dumps({"type": "done", "pii_detected": pii_found, "data_classification": classification, "session_id": session_id, "full_response": full_response})}\n\n'

        except Exception as exc:
            yield f'data: {json.dumps({"type": "error", "message": str(exc)})}\n\n'

    async def _classify(self, question: str) -> str:
        # Short-circuit: conversational/meta questions always go to RESUME
        if _is_conversational(question):
            return "RESUME"

        # Keyword classifier — covers 95%+ of queries with no LLM call
        return _heuristic_route(question)

    def _log(self, question: str, routing: str, answer: str) -> int:
        now = datetime.utcnow().isoformat()
        with get_db() as conn:
            conn.execute(
                "INSERT INTO audit_log (session_id, timestamp, agent_name, action, "
                "input_masked, output_masked, data_classification, provider, model, "
                "tokens_used, chunks_count, retention_expires_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (audit.generate_session_id(), now, "coordinator",
                 f"route:{routing}", question[:500], answer[:500],
                 "public", "system", "system", 0, 0,
                 audit.get_retention_expiry("public")),
            )
            return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def _is_conversational(question: str) -> bool:
    """Return True for meta/conversational questions that refer to the conversation itself.

    These must route to RESUME regardless of keyword classification, because only
    ResumeAgent receives the conversation_history injected into build_prompt().
    Input is accent-normalized before matching so users can omit diacritics.
    """
    q = unicodedata.normalize("NFD", question.lower())
    q = "".join(c for c in q if unicodedata.category(c) != "Mn")

    patterns = (
        "pergunta anterior", "pergunta passada",
        "o que voce disse", "o que foi dito", "voce disse antes",
        "explique melhor", "pode explicar melhor", "mais detalhes sobre isso",
        "resuma nossa conversa", "resuma o que discutimos", "resuma a conversa",
        "o que discutimos", "nossa conversa",
        "me lembra", "pode repetir", "repita o que",
        "contexto da conversa", "historico da conversa",
        "qual foi a ultima", "qual foi o ultimo",
        "como assim", "nao entendi", "elabore mais",
    )
    return any(p in q for p in patterns)


def _heuristic_route(question: str) -> str:
    """Route by keyword matching. Accent-insensitive, case-insensitive.

    Priority: PIPELINE > RESUME+MATCH > MATCH > RESUME (default).
    """
    q = unicodedata.normalize("NFD", question.lower())
    q = "".join(c for c in q if unicodedata.category(c) != "Mn")

    pipeline_kws = (
        "mover", "mova", "mude", "avance", "avançar",
        "rejeitar", "rejeite", "rejeitado",
        "aprovar", "aprove", "aprovado", "contratar",
        "funil", "relatorio do funil",
        "gere email", "gere e-mail", "gerar feedback",
        "etapa", "fase do pipeline",
        "teste tecnico",
        "mover candidato", "mova o candidato",
    )
    match_kws = (
        "score", "scores",
        "ranking", "rankear", "rankeie",
        "aderencia", "aderente",
        "comparar", "compare",
        "melhor candidato", "melhores candidatos",
        "top 5", "top 10",
        "match", "matches",
        "nota", "pontuacao",
        "mais qualificado", "mais qualificados",
        "quantos candidatos", "quantas candidatas",
        "acima de", "abaixo de",
        "distribuicao de scores",
        "vaga de", "candidatos para a vaga",
    )
    resume_kws = (
        "candidato", "candidata", "candidatos", "candidatas",
        "curriculo", "curriculos",
        "perfil", "perfis",
        "experiencia", "experiencias",
        "formacao", "formacoes",
        "habilidades", "skills", "competencias",
        "historico profissional",
        "educacao",
        "certificacao", "certificacoes",
        "trabalhou", "trabalha", "atuou",
    )

    is_pipeline = any(kw in q for kw in pipeline_kws)
    is_match = any(kw in q for kw in match_kws)
    is_resume = any(kw in q for kw in resume_kws)

    if is_pipeline:
        return "PIPELINE"
    if is_resume and is_match:
        return "RESUME+MATCH"
    if is_match:
        return "MATCH"
    return "RESUME"


def _to_detail(r: AgentResponse) -> dict:
    return {
        "agente": r.agent_name,
        "resposta": r.answer,
        "fontes": r.sources,
        "dados": r.data,
        "acoes": r.actions_taken,
    }
