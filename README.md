# TechHire AI

![CI](https://github.com/danielcampetti/techhire-ai/actions/workflows/ci.yml/badge.svg)
![Python](https://img.shields.io/badge/Python-3.11%2B-blue)
![License](https://img.shields.io/badge/License-MIT-green)
![Tests](https://img.shields.io/badge/Tests-149%20passing-brightgreen)

**Sistema multi-agente de triagem inteligente de currículos com RAG, LGPD e streaming em tempo real.**

Plataforma de recrutamento que ingere currículos e vagas em PDF, processa em banco vetorial e responde perguntas com citações precisas — orquestrando múltiplos agentes especializados para análise de perfis, ranking por aderência e gestão do funil de contratação.

---

## Arquitetura

```
PDF (currículos / vagas)
    → pdf_loader → chunker → embedder (ChromaDB: "resumes" | "job_postings")

Pergunta do recrutador
    → CoordinatorAgent (roteamento por palavras-chave, zero LLM)
        → ResumeAgent  — RAG sobre currículos (ChromaDB)
        → MatchAgent   — NL→SQL→SQLite→NL (scores de aderência)
        → PipelineAgent — mover etapas, funil, e-mail de feedback

Resposta com fontes → SSE streaming → frontend (vanilla JS)
```

### Componentes

| Componente | Responsabilidade |
|------------|-----------------|
| `ResumeAgent` | RAG sobre a coleção `resumes` do ChromaDB |
| `MatchAgent` | Gera SQL → executa → interpreta contra tabelas `matches`/`candidates` |
| `PipelineAgent` | Gerencia estágios (triagem → entrevista → teste_técnico → aprovado) |
| `CoordinatorAgent` | Classifica a intent via heurística de palavras-chave (RESUME / MATCH / PIPELINE / RESUME+MATCH) |

---

## Stack Tecnológico

| Camada | Tecnologia |
|--------|-----------|
| Linguagem | Python 3.11+ |
| LLM (padrão) | Ollama (llama3:8b) — local, zero custo |
| LLM (alternativo) | Anthropic Claude (claude-sonnet-4-6) |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) — local |
| Reranking | cross-encoder/mmarco-mMiniLMv2-L12-H384-v1 — multilíngue |
| Banco vetorial | ChromaDB (file-based, persistente) |
| Banco de dados | SQLite (`data/techhire.db`) |
| API | FastAPI |
| Framework de agentes | Implementação própria (sem LangChain/LangGraph) |
| Auth | JWT (PyJWT + bcrypt), RBAC (analyst / manager) |
| Frontend | HTML/JS/CSS vanilla (sem React) |
| Containerização | Docker + Docker Compose |
| CI/CD | GitHub Actions (Python 3.11 + 3.13, 149 testes) |

---

## Funcionalidades

### Triagem de Currículos
Faça perguntas em linguagem natural sobre qualquer candidato indexado:
```
"Quais candidatos têm experiência com RAG e Python?"
"Qual é a formação do candidato Lucas Mendes?"
"Liste os engenheiros sêniores com mais de 5 anos de experiência."
```

### Ranking por Aderência
O MatchAgent consulta os scores pré-calculados via SQL:
```
"Rankeie os top 5 candidatos para a vaga de Engenheiro de IA."
"Qual o score de aderência da Ana Beatriz para a vaga backend?"
"Compare os candidatos com score acima de 0.85."
```

### Gestão do Pipeline
Mova candidatos entre etapas, gere relatórios do funil, envie feedback:
```
"Mova o candidato #3 para entrevista."
"Qual o status atual do funil de contratação?"
"Gere um e-mail de feedback para o candidato #7."
```

### Multi-LLM
Troque entre Ollama (local, zero custo) e Claude por requisição:
```bash
curl -X POST http://localhost:8000/chat \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"pergunta": "Quem tem experiência com RAG?", "provider": "claude"}'
```

---

## Início Rápido

### Docker (recomendado)
```bash
# Suba tudo com um comando
docker compose up --build

# Na primeira execução, baixe o modelo Ollama
docker compose exec ollama ollama pull llama3:8b

# Acesse em http://localhost:8000/login
# Credenciais: analyst/analyst123 ou manager/manager123
```

### Execução local
```bash
pip install -r requirements.txt

# Inicie o Ollama separadamente
ollama serve
ollama pull llama3:8b

# (Opcional) Claude como backend
export ANTHROPIC_API_KEY=sk-ant-...

uvicorn src.api.main:app --reload
# Acesse http://localhost:8000/login
```

### Ingestão de PDFs
```bash
# Coloque PDFs em data/raw/ e execute:
MANAGER_TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -d "username=manager&password=manager123" | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

curl -X POST http://localhost:8000/ingest \
  -H "Authorization: Bearer $MANAGER_TOKEN"
```

---

## Endpoints

### Auth
| Método | Path | Papel | Descrição |
|--------|------|-------|-----------|
| POST | /auth/login | — | Login, retorna JWT |
| GET | /auth/me | qualquer | Perfil do usuário atual |
| POST | /auth/register | manager | Criar novo usuário |

### Chat & Agentes
| Método | Path | Papel | Descrição |
|--------|------|-------|-----------|
| POST | /chat | analyst, manager | Resposta RAG com citações |
| POST | /agent | analyst, manager | Roteamento multi-agente, JSON completo |
| POST | /agent/stream | analyst, manager | Streaming SSE multi-agente |

### Dados
| Método | Path | Papel | Descrição |
|--------|------|-------|-----------|
| POST | /ingest | manager | Indexar PDFs de data/raw/ |
| GET | /resumes | analyst, manager | Listar currículos indexados |
| GET | /candidates | analyst, manager | Listar candidatos (BD) |
| GET | /job-postings | analyst, manager | Listar vagas |
| GET | /pipeline | analyst, manager | Listar funil de contratação |
| GET | /matches/{job_id} | analyst, manager | Ranking de candidatos por vaga |
| POST | /match/{job_id} | manager | Calcular scores para uma vaga |
| PATCH | /pipeline/{cand_id}/{job_id} | manager | Mover candidato de etapa |

### Governança LGPD (apenas manager)
| Método | Path | Descrição |
|--------|------|-----------|
| GET | /governance/dashboard | KPIs, classificação de dados, alertas de retenção |
| GET | /governance/audit-log | Log de auditoria paginado |
| POST | /governance/purge-expired | Soft-purge de PII expirado |

---

## Decisões de Arquitetura

- **Local-first:** Zero dependência de cloud no config padrão. Ollama para LLM, sentence-transformers para embeddings, SQLite para dados.
- **Roteamento por palavras-chave:** O classificador heurístico trata 95%+ das queries com zero latência. O roteamento via LLM foi descartado após benchmark — adicionava 5+ segundos sem ganho de precisão.
- **Dual ChromaDB:** Coleções separadas para `resumes` e `job_postings` permitem busca vetorial direcionada por tipo de documento.
- **Cross-encoder multilíngue:** `mmarco-mMiniLMv2-L12-H384-v1` treinado em dados multilíngues incluindo português brasileiro — recupera mais de textos legais em PT-BR do que modelos English-only.
- **Sem LangChain:** Implementação direta do framework de agentes. Menor overhead, sem abstrações desnecessárias, mais fácil de debugar.
- **LGPD nativa:** Detecção de PII (CPF, nomes, telefones), mascaramento, audit log com retenção configurável e soft-purge.
- **Streaming SSE:** Tokens são emitidos palavra por palavra para o frontend via Server-Sent Events sem polling.

---

## Testes

```bash
# Suite completa (149 testes)
python -m pytest tests/ --ignore=tests/diagnose_rag.py -v --tb=short

# Por módulo
python -m pytest tests/test_agents.py -v
python -m pytest tests/test_coordinator.py -v
python -m pytest tests/test_database.py -v
```

CI executa automaticamente em Python 3.11 e 3.13 a cada push.

---

## Variáveis de Ambiente

```env
ANTHROPIC_API_KEY=sk-ant-...   # opcional, para features Claude
JWT_SECRET_KEY=seu-segredo     # alterar em produção
LLM_PROVIDER=ollama            # ou "claude"
```
