"""Match agent — translates natural language to SQL and interprets candidate match results."""
from __future__ import annotations

import re
import sqlite3

from src.agents.base import AgentResponse
from src.database.connection import get_db
from src.database.seed import init_db
from src.llm import llm_router

_MATCH_KEYWORDS = (
    "score", "scores",
    "ranking", "rankear", "rankeie", "rankeou",
    "aderência", "aderencia", "aderente",
    "comparar", "compare", "comparação", "comparacao",
    "melhor candidato", "melhores candidatos",
    "top", "top 5", "top 10",
    "match", "matches",
    "nota", "pontuação", "pontuacao",
    "classificação", "classificacao",
    "mais qualificado", "mais qualificados",
    "quantos candidatos", "quantas candidatas",
    "acima de", "abaixo de",
    "distribuição", "distribuicao",
    "vaga", "vagas",
    "recomendado", "recomendados",
    "pipeline", "funil",
    "etapa", "fase",
    "triagem", "entrevista", "aprovado", "rejeitado",
    "contratação", "contratacao",
)

_SCHEMA = """
Tabelas disponíveis:

candidates (id, full_name, email, phone, location, current_role,
            experience_years, education, skills, resume_filename, created_at)
  - skills: JSON array de strings com as habilidades do candidato

job_postings (id, title, company, description, requirements,
              desired_skills, seniority_level, work_model, salary_range, created_at)
  - seniority_level: 'junior', 'pleno', 'senior', 'specialist'
  - work_model: 'remote', 'hybrid', 'onsite'

matches (id, candidate_id, job_posting_id, overall_score, skills_score,
         experience_score, education_score, semantic_score, analysis, created_at)
  - overall_score: 0.0 a 1.0 (nota geral de aderência)
  - skills_score: 0.0 a 1.0 (match de habilidades)
  - experience_score: 0.0 a 1.0 (aderência de experiência)
  - education_score: 0.0 a 1.0 (aderência educacional)
  - semantic_score: 0.0 a 1.0 (similaridade vetorial do currículo)

pipeline (id, candidate_id, job_posting_id, stage, notes, updated_at)
  - stage: 'triagem', 'entrevista', 'teste_tecnico', 'aprovado', 'rejeitado'
"""

_SQL_GENERATION_PROMPT = """\
Você é um analista de recrutamento e seleção. Gere uma query SQL para o banco SQLite.

{schema}

Regras OBRIGATÓRIAS:
1. Gere APENAS queries SELECT (nunca DELETE, UPDATE, INSERT, DROP, CREATE).
2. Use aspas simples para strings.
3. Para datas, o formato é 'YYYY-MM-DD'.
4. Responda APENAS com a query SQL, sem nenhuma explicação, sem markdown, sem ```sql.
5. Para rankear candidatos, use ORDER BY overall_score DESC.

Pergunta: {question}
SQL:"""

_INTERPRETATION_PROMPT = """\
Você é um analista de recrutamento. Interprete os dados abaixo em linguagem natural, \
em português, de forma objetiva e profissional.

Pergunta original: {question}

Query SQL executada: {sql}

Resultado (até 20 primeiras linhas):
{results}

Forneça uma resposta clara e direta, citando nomes de candidatos e scores relevantes. \
Se o resultado estiver vazio, diga que nenhum registro foi encontrado.
"""

_SELECT_ONLY_RE = re.compile(r"^\s*SELECT\b", re.IGNORECASE)


class MatchAgent:
    """Agent specialized in querying and analyzing candidate match scores."""

    name = "match"

    def can_handle(self, question: str) -> float:
        """Return confidence score (0–1) for handling this question."""
        q = question.lower()
        hits = sum(1 for kw in _MATCH_KEYWORDS if kw in q)
        return min(hits * 0.2, 1.0)

    async def answer(
        self,
        question: str,
        extra_context: str = "",
        provider: str = "ollama",
    ) -> AgentResponse:
        """Query the recruitment database and interpret results.

        Args:
            question: Natural language question in Portuguese.
            extra_context: Optional resume context from the ResumeAgent.
            provider: LLM backend — "ollama" (default) or "claude".

        Returns:
            AgentResponse with SQL, results, and natural language interpretation.
        """
        init_db()

        sql_prompt = _SQL_GENERATION_PROMPT.format(
            schema=_SCHEMA,
            question=question + ("\n\nContexto adicional:\n" + extra_context if extra_context else ""),
        )
        raw_sql = await llm_router.generate(sql_prompt, provider=provider)
        sql = _extract_sql(raw_sql)

        if not _SELECT_ONLY_RE.match(sql):
            return AgentResponse(
                agent_name=self.name,
                answer="Não foi possível gerar uma consulta SQL segura para esta pergunta.",
                confidence=0.0,
            )

        try:
            rows, columns = _execute_sql(sql)
        except sqlite3.Error as exc:
            return AgentResponse(
                agent_name=self.name,
                answer=f"Erro ao executar consulta: {exc}",
                confidence=0.0,
            )

        results_text = _format_rows(rows, columns)
        interp_prompt = _INTERPRETATION_PROMPT.format(
            question=question, sql=sql, results=results_text
        )
        interpretation = await llm_router.generate(interp_prompt, provider=provider)

        return AgentResponse(
            agent_name=self.name,
            answer=interpretation,
            data={"sql": sql, "rows": [dict(zip(columns, r)) for r in rows[:20]], "total": len(rows)},
            confidence=0.85,
        )


def _extract_sql(raw: str) -> str:
    text = raw.strip()
    text = re.sub(r"^```(?:sql)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _execute_sql(sql: str) -> tuple[list[tuple], list[str]]:
    with get_db() as conn:
        cursor = conn.execute(sql)
        rows = cursor.fetchmany(100)
        columns = [d[0] for d in cursor.description] if cursor.description else []
    return rows, columns


def _format_rows(rows: list[tuple], columns: list[str]) -> str:
    if not rows:
        return "(nenhum resultado)"
    header = " | ".join(columns)
    lines = [header, "-" * len(header)]
    for row in rows[:20]:
        lines.append(" | ".join(str(v) for v in row))
    if len(rows) > 20:
        lines.append(f"... e mais {len(rows) - 20} linhas")
    return "\n".join(lines)
