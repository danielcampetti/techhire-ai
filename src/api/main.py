"""FastAPI application for TechHire AI.

Endpoints:
- GET  /              -- Chat UI (browser interface)
- POST /ingest        -- Index resume PDFs from data/raw/
- POST /ingest/job    -- Index a job posting text or PDF
- POST /chat          -- Answer a recruitment question with source citations
- GET  /resumes       -- List all indexed resumes
- GET  /candidates    -- List candidates with optional filters
- GET  /job-postings  -- List job postings
- GET  /matches/{job_id}  -- Ranked candidates for a job posting
- POST /match/{job_id}    -- Recalculate match scores for a job posting
- GET  /pipeline      -- List pipeline entries with optional stage filter
- PATCH /pipeline/{candidate_id}/{job_id} -- Move candidate to a new stage
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Union

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

_TEMPLATE_PATH  = Path(__file__).parent / "templates" / "index.html"
_LOGIN_PATH     = Path(__file__).parent / "templates" / "login.html"
_DASHBOARD_PATH = Path(__file__).parent / "templates" / "dashboard.html"

from src.config import settings
from src.api.auth import TokenUser, require_role
from src.api.auth_routes import auth_router
from src.ingestion.chunker import chunk_pages
from src.ingestion.embedder import (
    _get_client as _get_chroma_client,
    classify_document,
    index_chunks,
    list_indexed_documents,
)
from src.ingestion.pdf_loader import load_all_pdfs
from src.llm import ollama_client, claude_client
from src.retrieval.prompt_builder import build_prompt
from src.retrieval.query_engine import retrieve
from src.agents.coordinator import CoordinatorAgent, CoordinatorResponse
from src.database.connection import get_db
from src.database.seed import init_db
from src.services.conversation import ConversationService
from src.api.diagnostic import router as diagnostic_router
from src.api.evaluate import router as evaluate_router
from src.api.conversation_routes import conversation_router
from src.api.governance import governance_router

# ── Skill extraction helpers ────────────────────────────────────────────────

_COMMON_SKILLS = [
    "python", "java", "javascript", "typescript", "go", "rust", "c++", "c#",
    "sql", "nosql", "mongodb", "postgresql", "mysql", "redis", "kafka",
    "docker", "kubernetes", "aws", "gcp", "azure", "terraform",
    "fastapi", "django", "flask", "spring", "react", "angular", "vue",
    "machine learning", "deep learning", "nlp", "rag", "llm", "langchain",
    "pytorch", "tensorflow", "scikit-learn", "pandas", "numpy",
    "git", "api", "rest", "graphql", "microservices", "linux",
]


_PDF_NAME_PREFIX = re.compile(r"^(curriculo|curriculum|cv|resume|lattes)[_\-\s]?", re.IGNORECASE)


def _extract_candidate_data(filename: str, full_text: str) -> dict:
    """Parse candidate metadata from filename and raw PDF text."""
    # Strip common prefixes (curriculo_, cv_, resume_) from filename-based name
    stem = filename.rsplit(".", 1)[0]
    stem = _PDF_NAME_PREFIX.sub("", stem)
    name = stem.replace("_", " ").replace("-", " ").title().strip() or filename

    # Try to use the first non-empty line of the PDF if it looks like a proper name
    for line in full_text.split("\n"):
        line = line.strip()
        if not line:
            continue
        words = line.split()
        if 2 <= len(words) <= 5 and re.match(r"^[A-Za-zÀ-ÿ\s]+$", line):
            name = line.title()
        break  # only check the very first non-empty line

    lower = full_text.lower()
    skills = [s for s in _COMMON_SKILLS if s in lower]
    m = re.search(r"(\d+)\+?\s*anos?\s+de\s+experi", lower)
    exp_years = int(m.group(1)) if m else 0
    return {
        "full_name": name,
        "resume_filename": filename,
        "resume_text": full_text[:10_000],
        "skills": json.dumps(skills),
        "experience_years": exp_years,
    }


def _extract_job_data(filename: str, full_text: str) -> dict:
    """Parse job posting metadata from filename and raw PDF text."""
    title = filename.rsplit(".", 1)[0].replace("_", " ").replace("-", " ").title()
    return {
        "title": title,
        "description": full_text[:5_000],
        "requirements": full_text[:2_000],
    }


def _score_candidate_vs_job(cand: dict, job: dict, now: str) -> None:
    """Calculate and upsert a match score row for one candidate×job pair."""
    # Substring matching: for each candidate skill, check if it appears anywhere
    # in the requirements text. This avoids bag-of-words fragmentation issues
    # (e.g. "LLMs" in requirements matching "llm" in skills, "RAG pipelines"
    # matching "rag", etc.) and scales correctly with the skills list size.
    req_lower = (
        (job["requirements"] or "") + " " + (job["desired_skills"] or "")
    ).lower()
    try:
        cand_skills = [s.lower() for s in json.loads(cand["skills"] or "[]")]
    except Exception:
        cand_skills = []

    if cand_skills:
        matched = sum(1 for s in cand_skills if s in req_lower)
        skills_score = matched / len(cand_skills)
    else:
        skills_score = 0.3  # no skills data extracted

    req_exp = 3
    em = re.search(r"(\d+)\+?\s*anos", job["requirements"] or "", re.IGNORECASE)
    if em:
        req_exp = int(em.group(1))
    experience_score = min((cand["experience_years"] or 0) / max(req_exp, 1), 1.0)

    edu = (cand["education"] or "").lower()
    education_score = 1.0 if ("doutorado" in edu or "phd" in edu) else \
                      0.9 if ("mestrado" in edu or "mba" in edu) else \
                      0.75 if ("bacharelado" in edu or "graduação" in edu or "graduacao" in edu) else 0.7

    overall = round(0.5 * skills_score + 0.3 * experience_score + 0.2 * education_score, 4)

    with get_db() as conn:
        existing = conn.execute(
            "SELECT id FROM matches WHERE candidate_id=? AND job_posting_id=?",
            (cand["id"], job["id"]),
        ).fetchone()
        if existing:
            conn.execute(
                """UPDATE matches SET overall_score=?, skills_score=?,
                   experience_score=?, education_score=?, created_at=?
                   WHERE candidate_id=? AND job_posting_id=?""",
                (overall, skills_score, experience_score, education_score,
                 now, cand["id"], job["id"]),
            )
        else:
            conn.execute(
                """INSERT INTO matches
                   (candidate_id, job_posting_id, overall_score, skills_score,
                    experience_score, education_score, created_at)
                   VALUES (?,?,?,?,?,?,?)""",
                (cand["id"], job["id"], overall, skills_score,
                 experience_score, education_score, now),
            )


def _recalculate_matches(
    new_candidate_ids: list[int] | None = None,
    new_job_ids: list[int] | None = None,
) -> int:
    """Recalculate match scores after new data is ingested.

    - new_candidate_ids: score them against ALL active job_postings
    - new_job_ids: score ALL active candidates against them
    Returns total number of scores written.
    """
    now = datetime.utcnow().isoformat()
    total = 0

    with get_db() as conn:
        all_jobs = [dict(r) for r in conn.execute(
            "SELECT * FROM job_postings WHERE is_active=1"
        ).fetchall()]
        all_cands = [dict(r) for r in conn.execute(
            "SELECT * FROM candidates WHERE is_active=1"
        ).fetchall()]

    if new_candidate_ids:
        cands = [c for c in all_cands if c["id"] in new_candidate_ids]
        for cand in cands:
            for job in all_jobs:
                _score_candidate_vs_job(cand, job, now)
                total += 1

    if new_job_ids:
        jobs = [j for j in all_jobs if j["id"] in new_job_ids]
        for job in jobs:
            for cand in all_cands:
                _score_candidate_vs_job(cand, job, now)
                total += 1

    return total


# ── FastAPI app ──────────────────────────────────────────────────────────────

app = FastAPI(
    title="TechHire AI API",
    description="Plataforma inteligente de triagem de currículos com agentes de IA",
    version="1.0.0",
)

app.include_router(auth_router)
app.include_router(diagnostic_router)
app.include_router(evaluate_router)
app.include_router(conversation_router)
app.include_router(governance_router)


# -- Request / Response models -----------------------------------------------

class ChatRequest(BaseModel):
    pergunta: str
    provider: Optional[str] = None  # "ollama" or "claude"; falls back to settings.llm_provider


class FonteSchema(BaseModel):
    arquivo: str
    pagina: Union[int, str]
    score: float


class ChatResponse(BaseModel):
    resposta: str
    fontes: List[FonteSchema]


class AgentRequest(BaseModel):
    pergunta: str
    provider: Optional[str] = None  # "ollama" or "claude"; falls back to settings.llm_provider
    conversation_id: Optional[int] = None  # enables persistent memory


class PipelineUpdateRequest(BaseModel):
    stage: str
    notes: Optional[str] = None


class JobPostingRequest(BaseModel):
    title: str
    company: Optional[str] = None
    description: str
    requirements: Optional[str] = None
    desired_skills: Optional[str] = None
    seniority_level: Optional[str] = None
    work_model: Optional[str] = None
    salary_range: Optional[str] = None


# -- Endpoints ----------------------------------------------------------------

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def chat_ui() -> HTMLResponse:
    """Serve the browser chat interface."""
    return HTMLResponse(_TEMPLATE_PATH.read_text(encoding="utf-8"))


@app.get("/login", response_class=HTMLResponse, include_in_schema=False)
async def login_ui() -> HTMLResponse:
    return HTMLResponse(_LOGIN_PATH.read_text(encoding="utf-8"))


@app.get("/dashboard", response_class=HTMLResponse, include_in_schema=False)
async def dashboard_ui() -> HTMLResponse:
    return HTMLResponse(_DASHBOARD_PATH.read_text(encoding="utf-8"))


@app.post("/ingest", summary="Indexar currículos PDF — de data/raw/ ou upload direto")
async def ingest(
    files: Optional[List[UploadFile]] = File(default=None),
    current_user: TokenUser = Depends(require_role("manager")),
) -> dict:
    """Processa PDFs e indexa seus chunks no ChromaDB.

    Dois modos:
    - Sem arquivos: lê todos os PDFs de data/raw/
    - Com arquivos (multipart): processa os PDFs enviados diretamente

    Classifica automaticamente cada PDF como currículo ou vaga e usa a
    coleção correta (resumes vs job_postings).

    Returns:
        Dict com contagem de páginas processadas e chunks indexados.
    """
    from collections import defaultdict
    from src.ingestion.pdf_loader import DocumentPage

    # ── Gather pages from upload OR from data/raw/ ────────────────────
    pages: list = []

    if files:
        import fitz  # PyMuPDF
        for upload in files:
            if not upload.filename or not upload.filename.lower().endswith(".pdf"):
                continue
            raw_bytes = await upload.read()
            doc = fitz.open(stream=raw_bytes, filetype="pdf")
            for i, page in enumerate(doc):
                text = page.get_text()
                if text.strip():
                    pages.append(DocumentPage(
                        content=text,
                        filename=upload.filename,
                        page_number=i + 1,
                        title=upload.filename.rsplit(".", 1)[0].replace("_", " ").title(),
                        metadata={"source": upload.filename, "page": i + 1},
                    ))
            doc.close()
    else:
        raw_dir = Path(settings.data_raw_dir)
        if not raw_dir.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Diretório '{raw_dir}' não encontrado. Crie-o e adicione PDFs.",
            )
        pages = load_all_pdfs(raw_dir)

    if not pages:
        return {
            "mensagem": "Nenhum PDF com conteúdo encontrado.",
            "paginas_processadas": 0,
            "chunks_indexados": 0,
            "curriculos_indexados": 0,
            "vagas_indexadas": 0,
        }

    # ── Classify, index to ChromaDB, and upsert to SQLite ────────────
    init_db()
    now = datetime.utcnow().isoformat()

    pages_by_file: dict[str, list] = defaultdict(list)
    for page in pages:
        pages_by_file[page.filename].append(page)

    total_chunks = 0
    resume_files = 0
    job_files = 0
    new_candidate_ids: list[int] = []
    new_job_ids: list[int] = []

    for filename, file_pages in pages_by_file.items():
        full_text = " ".join(p.content for p in file_pages)
        doc_type = classify_document(full_text)

        if doc_type == "resume":
            # ── ChromaDB ──────────────────────────────────────────────
            chunks = chunk_pages(file_pages, document_type="resume")
            total_chunks += index_chunks(chunks, collection_name=settings.collection_name)
            resume_files += 1

            # ── SQLite candidates ─────────────────────────────────────
            cdata = _extract_candidate_data(filename, full_text)
            with get_db() as conn:
                existing = conn.execute(
                    "SELECT id FROM candidates WHERE resume_filename=?", (filename,)
                ).fetchone()
                if existing:
                    conn.execute(
                        """UPDATE candidates SET resume_text=?, skills=?,
                           experience_years=? WHERE id=?""",
                        (cdata["resume_text"], cdata["skills"],
                         cdata["experience_years"], existing["id"]),
                    )
                    new_candidate_ids.append(existing["id"])
                else:
                    conn.execute(
                        """INSERT INTO candidates
                           (full_name, resume_filename, resume_text, skills,
                            experience_years, created_at, is_active)
                           VALUES (?,?,?,?,?,?,1)""",
                        (cdata["full_name"], cdata["resume_filename"],
                         cdata["resume_text"], cdata["skills"],
                         cdata["experience_years"], now),
                    )
                    cid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                    new_candidate_ids.append(cid)

        else:
            # ── ChromaDB ──────────────────────────────────────────────
            chunks = chunk_pages(file_pages, document_type="job_posting")
            total_chunks += index_chunks(chunks, collection_name=settings.jobs_collection_name)
            job_files += 1

            # ── SQLite job_postings ───────────────────────────────────
            jdata = _extract_job_data(filename, full_text)
            with get_db() as conn:
                existing = conn.execute(
                    "SELECT id FROM job_postings WHERE title=?", (jdata["title"],)
                ).fetchone()
                if existing:
                    conn.execute(
                        "UPDATE job_postings SET description=?, requirements=? WHERE id=?",
                        (jdata["description"], jdata["requirements"], existing["id"]),
                    )
                    new_job_ids.append(existing["id"])
                else:
                    conn.execute(
                        """INSERT INTO job_postings
                           (title, description, requirements, created_by, created_at, is_active)
                           VALUES (?,?,?,?,?,1)""",
                        (jdata["title"], jdata["description"], jdata["requirements"],
                         current_user.user_id, now),
                    )
                    jid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                    new_job_ids.append(jid)

    # ── Auto-calculate match scores for new data ──────────────────────
    scores_written = _recalculate_matches(
        new_candidate_ids=new_candidate_ids or None,
        new_job_ids=new_job_ids or None,
    )

    return {
        "mensagem": "Indexação concluída com sucesso.",
        "paginas_processadas": len(pages),
        "chunks_indexados": total_chunks,
        "curriculos_indexados": resume_files,
        "vagas_indexadas": job_files,
        "scores_calculados": scores_written,
    }


@app.post("/ingest/job", summary="Indexar uma vaga a partir de texto")
async def ingest_job(
    request: JobPostingRequest,
    current_user: TokenUser = Depends(require_role("manager")),
) -> dict:
    """Salva uma vaga no banco de dados e indexa no ChromaDB.

    Returns:
        Dict com job_posting_id e chunks_indexados.
    """
    init_db()
    now = datetime.utcnow().isoformat()

    with get_db() as conn:
        conn.execute(
            """INSERT INTO job_postings
               (title, company, description, requirements, desired_skills,
                seniority_level, work_model, salary_range, created_by, created_at, is_active)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (request.title, request.company, request.description,
             request.requirements, request.desired_skills, request.seniority_level,
             request.work_model, request.salary_range, current_user.user_id, now, True),
        )
        job_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    # Index the job posting text into ChromaDB
    from src.ingestion.pdf_loader import DocumentPage
    full_text = "\n\n".join(filter(None, [
        request.title, request.description,
        request.requirements, request.desired_skills,
    ]))
    page = DocumentPage(
        content=full_text,
        filename=f"job_{job_id}_{request.title[:30]}.txt",
        page_number=1,
        title=request.title,
        metadata={"source": request.title, "company": request.company or "", "job_id": job_id},
    )
    chunks = chunk_pages([page], document_type="job_posting")
    count = index_chunks(chunks, collection_name=settings.jobs_collection_name)

    return {
        "mensagem": "Vaga indexada com sucesso.",
        "job_posting_id": job_id,
        "chunks_indexados": count,
    }


@app.post("/chat", response_model=ChatResponse, summary="Consultar currículos indexados")
async def chat(
    request: ChatRequest,
    _: TokenUser = Depends(require_role("analyst", "manager")),
) -> ChatResponse:
    """Recebe uma pergunta sobre candidatos e retorna resposta com citações das fontes.

    Args:
        request: JSON body com campo `pergunta`.

    Returns:
        Resposta gerada pelo LLM e lista de fontes utilizadas.
    """
    chunks = retrieve(request.pergunta)

    if not chunks:
        return ChatResponse(
            resposta="Esta informação não foi encontrada nos currículos disponíveis.",
            fontes=[],
        )

    prompt = build_prompt(request.pergunta, chunks)
    provider = (request.provider or settings.llm_provider).lower()
    try:
        if provider == "claude":
            resposta = await claude_client.generate(prompt)
        else:
            resposta = await ollama_client.generate(prompt)
    except ValueError as exc:
        if "ANTHROPIC_API_KEY" in str(exc):
            raise HTTPException(status_code=503, detail=str(exc))
        raise

    fontes = [
        FonteSchema(
            arquivo=str(c.metadata.get("source", "desconhecido")),
            pagina=c.metadata.get("page", "?"),
            score=round(c.score, 4),
        )
        for c in chunks
    ]

    return ChatResponse(resposta=resposta, fontes=fontes)


@app.get("/resumes", summary="Listar currículos indexados")
async def list_resumes(
    _: TokenUser = Depends(require_role("analyst", "manager")),
) -> dict:
    """Lista todos os currículos únicos presentes no índice vetorial.

    Returns:
        Dict com lista de documentos e contagem total.
    """
    client = _get_chroma_client()
    docs = list_indexed_documents(client, collection_name=settings.collection_name)
    return {"curriculos": docs, "total": len(docs)}


@app.get("/candidates", summary="Listar candidatos")
async def list_candidates(
    score_min: Optional[float] = None,
    score_max: Optional[float] = None,
    job_posting_id: Optional[int] = None,
    stage: Optional[str] = None,
    _: TokenUser = Depends(require_role("analyst", "manager")),
) -> dict:
    """Lista candidatos com filtros opcionais de score e etapa do pipeline."""
    init_db()
    conditions: list[str] = []
    params: list = []
    join = ""

    if job_posting_id is not None or score_min is not None or score_max is not None:
        join = "LEFT JOIN matches m ON c.id = m.candidate_id"
        if job_posting_id is not None:
            conditions.append("m.job_posting_id = ?")
            params.append(job_posting_id)
        if score_min is not None:
            conditions.append("m.overall_score >= ?")
            params.append(score_min)
        if score_max is not None:
            conditions.append("m.overall_score <= ?")
            params.append(score_max)

    if stage is not None:
        if not join:
            join = "LEFT JOIN pipeline p ON c.id = p.candidate_id"
        else:
            join += " LEFT JOIN pipeline p ON c.id = p.candidate_id"
        conditions.append("p.stage = ?")
        params.append(stage)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    order = "ORDER BY m.overall_score DESC" if join and "matches" in join else "ORDER BY c.created_at DESC"

    with get_db() as conn:
        rows = conn.execute(
            f"SELECT c.* {', m.overall_score, m.skills_score, m.analysis' if 'matches' in join else ''} "
            f"FROM candidates c {join} {where} {order}",
            params,
        ).fetchall()

    return {"candidatos": [dict(r) for r in rows], "total": len(rows)}


@app.get("/job-postings", summary="Listar vagas")
async def list_job_postings(
    _: TokenUser = Depends(require_role("analyst", "manager")),
) -> dict:
    """Lista todas as vagas ativas."""
    init_db()
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM job_postings WHERE is_active = 1 ORDER BY created_at DESC"
        ).fetchall()
    return {"vagas": [dict(r) for r in rows], "total": len(rows)}


@app.get("/matches/{job_id}", summary="Candidatos rankeados para uma vaga")
async def get_matches(
    job_id: int,
    limit: int = 20,
    _: TokenUser = Depends(require_role("analyst", "manager")),
) -> dict:
    """Retorna candidatos rankeados por score de aderência para uma vaga.

    Args:
        job_id: ID da vaga no banco de dados.
        limit: Máximo de candidatos a retornar (default 20).

    Returns:
        Lista de candidatos com scores, ordenados por overall_score DESC.
    """
    init_db()
    with get_db() as conn:
        job = conn.execute(
            "SELECT id, title, company FROM job_postings WHERE id = ?", (job_id,)
        ).fetchone()
        if not job:
            raise HTTPException(status_code=404, detail=f"Vaga #{job_id} não encontrada.")

        rows = conn.execute(
            """SELECT c.id, c.full_name, c.current_role, c.experience_years,
                      c.location, c.education, c.skills,
                      m.overall_score, m.skills_score, m.experience_score,
                      m.education_score, m.semantic_score, m.analysis,
                      p.stage
               FROM matches m
               JOIN candidates c ON c.id = m.candidate_id
               LEFT JOIN pipeline p ON p.candidate_id = c.id AND p.job_posting_id = ?
               WHERE m.job_posting_id = ? AND c.is_active = 1
               ORDER BY m.overall_score DESC
               LIMIT ?""",
            (job_id, job_id, limit),
        ).fetchall()

    return {
        "vaga": {"id": job["id"], "title": job["title"], "company": job["company"]},
        "candidatos": [dict(r) for r in rows],
        "total": len(rows),
    }


@app.post("/match/{job_id}", summary="Calcular match scores para uma vaga")
async def calculate_matches(
    job_id: int,
    _: TokenUser = Depends(require_role("manager")),
) -> dict:
    """Recalcula scores de aderência para todos os candidatos ativos contra uma vaga.

    Uses keyword skill matching and experience scoring (semantic scoring
    requires ChromaDB embeddings to be populated via /ingest first).

    Returns:
        Dict com total de scores calculados.
    """
    init_db()
    now = datetime.utcnow().isoformat()

    with get_db() as conn:
        job = conn.execute(
            "SELECT * FROM job_postings WHERE id = ?", (job_id,)
        ).fetchone()
        if not job:
            raise HTTPException(status_code=404, detail=f"Vaga #{job_id} não encontrada.")

        candidates = conn.execute(
            "SELECT * FROM candidates WHERE is_active = 1"
        ).fetchall()

    required_skills = set(
        s.strip().lower()
        for s in (job["requirements"] or "").replace(",", " ").split()
        if len(s.strip()) > 2
    )

    calculated = 0
    with get_db() as conn:
        for cand in candidates:
            import json as _json
            try:
                cand_skills = set(s.lower() for s in _json.loads(cand["skills"] or "[]"))
            except Exception:
                cand_skills = set()

            skills_score = (
                len(cand_skills & required_skills) / len(required_skills)
                if required_skills else 0.5
            )

            req_exp = 3  # default
            import re as _re
            exp_match = _re.search(r"(\d+)\+?\s*anos", job["requirements"] or "", _re.IGNORECASE)
            if exp_match:
                req_exp = int(exp_match.group(1))
            exp_years = cand["experience_years"] or 0
            experience_score = min(exp_years / max(req_exp, 1), 1.0)

            education_score = 0.7
            edu = (cand["education"] or "").lower()
            if "doutorado" in edu or "phd" in edu:
                education_score = 1.0
            elif "mestrado" in edu or "mba" in edu:
                education_score = 0.9
            elif "bacharelado" in edu or "graduação" in edu or "graduacao" in edu:
                education_score = 0.75

            overall_score = round(
                0.5 * skills_score + 0.3 * experience_score + 0.2 * education_score, 4
            )

            existing = conn.execute(
                "SELECT id FROM matches WHERE candidate_id=? AND job_posting_id=?",
                (cand["id"], job_id),
            ).fetchone()

            if existing:
                conn.execute(
                    """UPDATE matches SET overall_score=?, skills_score=?,
                       experience_score=?, education_score=?, created_at=?
                       WHERE candidate_id=? AND job_posting_id=?""",
                    (overall_score, skills_score, experience_score, education_score,
                     now, cand["id"], job_id),
                )
            else:
                conn.execute(
                    """INSERT INTO matches
                       (candidate_id, job_posting_id, overall_score, skills_score,
                        experience_score, education_score, created_at)
                       VALUES (?,?,?,?,?,?,?)""",
                    (cand["id"], job_id, overall_score, skills_score,
                     experience_score, education_score, now),
                )
            calculated += 1

    return {
        "mensagem": f"Scores calculados para {calculated} candidatos.",
        "job_posting_id": job_id,
        "total_calculado": calculated,
    }


@app.get("/pipeline", summary="Listar pipeline de contratação")
async def list_pipeline(
    stage: Optional[str] = None,
    job_posting_id: Optional[int] = None,
    _: TokenUser = Depends(require_role("analyst", "manager")),
) -> dict:
    """Lista entradas do pipeline com filtros opcionais de etapa e vaga."""
    init_db()
    conditions: list[str] = []
    params: list = []

    if stage:
        conditions.append("p.stage = ?")
        params.append(stage)
    if job_posting_id is not None:
        conditions.append("p.job_posting_id = ?")
        params.append(job_posting_id)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    with get_db() as conn:
        rows = conn.execute(
            f"""SELECT p.*, c.full_name, c.current_role, c.experience_years,
                       j.title as job_title
                FROM pipeline p
                JOIN candidates c ON c.id = p.candidate_id
                JOIN job_postings j ON j.id = p.job_posting_id
                {where}
                ORDER BY CASE p.stage
                  WHEN 'triagem' THEN 1 WHEN 'entrevista' THEN 2
                  WHEN 'teste_tecnico' THEN 3 WHEN 'aprovado' THEN 4
                  WHEN 'rejeitado' THEN 5 ELSE 6 END,
                p.updated_at DESC""",
            params,
        ).fetchall()

    return {"pipeline": [dict(r) for r in rows], "total": len(rows)}


@app.patch("/pipeline/{candidate_id}/{job_id}", summary="Mover candidato de etapa")
async def update_pipeline_stage(
    candidate_id: int,
    job_id: int,
    request: PipelineUpdateRequest,
    current_user: TokenUser = Depends(require_role("analyst", "manager")),
) -> dict:
    """Move um candidato para uma nova etapa do pipeline.

    Args:
        candidate_id: ID do candidato.
        job_id: ID da vaga.
        request: JSON body com stage e notes opcionais.

    Returns:
        Dict com confirmação e nova etapa.
    """
    valid_stages = ("triagem", "entrevista", "teste_tecnico", "aprovado", "rejeitado")
    if request.stage not in valid_stages:
        raise HTTPException(
            status_code=400,
            detail=f"Etapa inválida. Use: {', '.join(valid_stages)}",
        )

    init_db()
    now = datetime.utcnow().isoformat()

    with get_db() as conn:
        cand = conn.execute(
            "SELECT full_name FROM candidates WHERE id=?", (candidate_id,)
        ).fetchone()
        if not cand:
            raise HTTPException(status_code=404, detail=f"Candidato #{candidate_id} não encontrado.")

        existing = conn.execute(
            "SELECT id FROM pipeline WHERE candidate_id=? AND job_posting_id=?",
            (candidate_id, job_id),
        ).fetchone()

        if existing:
            conn.execute(
                "UPDATE pipeline SET stage=?, notes=?, updated_by=?, updated_at=? "
                "WHERE candidate_id=? AND job_posting_id=?",
                (request.stage, request.notes, current_user.user_id, now, candidate_id, job_id),
            )
        else:
            conn.execute(
                "INSERT INTO pipeline (candidate_id, job_posting_id, stage, notes, updated_by, updated_at) "
                "VALUES (?,?,?,?,?,?)",
                (candidate_id, job_id, request.stage, request.notes, current_user.user_id, now),
            )

    return {
        "mensagem": f"Candidato {cand['full_name']} movido para '{request.stage}'.",
        "candidate_id": candidate_id,
        "new_stage": request.stage,
    }


@app.post("/agent", response_model=CoordinatorResponse)
async def agent_endpoint(
    request: AgentRequest,
    current_user: TokenUser = Depends(require_role("analyst", "manager")),
) -> CoordinatorResponse:
    """Route a question to the appropriate specialized agent(s).

    When conversation_id is provided, saves both user question and agent response
    to the messages table and passes prior context to the coordinator.
    """
    provider = (request.provider or settings.llm_provider).lower()
    coordinator = CoordinatorAgent()
    svc = ConversationService()

    conversation_history = None
    if request.conversation_id is not None:
        if svc.get_by_id(request.conversation_id, current_user.user_id) is None:
            raise HTTPException(
                status_code=404,
                detail="Conversa não encontrada ou sem permissão de acesso.",
            )
        conversation_history = svc.get_context_messages(
            request.conversation_id, max_messages=10
        )
        is_first_message = len(conversation_history) == 0
        svc.add_message(request.conversation_id, "user", request.pergunta)
        if is_first_message:
            svc.update_title(
                request.conversation_id,
                current_user.user_id,
                ConversationService.auto_title(request.pergunta),
            )

    try:
        response = await coordinator.process(
            request.pergunta,
            provider=provider,
            user_id=current_user.user_id,
            username=current_user.username,
            conversation_history=conversation_history,
        )
    except ValueError as exc:
        if "ANTHROPIC_API_KEY" in str(exc):
            raise HTTPException(status_code=503, detail=str(exc))
        raise

    if request.conversation_id is not None:
        svc.add_message(
            request.conversation_id,
            "assistant",
            response.resposta_final,
            agent_used=",".join(response.agentes_utilizados),
            provider=response.provider_utilizado,
            data_classification=response.data_classification,
            pii_detected=response.pii_detected,
        )

    return response


@app.post("/agent/stream")
async def agent_stream_endpoint(
    request: AgentRequest,
    current_user: TokenUser = Depends(require_role("analyst", "manager")),
) -> StreamingResponse:
    """Stream agent response via Server-Sent Events.

    Mirrors /agent's auth, conversation_id handling, and message persistence.
    The original POST /agent endpoint is unchanged for backward compatibility.
    """
    provider = (request.provider or settings.llm_provider).lower()
    coordinator = CoordinatorAgent()
    svc = ConversationService()

    conversation_history = None
    if request.conversation_id is not None:
        if svc.get_by_id(request.conversation_id, current_user.user_id) is None:
            raise HTTPException(
                status_code=404,
                detail="Conversa não encontrada ou sem permissão de acesso.",
            )
        conversation_history = svc.get_context_messages(
            request.conversation_id, max_messages=10
        )
        is_first_message = len(conversation_history) == 0
        svc.add_message(request.conversation_id, "user", request.pergunta)
        if is_first_message:
            svc.update_title(
                request.conversation_id,
                current_user.user_id,
                ConversationService.auto_title(request.pergunta),
            )

    async def event_generator():
        full_response = ""
        agents_used: list[str] = []
        data_classification: str = "public"
        pii_detected: bool = False

        async for event in coordinator.process_stream(
            request.pergunta,
            provider=provider,
            user_id=current_user.user_id,
            username=current_user.username,
            conversation_history=conversation_history,
        ):
            yield event
            if event.startswith("data:"):
                try:
                    data = json.loads(event[5:].strip())
                    if data.get("type") == "metadata":
                        agents_used = data.get("agentes_utilizados", [])
                    elif data.get("type") == "done":
                        full_response = data.get("full_response", "")
                        data_classification = data.get("data_classification", "public")
                        pii_detected = data.get("pii_detected", False)
                except Exception:
                    pass

        if request.conversation_id is not None and full_response:
            svc.add_message(
                request.conversation_id,
                "assistant",
                full_response,
                agent_used=",".join(agents_used) if agents_used else None,
                provider=provider,
                data_classification=data_classification,
                pii_detected=pii_detected,
            )

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
