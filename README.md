# TechHire AI

![CI](https://github.com/danielcampetti/techhire-ai/actions/workflows/ci.yml/badge.svg)
![Python](https://img.shields.io/badge/Python-3.11%2B-blue)
![License](https://img.shields.io/badge/License-MIT-green)
![Tests](https://img.shields.io/badge/Tests-144%20passing-brightgreen)

**Sistema multi-agente de triagem inteligente de currículos com RAG, LGPD e streaming em tempo real.**

Plataforma de recrutamento que ingere currículos e vagas em PDF, processa em banco vetorial e responde perguntas em linguagem natural com citações precisas — orquestrando múltiplos agentes especializados para análise de perfis, ranking por aderência e gestão do funil de contratação.

---

## Arquitetura

```
PDF (currículos / vagas)
    → pdf_loader → chunker → embedder
        → ChromaDB "resumes"       (currículos)
        → ChromaDB "job_postings"  (vagas)

Pergunta do recrutador → CoordinatorAgent (roteamento por palavras-chave, zero LLM)
    → ResumeAgent    — RAG sobre ChromaDB "resumes"
    → MatchAgent     — NL→SQL→SQLite→NL (scores de aderência)
    → PipelineAgent  — mover etapas, funil, e-mail de feedback
    → Resume+Match   — perfil + score combinados

Resposta → SSE streaming → frontend (vanilla JS)
```

```
+-------------+     +---------------------------------------------------+
|  Frontend   |     |                   Backend                         |
|  (HTML/JS)  | --> |  +-----------+   +----------------------------+  |
|             | SSE |  |  FastAPI  |   |      CoordinatorAgent      |  |
| - Login     | <-- |  | + JWT Auth| ->|     (keyword routing)      |  |
| - Chat      |     |  +-----------+   +-------+--------+-----------+  |
| - Dashboard |     |                          |        |         |     |
| - Scorecard |     |                          v        v         v     |
+-------------+     |  +-----------+ +--------+ +-----------+         |
                    |  | Resume    | | Match  | | Pipeline  |         |
                    |  | Agent     | | Agent  | | Agent     |         |
                    |  +-----+-----+ +---+----+ +-----+-----+         |
                    |        |           |            |                |
                    |  +-----+-----+ +---+----+ +----+------+         |
                    |  | ChromaDB  | | SQLite | | SQLite    |         |
                    |  | (vetores) | |(scores)| | (pipeline)|         |
                    |  +-----------+ +--------+ +-----------+         |
                    |                                                  |
                    |  +----------------------------------------------+|
                    |  |            Governanca LGPD                    ||
                    |  | PII Detector > Audit Log > Retention Manager  ||
                    |  +----------------------------------------------+|
                    +---------------------------------------------------+
```

---

## Destaques

| Feature | Detalhe |
|---------|---------|
| Multi-agente sem lock-in | Ollama + Claude API com toggle no frontend |
| SSE Streaming | Token-por-token em tempo real com animação |
| Upload inteligente | Drag-and-drop por vaga, classificação automática currículo vs vaga |
| Scorecard transparente | Modal com barras visuais, skill chips (match/missing/extra), detalhes |
| Autenticação JWT | Roles (analyst/manager), controle por endpoint |
| Memória conversacional | Sidebar com histórico, contexto no prompt |
| Docker + CI/CD | Dockerfile, docker-compose, GitHub Actions (144 testes) |

---

## Stack Tecnológico

| Camada | Tecnologia |
|--------|-----------|
| Linguagem | Python 3.11+ |
| LLM (padrão) | Ollama (llama3:8b) — local, zero custo |
| LLM (alternativo) | Anthropic Claude (claude-sonnet-4-6) |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) — local |
| Reranking | cross-encoder/mmarco-mMiniLMv2-L12-H384-v1 — multilíngue |
| Banco vetorial | ChromaDB (file-based, persistente) — dual collections |
| Banco de dados | SQLite (`data/techhire.db`) |
| API | FastAPI |
| Framework de agentes | Implementação própria (sem LangChain/LangGraph) |
| Auth | JWT (PyJWT + bcrypt), RBAC (analyst / manager) |
| Frontend | HTML/JS/CSS vanilla (sem React) |
| Containerização | Docker + Docker Compose |
| CI/CD | GitHub Actions (Python 3.11 + 3.13, 144 testes) |

---

## Funcionalidades

### Triagem de Currículos (RAG)
Perguntas em linguagem natural sobre qualquer candidato indexado:
```
"Quais candidatos têm experiência com RAG e Python?"
"Liste os engenheiros com mais de 5 anos em backend."
"Qual é a formação do candidato mais recente?"
```

### Ranking por Aderência (NL→SQL)
O MatchAgent converte linguagem natural em SQL e interpreta os resultados:
```
"Rankeie os top 5 candidatos para a vaga de Engenheiro de IA."
"Compare os candidatos com score acima de 0.85."
"Qual candidato tem o melhor score de habilidades técnicas?"
```

### Scorecard por Candidato
Detalhamento completo do score de um candidato para uma vaga, com breakdown por dimensão e evidências utilizadas no cálculo.

### Gestão do Pipeline
```
"Mova o candidato para entrevista."
"Qual o status atual do funil de contratação?"
"Gere um e-mail de feedback de rejeição."
```

### Multi-LLM
Troque entre Ollama (local) e Claude por requisição, via parâmetro `provider`:
```bash
curl -X POST http://localhost:8000/agent \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"pergunta": "Quem tem experiência com RAG?", "provider": "claude"}'
```

---

## Algoritmo de Scoring

Cada candidato é pontuado contra cada vaga em quatro dimensões independentes:

| Dimensão | Peso | Como é calculada |
|----------|------|-----------------|
| Habilidades (`skills_score`) | **40%** | Interseção entre skills do candidato e requisitos da vaga; normalizada pelo conjunto maior |
| Experiência (`experience_score`) | **35%** | Razão entre anos do candidato e anos exigidos, com cap em 1.0 |
| Educação (`education_score`) | **15%** | Escala ordinal: pós-graduação (1.0) → graduação (0.90) → técnico (0.75) → cursando (0.70) |
| Bônus sênior (`bonus_score`) | **10%** | Detecta liderança técnica e experiência em escala; 0.5 por critério atendido |

**Score final:**
```
overall = 0.40 × skills + 0.35 × experience + 0.15 × education + 0.10 × bonus
```

O endpoint `GET /matches/{candidate_id}/{job_posting_id}/details` retorna o breakdown completo com evidências (skills correspondidas, anos detectados, nível de educação encontrado) para cada dimensão.

---

## Início Rápido

### Docker (recomendado)
```bash
docker compose up --build

# Na primeira execução, baixe o modelo:
docker compose exec ollama ollama pull llama3:8b

# Acesse: http://localhost:8000/login
# Credenciais: analyst/analyst123  ou  manager/manager123
```

### Execução local
```bash
pip install -r requirements.txt

ollama serve
ollama pull llama3:8b

export ANTHROPIC_API_KEY=sk-ant-...   # opcional

uvicorn src.api.main:app --reload
# Acesse: http://localhost:8000/login
```

### Ingestão de PDFs
```bash
# Coloque PDFs em data/raw/ e execute (requer role manager):
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -d "username=manager&password=manager123" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

curl -X POST http://localhost:8000/ingest \
  -H "Authorization: Bearer $TOKEN"
```

---

## Endpoints

Todos os endpoints (exceto `/`, `/login`, `/dashboard` e `POST /auth/login`) exigem `Authorization: Bearer <token>`.

### Auth
| Método | Path | Papel | Descrição |
|--------|------|-------|-----------|
| POST | /auth/login | — | Login, retorna JWT |
| GET | /auth/me | qualquer | Perfil do usuário atual |
| POST | /auth/register | manager | Criar novo usuário |

### Chat & Agentes
| Método | Path | Descrição |
|--------|------|-----------|
| POST | /chat | Resposta RAG com citações (JSON) |
| POST | /agent | Roteamento multi-agente, resposta completa |
| POST | /agent/stream | Streaming SSE multi-agente |

### Currículos & Candidatos
| Método | Path | Papel | Descrição |
|--------|------|-------|-----------|
| POST | /ingest | manager | Indexar PDFs de `data/raw/` no ChromaDB |
| POST | /ingest/job | manager | Indexar uma vaga (texto ou PDF) |
| GET | /resumes | qualquer | Listar currículos indexados no ChromaDB |
| GET | /resumes/{id}/download | qualquer | Baixar PDF original do candidato |
| GET | /candidates | qualquer | Listar candidatos do banco de dados |
| GET | /job-postings | qualquer | Listar vagas cadastradas |

### Scores & Pipeline
| Método | Path | Papel | Descrição |
|--------|------|-------|-----------|
| GET | /matches/{job_id} | qualquer | Ranking de candidatos para uma vaga |
| GET | /matches/{cand_id}/{job_id}/details | qualquer | Breakdown completo do score |
| POST | /match/{job_id} | manager | Calcular/recalcular scores para uma vaga |
| GET | /pipeline | qualquer | Listar funil de contratação |
| PATCH | /pipeline/{cand_id}/{job_id} | manager | Mover candidato de etapa |

### Governança LGPD (apenas manager)
| Método | Path | Descrição |
|--------|------|-----------|
| GET | /governance/dashboard | KPIs, classificação de dados, alertas de retenção |
| GET | /governance/audit-log | Log de auditoria paginado |
| POST | /governance/purge-expired | Soft-purge de PII expirado |

---

## Decisões de Arquitetura

- **Local-first:** Zero dependência de cloud na configuração padrão. Ollama para LLM, sentence-transformers para embeddings, SQLite para persistência.
- **Roteamento por palavras-chave:** Classificador heurístico sem LLM cobre 95%+ das queries com zero latência extra. O roteamento via LLM foi descartado após benchmark — adicionava 5+ segundos sem ganho de precisão.
- **Dual ChromaDB:** Coleções separadas `resumes` e `job_postings` permitem busca vetorial direcionada; sem ruído cruzado entre tipos de documento.
- **Cross-encoder multilíngue:** `mmarco-mMiniLMv2-L12-H384-v1` treinado em dados multilíngues incluindo PT-BR — reranking mais preciso que modelos English-only para textos de currículos brasileiros.
- **Sem LangChain:** Implementação direta do framework de agentes. Menor overhead, sem abstrações ocultas, mais fácil de inspecionar e debugar.
- **LGPD nativa:** Detecção de PII (CPF, nomes, telefones), mascaramento antes de persistência, audit log com retenção configurável e soft-purge.
- **Streaming SSE:** Tokens emitidos palavra por palavra via Server-Sent Events — sem polling, sem buffering desnecessário.

---

## Testes

```bash
# Suite completa (144 testes)
python -m pytest tests/ --ignore=tests/diagnose_rag.py -v --tb=short

# Por módulo
python -m pytest tests/test_agents.py -v
python -m pytest tests/test_coordinator.py -v
python -m pytest tests/test_database.py -v
```

CI executa automaticamente em Python 3.11 e 3.13 a cada push para `master`.

---

## Variáveis de Ambiente

| Variável | Padrão | Descrição |
|----------|--------|-----------|
| `ANTHROPIC_API_KEY` | — | Necessário apenas para `provider=claude` |
| `JWT_SECRET_KEY` | (dev default) | Alterar em produção |
| `LLM_PROVIDER` | `ollama` | Provider padrão: `ollama` ou `claude` |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | URL do servidor Ollama |

---

## Estrutura do Projeto

```
techhire-ai/
├── src/
│   ├── agents/          # CoordinatorAgent, ResumeAgent, MatchAgent, PipelineAgent
│   ├── api/
│   │   ├── main.py      # FastAPI app, endpoints, scoring algorithm
│   │   ├── auth.py      # JWT, bcrypt, RBAC
│   │   ├── governance.py        # Endpoints LGPD
│   │   ├── conversation_routes.py
│   │   └── templates/   # login.html, index.html (chat), dashboard.html
│   ├── database/        # setup.py (schema), seed.py (users), connection.py
│   ├── governance/      # PII detector, audit log, retention manager
│   ├── ingestion/       # pdf_loader, chunker, embedding, classificação
│   ├── llm/             # LLM router, Ollama client, Claude client
│   ├── retrieval/       # Query engine, prompt builder
│   └── services/        # Conversation memory
├── tests/               # 144 pytest tests
├── scripts/start.sh     # Startup Docker
├── Dockerfile
├── docker-compose.yml
└── CLAUDE.md
```

---

## Autor

Daniel Campetti — Engenheiro Mecânico (UnB) | AI Engineer
GitHub: [github.com/danielcampetti](https://github.com/danielcampetti)
