# LGPD Governance System — Design Spec
**Date:** 2026-04-12  
**Project:** ComplianceAgent (Phase 4 — Governance & Observability)  
**Status:** Approved

---

## Problem Statement

ComplianceAgent processes sensitive Brazilian financial data (CPFs, client names, transaction amounts) in every Data Agent query. This data is stored in plain text in `agent_log`, which means our compliance tool itself violates LGPD (Brazil's data protection law). This spec defines the governance layer that fixes this.

---

## Scope

Six components, implemented in order:

1. PII Detection & Masking Module
2. Enhanced Audit Trail (new `audit_log` table + `audit.py`)
3. Data Retention Manager
4. Privacy Notice & Consent (frontend)
5. Governance Dashboard API (`/governance/*` endpoints)
6. Integration of PII masking into the agent pipeline

---

## Architecture & Data Flow

```
User question
    │
    ▼
POST /agent (FastAPI)
    │  generates session_id
    ▼
CoordinatorAgent.process()
    ├── _classify() → route
    ├── agent.answer() → AgentResponse
    │
    ├── pii_detector.detect_pii(response.answer)
    │       → list[PIIMatch]
    │
    ├── audit.log_interaction(session_id, agent, input, output, ...)
    │       → masks PII, writes to audit_log, updates daily stats
    │
    └── CoordinatorResponse(
            ...existing fields...,
            pii_detected=bool,
            data_classification=str,
            session_id=str
        )

GET /governance/dashboard        → queries audit_log + daily_stats
GET /governance/audit-log        → paginated audit_log (already masked)
GET /governance/retention-report → calls retention.get_retention_report()
```

**Key invariant:** User-facing `resposta_final` is **never masked**. PII masking applies only to what is stored in `audit_log.input_masked` / `output_masked`. The `pii_detected` flag on the response tells the frontend to show the 🔒 LGPD notice.

---

## Component 1 — PII Detector (`src/governance/pii_detector.py`)

### Detection patterns (compiled regex)

| Type | Pattern | Partial mask | Full mask |
|------|---------|-------------|----------|
| CPF | `\d{3}\.?\d{3}\.?\d{3}-?\d{2}` | `123.***.**9-00` | `[CPF_MASCARADO]` |
| Name | 2+ consecutive Title-Case words not in exclusion list | `R. A. Costa` | `[NOME_MASCARADO]` |
| Money ≥ R$10k | `R\$\s*[\d.,]+` | `R$ *.**` | `[VALOR_MASCARADO]` |
| Phone | `\(?\d{2}\)?\s*\d{4,5}-?\d{4}` | `(11) ****-1234` | `[TELEFONE_MASCARADO]` |
| Email | standard email regex | `j***@email.com` | `[EMAIL_MASCARADO]` |

### Name detection strategy

Two signals combined:
- Regex for sequences of 2+ Title-Case words
- List of the 100 most common Brazilian first names (single-word match also qualifies)

Exclusion set (~30 terms): `"Art."`, `"Resolução"`, `"Circular"`, `"COAF"`, `"Banco Central"`, `"LGPD"`, `"CLT"`, `"PIX"`, `"STR"`, `"RSFN"`, `"BCB"`, `"CMN"`, `"CVM"`, and similar regulatory/institutional terms.

### Overlap handling

When two patterns match overlapping spans, the longer match wins. Replacements are applied right-to-left by position to avoid offset drift.

### Money threshold

Values of R$10,000+ are flagged. Configurable via `MONEY_THRESHOLD = 10_000` module-level constant.

### Public API

```python
class PIIType(Enum): CPF | NAME | MONEY | PHONE | EMAIL
class MaskLevel(Enum): PARTIAL | FULL

@dataclass
class PIIMatch:
    type: PIIType
    original: str
    start: int
    end: int
    masked_partial: str
    masked_full: str

def detect_pii(text: str) -> list[PIIMatch]: ...
def mask_text(text: str, level: MaskLevel = MaskLevel.FULL) -> tuple[str, list[PIIMatch]]: ...
def has_pii(text: str) -> bool: ...
def count_pii(text: str) -> dict[str, int]: ...
```

### Tests (`tests/test_pii_detector.py`)

- Each PII type: detection + both mask levels
- CPF: formatted and unformatted variants
- Name: multi-word, single Brazilian first name, exclusion list terms (should NOT match)
- Money: above and below threshold
- Overlap: CPF inside longer number sequence (should not match)
- `count_pii`: returns correct counts by type
- `has_pii`: quick boolean check

---

## Component 2 — Database Schema (`src/database/setup.py`)

### Strategy: keep `agent_log`, add `audit_log` alongside it

`agent_log` is preserved as a legacy table — no data loss, no risky migration on live DB.
`audit_log` is the new LGPD-compliant log; all agents write here going forward.

### New table: `audit_log`

```sql
CREATE TABLE IF NOT EXISTS audit_log (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id            TEXT NOT NULL,
    timestamp             TEXT NOT NULL,
    agent_name            TEXT NOT NULL,
    action                TEXT NOT NULL,
    input_original        TEXT,           -- NULL if input had PII
    input_masked          TEXT NOT NULL,  -- always populated
    output_original       TEXT,           -- NULL if output had PII
    output_masked         TEXT NOT NULL,  -- always populated
    input_has_pii         BOOLEAN DEFAULT FALSE,
    output_has_pii        BOOLEAN DEFAULT FALSE,
    pii_types_detected    TEXT,           -- JSON: {"cpf": 1, "name": 2}
    data_classification   TEXT DEFAULT 'public',
    provider              TEXT,
    model                 TEXT,
    tokens_used           INTEGER,
    chunks_ids            TEXT,           -- JSON array
    chunks_count          INTEGER DEFAULT 0,
    retention_expires_at  TEXT,
    pii_purged            BOOLEAN DEFAULT FALSE
);
```

### New table: `governance_daily_stats`

```sql
CREATE TABLE IF NOT EXISTS governance_daily_stats (
    date                      TEXT PRIMARY KEY,
    total_queries             INTEGER DEFAULT 0,
    queries_with_pii          INTEGER DEFAULT 0,
    classification_public     INTEGER DEFAULT 0,
    classification_internal   INTEGER DEFAULT 0,
    classification_confidential INTEGER DEFAULT 0,
    classification_restricted INTEGER DEFAULT 0,
    pii_cpf_count             INTEGER DEFAULT 0,
    pii_name_count            INTEGER DEFAULT 0,
    pii_money_count           INTEGER DEFAULT 0
);
```

Updated via `INSERT OR REPLACE` upsert on each `log_interaction()` call — avoids expensive aggregate queries on the dashboard endpoint.

---

## Component 2 — Audit Module (`src/governance/audit.py`)

### Responsibilities

1. `generate_session_id() -> str` — 8-char UUID prefix
2. `classify_query(agent_name, has_pii, query) -> str` — classification rules:
   - DataAgent with PII → `"restricted"`
   - DataAgent without PII → `"confidential"` (financial data regardless)
   - ActionAgent → `"confidential"` (modifies data)
   - KnowledgeAgent → `"public"` (regulatory documents)
   - KNOWLEDGE+DATA → `"confidential"`
3. `get_retention_expiry(classification) -> str` — ISO date:
   - `"restricted"` → today + 1 year
   - `"confidential"` → today + 2 years
   - `"public"` / `"internal"` → today + 5 years
4. `log_interaction(session_id, agent_name, action, input_text, output_text, provider, model, tokens_used, chunks_count) -> int` — detects PII, masks, classifies, inserts, upserts daily stats, returns `audit_log` row ID

**Note:** `log_interaction` is `async def` for consistency with the agent layer, but all DB operations inside are synchronous (matching existing `get_db()` pattern).

---

## Component 3 — Retention Manager (`src/governance/retention.py`)

### `purge_expired_pii() -> dict`

Runs a single SQL UPDATE — rows are **never deleted**:
```sql
UPDATE audit_log
SET input_original  = '[DADO_EXPIRADO]',
    output_original = '[DADO_EXPIRADO]',
    input_masked    = '[DADO_EXPIRADO]',
    output_masked   = '[DADO_EXPIRADO]',
    pii_purged      = TRUE
WHERE retention_expires_at <= <today>
  AND pii_purged = FALSE
  AND input_has_pii = TRUE
```

Metadata (agent_name, timestamp, classification, token counts) is preserved for the 5-year regulatory audit trail per Art. 23 of Resolution CMN 4.893.

Returns `{'rows_purged': N, 'oldest_purged': date, 'newest_purged': date}`.

### `get_retention_report() -> dict`

Aggregate queries on `audit_log`:
- Total records, records with PII, records already purged
- Records expiring within 30 days (upcoming purge candidates)
- Oldest record date
- Storage breakdown by classification

No scheduled execution in this phase — on-demand only. Cron automation is Phase 4.

---

## Component 4 — Coordinator Integration (`src/agents/coordinator.py`)

### Changes to `CoordinatorAgent.process()`

1. Generate `session_id = audit.generate_session_id()` at entry
2. After each agent returns, run `pii_detector.detect_pii(response.answer)`
3. Call `await audit.log_interaction(session_id, ...)` — replaces the old `self._log()` method entirely
4. For `KNOWLEDGE+DATA` routing: log both sub-agent calls separately under the same `session_id`
5. `log_id` in `CoordinatorResponse` becomes the `audit_log` row ID from the final agent call

### New fields on `CoordinatorResponse`

```python
pii_detected: bool = False       # True if any agent response had PII
data_classification: str = "public"  # highest classification across agents used
session_id: str = ""             # for frontend correlation
```

### LGPD footer injection

If `pii_detected=True` and `"data"` in `agentes_utilizados`, the Coordinator appends to `resposta_final`:
```
\n\n---\n🔒 Esta resposta contém dados pessoais protegidos pela LGPD. Uso restrito a fins de compliance.
```

`DataAgent` itself has no PII awareness — stays clean.

---

## Component 5 — Governance API (`src/api/governance.py`)

Three endpoints registered in `main.py` via `app.include_router(governance_router)`:

### `GET /governance/dashboard`

Queries `governance_daily_stats` for the last 30 days and `audit_log` for retention data. Alerts block is rule-based: if `records_expiring_30_days > 0`, emits a warning; otherwise `"Nenhum alerta de governança ativo"`.

```json
{
  "periodo": "últimos 30 dias",
  "metricas": {
    "total_consultas": 150,
    "consultas_com_pii": 45,
    "percentual_pii": 30.0,
    "por_classificacao": {"public": 80, "internal": 25, "confidential": 40, "restricted": 5},
    "por_agente": {"knowledge": 80, "data": 45, "action": 20, "coordinator": 5},
    "pii_por_tipo": {"cpf": 30, "name": 45, "money": 20, "phone": 2, "email": 1}
  },
  "retencao": {
    "registros_com_pii": 45,
    "registros_pii_purgados": 0,
    "registros_expirando_30_dias": 0,
    "registro_mais_antigo": "2026-04-01"
  },
  "alertas": ["Nenhum alerta de governança ativo"]
}
```

### `GET /governance/audit-log`

Paginated query against `audit_log`. Returns masked fields only (`input_masked`, `output_masked` — never `_original`).

Query params: `page` (default 1), `limit` (default 20, max 100), `classification`, `agent`, `has_pii` (bool).

Response: `{ "total": N, "page": N, "pages": N, "registros": [...] }`

### `GET /governance/retention-report`

Thin wrapper around `retention.get_retention_report()`. No params.

All three endpoints call `init_db()` to ensure tables exist.

---

## Component 6 — Frontend (`src/api/templates/index.html`)

### Privacy modal

- Shown on first visit; blocked by `localStorage` key `"privacy_accepted"`
- Centered overlay, dark theme (`#1a1a2e` background, matching existing palette)
- Portuguese text per spec
- `acceptPrivacy()` sets localStorage and hides modal

### PII notice footer

When response JSON has `pii_detected: true`, append inside the chat bubble:
```html
<div class="pii-notice">
  🔒 Esta resposta contém dados pessoais protegidos pela LGPD. Uso restrito a fins de compliance.
</div>
```

### Classification badge

Small inline badge next to the routing label, colour-coded:
- `public` → grey
- `internal` → blue
- `confidential` → yellow (`#f0b429`)
- `restricted` → red (`#e53e3e`)

### JS changes

Existing `fetch('/agent', ...)` handler reads `pii_detected` and `data_classification` from response JSON before rendering the message bubble. No new fetch calls needed.

---

## New Files

```
src/
  governance/
    __init__.py
    pii_detector.py
    audit.py
    retention.py
  api/
    governance.py          (new)
    main.py                (updated — include governance router)
  database/
    setup.py               (updated — 2 new tables)
  agents/
    coordinator.py         (updated — session_id, audit, pii fields on response)

tests/
  test_pii_detector.py     (new)
  test_audit.py            (new)
  test_governance_api.py   (new)
```

---

## Implementation Order

1. `pii_detector.py` + `tests/test_pii_detector.py` — test in isolation
2. `setup.py` — add new tables, verify with SQLite
3. `audit.py` + `tests/test_audit.py` — test logging with PII masking
4. `retention.py` — test purge logic
5. `coordinator.py` — integrate session_id, audit logging, PII fields on response
6. `governance.py` + register in `main.py`
7. `index.html` — privacy modal, PII notice, classification badge
8. `tests/test_governance_api.py` — end-to-end API tests
9. Update `CLAUDE.md`

---

## Testing the Complete Flow

```bash
# 1. Data Agent query with PII → pii_detected=true, classification=restricted
curl -X POST http://localhost:8000/agent \
  -d '{"pergunta": "Quais transações do Roberto Alves Costa não foram reportadas ao COAF?"}'

# 2. Audit log — PII should be masked
curl "http://localhost:8000/governance/audit-log?limit=1"
# Expected: [NOME_MASCARADO] instead of "Roberto Alves Costa"

# 3. Governance dashboard
curl http://localhost:8000/governance/dashboard

# 4. Knowledge Agent query (no PII) → pii_detected=false, classification=public
curl -X POST http://localhost:8000/agent \
  -d '{"pergunta": "Qual o prazo da Resolução 5.274?"}'

# 5. Retention report
curl http://localhost:8000/governance/retention-report
```

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| `agent_log` migration | Keep both tables | No data loss, safe migration on live DB |
| PII masking layer | Coordinator-centric | Single audit choke-point; agents stay clean |
| User-facing responses | Never masked | Users need actual data to do their work |
| `retention-report` | Dedicated endpoint | Explicit in test flow; `get_retention_report()` already standalone |
| Money threshold | R$10,000+ | Compliance relevance threshold; configurable constant |
| DB operations | Synchronous in async wrapper | Matches existing `get_db()` pattern |
| Purge strategy | Overwrite text, keep row | Preserves 5-year metadata for Art. 23 compliance |
