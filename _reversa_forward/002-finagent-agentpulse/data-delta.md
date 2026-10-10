# Data Delta: Migração FinAgent para Infraestrutura AgentPulse

> Feature: `002-finagent-agentpulse`
> Data: `2026-10-05`
> Base: `_reversa_sdd/architecture.md#3` (ERD), `_reversa_sdd/domain.md` (schemas)

## 1. Resumo conceitual

A migração adiciona **persistência operacional** ao modelo existente: o FinAgent hoje roda em memória (schemas Pydantic imutáveis). A feature introduz tabelas de estado, eventos, idempotência, métricas persistidas e publicação — sem alterar os schemas de domínio (`MarketDataPayload`, `QuantAnalysisMetrics`, `AgentState` permanecem inalterados).

## 2. Novas tabelas

### 2.1 `tasks` — Estado central da execução

| Coluna | Tipo | Constraints | Descrição |
|--------|------|-------------|-----------|
| `task_id` | UUID | PK | Identificador da execução (= `execution_id` = Celery task_id = LangGraph `thread_id`) |
| `symbol` | VARCHAR(32) | NOT NULL | Ativo analisado (ex: `PETR4`, `AAPL`, `USD/BRL`) |
| `asset_class` | VARCHAR(16) | NOT NULL | `equity` \| `fx` \| `crypto` \| `other` (para `stale_max_age_days`) |
| `status` | VARCHAR(32) | NOT NULL, DEFAULT `PENDING` | `PENDING` \| `RUNNING` \| `AWAITING_APPROVAL` \| `APPROVED` \| `PUBLISHED` \| `REJECTED` \| `EXPIRED` \| `FAILED` \| `BUDGET_EXCEEDED` \| `DATA_QUALITY_BLOCKED` |
| `execution_id` | VARCHAR(64) | NOT NULL, UNIQUE | Chave de idempotência externa (mesmo `task_id` na prática) |
| `graph_version` | VARCHAR(16) | NOT NULL | Versão do grafo no momento da criação (`GRAPH_VERSION`) |
| `acknowledge_simulated` | BOOLEAN | DEFAULT FALSE | Flag da request para permitir `SIMULATED` fora de prod |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Criação da tarefa |
| `updated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Última transição de estado |
| `approved_at` | TIMESTAMPTZ | NULLABLE | Timestamp da aprovação humana |
| `heartbeat_at` | TIMESTAMPTZ | NULLABLE | Último heartbeat do worker (para reaper) |
| `locked_by` | VARCHAR(64) | NULLABLE | Worker ID que detém lock (fallback lease) |
| `lease_until` | TIMESTAMPTZ | NULLABLE | Expiração do lease (fallback) |
| `attempts` | INT | DEFAULT 0 | Contador de reenfileiramentos (reaper, reentrega) |
| `reject_reason` | VARCHAR(32) | NULLABLE | `data_quality` \| `numbers_mismatch` \| `policy` \| `other` |
| `snapshot_hash` | BYTEA | NULLABLE | Hash do snapshot visto pelo aprovador (para conferência na publicação) |

**Índices**: `(status, updated_at)` para reaper; `(symbol, created_at)` para consultas analíticas.

### 2.2 `task_events` — Trilha de auditoria imutável

| Coluna | Tipo | Constraints | Descrição |
|--------|------|-------------|-----------|
| `seq` | BIGSERIAL | PK | Sequencial global |
| `task_id` | UUID | NOT NULL, FK → `tasks.task_id` | Referência à tarefa |
| `event_type` | VARCHAR(64) | NOT NULL | `TASK_CREATED` \| `STATE_TRANSITION` \| `CHECKPOINT_SAVED` \| `REVIEW_READY` \| `APPROVAL_DECISION` \| `PUBLICATION` \| `REAPER_ACTION` \| `BUDGET_EXCEEDED` \| `DATA_QUALITY_BLOCKED` \| `MARKET_DATA_COLLECTED` |
| `payload_jsonb` | JSONB | NOT NULL | Dados do evento (estado, métricas, decisão, etc.) |
| `chain_hash` | BYTEA | NOT NULL | Hash encadeado: `sha256(lag(chain_hash) || payload_jsonb || created_at || actor_id)` |
| `actor_role` | VARCHAR(16) | NOT NULL | `analyst` \| `approver` \| `system` |
| `actor_id` | VARCHAR(64) | NOT NULL | `api_key_id` ou `worker_id` |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Timestamp do evento |

**Trigger**: `AFTER INSERT` calcula `chain_hash` via `LAG` window function.
**Roles Postgres**: `app_user` (INSERT/SELECT), `retention_role` (DELETE/UPDATE retenção), `migrator` (DDL).

### 2.3 `idempotency_keys` — Chaves de idempotência por API key

| Coluna | Tipo | Constraints | Descrição |
|--------|------|-------------|-----------|
| `api_key_id` | UUID | NOT NULL, PK (parte) | Escopo da idempotência (não global) |
| `key` | VARCHAR(128) | NOT NULL, PK (parte) | Valor do header `Idempotency-Key` |
| `task_id` | UUID | NOT NULL, FK → `tasks.task_id` | Tarefa criada/replay |
| `payload_hash` | BYTEA | NOT NULL | `sha256(request_body)` para detectar reuso com payload diferente |
| `response_status` | INT | NOT NULL | Status HTTP da resposta original (202, 200, 409, etc.) |
| `response_body` | JSONB | NOT NULL | Corpo da resposta original (para replay) |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Criação da chave |

**Constraint única**: `(api_key_id, key)` — mesma chave + mesma API key = mesmo resultado.

### 2.4 `market_payloads` — Dados de mercado idempotentes por execução

| Coluna | Tipo | Constraints | Descrição |
|--------|------|-------------|-----------|
| `task_id` | UUID | NOT NULL, PK (parte), FK → `tasks.task_id` | Execução |
| `symbol` | VARCHAR(32) | NOT NULL, PK (parte) | Ativo |
| `source` | VARCHAR(32) | NOT NULL, PK (parte) | `yahoo_finance` \| `bcb` \| `mock` |
| `payload_jsonb` | JSONB | NOT NULL | `MarketDataPayload` serializado |
| `fetched_at` | TIMESTAMPTZ | NOT NULL | Momento da coleta |
| `data_quality` | VARCHAR(16) | NOT NULL | `LIVE` \| `STALE` \| `SIMULATED` |

**Constraint única**: `(task_id, symbol, source)` — `ON CONFLICT DO NOTHING` garante idempotência por execução.

### 2.5 `quant_metrics` — Métricas quantitativas persistidas (para auditoria e golden tests)

| Coluna | Tipo | Constraints | Descrição |
|--------|------|-------------|-----------|
| `task_id` | UUID | NOT NULL, PK, FK → `tasks.task_id` | Execução |
| `symbol` | VARCHAR(32) | NOT NULL | Ativo |
| `metrics_json` | JSONB | NOT NULL | `QuantAnalysisMetrics` serializado (dict chave→valor) |
| `hash` | BYTEA | NOT NULL | `sha256(metrics_json)` para detecção de mudança |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Persistência |

**Constraint única**: `(task_id, symbol)` — `ON CONFLICT DO NOTHING` (idempotente).
**Uso**: Auditoria compara `StructuredReport` com esta tabela (não só checkpoint, que é podado).

### 2.6 `published` — Publicação única garantida

| Coluna | Tipo | Constraints | Descrição |
|--------|------|-------------|-----------|
| `task_id` | UUID | PK, FK → `tasks.task_id` | Execução |
| `report_jsonb` | JSONB | NOT NULL | Relatório final (`StructuredReport` serializado) |
| `published_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Momento da publicação |
| `published_by` | UUID | NOT NULL | `api_key_id` do aprovador |
| `snapshot_hash` | BYTEA | NOT NULL | Hash do snapshot aprovado (conferência) |

**Constraint única**: `task_id` — garante exactly-once publication.

### 2.7 `api_keys` — Autenticação e autorização

| Coluna | Tipo | Constraints | Descrição |
|--------|------|-------------|-----------|
| `api_key_id` | UUID | PK | Identificador da chave |
| `hashed_key` | VARCHAR(256) | NOT NULL, UNIQUE | Hash da chave (bcrypt/argon2) |
| `role` | VARCHAR(16) | NOT NULL | `analyst` \| `approver` |
| `name` | VARCHAR(128) | NOT NULL | Nome amigável |
| `created_at` | TIMESTAMPTZ | DEFAULT NOW() | Criação |
| `revoked_at` | TIMESTAMPTZ | NULLABLE | Revogação |

## 3. Mudanças em schemas Pydantic existentes (zero alteração)

| Schema | Status | Observação |
|--------|--------|------------|
| `MarketDataPayload` | ✅ Inalterado | Ganha campos opcionais `source`, `fetched_at`, `ttl_seconds`, `raw_sample_hash`, `data_quality`, `stale_warning` via herança/extensão no collector |
| `QuantAnalysisMetrics` | ✅ Inalterado | Persistido em `quant_metrics.metrics_json` |
| `AgentState` | ✅ Inalterado | Estado do grafo LangGraph (checkpointer) |

## 4. Migrações necessárias (ordem)

1. **001_create_roles.sql** — Roles `app_user`, `retention_role`, `migrator` + grants
2. **002_create_tasks_table.sql** — Tabela `tasks` com índices
3. **003_create_task_events.sql** — `task_events` + trigger `chain_hash`
4. **004_create_idempotency_keys.sql** — `idempotency_keys`
5. **005_create_market_payloads.sql** — `market_payloads` + unique constraint
6. **006_create_quant_metrics.sql** — `quant_metrics` + unique constraint
7. **007_create_published.sql** — `published` + unique constraint
8. **008_create_api_keys.sql** — `api_keys`
9. **009_langgraph_checkpointer.sql** — Tabelas do `PostgresSaver` (executadas pelo `migrator` no deploy)
10. **010_add_stale_config.sql** — Tabela `stale_config` ou entrada em `config` para `stale_max_age_days` por classe

## 5. Retenção

| Tabela | Regra | Role | Frequência |
|--------|-------|------|------------|
| `task_events` | `status` terminal + `updated_at > 365 dias` | `retention_role` | Diária |
| `market_payloads` | `task_id` em tarefa terminal + 365 dias | `retention_role` | Diária |
| `quant_metrics` | `task_id` em tarefa terminal + 365 dias | `retention_role` | Diária |
| `published` | `task_id` em tarefa terminal + 365 dias | `retention_role` | Diária |
| `checkpoints` (LangGraph) | `status` terminal + 7 dias | `retention_role` | Diária |

## 6. Compatibilidade com modo legacy (`--legacy`)

- Modo legacy **não usa** nenhuma tabela acima
- Executa pipeline original em memória (schemas Pydantic apenas)
- Sem checkpoints, sem idempotência, sem aprovação, sem auditoria persistida
- Aviso no `--help`: "Modo legacy NÃO tem durabilidade, retomada nem aprovação humana"

## 7. Referências

- `_reversa_sdd/architecture.md#3` — ERD original (3 schemas)
- `_reversa_sdd/domain.md` — RN-01 a RN-06, glossário
- `requirements.md` seções 4, 5, 7, 10 — regras de negócio, RFs, critérios, decisões