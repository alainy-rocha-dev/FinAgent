# Spec: task-state-machine

> Selo 🟡 PLANEJADO. Componente gerado pelo reversa-spec-sdd a partir do PRD FinAgent + AgentPulse.

---

## 1. Resumo

🟡 Dona das transições atômicas de estado da tarefa, do advisory lock por `task_id` e do motivo legível em cada transição. Centraliza o que hoje está espalhado entre API, worker e aprovação, eliminando o risco de corrida.

---

## 2. Requisitos Funcionais

| ID | Requisito | Prioridade | Critério de Aceite |
|----|-----------|------------|---------------------|
| 🟡 RF-01 | Definir estados e transições permitidas | Must | Estados: PENDING, RUNNING, AWAITING_APPROVAL, APPROVED, PUBLISHED. Terminais: PUBLISHED, REJECTED, EXPIRED, FAILED, BUDGET_EXCEEDED, DATA_QUALITY_BLOCKED. Transições conforme matriz abaixo |
| 🟡 RF-02 | Garantir transições atômicas via UPDATE ... WHERE status = 'X' | Must | Condição de corrida impossível: apenas uma transição PENDING→RUNNING, RUNNING→AWAITING_APPROVAL, etc., por task_id |
| 🟡 RF-03 | Advisory lock de sessão por task_id (padrão) | Must | Try-lock sem bloquear (NOWAIT), em conexão dedicada durante execução inteira; lock liberado ao fechar conexão |
| 🟡 RF-04 | Fallback: lease em tabela `tasks` (locked_by, lease_until) | Should | Renovado pelo heartbeat; usado se advisory lock inviável (pooler) — detectado no spike |
| 🟡 RF-05 | Motivo legível em cada transição (campo `transition_reason`) | Must | Ex: "worker_started", "quant_completed", "human_approved", "human_rejected:data_quality", "expired", "budget_exceeded", "data_quality_blocked", "worker_lost" |
| 🟡 RF-06 | Incrementar `attempts` em reenfileiramento (reaper, reentrega) sem mudar estado | Must | `attempts` usado para limite de retentativas; estado inalterado |
| 🟡 RF-07 | Rejeitar transições fora da matriz com erro claro | Must | Tentativa inválida → exceção `InvalidTransition` com estado atual, estado solicitado, transições permitidas |
| 🟡 RF-08 | Expor função `transition(task_id, from_status, to_status, reason, actor_role, actor_id)` | Must | Usada por API, worker, reaper, aprovação; única entrada de mudança de estado |

---

## 3. Comportamentos

🟡 **Matriz de transições permitidas:**
| De → Para | Permitida? | Condição / Actor |
|-----------|------------|------------------|
| PENDING → RUNNING | ✅ | Worker adquire lock, `actor_role=system` |
| RUNNING → AWAITING_APPROVAL | ✅ | Nó `prepare_review` completa, `actor_role=system` |
| RUNNING → FAILED | ✅ | Erro não recuperável, `actor_role=system` |
| RUNNING → BUDGET_EXCEEDED | ✅ | Budget-control aborta, `actor_role=system` |
| RUNNING → DATA_QUALITY_BLOCKED | ✅ | Falha precoce pós-coletor, `actor_role=system` |
| AWAITING_APPROVAL → APPROVED | ✅ | `actor_role=approver`, `X-Snapshot-Hash` confere |
| AWAITING_APPROVAL → REJECTED | ✅ | `actor_role=approver`, `reject_reason` obrigatório |
| AWAITING_APPROVAL → EXPIRED | ✅ | TTL expirado (reaper ou job), `actor_role=system` |
| APPROVED → PUBLISHED | ✅ | Publisher insere em `published`, `actor_role=system` |
| APPROVED → FAILED | ✅ | Erro na publicação (duplicidade), `actor_role=system` |
| * → * (outras) | ❌ | Rejeitado com `InvalidTransition` |

🟡 **Lock advisory (padrão):**
- Conexão dedicada `lock_conn` aberta no início da execução do worker, mantida até fim
- `SELECT pg_try_advisory_xact_lock(hash(task_id))` — NOWAIT, sem bloquear
- Se falha → `LockNotAcquired` (tarefa já em execução por outro worker)
- Liberado automaticamente no fim da transação (conexão dedicada = transação única)

🟡 **Lease fallback:**
- `UPDATE tasks SET locked_by = :worker_id, lease_until = now() + interval '5 min' WHERE task_id = :id AND (locked_by IS NULL OR lease_until < now())`
- Heartbeat renova a cada 30s (configurável)
- Reaper limpa leases expirados

---

## 4. Edge Cases

| Cenário | Comportamento |
|---------|---------------|
| 🟡 Dois workers tentam PENDING→RUNNING simultaneamente | Um adquire lock, outro recebe `LockNotAcquired` → tarefa reenfileirada |
| 🟡 Approve e reject concorrentes no mesmo task_id | Primeiro vence (UPDATE atômico com WHERE status); segundo recebe 409 |
| 🟡 Worker morre segurando lock advisory | Lock liberado automaticamente (fim de transação/sessão) |
| 🟡 Worker morre com lease ativo | Lease expira; reaper limpa e reenfileira |
| 🟡 Tentativa de transição de estado terminal | `InvalidTransition` — terminais não têm saídas |
| 🟡 Reentrega do broker com tarefa já em RUNNING | Lock advisory impede segunda execução; tarefa reenfileirada |

---

## 5. Não-Gols

🟡 Não implementar fila Celery / configuração de worker (componente `worker-queue`)
🟡 Não implementar checkpointer LangGraph (componente `langgraph-checkpointer`)
🟡 Não implementar endpoints HTTP (componente `task-api`)
🟡 Não definir TTL de aprovação (componente `approval-flow`)
🟡 Não implementar reaper (componente `worker-queue` — usa esta máquina)

---

## 6. Interface de Integração

🟡 **Entrada:** `task_id`, estado atual, estado desejado, motivo, ator
🟡 **Saída:** Novo estado persistido + evento em `task_events` + lock adquirido/liberado
🟡 **Dependências:** Pool `domain_pool` (conexões transacionais), conexão dedicada de lock, tabela `tasks`, tabela `task_events`

---

## 7. Critérios de Aceite (Gherkin)

```gherkin
Cenário: Transição atômica PENDING → RUNNING com lock
  Dado tarefa em PENDING
  Quando worker chama transition(task_id, 'PENDING', 'RUNNING', 'worker_started', 'system', worker_id)
  E outro worker tenta a mesma transição simultaneamente
  Então apenas um adquire o lock e persiste RUNNING
  E o outro recebe LockNotAcquired
  E task_events registra a transição com motivo legível

Cenário: Aprovação concorrente
  Dado tarefa em AWAITING_APPROVAL
  Quando duas requisições approve chegam simultaneamente com X-Snapshot-Hash válido
  Então uma transiciona para APPROVED
  E a outra recebe 409 com erro de conflito de estado

Cenário: Transição inválida rejeitada
  Dado tarefa em PUBLISHED
  Quando tenta transicionar para APPROVED
  Então InvalidTransition com detalhe: "PUBLISHED é terminal, transições permitidas: []"
```

---

## 8. Perguntas Abertas

⚠️ **ABERTO:** Advisory lock de sessão atrás de pooler (PgBouncer transaction mode) — confirmado não funcionar; MVP = conexão direta. Lease fallback validado no spike?
⚠️ **ABERTO:** Hash do `task_id` para advisory lock: `hashtext(task_id)` vs função customizada? Colisões aceitáveis?

---

## 9. Valores Iniciais (a medir)

| Parâmetro | Valor Inicial | Fonte |
|-----------|---------------|-------|
| 🟡 Lease TTL | 5 min | Arbitrário |
| 🟡 Heartbeat interval | 30s | Arbitrário |
| 🟡 Max reaper attempts | 3 | Arbitrário |

---

## 10. Relatório de Avaliação (Scoring)

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SCORE TOTAL: 90/100
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Breakdown:
  Completude:    95/100 (peso 30%)
  Testabilidade: 90/100 (peso 25%)
  Clareza:       90/100 (peso 20%)
  Escopo:        90/100 (peso 15%)
  Edge Cases:    85/100 (peso 10%)

Gaps críticos:
  - Validação do lease fallback no spike (se advisory lock falhar)
  - Hash para advisory lock: estratégia de colisão

Sugestões:
  1. Testar advisory lock com pg_try_advisory_xact_lock em cenários de concorrência real
  2. Documentar decisão de conexão direta ao Postgres (sem pooler transaction mode) no ADR
```