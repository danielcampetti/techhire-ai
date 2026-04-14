"""Pipeline agent — manages recruitment pipeline stages and generates feedback."""
from __future__ import annotations

import re
from datetime import datetime

from src.agents.base import AgentResponse
from src.database.connection import get_db
from src.database.seed import init_db

_PIPELINE_KEYWORDS = (
    "mover", "mova", "move", "mude", "mudar",
    "etapa", "fase",
    "entrevista", "entrevistar",
    "aprovar", "approve", "aprovado",
    "rejeitar", "rejeite", "rejeitado", "reprovar",
    "feedback", "e-mail", "email",
    "funil", "pipeline",
    "avançar", "avance",
    "status do candidato", "atualizar candidato",
    "teste técnico", "teste tecnico",
    "contratar",
    "relatório do funil", "relatorio do funil",
    "quantos na", "quantos em",
)

_STAGES = ("triagem", "entrevista", "teste_tecnico", "aprovado", "rejeitado")


class PipelineAgent:
    """Agent specialized in managing the recruitment pipeline."""

    name = "pipeline"

    def can_handle(self, question: str) -> float:
        """Return confidence score (0–1) for handling this question."""
        q = question.lower()
        hits = sum(1 for kw in _PIPELINE_KEYWORDS if kw in q)
        return min(hits * 0.5, 1.0)

    async def answer(self, question: str) -> AgentResponse:
        """Dispatch to the appropriate pipeline action.

        Args:
            question: Natural language question in Portuguese.

        Returns:
            AgentResponse with the action result.
        """
        init_db()
        q = question.lower()

        if any(w in q for w in ("funil", "relatorio do funil", "relatório do funil")):
            return await self._report_funnel()

        if "feedback" in q or ("e-mail" in q or "email" in q):
            return await self._generate_feedback_email(question)

        if any(w in q for w in ("rejeitar", "rejeite", "rejeitado", "reprovar")):
            return await self._reject_candidate(question)

        if any(w in q for w in ("aprovar", "aprovado", "contratar")):
            return await self._move_stage(question, "aprovado")

        if "teste técnico" in q or "teste tecnico" in q:
            return await self._move_stage(question, "teste_tecnico")

        if "entrevista" in q:
            return await self._move_stage(question, "entrevista")

        if any(w in q for w in ("mover", "mova", "move", "mude", "avançar", "avance")):
            return await self._move_stage(question, None)

        return AgentResponse(
            agent_name=self.name,
            answer=(
                "Ação não reconhecida. Ações suportadas: mover candidato de etapa, "
                "rejeitar candidato, gerar relatório do funil, gerar e-mail de feedback."
            ),
            confidence=0.0,
        )

    async def _report_funnel(self) -> AgentResponse:
        """Report current recruitment funnel counts by stage."""
        with get_db() as conn:
            rows = conn.execute(
                """SELECT p.stage, COUNT(*) as total
                   FROM pipeline p
                   GROUP BY p.stage
                   ORDER BY CASE p.stage
                     WHEN 'triagem' THEN 1
                     WHEN 'entrevista' THEN 2
                     WHEN 'teste_tecnico' THEN 3
                     WHEN 'aprovado' THEN 4
                     WHEN 'rejeitado' THEN 5
                     ELSE 6 END"""
            ).fetchall()

        if not rows:
            summary = "Nenhum candidato no pipeline ainda."
        else:
            total = sum(r["total"] for r in rows)
            lines = [f"Funil de contratação — {total} candidatos no total:\n"]
            stage_labels = {
                "triagem": "Triagem",
                "entrevista": "Entrevista",
                "teste_tecnico": "Teste Técnico",
                "aprovado": "Aprovado",
                "rejeitado": "Rejeitado",
            }
            for r in rows:
                label = stage_labels.get(r["stage"], r["stage"])
                lines.append(f"  • {label}: {r['total']} candidato(s)")
            summary = "\n".join(lines)

        data = {stage: 0 for stage in _STAGES}
        for r in rows:
            if r["stage"] in data:
                data[r["stage"]] = r["total"]

        return AgentResponse(
            agent_name=self.name,
            answer=summary,
            actions_taken=["Gerou relatório do funil de contratação"],
            data=data,
            confidence=1.0,
        )

    async def _move_stage(self, question: str, target_stage: str | None) -> AgentResponse:
        """Move a candidate to a new pipeline stage."""
        cand_match = re.search(
            r"candidato\s+(?:id\s+)?#?(\d+)|candidata\s+(?:id\s+)?#?(\d+)",
            question, re.IGNORECASE
        )
        if not cand_match:
            return AgentResponse(
                agent_name=self.name,
                answer="Informe o ID do candidato. Exemplo: 'Mova o candidato #3 para entrevista'.",
                confidence=0.0,
            )

        cand_id = int(cand_match.group(1) or cand_match.group(2))

        if target_stage is None:
            stage_match = re.search(
                r"(triagem|entrevista|teste.tecnico|aprovado|rejeitado)",
                question, re.IGNORECASE
            )
            if not stage_match:
                return AgentResponse(
                    agent_name=self.name,
                    answer=f"Informe a etapa desejada: {', '.join(_STAGES)}.",
                    confidence=0.0,
                )
            target_stage = stage_match.group(1).lower().replace(" ", "_")

        now = datetime.utcnow().isoformat()
        with get_db() as conn:
            existing = conn.execute(
                "SELECT id FROM pipeline WHERE candidate_id=?", (cand_id,)
            ).fetchone()

            if existing:
                conn.execute(
                    "UPDATE pipeline SET stage=?, updated_at=? WHERE candidate_id=?",
                    (target_stage, now, cand_id),
                )
            else:
                conn.execute(
                    "INSERT INTO pipeline (candidate_id, job_posting_id, stage, updated_at) "
                    "VALUES (?,1,?,?)",
                    (cand_id, target_stage, now),
                )

            cand_name = conn.execute(
                "SELECT full_name FROM candidates WHERE id=?", (cand_id,)
            ).fetchone()

        name = cand_name["full_name"] if cand_name else f"#{cand_id}"
        return AgentResponse(
            agent_name=self.name,
            answer=f"Candidato {name} movido para a etapa '{target_stage}' com sucesso.",
            actions_taken=[f"Moveu {name} → {target_stage}"],
            data={"candidate_id": cand_id, "new_stage": target_stage},
            confidence=1.0,
        )

    async def _reject_candidate(self, question: str) -> AgentResponse:
        """Move a candidate to 'rejeitado' stage."""
        return await self._move_stage(question, "rejeitado")

    async def _generate_feedback_email(self, question: str) -> AgentResponse:
        """Generate a personalized feedback email for a candidate."""
        cand_match = re.search(
            r"candidato\s+(?:id\s+)?#?(\d+)|candidata\s+(?:id\s+)?#?(\d+)",
            question, re.IGNORECASE
        )
        if not cand_match:
            return AgentResponse(
                agent_name=self.name,
                answer="Informe o ID do candidato. Exemplo: 'Gere e-mail de feedback para o candidato #2'.",
                confidence=0.0,
            )

        cand_id = int(cand_match.group(1) or cand_match.group(2))

        with get_db() as conn:
            cand = conn.execute(
                "SELECT full_name, email, current_role, skills FROM candidates WHERE id=?",
                (cand_id,)
            ).fetchone()
            pipeline_row = conn.execute(
                "SELECT stage FROM pipeline WHERE candidate_id=?", (cand_id,)
            ).fetchone()

        if not cand:
            return AgentResponse(
                agent_name=self.name,
                answer=f"Candidato #{cand_id} não encontrado.",
                confidence=0.0,
            )

        stage = pipeline_row["stage"] if pipeline_row else "triagem"
        is_approved = stage == "aprovado"

        if is_approved:
            subject = "Parabéns — Aprovação no Processo Seletivo"
            body = (
                f"Prezado(a) {cand['full_name']},\n\n"
                f"Temos o prazer de informar que você foi aprovado(a) no nosso processo seletivo "
                f"e gostaríamos de fazer uma proposta formal.\n\n"
                f"Em breve, nossa equipe entrará em contato para discutir os detalhes da oferta.\n\n"
                f"Parabéns pela sua trajetória como {cand['current_role']}.\n\n"
                f"Atenciosamente,\nEquipe de Recrutamento — TechHire Corp"
            )
        else:
            subject = "Retorno sobre o Processo Seletivo"
            body = (
                f"Prezado(a) {cand['full_name']},\n\n"
                f"Agradecemos pelo seu interesse e pela participação no nosso processo seletivo.\n\n"
                f"Após análise cuidadosa do seu perfil como {cand['current_role']}, "
                f"informamos que não daremos continuidade à sua candidatura neste momento.\n\n"
                f"Seu currículo permanecerá em nosso banco de talentos para oportunidades futuras.\n\n"
                f"Desejamos sucesso na sua carreira.\n\n"
                f"Atenciosamente,\nEquipe de Recrutamento — TechHire Corp"
            )

        email_text = f"Para: {cand['email']}\nAssunto: {subject}\n\n{body}"

        return AgentResponse(
            agent_name=self.name,
            answer=f"E-mail de feedback gerado para {cand['full_name']}:\n\n{email_text}",
            actions_taken=[f"Gerou e-mail de feedback para {cand['full_name']}"],
            data={"candidate_id": cand_id, "email": cand["email"], "stage": stage},
            confidence=1.0,
        )
