# Spec: approval-flow

> Selo 🟡 PLANEJADO. Componente gerado pelo reversa-spec-sdd a partir do PRD FinAgent + AgentPulse.

---

## 1. Resumo

🟡 Fluxo de aprovação humana com `X-Snapshot-Hash` obrigatório, estado `EXPIRED` por TTL (7 dias), categoria de rejeição obrigatória, nó `await_approval` sem efeitos colaterais. Snapshot montado pelo nó `prepare_review` (idempotente).

---

## 2. Requisitos Funcionais

| ID | Requisito | Prioridade | Critério de Aceite |
|----|-----------|------------|---------------------|
| 🟡 RF-01 | `X-Snapshot-Hash` obrigatório em `POST /tasks/{id}/approve|reject` | Must | Cliente (UI ou API) deve enviar hash do snapshot visto; servidor compara com `task_events` mais recente; mismatch → 409 |
| 🟡 RF-02 | Estado `EXPIRED` por TTL: `approval_ttl_hours = 168` (7 dias, arbitrário) | Must | Tarefa em `AWAITING_APPROVAL` sem decisão → transição atômica para `EXPIRED` (UPDATE WHERE status='AWAITING_APPROVAL' AND created_at < now() - interval) |
| 🟡 RF-03 | Reaper também detecta `AWAITING_APPROVAL` expiradas e transiciona para `EXPIRED` | Must | Critério: `created_at < now() - 168h` |
| 🟡 RF-04 | Categoria de rejeição obrigatória: `reject_reason` enum (`data_quality | numbers_mismatch | policy | other`) | Must | Persistido em `tasks.reject_reason` e `task_events`; `justification` obrigatório se `other` |
| 🟡 RF-05 | Nó `await_approval` sem efeitos colaterais: não grava, não chama LLM, não emite evento | Must | Apenas sinaliza `interrupt()`; snapshot já montado por `prepare_review` |
| 🟡 RF-06 | Transições atômicas via `task-state-machine`: `AWAITING_APPROVAL → APPROVED | REJECTED | EXPIRED` | Must | Condição de corrida impossível (UPDATE WHERE status) |
| 🟡 RF-07 | `approval_ttl_hours` configurável (padrão 168h) | Should | Variável de ambiente / config |

---

## 3. Comportamentos

🟡 **Fluxo de aprovação:**
1. Grafo executa até `prepare_review` → monta snapshot idempotente → grava `task_events` (`REVIEW_READY`) com `snapshot_hash`
2. Grafo executa `await_approval` → `interrupt()` → worker termina, tarefa fica em `AWAITING_APPROVAL`
3. Aprovador acessa UI / API → vê snapshot com `snapshot_hash` exibido
4. Aprovação: `POST /tasks/{id}/approve` com `X-Snapshot-Hash: H123` + `justification` (opcional)
   - Servidor: `task-state-machine.transition(task_id, 'AWAITING_APPROVAL', 'APPROVED', 'human_approved', 'approver', api_key_id)`
   - Se hash confere → enfileira resume no Celery (mesmo `thread_id`)
5. Rejeição: `POST /tasks/{id}/reject` com `X-Snapshot-Hash: H123` + `reject_reason` (enum) + `justification` (obrigatório se `other`)
   - Servidor: `task-state-machine.transition(task_id, 'AWAITING_APPROVAL', 'REJECTED', 'human_rejected:' + reject_reason, 'approver', api_key_id)`
   - Tarefa termina em `REJECTED`; sem resume

🟡 **Expiração (TTL):**
- `approval_ttl_hours = 168` (7 dias, arbitrário)
- Transição atômica: `UPDATE tasks SET status = 'EXPIRED', updated_at = now() WHERE status = 'AWAITING_APPROVAL' AND created_at < now() - interval '168 hours'`
- Executada por: job de retenção (diário) OU reaper (a cada 60s) — ambos idempotentes
- Evento `TASK_EXPIRED` gravado em `task_events`

🟡 **Hash do snapshot (`snapshot_hash`):**
- Calculado em `prepare_review`: `sha256(json_canonico(snapshot))`
- Snapshot inclui: `execution_id`, `step_name`, `market_payload_ref`, `quant_metrics_ref`, `report_draft_ref`, `audit_result_ref`, `data_quality`, `created_at`
- Exibido na UI e enviado no `X-Snapshot-Hash`

---

## 4. Edge Cases

| Cenário | Comportamento |
|---------|---------------|
| 🟡 Dois approve concorrentes no mesmo task_id | Primeiro vence (UPDATE atômico); segundo 409 "task not in AWAITING_APPROVAL" |
| 🟡 Approve com `X-Snapshot-Hash` errado | 409 `{expected: "H123", received: "H456"}` |
| 🟡 Reject sem `reject_reason` | 422 validation error |
| 🟡 Reject com `other` sem `justification` | 422 validation error |
| 🟡 Tarefa expira enquanto aprovador está na página | UI detecta 410 (EXPIRED) ao submeter; exibe mensagem |
| 🟡 Aprovador tenta aprovar tarefa já `APPROVED` | 409 "task not in AWAITING_APPROVAL" |

---

## 5. Não-Gols

🟡 Não implementar UI de aprovação (componente `approval-ui`)
🟡 Não implementar máquina de estados (componente `task-state-machine`)
🟡 Não implementar nó `prepare_review` (componente `analysis-graph`)
🟡 Não implementar publicação (componente `publication`)
🟡 Não definir `approval_ttl_hours` fixo (configurável, padrão 168h)

---

## 6. Interface de Integração

🟡 **Entrada:** Decisão humana (approve/reject) via API com `X-Snapshot-Hash`, `reject_reason`, `justification`
🟡 **Saída:** Transição de estado + enfileiramento resume (se approve) + eventos em `task_events`
🟡 **Dependências:** `task-state-machine` (transições), `task-api` (endpoints), `analysis-graph` (`prepare_review` monta snapshot), `audit-trail` (eventos), `worker-queue` (enfileirar resume)

---

## 7. Critérios de Aceite (Gherkin)

```gherkin
Cenário: Aprovação com hash correto
  Dado tarefa em AWAITING_APPROVAL com snapshot_hash = "H123"
  Quando POST /tasks/{id}/approve com X-Snapshot-Hash: H123
  Então task-state-machine transiciona para APPROVED
  E resume enfileirado no Celery com mesmo thread_id
  E evento APPROVAL_DECISION gravado com decision=approved

Cenário: Rejeição com categoria obrigatória
  Dado tarefa em AWAITING_APPROVAL
  Quando POST /tasks/{id}/reject com X-Snapshot-Hash válido, reject_reason=data_quality, justification="dados simulados"
  Então transição para REJECTED
  E tasks.reject_reason = 'data_quality'
  E evento APPROVAL_DECISION com reject_reason=data_quality

Cenário: Expiração por TTL
  Dado tarefa em AWAITING_APPROVAL criada há 169 horas
  Quando reaper roda (ou job diário)
  Então transição atômica para EXPIRED
  E evento TASK_EXPIRED gravado
  E nenhum resume enfileirado
```

---

## 8. Perguntas Abertas

⚠️ **ABERTO:** `approval_ttl_hours = 168` (7 dias) — confirmar se atende necessidade de negócio (gestor com agenda cheia)
⚠️ **ABERTO:** Job de expiração: reaper (60s) vs job diário — qual executa a transição? (ambos idempotentes, reaper mais rápido)

---

## 9. Valores Iniciais (a medir)

| Parâmetro | Valor Inicial | Fonte |
|-----------|---------------|-------|
| 🟡 `approval_ttl_hours` | 168 (7 dias) | Arbitrário |
| 🟡 Limite motivo rejeição (min/max chars) | 10 / 1000 | Arbitrário |

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
  - TTL de aprovação (7 dias) precisa validação com persona aprovador
  - Quem executa a transição EXPIRED: reaper ou job diário (ou ambos)

Sugestões:
  1. Validar TTL com stakeholders (7 dias vs 30 dias)
  2. Testar concorrência: approve + expire simultâneos
  3. Documentar que snapshot_hash é sha256 canonical JSON
```