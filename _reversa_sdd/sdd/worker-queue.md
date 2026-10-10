# Spec: worker-queue

> Selo 🟡 PLANEJADO. Componente gerado pelo reversa-spec-sdd a partir do PRD FinAgent + AgentPulse.

---

## 1. Resumo

🟡 Fila Celery + Redis com `acks_late`, `task_reject_on_worker_lost`, `worker_prefetch_multiplier=1`, `visibility_timeout` fixo, reaper protegido por advisory lock, pools criados pós-fork.

---

## 2. Requisitos Funcionais

| ID | Requisito | Prioridade | Critério de Aceite |
|----|-----------|------------|---------------------|
| 🟡 RF-01 | Configurar Celery com `acks_late=True`, `task_reject_on_worker_lost=True`, `worker_prefetch_multiplier=1` | Must | Tarefa não ackada até fim; worker perdido → reentrega; sem prefetch excessivo |
| 🟡 RF-02 | `visibility_timeout` fixo e global = `task_time_limit` + maior backoff + margem | Must | Valor inicial 900s (arbitrário); confirmado/ajustado por p99 no spike; caos usa valor reduzido |
| 🟡 RF-03 | Pools Postgres criados em `worker_process_init` (pós-fork) e fechados em `worker_process_shutdown` | Must | Nunca no import; filho não herda sockets do pai |
| 🟡 RF-04 | Dois pools psycopg: `domain_pool` (transacional) + `checkpoint_pool` (autocommit, dict_row) + 1 conexão de lock | Must | Fórmula: `pool_size ≥ 1 (lock) + domain_pool_size + checkpoint_pool_size`; testar mínimo |
| 🟡 RF-05 | Reaper: tarefa periódica (Celery beat, instância única, advisory lock) a cada 60s | Must | Detecta e reenfileira: PENDING > 2min, RUNNING sem heartbeat > 45s (3×15s), APPROVED > 2min |
| 🟡 RF-06 | Reaper incrementa `attempts` a cada reenfileiramento; acima de 3 → FAILED | Must | `max_reaper_attempts = 3` (arbitrário); reenfileirar duplicado é inofensivo (lock atômico) |
| 🟡 RF-07 | Heartbeat: thread leve atualiza `tasks.heartbeat_at` durante chamadas longas (LLM) | Must | Intervalo 15s (arbitrário); atualizar só entre nós deixa reaper confundir lento com morto |
| 🟡 RF-08 | Failpoints ativáveis só com `APP_ENV=test` (SIGKILL no próprio processo); recusados no startup em prod | Must | `APP_ENV=prod` + failpoint ativo → erro de startup claro |

---

## 3. Comportamentos

🟡 **Configuração Celery (produção):**
```python
celery.conf.update(
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_time_limit=600,           # 10 min (valor inicial, a medir)
    task_soft_time_limit=540,      # 9 min
    visibility_timeout=900,        # 15 min = task_time_limit + backoff_max + margem
    result_expires=86400,          # 24h
)
```

🟡 **Pools (criados no `worker_process_init`):**
```python
# domain_pool: transacional
domain_pool = psycopg_pool.AsyncConnectionPool(
    conninfo=DATABASE_URL,
    min_size=2, max_size=5,  # ≥ 2
    kwargs={"autocommit": False}
)

# checkpoint_pool: autocommit + dict_row
checkpoint_pool = psycopg_pool.AsyncConnectionPool(
    conninfo=DATABASE_URL,
    min_size=2, max_size=5,
    kwargs={"autocommit": True, "row_factory": dict_row}
)

# lock_connection: dedicada, fora dos pools
lock_conn = await psycopg.AsyncConnection.connect(DATABASE_URL, autocommit=True)
```

🟡 **Reaper (beat, instância única, advisory lock):**
- Schedule: `*/1 * * * *` (cada 1 min)
- Lock: `pg_try_advisory_xact_lock(hash('reaper'))` — NOWAIT
- Critérios (configuráveis, iniciais arbitrários):
  - `PENDING` sem execução > 2 min → reenfileira
  - `RUNNING` com `heartbeat_at < now() - 45s` (3 × 15s) → reenfileira
  - `APPROVED` sem avançar > 2 min → reenfileira (retoma publicação)
- Cada reenfileiramento: `UPDATE tasks SET attempts = attempts + 1 WHERE task_id = :id`
- Se `attempts > 3` → `task-state-machine` transiciona para `FAILED`

🟡 **Heartbeat thread:**
- Iniciada no `worker_process_init`, para no `worker_process_shutdown`
- Atualiza `tasks.heartbeat_at = now()` a cada 15s enquanto tarefa em `RUNNING`
- Durante chamadas LLM longas: thread continua batendo; nó não bloqueia heartbeat

---

## 4. Edge Cases

| Cenário | Comportamento |
|---------|---------------|
| 🟡 Worker morre antes de criar pools | `worker_process_init` não rodou; tarefa reentregue pelo broker (`task_reject_on_worker_lost`) |
| 🟡 Redis indisponível no beat | Reaper não roda; tarefas presas até Redis voltar; `visibility_timeout` garante reentrega eventual |
| 🟡 Dois beaters tentam rodar reaper | Advisory lock garante instância única; segundo pula |
| 🟡 Tarefa `RUNNING` com heartbeat ativo mas worker travado (deadlock) | Heartbeat para → reaper detecta após 45s → reenfileira |
| 🟡 `APPROVED` preso (Publisher falhou) | Reaper reenfileira → worker retoma em `APPROVED` → Publisher tenta de novo (idempotente) |
| 🟡 Failpoint ativado em prod | Startup falha antes de criar pools; tarefa não executada |

---

## 5. Não-Gols

🟡 Não implementar máquina de estados (componente `task-state-machine`)
🟡 Não implementar checkpointer LangGraph (componente `langgraph-checkpointer`)
🟡 Não definir `task_time_limit`, `retry_backoff_max`, `max_retries` (valores a medir no spike)
🟡 Não implementar CI / job noturno (componente `ci-quality`)
🟡 Não implementar API HTTP (componente `task-api`)

---

## 6. Interface de Integração

🟡 **Entrada:** Tarefas Celery (serializadas), configuração via env/settings
🟡 **Saída:** Worker executa grafo; pools disponíveis via contexto; reaper mantém fila saudável
🟡 **Dependências:** `task-state-machine` (transições), `langgraph-checkpointer` (pools), `ci-quality` (beat schedule), `analysis-graph` (grafo executado)

---

## 7. Critérios de Aceite (Gherkin)

```gherkin
Cenário: Worker cria pools pós-fork
  Dado Celery worker inicia (prefork)
  Quando sinal worker_process_init é emitido
  Então domain_pool, checkpoint_pool e lock_connection são criados
  E pools não existem no módulo pai (import time)

Cenário: Reaper reenfileira tarefa RUNNING sem heartbeat
  Dado tarefa em RUNNING com heartbeat_at = now() - 60s
  E reaper roda com advisory lock
  Quando reaper processa
  Então tarefa reenfileirada com attempts + 1
  E heartbeat_at atualizado na retomada

Cenário: Failpoint recusado em prod
  Dado APP_ENV=prod e FAILPOINT_KILL_AFTER_QUANT=1
  Quando worker inicia
  Então erro de startup: "Failpoints não permitidos em produção"
  E worker não processa tarefas
```

---

## 8. Perguntas Abertas

⚠️ **ABERTO:** `task_time_limit`, `retry_backoff_max`, `max_retries` do Celery — valores baseados em p99 medido no spike
⚠️ **ABERTO:** Comportamento de `task_reject_on_worker_lost` + tempo de recuperação após SIGKILL com `visibility_timeout` do Redis
⚠️ **ABERTO:** Retry com `countdown` no Redis em relação ao `visibility_timeout` (evitar reentrega antes do countdown expirar)
⚠️ **ABERTO:** Celery beat com instância única para o reaper (confirmado: advisory lock)

---

## 9. Valores Iniciais (a medir)

| Parâmetro | Valor Inicial | Fonte |
|-----------|---------------|-------|
| 🟡 `task_time_limit` | 600s | Arbitrário |
| 🟡 `task_soft_time_limit` | 540s | Arbitrário |
| 🟡 `visibility_timeout` | 900s | task_time_limit + backoff + margem |
| 🟡 `retry_backoff_max` | TBD | Medir no spike |
| 🟡 `max_retries` | TBD | Medir no spike |
| 🟡 `worker_prefetch_multiplier` | 1 | Fixado |
| 🟡 Reaper interval | 60s | Arbitrário |
| 🟡 PENDING threshold | 2 min | Arbitrário |
| 🟡 RUNNING heartbeat threshold | 45s (3 × 15s) | Arbitrário |
| 🟡 APPROVED threshold | 2 min | Arbitrário |
| 🟡 Heartbeat interval | 15s | Arbitrário |
| 🟡 Max reaper attempts | 3 | Arbitrário |
| 🟡 `domain_pool` min/max | 2/5 | Arbitrário |
| 🟡 `checkpoint_pool` min/max | 2/5 | Arbitrário |

---

## 10. Relatório de Avaliação (Scoring)

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SCORE TOTAL: 86/100
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Breakdown:
  Completude:    85/100 (peso 30%)
  Testabilidade: 85/100 (peso 25%)
  Clareza:       85/100 (peso 20%)
  Escopo:        90/100 (peso 15%)
  Edge Cases:    85/100 (peso 10%)

Gaps críticos:
  - Timeouts e retries do Celery dependem de medições do spike
  - Interação retry countdown vs visibility_timeout precisa validação

Sugestões:
  1. Medir p99 de duração de nó no spike para calibrar timeouts
  2. Testar reaper com advisory lock sob concorrência real
  3. Validar que heartbeat thread não interfere em grafo síncrono
```