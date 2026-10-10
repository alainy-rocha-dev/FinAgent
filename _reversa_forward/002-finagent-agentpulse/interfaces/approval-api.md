# Interface: Approval API (HTTP)

> Feature: `002-finagent-agentpulse`
> Contrato: `POST /tasks/{id}/approve`, `POST /tasks/{id}/reject`
> Autenticação: API Key (header `Authorization: Bearer <key>`)
> Papel requerido: `approver`

## 1. POST /tasks/{id}/approve

### Request

```http
POST /tasks/{task_id}/approve HTTP/1.1
Host: localhost:8000
Authorization: Bearer <approver-api-key>
X-Snapshot-Hash: <sha256-hex>        # obrigatório
Content-Type: application/json

{
  "justification": "Métricas conferem, dados atuais"  # opcional
}
```

**Headers obrigatórios:**
- `Authorization: Bearer <key>` — role deve ser `approver` → `403` se `analyst`
- `X-Snapshot-Hash` — hash do snapshot visto pelo aprovador (obtido em `GET /tasks/{id}` ou UI). Comparado com `task_events` mais recente (`APPROVAL_DECISION` ou `REVIEW_READY`). Mismatch → `409`.

**Body:**
- `justification`: string opcional (motivo da aprovação)

### Response

| Status | Condição | Body |
|--------|----------|------|
| `200` | Aprovação aceita, resume enfileirado | `{"task_id": "uuid", "status": "APPROVED", "message": "Resume enfileirado"}` |
| `403` | Role incorreta (`analyst`) | `{"detail": "approver role required"}` |
| `404` | Tarefa não existe | `{"detail": "task not found"}` |
| `409` | Estado inválido (não `AWAITING_APPROVAL`) | `{"detail": "task not in AWAITING_APPROVAL", "current_status": "..."}` |
| `409` | Hash mismatch | `{"detail": "snapshot_hash mismatch", "expected": "sha256...", "received": "sha256..."}` |
| `410` | Tarefa `EXPIRED` (TTL 7 dias) | `{"detail": "task expired", "ttl_hours": 168}` |
| `422` | `X-Snapshot-Hash` ausente | `{"detail": "X-Snapshot-Hash header required"}` |

**Efeitos colaterais:**
- Transição atômica: `AWAITING_APPROVAL` → `APPROVED` (via `task-state-machine` com `UPDATE ... WHERE status = 'AWAITING_APPROVAL'`)
- Evento `APPROVAL_DECISION` gravado em `task_events` com `{decision: "approved", justification, snapshot_hash, actor_role: "approver", actor_id, viewed_at}`
- Resume enfileirado no Celery com mesmo `thread_id` (= `task_id`)

## 2. POST /tasks/{id}/reject

### Request

```http
POST /tasks/{task_id}/reject HTTP/1.1
Host: localhost:8000
Authorization: Bearer <approver-api-key>
X-Snapshot-Hash: <sha256-hex>        # obrigatório
Content-Type: application/json

{
  "reject_reason": "data_quality",   # obrigatório, enum
  "justification": "Dados simulados não permitidos em produção"  # obrigatório se other
}
```

**Headers obrigatórios:** mesmos do approve.

**Body:**
- `reject_reason`: enum obrigatório — `data_quality` | `numbers_mismatch` | `policy` | `other`
- `justification`: string — **obrigatória se `reject_reason = "other"`**, opcional caso contrário

### Response

| Status | Condição | Body |
|--------|----------|------|
| `200` | Rejeição aceita | `{"task_id": "uuid", "status": "REJECTED", "reject_reason": "data_quality"}` |
| `403` | Role incorreta | `{"detail": "approver role required"}` |
| `404` | Tarefa não existe | `{"detail": "task not found"}` |
| `409` | Estado inválido (não `AWAITING_APPROVAL`) | `{"detail": "task not in AWAITING_APPROVAL"}` |
| `409` | Hash mismatch | `{"detail": "snapshot_hash mismatch", "expected": "...", "received": "..."}` |
| `410` | Tarefa `EXPIRED` | `{"detail": "task expired"}` |
| `422` | `reject_reason` ausente ou inválido | `{"detail": "reject_reason required", "allowed": ["data_quality","numbers_mismatch","policy","other"]}` |
| `422` | `other` sem `justification` | `{"detail": "justification required when reject_reason=other"}` |

**Efeitos colaterais:**
- Transição atômica: `AWAITING_APPROVAL` → `REJECTED`
- Evento `APPROVAL_DECISION` com `{decision: "rejected", reject_reason, justification, snapshot_hash, actor_role: "approver", actor_id}`
- **Sem resume enfileirado** — tarefa termina

## 3. Estados terminais de aprovação

| Estado | Descrição | Próximo |
|--------|-----------|---------|
| `APPROVED` | Aprovado, resume enfileirado | Worker retoma → `Publish` → `PUBLISHED` |
| `REJECTED` | Rejeitado com categoria | Terminal — sem resume |
| `EXPIRED` | TTL 7 dias (168h) sem decisão | Terminal — transição atômica via reaper/job diário |

## 4. X-Snapshot-Hash — Especificação

- **Origem**: Calculado no nó `prepare_review` (idempotente): `sha256(json_canonico(snapshot))`
- **Snapshot inclui**: `execution_id`, `step_name`, `market_payload_ref`, `quant_metrics_ref`, `report_draft_ref`, `audit_result_ref`, `data_quality`, `created_at`
- **Armazenado**: Em `task_events` (evento `REVIEW_READY`) + `tasks.snapshot_hash`
- **Exibido**: Na UI (`/approval/{task_id}`) e no `GET /tasks/{id}` quando status `AWAITING_APPROVAL` ou `APPROVED`
- **Validado**: No approve/reject — compara com `task_events` mais recente da tarefa
- **Mismatch**: Indica que aprovador viu snapshot desatualizado (concorrência ou retry) → `409`

## 5. Reject Reason — Enum

| Valor | Quando usar | Exige justification |
|-------|-------------|---------------------|
| `data_quality` | Dados `SIMULADOS` sem acknowledge, `STALE` não aceito | Não (opcional) |
| `numbers_mismatch` | Auditoria numérica falhou / números não conferem | Não (opcional) |
| `policy` | Viola política interna (ex: setor proibido, risco) | Não (opcional) |
| `other` | Motivo não coberto acima | **Sim (obrigatório)** |

## 6. TTL de aprovação (EXPIRED)

- Config: `approval_ttl_hours = 168` (7 dias, arbitrário, configurável)
- Transição atômica: `UPDATE tasks SET status = 'EXPIRED' WHERE status = 'AWAITING_APPROVAL' AND created_at < now() - interval '168 hours'`
- Executado por: Reaper (a cada 60s) **E** job diário (Celery beat) — idempotente
- Evento: `TASK_EXPIRED` em `task_events`

## 6. Rate limiting

| Endpoint | Limite (default) | Escopo |
|----------|------------------|--------|
| `POST /tasks/{id}/approve` | 20 req/s | por `api_key_id` |
| `POST /tasks/{id}/reject` | 20 req/s | por `api_key_id` |

## 7. UI de aprovação (GET /approval/{task_id})

Ver `interfaces/approval-ui.md` — página HTML servida pelo FastAPI (Jinja2), consome estes endpoints.