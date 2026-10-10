# Interface: Tasks API (HTTP)

> Feature: `002-finagent-agentpulse`
> Contrato: `POST /tasks`, `GET /tasks/{id}`
> Autenticação: API Key (header `Authorization: Bearer <key>`)
> Papel requerido: `analyst`

## 1. POST /tasks

### Request

```http
POST /tasks HTTP/1.1
Host: localhost:8000
Authorization: Bearer <analyst-api-key>
Idempotency-Key: <string>          # obrigatório, escopo por api_key_id
Content-Type: application/json

{
  "symbol": "PETR4",               # obrigatório, sanitizado upper/strip
  "acknowledge_simulated": true    # opcional, default false
}
```

**Validações:**
- `symbol`: não vazio, `strip().upper()` → `INVALID_SYMBOL` se falhar
- `acknowledge_simulated`: boolean, default `false`
- `Idempotency-Key`: header obrigatório → `422` se ausente
- Role da API key deve ser `analyst` → `403` se `approver`

### Response

| Status | Condição | Headers | Body |
|--------|----------|---------|------|
| `202` | Nova tarefa criada | — | `{"task_id": "uuid", "status": "PENDING"}` |
| `200` | Replay idempotente | `Idempotent-Replay: true` | Mesmo body do `202` original |
| `409` | Mesma chave + payload diferente | — | `{"error": "idempotency_key_reused_with_different_payload"}` |
| `422` | Validação falhou (symbol, idempotency-key ausente) | — | `{"detail": [...]}` |
| `403` | Role incorreta (`approver` tentando criar) | — | `{"detail": "analyst role required"}` |
| `429` | Limite tarefas ativas por `api_key_id` excedido | `Retry-After: <segundos>` | `{"detail": "max active tasks exceeded"}` |
| `401` | API key inválida/ausente | — | `{"detail": "invalid api key"}` |

**Idempotência:**
- Escopo: `(api_key_id, Idempotency-Key)` — constraint única em `idempotency_keys`
- Tabela armazena: `payload_hash` (sha256 do body), `response_status`, `response_body`
- Replay retorna body original + header `Idempotent-Replay: true`

**Limite ativas:** Conta tarefas em `PENDING | RUNNING | AWAITING_APPROVAL | APPROVED` por `api_key_id`. Default: 10 (configurável `max_active_tasks_per_key`).

### Rate limiting

| Endpoint | Limite (default) | Escopo |
|----------|------------------|--------|
| `POST /tasks` | 10 req/s | por `api_key_id` |
| `GET /tasks/{id}` | 30 req/s | por `api_key_id` |
| `POST /tasks/{id}/approve` | 20 req/s | por `api_key_id` |
| `POST /tasks/{id}/reject` | 20 req/s | por `api_key_id` |

## 2. GET /tasks/{id}

### Request

```http
GET /tasks/{task_id} HTTP/1.1
Host: localhost:8000
Authorization: Bearer <analyst|approver-api-key>
```

**Autorização:** Ambos papéis podem ler. Dados sensíveis filtrados conforme role.

### Response

| Status | Condição | Body |
|--------|----------|------|
| `200` | Sucesso | Objeto `TaskDetail` (ver abaixo) |
| `404` | Tarefa não existe | `{"detail": "task not found"}` |
| `403` | Role incorreta (não `analyst` nem `approver`) | `{"detail": "forbidden"}` |

### TaskDetail (JSON)

```json
{
  "task_id": "uuid",
  "execution_id": "uuid",
  "symbol": "PETR4",
  "asset_class": "equity",
  "status": "AWAITING_APPROVAL",
  "data_quality": "LIVE",
  "stale_warning": false,
  "acknowledge_simulated": false,
  "graph_version": "1.0.0",
  "created_at": "2026-10-05T10:00:00Z",
  "updated_at": "2026-10-05T10:05:00Z",
  "approved_at": null,
  "heartbeat_at": "2026-10-05T10:04:30Z",
  "attempts": 0,
  "reject_reason": null,
  "snapshot_hash": "sha256...",
  "market_payload": { "symbol": "PETR4", "source": "yahoo_finance", "fetched_at": "...", "data_quality": "LIVE", ... },
  "quant_metrics": { "vol_30d": 0.2345, "sharpe_1y": 1.23, ... },
  "report_draft": "<html>...</html>",
  "audit_result": { "passed": true, "details": [] },
  "published_report": null
}
```

**Campos condicionais:**
- `approved_at`, `published_report`: só se status terminal `PUBLISHED`
- `reject_reason`: só se `REJECTED`
- `report_draft` + `audit_result` + `snapshot_hash`: só se `AWAITING_APPROVAL` ou `APPROVED`
- `market_payload`, `quant_metrics`: sempre após respectivos nós

## 3. Códigos de erro padronizados

| Código HTTP | Código erro | Descrição |
|-------------|-------------|-----------|
| `400` | `invalid_request` | Body malformado |
| `401` | `unauthorized` | API key inválida/ausente |
| `403` | `forbidden` | Role não tem permissão (ex: `approver` no POST /tasks) |
| `404` | `not_found` | Recurso não existe |
| `409` | `idempotency_conflict` | Mesma chave + payload diferente |
| `409` | `state_conflict` | Transição inválida (ex: approve em tarefa não `AWAITING_APPROVAL`) |
| `410` | `expired` | Tarefa `EXPIRED` (TTL 7 dias) |
| `422` | `validation_error` | Campos inválidos/ausentes |
| `429` | `rate_limited` / `max_active_tasks` | Limite excedido |
| `500` | `internal_error` | Erro inesperado (logged) |
| `503` | `service_unavailable` | Dependência indisponível (Postgres, Redis) |

## 4. Idempotency-Key — Especificação IETF

- Header: `Idempotency-Key` (conforme [IETF draft](https://datatracker.ietf.org/doc/draft-ietf-httpapi-idempotency-key-headers/), registrar versão+data)
- Escopo: por `api_key_id` (não global) — `UNIQUE (api_key_id, key)`
- Semântica: replay seguro retorna resposta original (`200` + `Idempotent-Replay: true`)
- Payload hash: `sha256(request_body)` evita reuso com payload diferente
- TTL: chaves expiram após 24h (job de limpeza), replay dentro do TTL

## 5. Versionamento

- API versionada via URL path: `/v1/tasks` (futuro)
- `graph_version` no `TaskDetail` para compatibilidade de checkpoint
- Mudanças breaking → nova versão `/v2/`