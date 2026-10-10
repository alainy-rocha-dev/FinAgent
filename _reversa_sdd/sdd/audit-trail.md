# Spec: audit-trail

> Selo 🟡 PLANEJADO. Componente gerado pelo reversa-spec-sdd a partir do PRD FinAgent + AgentPulse.

---

## 1. Resumo

🟡 Trilha de auditoria imutável em `task_events` com hash encadeado, papéis de banco segregados (`app_user`, `retention_role`, `migrator`), retenção de 365 dias no mesmo banco, snapshot do que o aprovador viu no momento da decisão.

---

## 2. Requisitos Funcionais

| ID | Requisito | Prioridade | Critério de Aceite |
|----|-----------|------------|---------------------|
| 🟡 RF-01 | Tabela `task_events` com colunas: `seq` (bigserial PK), `task_id`, `event_type` (enum), `payload_jsonb`, `snapshot_hash` (sha256), `actor_role` (enum), `actor_id` (api_key_id), `created_at` (timestamptz) | Must | Todos os eventos do ciclo de vida gravados |
| 🟡 RF-02 | Trigger `AFTER INSERT` grava hash encadeado: `chain_hash = sha256(lag(chain_hash) OVER (PARTITION BY task_id ORDER BY seq) || payload_jsonb || created_at || actor_id)` | Must | Imutabilidade: alteração de qualquer evento quebra a cadeia |
| 🟡 RF-03 | Papéis de banco segregados: `app_user` (INSERT/SELECT), `retention_role` (DELETE/UPDATE para retenção), `migrator` (DDL) | Must | `app_user` não faz UPDATE/DELETE; migrações com `migrator` no deploy |
| 🟡 RF-04 | Eventos obrigatórios: `TASK_CREATED`, `STATE_TRANSITION`, `CHECKPOINT_SAVED`, `REVIEW_READY`, `APPROVAL_DECISION`, `PUBLICATION`, `REAPER_ACTION`, `BUDGET_EXCEEDED`, `DATA_QUALITY_BLOCKED` | Must | Cada transição/ação crítica gera evento com payload completo |
| 🟡 RF-05 | Snapshot da aprovação: `APPROVAL_DECISION` grava `payload_jsonb` com `{decision, justification, reject_reason, snapshot_hash, actor_role, actor_id, viewed_at}` | Must | O que o aprovador viu fica imutável para auditoria |
| 🟡 RF-06 | Retenção: job diário com `retention_role` apaga eventos de tarefas terminais > 365 dias (mesmo banco, sem camada de arquivo) | Must | `retention_days = 365` (valor inicial, a medir); tarefas ativas preservadas |
| 🟡 RF-07 | Índices: `(task_id, seq)`, `(task_id, event_type)`, `(created_at)` para consultas de auditoria | Must | Consultas por tarefa e por período performáticas |

---

## 3. Comportamentos

🟡 **Hash encadeado (chain_hash):**
- `chain_hash = sha256(coalesce(lag(chain_hash) OVER (PARTITION BY task_id ORDER BY seq), '') || payload_jsonb || created_at || actor_id)`
- Armazenado em coluna `chain_hash` (bytea) na mesma tabela
- Verificação: `SELECT seq, chain_hash = computed_hash FROM ...` — qualquer mismatch = violação

🟡 **Papéis (roles):**
```sql
-- app_user: usado pelos pools da API e worker
GRANT INSERT, SELECT ON task_events TO app_user;
-- retention_role: job de retenção
GRANT DELETE, UPDATE ON task_events TO retention_role;
-- migrator: DDL (Alembic)
GRANT ALL ON task_events TO migrator;
```

🟡 **Evento `APPROVAL_DECISION` payload:**
```json
{
  "decision": "approved|rejected",
  "justification": "string",
  "reject_reason": "data_quality|numbers_mismatch|policy|other|null",
  "snapshot_hash": "sha256_do_snapshot_visto",
  "actor_role": "approver",
  "actor_id": "api_key_id",
  "viewed_at": "2026-10-05T10:30:00Z"
}
```

🟡 **Job de retenção (Celery beat, `retention_role`):**
```sql
DELETE FROM task_events
WHERE task_id IN (
  SELECT task_id FROM tasks
  WHERE status IN ('PUBLISHED','REJECTED','EXPIRED','FAILED','BUDGET_EXCEEDED','DATA_QUALITY_BLOCKED')
    AND updated_at < now() - interval '365 days'
);
```

---

## 4. Edge Cases

| Cenário | Comportamento |
|---------|---------------|
| 🟡 Tentativa de UPDATE/DELETE por `app_user` | Erro de permissão (Postgres bloqueia) |
| 🟡 Evento inserido fora de ordem (race) | `seq` serial garante ordem; `chain_hash` usa `LAG` sobre `seq` |
| 🟡 Tarefa com muitos eventos (performance) | Índices em `(task_id, seq)`; paginação por `seq` |
| 🟡 Retenção remove eventos de tarefa ainda ativa | Query filtra por `tasks.status` terminal + `updated_at`; ativas não entram |
| 🟡 `chain_hash` verification falha | Alerta crítico; loga violação; investigação manual |

---

## 5. Não-Gols

🟡 Não implementar tabela `published` (componente `publication`)
🟡 Não implementar máquina de estados (componente `task-state-machine`)
🟡 Não implementar job de retenção (Celery beat — componente `worker-queue` / `ci-quality`)
🟡 Não implementar criptografia de dados sensíveis (não há dados pessoais além de `actor_id` + timestamp)

---

## 6. Interface de Integração

🟡 **Entrada:** Eventos do sistema (worker, API, reaper, publisher) via repositório injetado
🟡 **Saída:** Eventos persistidos com `chain_hash`; consultas de auditoria
🟡 **Dependências:** Pool `domain_pool` (transacional), role `app_user` (INSERT/SELECT), role `retention_role` (retenção), `task-state-machine` (emite eventos de transição)

---

## 7. Critérios de Aceite (Gherkin)

```gherkin
Cenário: Hash encadeado garante imutabilidade
  Dado eventos E1, E2, E3 para task_id=123 inseridos em ordem
  Quando calcula chain_hash para cada um
  Então chain_hash(E1) = sha256('' || payload1 || ts1 || actor1)
  E chain_hash(E2) = sha256(chain_hash(E1) || payload2 || ts2 || actor2)
  E chain_hash(E3) = sha256(chain_hash(E2) || payload3 || ts3 || actor3)
  Se alguém faz UPDATE direto no payload de E2
  Então verificação de chain_hash falha em E3

Cenário: Papel app_user não consegue apagar
  Dado conexão com role app_user
  Quando DELETE FROM task_events WHERE task_id = 123
  Então erro: permission denied

Cenário: Snapshot de aprovação imutável
  Dado aprovador vê snapshot com hash H123
  Quando clica Aprovar
  Então evento APPROVAL_DECISION gravado com snapshot_hash = H123
  E chain_hash inclui esse evento
```

---

## 8. Perguntas Abertas

⚠️ **ABERTO:** Enum exato de `event_type` (lista acima é proposta)
⚠️ **ABERTO:** `retention_days = 365` — confirmar se 365 dias no mesmo banco atende compliance (sem camada de arquivo frio)
⚠️ **ABERTO:** Tamanho máximo de `payload_jsonb` (limitar para evitar bloat?)

---

## 9. Valores Iniciais (a medir)

| Parâmetro | Valor Inicial | Fonte |
|-----------|---------------|-------|
| 🟡 `retention_days` | 365 dias | Arbitrário |
| 🟡 Tamanho máximo payload_jsonb | 1 MB | Arbitrário |

---

## 10. Relatório de Avaliação (Scoring)

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SCORE TOTAL: 87/100
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Breakdown:
  Completude:    90/100 (peso 30%)
  Testabilidade: 85/100 (peso 25%)
  Clareza:       85/100 (peso 20%)
  Escopo:        90/100 (peso 15%)
  Edge Cases:    85/100 (peso 10%)

Gaps críticos:
  - Enum event_type e payload_jsonb max size precisam definição final
  - 365 dias no mesmo banco vs camada fria — confirmar compliance

Sugestões:
  1. Definir enum event_type completo no código (Python enum + Postgres enum)
  2. Testar trigger chain_hash com concorrência (inserções simultâneas mesma task)
  3. Validar performance de verificação de chain_hash em lote
```