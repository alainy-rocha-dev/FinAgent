# Spec: task-api

> Selo 🟡 PLANEJADO. Componente gerado pelo reversa-spec-sdd a partir do PRD FinAgent + AgentPulse.

---

## 1. Resumo

🟡 API assíncrona FastAPI com `POST /tasks` (Idempotency-Key obrigatória, escopo por `api_key_id`), `GET /tasks/{id}`, autenticação API key com papéis `analyst`/`approver` (403 cruzado), hash do payload, tabela de respostas idempotentes, limite de tarefas ativas por chave.

---

## 2. Requisitos Funcionais

| ID | Requisito | Prioridade | Critério de Aceite |
|----|-----------|------------|---------------------|
| 🟡 RF-01 | `POST /tasks` com `Idempotency-Key` obrigatório | Must | Header obrigatório; 422 se ausente |
| 🟡 RF-02 | Idempotência com escopo `api_key_id`: constraint única em `idempotency_keys(api_key_id, key)` | Must | Mesma chave + mesmo `api_key_id` + mesmo payload → 200 com `Idempotent-Replay: true`; mesmo `api_key_id` + payload diferente → 409 |
| 🟡 RF-03 | Tabela `idempotency_keys`: `api_key_id`, `key`, `task_id`, `payload_hash`, `created_at`, `response_status`, `response_body` | Must | Replay retorna corpo original com status original |
| 🟡 RF-04 | Dois papéis de API key: `analyst` (POST/GET tasks) e `approver` (POST approve/reject, GET) | Must | `analyst` em approve/reject → 403; `approver` em POST /tasks → 403 |
| 🟡 RF-05 | `GET /tasks/{id}` retorna estado, checkpoints, eventos, qualidade de dados | Must | Ambos papéis podem ler; dados sensíveis filtrados |
| 🟡 RF-06 | Limite de tarefas ativas por `api_key_id`: `max_active_tasks_per_key` (padrão 10) | Must | Conta `PENDING | RUNNING | AWAITING_APPROVAL | APPROVED`; excedente → 429 com `Retry-After` |
| 🟡 RF-07 | Tabela de respostas HTTP padronizada | Must | 202 (aceita), 200 (replay), 409 (conflito idempotência), 422 (validação), 429 (rate limit), 403 (papel), 401 (auth), 404 (não existe) |
| 🟡 RF-08 | Hash do payload (sha256) salvo na idempotência e comparado no replay | Must | Garante que replay só com payload idêntico |
| 🟡 RF-09 | Engine SQLAlchemy async com `asyncpg` (pool do AgentPulse) | Must | Usada em POST /tasks, approve/reject, leituras |

---

## 3. Comportamentos

🟡 **Fluxo `POST /tasks`:**
1. Valida API key → extrai `api_key_id`, `role`
2. Se `role != analyst` → 403
3. Valida `Idempotency-Key` presente
4. Calcula `payload_hash = sha256(request_body)`
5. Tenta `INSERT INTO idempotency_keys (api_key_id, key, payload_hash, ...) ON CONFLICT (api_key_id, key) DO UPDATE SET ...`
   - Se conflito e `payload_hash` igual → retorna resposta salva (200, `Idempotent-Replay: true`)
   - Se conflito e `payload_hash` diferente → 409 `{error: "idempotency_key_reused_with_different_payload"}`
6. Conta tarefas ativas da `api_key_id` → se ≥ 10 → 429
7. Cria `task` em `PENDING`, grava `task_id` na `idempotency_keys`
8. Enfileira tarefa no Celery (com `task_id` como ID da task Celery)
9. Retorna 202 `{task_id, status: "PENDING"}`

🟡 **Fluxo `POST /tasks/{id}/approve|reject`:**
1. Valida API key → `api_key_id`, `role`
2. Se `role != approver` → 403
3. Valida `X-Snapshot-Hash` header obrigatório
4. `task-state-machine.transition(task_id, 'AWAITING_APPROVAL', 'APPROVED'|'REJECTED', reason, 'approver', api_key_id)`
   - Se estado não é `AWAITING_APPROVAL` → 409
   - Se `X-Snapshot-Hash` não confere com `task_events` mais recente → 409
5. Se approve: enfileira resume no Celery (mesmo `thread_id`)
6. Se reject: `reject_reason` enum obrigatório (`data_quality | numbers_mismatch | policy | other`), `justification` obrigatório se `other`
7. Retorna 200 com estado atualizado

---

## 4. Edge Cases

| Cenário | Comportamento |
|---------|---------------|
| 🟡 `Idempotency-Key` reutilizada com payload diferente (mesmo `api_key_id`) | 409 imediato; nenhuma tarefa criada |
| 🟡 `Idempotency-Key` reutilizada com payload idêntico | 200 replay; resposta idêntica à original |
| 🟡 `api_key_id` atinge limite de tarefas ativas | 429 com `Retry-After` estimado |
| 🟡 `approver` tenta criar tarefa | 403 "analyst role required" |
| 🟡 `analyst` tenta aprovar | 403 "approver role required" |
| 🟡 Tarefa não existe / já terminal | 404 ou 409 conforme caso |
| 🟡 `X-Snapshot-Hash` mismatch | 409 `{expected: "...", received: "..."}` |

---

## 5. Não-Gols

🟡 Não implementar orçamento de tokens/custo (componente `budget-control`)
🟡 Não implementar máquina de estados (componente `task-state-machine`)
🟡 Não implementar fila Celery (componente `worker-queue`)
🟡 Não implementar página de aprovação HTML (componente `approval-ui`)
🟡 Não implementar autenticação OAuth/SSO (apenas API key)

---

## 6. Interface de Integração

🟡 **Entrada:** HTTP requests com headers `Authorization: Bearer <key>`, `Idempotency-Key`, `X-Snapshot-Hash`
🟡 **Saída:** JSON responses com códigos padronizados, headers `Idempotent-Replay`, `Retry-After`
🟡 **Dependências:** `task-state-machine` (transições), `worker-queue` (enfileirar), `audit-trail` (eventos), `budget-control` (estimativa prévia), pool SQLAlchemy async (AgentPulse)

---

## 7. Critérios de Aceite (Gherkin)

```gherkin
Cenário: Criação idempotente de tarefa
  Dado API key com role=analyst
  Quando POST /tasks com Idempotency-Key=abc e payload {symbol: "PETR4"}
  Então resposta 202 com task_id
  Quando POST /tasks com mesma Idempotency-Key e mesmo payload
  Então resposta 200 com Idempotent-Replay: true e mesmo task_id
  Quando POST /tasks com mesma Idempotency-Key mas payload {symbol: "AAPL"}
  Então resposta 409 idempotency_key_reused_with_different_payload

Cenário: Papéis cruzados bloqueados
  Dado API key com role=analyst
  Quando POST /tasks/{id}/approve
  Então 403 "approver role required"
  Dado API key com role=approver
  Quando POST /tasks
  Então 403 "analyst role required"

Cenário: Limite de tarefas ativas
  Dado api_key_id com 10 tarefas em PENDING|RUNNING|AWAITING_APPROVAL|APPROVED
  Quando POST /tasks com nova tarefa
  Então 429 com Retry-After
```

---

## 8. Perguntas Abertas

⚠️ **ABERTO:** Estrutura exata da tabela `api_keys` (campos: `id`, `role`, `name`, `hashed_key`, `created_at`, `revoked_at`)
⚠️ **ABERTO:** Rate limiting por classe de endpoint (baldes separados para POST /tasks, GET, approve/reject) — limites iniciais a definir
⚠️ **ABERTO:** `task_time_limit`, `retry_backoff_max`, `max_retries` do Celery (definidos no `worker-queue`) impactam `visibility_timeout` e `Retry-After`

---

## 9. Valores Iniciais (a medir)

| Parâmetro | Valor Inicial | Fonte |
|-----------|---------------|-------|
| 🟡 `max_active_tasks_per_key` | 10 | Arbitrário |
| 🟡 Limite motivo rejeição (min/max chars) | 10 / 1000 | Arbitrário |
| 🟡 Rate limit: POST /tasks | 10 req/s por key | Arbitrário |
| 🟡 Rate limit: GET /tasks/{id} | 30 req/s por key | Arbitrário |
| 🟡 Rate limit: approve/reject | 20 req/s por key | Arbitrário |

---

## 10. Relatório de Avaliação (Scoring)

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SCORE TOTAL: 88/100
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Breakdown:
  Completude:    90/100 (peso 30%)
  Testabilidade: 90/100 (peso 25%)
  Clareza:       85/100 (peso 20%)
  Escopo:        85/100 (peso 15%)
  Edge Cases:    90/100 (peso 10%)

Gaps críticos:
  - Estrutura da tabela api_keys e rate limiting por classe de endpoint não definidos
  - Integração com budget-control (estimativa prévia) precisa especificação

Sugestões:
  1. Definir schema api_keys e migração Alembic
  2. Implementar rate limiting com Redis (token bucket por api_key_id + endpoint class)
  3. Testar idempotência com concorrência real (50 POSTs simultâneos mesma chave)
```