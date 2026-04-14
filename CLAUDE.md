# TechHire AI — Project Guide for Claude

## What This Project Is

TechHire AI is a multi-agent RAG-based platform for intelligent resume screening and recruitment pipeline management. It ingests candidate resumes and job postings as PDFs, processes them into a vector store, and answers questions with source citations via specialized agents.

**Target Audience:** AI Engineer / GenAI Engineer positions at Brazilian tech companies and startups.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.11+ |
| LLM | Ollama (llama3:8b) — local, zero cost |
| LLM (alternate) | Anthropic Claude (claude-sonnet-4-6) — via `anthropic` SDK |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) — local |
| Reranking | cross-encoder/mmarco-mMiniLMv2-L12-H384-v1 — multilingual, local |
| Vector Store | ChromaDB (file-based, persistent) — dual collections: `resumes`, `job_postings` |
| Database | SQLite (file: `data/techhire.db`) |
| API | FastAPI |
| Agent Framework | Custom implementation (no LangChain/LangGraph) |
| Auth | JWT (PyJWT + bcrypt), role-based (analyst / manager) |
| Frontend | Vanilla HTML/JS/CSS (no React framework) |
| HTTP client | httpx (async) |
| Containerization | Docker + Docker Compose |
| CI/CD | GitHub Actions (Python 3.11 + 3.13, 144 tests) |

## Architecture

```
PDF (resumes / job postings)
    → pdf_loader → chunker → embedder
        → ChromaDB "resumes" collection  (resumes)
        → ChromaDB "job_postings" collection  (job postings)

Recruiter question → CoordinatorAgent
    → keyword classifier (accent-insensitive, zero LLM)
        → ResumeAgent    (RAG over "resumes" collection)
        → MatchAgent     (NL→SQL→SQLite→NL interpretation)
        → PipelineAgent  (stage moves, funnel reports, feedback emails)
        → ResumeAgent + MatchAgent  (combined profile+score queries)
```

## Module Reference

### Config (`src/config.py`)
- `app_name = "TechHireAI API"`
- `db_path = "./data/techhire.db"`
- `collection_name = "resumes"` (ChromaDB)
- `jobs_collection_name = "job_postings"` (ChromaDB)
- `resume_chunk_size = 300`, `resume_chunk_overlap = 50`
- `retrieval_top_k = 50`, `rerank_top_k = 20`
- All Ollama, Claude, JWT settings inherited from prior phases

### Database (`src/database/`)

**Tables (`setup.py`):**
- `users` — id, username, password_hash, full_name, role, created_at, last_login, is_active
- `job_postings` — id, title, company, description, requirements, desired_skills, seniority_level, work_model, salary_range, created_by FK users, created_at, is_active
- `candidates` — id, full_name, email, phone, cpf, location, current_role, experience_years, education, skills TEXT JSON, resume_filename, resume_text, resume_pdf BLOB, created_at, is_active
- `matches` — id, candidate_id FK, job_posting_id FK, overall_score REAL, skills_score, experience_score, education_score, semantic_score, analysis TEXT, created_at
- `pipeline` — id, candidate_id FK, job_posting_id FK, stage TEXT DEFAULT 'triagem', notes, updated_by FK users, updated_at
- `conversations`, `messages`, `audit_log`, `governance_daily_stats` — unchanged

**Seed (`seed.py`):**
- `init_db()` calls `create_tables()` → `seed_users()`
- Seeds only 2 default users: `analyst/analyst123` and `manager/manager123`
- Candidates, job postings, matches, and pipeline entries are created exclusively via PDF upload through the dashboard — no sample/seed data for those tables

### Agents (`src/agents/`)

**`base.py`** — `AgentResponse` Pydantic model (unchanged)

**`resume_agent.py`** — `ResumeAgent`
- `name = "resume"`
- Keywords: candidato, currículo, perfil, experiência, formação, habilidades, skills, ...
- `can_handle(question)` → float (hits × 0.2, capped at 1.0)
- `answer(question, provider, conversation_history)` → `AgentResponse`
- `prepare(question, conversation_history)` → `(prompt, chunks)` (for SSE streaming)
- RAG targets `resumes` ChromaDB collection

**`match_agent.py`** — `MatchAgent`
- `name = "match"`
- Keywords: score, ranking, aderência, comparar, melhor, top, match, ...
- NL→SQL→execute→NL-interpret against `candidates`, `matches`, `pipeline`, `job_postings`
- Helpers: `_extract_sql()`, `_execute_sql()`, `_SELECT_ONLY_RE` (security: blocks non-SELECT)

**`pipeline_agent.py`** — `PipelineAgent`
- `name = "pipeline"`
- Keywords: mover, etapa, aprovar, aprove, rejeitar, feedback, funil, e-mail, ...
- Actions: `_report_funnel()`, `_move_stage()`, `_reject_candidate()`, `_generate_feedback_email()`
- Pipeline stages: `triagem → entrevista → teste_tecnico → aprovado → rejeitado`

**`coordinator.py`** — `CoordinatorAgent`
- `_heuristic_route(question)` → PIPELINE > RESUME+MATCH > MATCH > RESUME (default)
- `_classify(question)` → uses heuristic only, never calls LLM
- `process(question, provider, user_id, username, conversation_history)` → `CoordinatorResponse`
- `process_stream(...)` → async SSE generator
- LGPD: detects PII, masks before storage, logs to `audit_log` table

### Ingestion (`src/ingestion/`)

**`pdf_loader.py`** — PyMuPDF → `DocumentPage` dataclasses (unchanged)

**`chunker.py`** — `chunk_pages(pages, chunk_size, chunk_overlap, document_type)`
- `document_type="resume"` → 300/50
- `document_type="job_posting"` → 500/100
- `document_type="generic"` → caller values (default 800/100)
- `clean_text(text)` → removes URLs, timestamps, "Siga o BC" footers, cookie banners, BCB institutional text, navigation artifacts

**`embedder.py`**
- `classify_document(text)` → `"resume"` or `"job_posting"` (keyword counting)
- `index_chunks(chunks, collection_name=None)` → routes to correct ChromaDB collection
- `list_indexed_documents(client=None, collection_name=None)` → unique sources

### Retrieval (`src/retrieval/`)

**`query_engine.py`** — top-50 vector search → cross-encoder rerank to top-20 (unchanged)

**`prompt_builder.py`** — recruitment-focused system prompt (7 rules):
1. Base answers exclusively on provided chunks
2. Always cite candidate name and document section
3. Never output CPF numbers
4. Make objective, data-based comparisons
5. Copy numeric values (scores, years) exactly
6. Say clearly when information is not found
7. Use conversation history for context

### API (`src/api/main.py`)

Key endpoints beyond standard auth/chat:
- `POST /ingest` — classifies each PDF as resume/job_posting, routes to correct collection
- `POST /ingest/job` — index a single job posting text or PDF
- `GET /resumes` — indexed resumes from ChromaDB
- `GET /resumes/{candidate_id}/download` — download original CV PDF (stored as BLOB in SQLite)
- `GET /candidates` — candidates from SQLite
- `GET /job-postings` — job postings from SQLite
- `GET /pipeline` — pipeline entries with candidate/job info
- `GET /matches/{job_id}` — ranked candidates for a job
- `GET /matches/{candidate_id}/{job_posting_id}/details` — detailed score breakdown for one candidate×job pair
- `POST /match/{job_id}` — calculate keyword+experience+education scores
- `PATCH /pipeline/{candidate_id}/{job_id}` — move candidate to new stage

### Frontend (`src/api/templates/`)

- `index.html` — Chat UI branded "TechHire AI", 4 recruitment example chips, 👥 icon
- `login.html` — "TechHire AI — Login", subtitle "RECRUTAMENTO INTELIGENTE"
- `dashboard.html` — LGPD governance dashboard with KPI labels: "TOTAL DE TRIAGENS", "CURRÍCULOS COM PII", "CLASSIFICAÇÃO RESTRITA"

## Development Rules

- **NEVER use git worktrees.** Always work directly on `master` or create simple feature branches with `git checkout -b feature/xxx`. Worktrees cause environment fragmentation.
- **Before pushing:** Run `python -m pytest tests/ --ignore=tests/diagnose_rag.py -v --tb=short` locally and confirm 0 failures.
- **diagnose_rag.py is excluded from CI:** It makes real Ollama/ChromaDB calls and is not a pytest test.
- **`create_tables()` before `seed_users()`:** `init_db()` must call them in this order — tables must exist before inserting users.
- **ChromaDB collection routing:** Always pass `collection_name` to `index_chunks()` and `list_indexed_documents()` when targeting a specific collection. Default falls back to `settings.collection_name` ("resumes").

## CI/CD

GitHub Actions runs on every push to `master` and every pull request.

- **Workflow:** `.github/workflows/ci.yml`
- **What it does:** Runs `python -m pytest tests/ --ignore=tests/diagnose_rag.py -v --tb=short --timeout=60` on Python 3.11 and 3.13
- **No secrets needed:** All external services (Ollama, ChromaDB, Anthropic) are mocked in tests

## Module Status

| Module | Status |
|--------|--------|
| src/config.py | ✅ Done |
| src/ingestion/pdf_loader.py | ✅ Done |
| src/ingestion/chunker.py | ✅ Done |
| src/ingestion/embedder.py | ✅ Done |
| src/retrieval/query_engine.py | ✅ Done |
| src/retrieval/prompt_builder.py | ✅ Done |
| src/llm/ollama_client.py | ✅ Done |
| src/llm/claude_client.py | ✅ Done |
| src/llm/llm_router.py | ✅ Done |
| src/api/main.py | ✅ Done |
| src/api/auth.py | ✅ Done |
| src/api/auth_routes.py | ✅ Done |
| src/api/diagnostic.py | ✅ Done |
| src/api/evaluate.py | ✅ Done |
| src/api/governance.py | ✅ Done |
| src/api/conversation_routes.py | ✅ Done |
| src/api/templates/index.html | ✅ Done |
| src/api/templates/login.html | ✅ Done |
| src/api/templates/dashboard.html | ✅ Done |
| src/agents/base.py | ✅ Done |
| src/agents/coordinator.py | ✅ Done |
| src/agents/resume_agent.py | ✅ Done |
| src/agents/match_agent.py | ✅ Done |
| src/agents/pipeline_agent.py | ✅ Done |
| src/database/connection.py | ✅ Done |
| src/database/setup.py | ✅ Done |
| src/database/seed.py | ✅ Done |
| src/governance/__init__.py | ✅ Done |
| src/governance/pii_detector.py | ✅ Done |
| src/governance/audit.py | ✅ Done |
| src/governance/retention.py | ✅ Done |
| src/services/__init__.py | ✅ Done |
| src/services/conversation.py | ✅ Done |
| src/evaluation/__init__.py | ✅ Done |
| src/evaluation/benchmark.py | ✅ Done |
| Dockerfile | ✅ Done |
| docker-compose.yml | ✅ Done |
| .dockerignore | ✅ Done |
| scripts/start.sh | ✅ Done |
| .github/workflows/ci.yml | ✅ Done |
| tests/test_api.py | ✅ Done |
| tests/test_agents.py | ✅ Done |
| tests/test_agent_provider.py | ✅ Done |
| tests/test_chunker.py | ✅ Done |
| tests/test_conversations.py | ✅ Done |
| tests/test_coordinator.py | ✅ Done |
| tests/test_database.py | ✅ Done |
| tests/test_embedder.py | ✅ Done |
| tests/test_llm_router.py | ✅ Done |
| tests/test_pdf_loader.py | ✅ Done |
| tests/test_query_engine.py | ✅ Done |
| tests/test_retrieval_fixes.py | ✅ Done |
| tests/test_streaming.py | ✅ Done |

## Running Locally

```bash
pip install -r requirements.txt

ollama serve
ollama pull llama3:8b

export ANTHROPIC_API_KEY=sk-ant-...  # optional

uvicorn src.api.main:app --reload
# Open http://localhost:8000/login
# Default: analyst/analyst123 or manager/manager123
```

## API Quick Reference

All endpoints except `/`, `/login`, `/dashboard`, and `/auth/login` require `Authorization: Bearer <token>`.

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -d "username=analyst&password=analyst123" | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Resume question (RAG)
curl -X POST http://localhost:8000/agent \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"pergunta": "Quais candidatos têm experiência com RAG?"}'

# Score/ranking question (SQL)
curl -X POST http://localhost:8000/agent \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"pergunta": "Rankeie os top 5 por score de aderência"}'

# Pipeline action
curl -X POST http://localhost:8000/agent \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"pergunta": "Qual o status do funil de contratação?"}'

# With Claude instead of Ollama
curl -X POST http://localhost:8000/agent \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"pergunta": "Quem tem experiência com Python?", "provider": "claude"}'
```

## Coding Conventions

- **Type hints** on all function signatures and class attributes
- **Docstrings** on all public functions and classes (Google style)
- **Async** for all FastAPI endpoints and LLM clients
- **dataclasses** for DTOs (DocumentPage, TextChunk, RetrievedChunk)
- **No global state** — models loaded inside functions or dependency-injected
- All user-facing text in **Brazilian Portuguese**
- Tests use `pytest`, mocking external services (ChromaDB, Ollama, SentenceTransformer)
