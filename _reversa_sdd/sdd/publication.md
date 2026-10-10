# Spec: publication

> Selo 🟡 PLANEJADO. Componente gerado pelo reversa-spec-sdd a partir do PRD FinAgent + AgentPulse.

---

## 1. Resumo

🟡 Publicação única garantida por tabela `published` com constraint única em `task_id`, Publisher serviço transacional, conferência de hash do snapshot aprovado.

---

## 2. Requisitos Funcionais

| ID | Requisito | Prioridade | Critério de Aceite |
|----|-----------|------------|---------------------|
| 🟡 RF-01 | Tabela `published`: `task_id` (PK, FK tasks), `report_jsonb`, `published_at`, `published_by` (api_key_id), `snapshot_hash` | Must | Constraint única em `task_id` garante publicação única |
| 🟡 RF-02 | Publisher: transação atômica INSERT `published` + UPDATE `tasks` status=PUBLISHED + INSERT `task_events` (PUBLICATION) | Must | Se INSERT `published` falha por duplicidade → transação aborta, tarefa fica em `APPROVED` (retry seguro) |
| 🟡 RF-03 | Conferência de hash: Publisher compara `snapshot_hash` do evento de aprovação com `task_events` mais recente | Must | Divergência → não publica, loga erro, tarefa volta para `AWAITING_APPROVAL` com flag |
| 🟡 RF-04 | Evento `PUBLICATION` em `task_events` com `payload_jsonb` contendo `{task_id, report_hash, published_by, published_at, snapshot_hash}` | Must | Trilha completa da publicação |
| 🟡 RF-05 | Role `app_user` faz INSERT/SELECT em `published`; `retention_role` para retenção; `migrator` para DDL | Must | Mesma segregação do `audit-trail` |

---

## 3. Comportamentos

🟡 **Fluxo de publicação (após approve):**
1. Worker retoma grafo em `APPROVED` → nó `publish`
2. Publisher executa em transação (`domain_pool`):
   ```sql
   BEGIN;
   INSERT INTO published (task_id, report_jsonb, published_at, published_by, snapshot_hash)
   VALUES (:task_id, :report, now(), :api_key_id, :snapshot_hash)
   ON CONFLICT (task_id) DO NOTHING;  -- se já existe, não faz nada
   -- Verifica se inseriu:
   IF NOT FOUND THEN
     ROLLBACK;
     RAISE EXCEPTION 'duplicate_publication';
   END IF;
   UPDATE tasks SET status = 'PUBLISHED', updated_at = now() WHERE task_id = :task_id;
   INSERT INTO task_events (task_id, event_type, payload_jsonb, actor_role, actor_id)
   VALUES (:task_id, 'PUBLICATION', :payload, 'system', :api_key_id);
   COMMIT;
   ```
3. Se `duplicate_publication` → tarefa permanece `APPROVED` → worker pode retry (idempotente)

🟡 **Conferência de hash:**
- Antes da transação, Publisher busca `task_events` mais recente da tarefa com `event_type = 'APPROVAL_DECISION'`
- Extrai `snapshot_hash` do payload
- Compara com `snapshot_hash` recebido no evento de resume
- Se diferente → `log.error("snapshot_hash mismatch", expected=..., received=...)`, tarefa → `AWAITING_APPROVAL` com flag `hash_mismatch=true`

🟡 **Idempotência da publicação:**
- `ON CONFLICT (task_id) DO NOTHING` + verificação `IF NOT FOUND` garante que apenas uma publicação persiste
- Retry seguro: se worker morre após INSERT mas antes de COMMIT, transação rola back; retomada tenta de novo

---

## 4. Edge Cases

| Cenário | Comportamento |
|---------|---------------|
| 🟡 Dois workers tentam publicar mesmo task_id simultaneamente | Um consegue INSERT, outro `ON CONFLICT DO NOTHING` → `IF NOT FOUND` → rollback → retry |
| 🟡 Hash do snapshot diverge (tampering ou bug) | Publicação abortada; tarefa volta para `AWAITING_APPROVAL`; alerta logado |
| 🟡 Worker morre após INSERT `published` mas antes de UPDATE `tasks` | Transação rola back (não comitada); retomada tenta de novo |
| 🟡 Tarefa já `PUBLISHED` recebe resume duplicado | Publisher vê `ON CONFLICT` → aborta; tarefa já terminal |
| 🟡 `report_jsonb` muito grande | Armazenado em `published.report_jsonb` (jsonb); se > 1MB, considerar tabela separada |

---

## 5. Não-Gols

🟡 Não implementar trilha de auditoria (componente `audit-trail`)
🟡 Não implementar máquina de estados (componente `task-state-machine`)
🟡 Não implementar fluxo de aprovação (componente `approval-flow`)
🟡 Não implementar UI (componente `approval-ui`)
🟡 Não definir retenção de `published` (mesma política de `task_events`: 365 dias, `retention_role`)

---

## 6. Interface de Integração

🟡 **Entrada:** `task_id`, `report_jsonb`, `snapshot_hash`, `published_by` (api_key_id)
🟡 **Saída:** Linha em `published` + `tasks.status = PUBLISHED` + evento `PUBLICATION`
🟡 **Dependências:** `task-state-machine` (estado APPROVED), `approval-flow` (hash do snapshot), `audit-trail` (eventos), `worker-queue` (worker executa Publisher), `domain_pool` (transacional)

---

## 7. Critérios de Aceite (Gherkin)

```gherkin
Cenário: Publicação única sob concorrência
  Dado tarefa em APPROVED
  Quando dois workers executam Publisher simultaneamente
  Então um insere em published e comita
  E o outro recebe ON CONFLICT DO NOTHING, faz rollback, retry
  E exatamente 1 linha em published para o task_id

Cenário: Hash mismatch aborta publicação
  Dado tarefa em APPROVED com snapshot_hash = "H123" no evento de aprovação
  Quando Publisher recebe snapshot_hash = "H456" (divergente)
  Então publicação abortada
  E tarefa transiciona para AWAITING_APPROVAL com flag hash_mismatch
  E erro logado com expected/received

Cenário: Retry seguro após falha no meio da transação
  Dado worker morre após INSERT published mas antes de COMMIT
  Quando worker retoma e executa Publisher
  Então transação anterior rolou back (sem commit)
  E nova tentativa insere e comita com sucesso
  E tarefa finaliza PUBLISHED
```

---

## 8. Perguntas Abertas

⚠️ **ABERTO:** Tamanho máximo de `report_jsonb` — se exceder, mover para tabela `reports` com FK?
⚠️ **ABERTO:** Retenção de `published`: mesma política 365 dias + `retention_role`?
⚠️ **ABERTO:** `published_by` guarda `api_key_id` do aprovador — confirmar se suficiente para auditoria

---

## 9. Valores Iniciais (a medir)

| Parâmetro | Valor Inicial | Fonte |
|-----------|---------------|-------|
| 🟡 `report_jsonb` max size | 1 MB | Arbitrário |
| 🟡 Retenção `published` | 365 dias | Mesmo `audit-trail` |

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
  - Tamanho do report_jsonb e estratégia se exceder
  - Retenção de published confirmar alinhamento com audit-trail

Sugestões:
  1. Testar concorrência real: N workers publicando mesmo task_id
  2. Validar hash mismatch com cenário de tampering simulado
  3. Definir migração Alembic para tabela published
```