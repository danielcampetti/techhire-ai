"""Benchmark runner — batch RAG quality evaluation across 15 compliance questions.

Usage:
    python -m src.evaluation.benchmark                          # ollama (default)
    python -m src.evaluation.benchmark --provider claude
    python -m src.evaluation.benchmark --compare
    python -m src.evaluation.benchmark --limit 3
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import time
from datetime import datetime
from pathlib import Path

import anthropic

from src.config import settings
from src.llm import llm_router
from src.retrieval.prompt_builder import build_prompt
from src.retrieval.query_engine import retrieve

_DATASET = Path(__file__).parent / "test_dataset.json"
_REPORT_DIR = Path("data")

# Claude Sonnet pricing (per million tokens) — update if pricing changes
_CLAUDE_INPUT_PRICE_PER_MTOK = 3.0
_CLAUDE_OUTPUT_PRICE_PER_MTOK = 15.0

_SYS = """\
Você é um avaliador especialista em compliance regulatório financeiro brasileiro.
Avalie respostas de um sistema RAG sobre normativos do Banco Central do Brasil.
Seja rigoroso, preciso e justo."""

_PROMPT = """\
## PERGUNTA
{pergunta}

## TRECHOS RECUPERADOS
{chunks}

## RESPOSTA GERADA
{resposta}

## RESPOSTA ESPERADA (referência)
{esperada}

Compare a resposta gerada com a esperada. Avalie em 5 critérios (0-10 cada).
JSON apenas, sem markdown:
{{"precisao_normativa":<0-10>,"completude":<0-10>,"relevancia_chunks":<0-10>,"coerencia":<0-10>,"alucinacao":<0-10>,"nota_geral":<média com 1 casa>,"analise":"<breve parágrafo>","problemas_identificados":[],"sugestoes_melhoria":[],"veredicto":"<APROVADO se >= 7.0, REPROVADO se < 7.0>"}}"""


async def _evaluate_one(
    pergunta: str,
    resposta: str,
    chunks_text: list[str],
    resposta_esperada: str,
    api_key: str,
) -> dict:
    prompt = _PROMPT.format(
        pergunta=pergunta,
        chunks="\n\n".join(f"[{i+1}] {t}" for i, t in enumerate(chunks_text)),
        resposta=resposta,
        esperada=resposta_esperada,
    )
    client = anthropic.AsyncAnthropic(api_key=api_key)
    response = await client.messages.create(
        model=settings.claude_model,
        max_tokens=1024,
        system=[{"type": "text", "text": _SYS, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.content[0].text.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"\s*```$", "", raw)
    try:
        return json.loads(raw.strip())
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        return json.loads(m.group()) if m else {
            "nota_geral": 0.0, "veredicto": "ERRO", "analise": raw[:200],
            "precisao_normativa": 0.0, "completude": 0.0,
            "relevancia_chunks": 0.0, "coerencia": 0.0, "alucinacao": 0.0,
            "problemas_identificados": [], "sugestoes_melhoria": [],
        }


async def run_benchmark(provider: str = "ollama", limit: int | None = None) -> dict:
    """Run the benchmark for a given provider and return the full results dict.

    Args:
        provider: "ollama" or "claude".
        limit: Cap the number of questions (useful for quick tests).

    Returns:
        Report dict with results, averages, and cost info.
        Empty dict if API key missing.
    """
    api_key = settings.anthropic_api_key
    if not api_key:
        print("ERRO: ANTHROPIC_API_KEY não configurado. Benchmark requer acesso ao Claude para avaliação.")
        return {}

    dataset = json.loads(_DATASET.read_text(encoding="utf-8"))
    if limit:
        dataset = dataset[:limit]

    total = len(dataset)
    results: list[dict] = []
    t_start = time.monotonic()
    gen_input_tokens = 0
    gen_output_tokens = 0

    provider_label = f"claude ({settings.claude_model})" if provider == "claude" else f"ollama ({settings.ollama_model})"
    print(f"\n  Iniciando benchmark: {total} questões | provider: {provider_label}\n")

    for item in dataset:
        qid      = item["id"]
        pergunta = item["pergunta"]
        esperada = item["resposta_esperada"]
        categoria = item.get("categoria", "geral")

        try:
            chunks = retrieve(pergunta)
            if not chunks:
                raise RuntimeError("Nenhum chunk recuperado — execute /ingest primeiro")
            prompt = build_prompt(pergunta, chunks)

            if provider == "claude":
                # Use Anthropic client directly to capture token usage for cost tracking
                from src.llm.claude_client import _get_client as _get_claude
                split_marker = "CONTEXTO REGULATÓRIO:"
                if split_marker in prompt:
                    sys_part, usr_part = prompt.split(split_marker, 1)
                    sys_content = sys_part.strip()
                    usr_content = f"{split_marker}{usr_part}"
                else:
                    sys_content = ""
                    usr_content = prompt

                kwargs: dict = {
                    "model": settings.claude_model,
                    "max_tokens": 1024,
                    "messages": [{"role": "user", "content": usr_content}],
                }
                if sys_content:
                    kwargs["system"] = [{"type": "text", "text": sys_content, "cache_control": {"type": "ephemeral"}}]

                claude = _get_claude()
                gen_response = await claude.messages.create(**kwargs)
                resposta = gen_response.content[0].text
                gen_input_tokens  += gen_response.usage.input_tokens
                gen_output_tokens += gen_response.usage.output_tokens
            else:
                resposta = await llm_router.generate(prompt, provider="ollama")

            scores = await _evaluate_one(
                pergunta, resposta, [c.content for c in chunks], esperada, api_key
            )
        except Exception as exc:
            print(f"  ✗ #{qid} ERRO: {exc}")
            results.append({
                "id": qid, "categoria": categoria, "pergunta": pergunta,
                "nota_geral": 0.0, "veredicto": "ERRO", "scores": {}, "elapsed": 0.0,
            })
            continue

        nota      = float(scores.get("nota_geral", 0.0))
        veredicto = scores.get("veredicto", "REPROVADO")
        symbol    = "✓" if veredicto == "APROVADO" else "✗"
        print(f"  {symbol} #{qid:<2} [{categoria[:4]}] nota={nota:.1f}")

        results.append({
            "id": qid, "categoria": categoria, "pergunta": pergunta,
            "nota_geral": nota, "veredicto": veredicto, "scores": scores, "elapsed": 0.0,
        })

    total_time = round(time.monotonic() - t_start, 1)

    valid  = [r for r in results if r["veredicto"] != "ERRO"]
    passed = [r for r in valid if r["veredicto"] == "APROVADO"]
    failed = [r for r in valid if r["veredicto"] == "REPROVADO"]

    criteria = ["precisao_normativa", "completude", "relevancia_chunks", "coerencia", "alucinacao"]
    avgs: dict[str, float] = {}
    for c in criteria:
        vals = [float(r["scores"].get(c, 0.0)) for r in valid if r.get("scores")]
        avgs[c] = round(sum(vals) / len(vals), 1) if vals else 0.0

    avg_geral = round(sum(r["nota_geral"] for r in valid) / max(len(valid), 1), 1)

    generation_cost_usd = 0.0
    if provider == "claude":
        generation_cost_usd = round(
            (gen_input_tokens / 1_000_000) * _CLAUDE_INPUT_PRICE_PER_MTOK
            + (gen_output_tokens / 1_000_000) * _CLAUDE_OUTPUT_PRICE_PER_MTOK,
            4,
        )

    return {
        "date": datetime.now().isoformat(),
        "provider": provider,
        "model": settings.claude_model if provider == "claude" else settings.ollama_model,
        "total_questions": total,
        "passed": len(passed),
        "failed": len(failed),
        "avg_scores": avgs,
        "avg_geral": avg_geral,
        "total_time_seconds": total_time,
        "generation_tokens": {"input": gen_input_tokens, "output": gen_output_tokens} if provider == "claude" else {},
        "generation_cost_usd": generation_cost_usd,
        "results": results,
    }


def print_single_report(report: dict) -> None:
    """Print a single-provider benchmark report to stdout."""
    total      = report["total_questions"]
    passed_n   = report["passed"]
    avgs       = report["avg_scores"]
    avg_geral  = report["avg_geral"]
    total_time = report["total_time_seconds"]
    provider   = report.get("provider", "ollama")
    model      = report.get("model", "?")
    results    = report.get("results", [])

    valid  = [r for r in results if r["veredicto"] != "ERRO"]
    failed = [r for r in valid if r["veredicto"] == "REPROVADO"]
    by_cat: dict[str, list] = {}
    for r in valid:
        by_cat.setdefault(r["categoria"], []).append(r)

    W = 57
    print(f"\n{'═'*W}")
    print("  ComplianceAgent — Benchmark Report")
    print(f"  Data: {datetime.now().strftime('%Y-%m-%d')} | Provider: {provider} | Modelo: {model} | Questões: {total}")
    print(f"{'═'*W}\n")
    print(f"  Resultados:  {passed_n}/{total} APROVADOS ({round(passed_n/max(total,1)*100)}%)\n")

    labels = {
        "precisao_normativa": "Precisão Normativa ",
        "completude":         "Completude         ",
        "relevancia_chunks":  "Relevância Chunks  ",
        "coerencia":          "Coerência          ",
        "alucinacao":         "Alucinação         ",
    }
    print("  ┌─────────────────────┬───────┐")
    print("  │ Critério            │ Média │")
    print("  ├─────────────────────┼───────┤")
    for c, label in labels.items():
        print(f"  │ {label}│ {avgs.get(c, 0.0):<5.1f} │")
    print("  ├─────────────────────┼───────┤")
    print(f"  │ MÉDIA GERAL         │ {avg_geral:<5.1f} │")
    print("  └─────────────────────┴───────┘\n")

    if by_cat:
        print("  Por Categoria:")
        for cat, items in sorted(by_cat.items()):
            cat_avg  = round(sum(r["nota_geral"] for r in items) / len(items), 1)
            cat_pass = sum(1 for r in items if r["veredicto"] == "APROVADO")
            print(f"  - {cat:<32} {cat_avg} avg ({cat_pass}/{len(items)} aprovados)")

    if failed:
        print(f"\n  Reprovados:")
        for r in sorted(failed, key=lambda x: x["nota_geral"]):
            preview = r["pergunta"][:55] + "..."
            print(f"  ✗ #{r['id']:<2} \"{preview}\" — {r['nota_geral']:.1f}")

    avg_time = round(total_time / max(total, 1), 1)
    print(f"\n  Tempo: {total_time}s total | {avg_time}s médio por questão")

    if provider == "claude" and report.get("generation_cost_usd", 0) > 0:
        tok = report.get("generation_tokens", {})
        print(f"  Tokens de geração: {tok.get('input', 0):,} entrada + {tok.get('output', 0):,} saída")
        print(f"  Custo estimado de geração: US$ {report['generation_cost_usd']:.4f}")

    print(f"\n{'═'*W}\n")


def print_compare_report(ollama_report: dict, claude_report: dict) -> None:
    """Print a side-by-side comparison of Ollama vs Claude benchmark results."""
    criteria = ["precisao_normativa", "completude", "relevancia_chunks", "coerencia", "alucinacao"]
    o_avgs   = ollama_report.get("avg_scores", {})
    c_avgs   = claude_report.get("avg_scores", {})
    o_pass   = ollama_report.get("passed", 0)
    c_pass   = claude_report.get("passed", 0)
    total    = ollama_report.get("total_questions", 15)
    o_avg    = ollama_report.get("avg_geral", 0.0)
    c_avg    = claude_report.get("avg_geral", 0.0)
    o_model  = ollama_report.get("model", "llama3:8b")
    c_model  = claude_report.get("model", "sonnet")

    W = 65
    print(f"\n{'═'*W}")
    print("  ComplianceAgent — Benchmark Comparison")
    print(f"  Data: {datetime.now().strftime('%Y-%m-%d')} | Questões: {total}")
    print(f"{'═'*W}\n")

    print(f"  ┌─────────────────────┬──────────┬──────────┐")
    print(f"  │ Métrica             │ Ollama   │ Claude   │")
    print(f"  │                     │ {o_model[:8]:<8} │ {c_model[:8]:<8} │")
    print(f"  ├─────────────────────┼──────────┼──────────┤")
    print(f"  │ Aprovados           │ {f'{o_pass}/{total}':<8} │ {f'{c_pass}/{total}':<8} │")
    print(f"  │ Média Geral         │ {o_avg:<8.1f} │ {c_avg:<8.1f} │")
    print(f"  ├─────────────────────┼──────────┼──────────┤")
    labels = {
        "precisao_normativa": "Precisão Normativa ",
        "completude":         "Completude         ",
        "relevancia_chunks":  "Relevância Chunks  ",
        "coerencia":          "Coerência          ",
        "alucinacao":         "Alucinação         ",
    }
    for c, label in labels.items():
        print(f"  │ {label}│ {o_avgs.get(c, 0.0):<8.1f} │ {c_avgs.get(c, 0.0):<8.1f} │")
    print(f"  └─────────────────────┴──────────┴──────────┘\n")

    # Per-question comparison
    o_by_id = {r["id"]: r for r in ollama_report.get("results", [])}
    c_by_id = {r["id"]: r for r in claude_report.get("results", [])}
    all_ids = sorted(set(o_by_id) | set(c_by_id))

    print(f"  ┌────┬─────────────────────────────────┬──────────┬──────────┐")
    print(f"  │ #  │ Pergunta (resumida)              │ Ollama   │ Claude   │")
    print(f"  ├────┼─────────────────────────────────┼──────────┼──────────┤")
    for qid in all_ids:
        o_r = o_by_id.get(qid, {})
        c_r = c_by_id.get(qid, {})
        o_nota = o_r.get("nota_geral", 0.0)
        c_nota = c_r.get("nota_geral", 0.0)
        o_sym  = "✓" if o_r.get("veredicto") == "APROVADO" else "✗"
        c_sym  = "✓" if c_r.get("veredicto") == "APROVADO" else "✗"
        q_text = (o_r.get("pergunta") or c_r.get("pergunta") or "")[:31]
        print(f"  │ {qid:<2} │ {q_text:<31} │ {o_nota:.1f} {o_sym:<4}  │ {c_nota:.1f} {c_sym:<4}  │")
    print(f"  └────┴─────────────────────────────────┴──────────┴──────────┘\n")

    # Diagnosis
    both_failed = [qid for qid in all_ids
                   if o_by_id.get(qid, {}).get("veredicto") == "REPROVADO"
                   and c_by_id.get(qid, {}).get("veredicto") == "REPROVADO"]
    only_ollama_failed = [qid for qid in all_ids
                          if o_by_id.get(qid, {}).get("veredicto") == "REPROVADO"
                          and c_by_id.get(qid, {}).get("veredicto") == "APROVADO"]

    print("  Diagnóstico:")
    if c_avg > o_avg + 1.5:
        print("  → Claude pontuou significativamente mais alto: problema é qualidade do modelo, não o RAG.")
    elif abs(c_avg - o_avg) <= 1.5 and both_failed:
        print("  → Ambos pontuam baixo nas mesmas questões: problema pode ser no pipeline de recuperação.")
    else:
        print("  → Resultados mistos: verifique questões individuais acima.")

    if both_failed:
        print(f"  → Ambos falharam nas questões: {both_failed}")
    if only_ollama_failed:
        print(f"  → Apenas Ollama falhou (Claude passou): {only_ollama_failed}")

    if claude_report.get("generation_cost_usd", 0) > 0:
        print(f"\n  Custo estimado geração Claude: US$ {claude_report['generation_cost_usd']:.4f}")

    print(f"\n{'═'*W}\n")


def _save_report(report: dict, provider: str) -> Path:
    date_str = datetime.now().strftime("%Y-%m-%d")
    path = _REPORT_DIR / f"benchmark_{provider}_{date_str}.json"
    _REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ComplianceAgent Benchmark Runner")
    parser.add_argument("--provider", choices=["ollama", "claude"], default="ollama",
                        help="LLM provider para geração de respostas")
    parser.add_argument("--compare", action="store_true",
                        help="Executar ambos providers e imprimir comparação lado a lado")
    parser.add_argument("--limit", type=int, default=None,
                        help="Limitar a N questões (útil para testes rápidos)")
    args = parser.parse_args()

    if args.compare:
        async def _compare():
            print("  Executando Ollama primeiro...")
            ollama_report = await run_benchmark(provider="ollama", limit=args.limit)
            if not ollama_report:
                return
            o_path = _save_report(ollama_report, "ollama")
            print(f"\n  Relatório Ollama salvo em: {o_path}")

            print("\n  Executando Claude...")
            claude_report = await run_benchmark(provider="claude", limit=args.limit)
            if not claude_report:
                return
            c_path = _save_report(claude_report, "claude")
            print(f"  Relatório Claude salvo em: {c_path}\n")

            print_compare_report(ollama_report, claude_report)

        asyncio.run(_compare())
    else:
        async def _single():
            report = await run_benchmark(provider=args.provider, limit=args.limit)
            if not report:
                return
            print_single_report(report)
            path = _save_report(report, args.provider)
            print(f"  Relatório salvo em: {path}\n")

        asyncio.run(_single())
