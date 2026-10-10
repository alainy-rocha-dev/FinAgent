# Interface: Worker Queue (Celery)

> Feature: `002-finagent-agentpulse`
> Contrato: Tarefa Celery `execute_graph` + sinais de observabilidade
> Queue: `finagent` (configurável)

## 1. Tarefa Celery: `execute_graph`

### Invocação (pela API)

```python
# Em task-api ao criar tarefa
celery.send_task(
    "worker.execute_graph",
    args=[task_id],           # UUID string = execution_id = thread_id
    kwargs={
        "symbol": "PETR4",
        "acknowledge_simulated": True,
        "graph_version": "1.0.0"
    },
    headers={
        "traceparent": "00-...",      # OpenTelemetry trace propagation
        "tracestate": "...",
        "idempotency_key": "...",     # para correlação
    },
    task_id=task_id,         # Celery task_id = task_id (permite deduplicação)
    queue="finagent"
)
```

### Parâmetros da task

| Arg | Tipo | Obrigatório | Descrição |
|-----|------|-------------|-----------|
| `task_id` | string (UUID) | Sim | Identificador único = `execution_id` = LangGraph `thread_id` |
| `symbol` | string | Sim | Ativo a analisar |
| `acknowledge_simulated` | boolean | Não (default false) | Permite `SIMULATED` fora de prod |
| `graph_version` | string | Sim | `GRAPH_VERSION` do código (ex: `1.0.0`) |

### Headers de observabilidade

| Header | Origem | Propagação |
|--------|--------|------------|
| `traceparent` | API (OTEL) | Worker extrai e continua span |
| `tracestate` | API (OTEL) | Worker extrai e continua span |
| `idempotency_key` | API | Correlação logs/métricas |

## 2. Configuração Celery (Worker)

```python
# worker/celery_app.py
celery.conf.update(
    # Execução
    task_acks_late=True,                    # Ack só após conclusão
    task_reject_on_worker_lost=True,        # Reentrega se worker morre
    worker_prefetch_multiplier=1,           # Sem prefetch (um por worker)
    
    # Timeouts (valores iniciais, a medir no spike)
    task_time_limit=600,                    # Hard limit (10 min)
    task_soft_time_limit=540,               # Soft limit (9 min)
    
    # Visibility timeout = task_time_limit + retry_backoff_max + margem
    # Valor inicial: 900s (15 min) — reduzido no caos para forçar reentrega
    broker_transport_options={
        "visibility_timeout": 900,
    },
    
    # Resultado
    result_expires=86400,                   # 24h
    result_backend="redis://localhost:6379/1",
    
    # Serialização
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    
    # Beat (reaper)
    beat_schedule={
        "reaper": {
            "task": "worker.reaper.run_reaper",
            "schedule": 60.0,  # cada 60s
            "options": {"queue": "finagent"},
        },
    },
)
```

## 3. Sinais Celery (Observabilidade)

### `task_prerun` — Extrai trace context

```python
@signals.task_prerun.connect
def extract_trace_context(sender=None, headers=None, **kwargs):
    """Continua trace da API no worker."""
    if headers:
        ctx = trace.get_current_span().get_span_context().extract(headers)
        trace.set_span_in_context(ctx)
```

### `task_postrun` — Métricas de duração

```python
@signals.task_postrun.connect
def record_task_metrics(sender=None, task_id=None, task=None, args=None, kwargs=None, retval=None, state=None, **kwargs):
    duration = time.time() - sender.request.start_time
    TASK_DURATION_SECONDS.labels(status=state).observe(duration)
    QUEUE_WAIT_SECONDS.labels().observe(sender.request.delivery_info.get("queue_wait", 0))
    
    # Incrementa contadores por status
    TASKS_COMPLETED_TOTAL.labels(status=state).inc()
```

### `worker_process_init` / `worker_process_shutdown` — Pools Postgres

```python
@signals.worker_process_init.connect
def init_pools(**kwargs):
    """Cria pools APÓS fork (nunca no import)."""
    global domain_pool, checkpoint_pool, lock_conn
    domain_pool = psycopg_pool.AsyncConnectionPool(
        conninfo=DATABASE_URL,
        min_size=2, max_size=5,
        kwargs={"autocommit": False}
    )
    checkpoint_pool = psycopg_pool.AsyncConnectionPool(
        conninfo=DATABASE_URL,
        min_size=2, max_size=5,
        kwargs={"autocommit": True, "row_factory": dict_row}
    )
    lock_conn = await psycopg.AsyncConnection.connect(DATABASE_URL, autocommit=True)

@signals.worker_process_shutdown.connect
async def close_pools(**kwargs):
    await domain_pool.close()
    await checkpoint_pool.close()
    await lock_conn.close()
```

## 4. Reaper (Celery Beat, instância única)

### Task: `worker.reaper.run_reaper`

```python
@celery.task(bind=True, max_retries=0)
def run_reaper(self):
    # Advisory lock garante instância única
    lock_acquired = await pg_try_advisory_xact_lock(hash("reaper"))
    if not lock_acquired:
        return  # Outra instância rodando
    
    now = datetime.utcnow()
    
    # PENDING > 2 min sem execução
    pending_stuck = await fetch("""
        SELECT task_id FROM tasks 
        WHERE status = 'PENDING' AND created_at < $1
    """, now - timedelta(minutes=2))
    
    # RUNNING sem heartbeat > 45s (3 × 15s)
    running_stuck = await fetch("""
        SELECT task_id FROM tasks 
        WHERE status = 'RUNNING' AND heartbeat_at < $1
    """, now - timedelta(seconds=45))
    
    # APPROVED > 2 min sem avançar
    approved_stuck = await fetch("""
        SELECT task_id FROM tasks 
        WHERE status = 'APPROVED' AND updated_at < $1
    """, now - timedelta(minutes=2))
    
    for task_id in pending_stuck + running_stuck + approved_stuck:
        await reenqueue(task_id)
```

### Critérios de reenfileiramento (configuráveis, valores iniciais)

| Estado | Threshold inicial | Ação |
|--------|-------------------|------|
| `PENDING` | > 2 min sem execução | Reenfileira |
| `RUNNING` | `heartbeat_at` > 45s (3 × 15s) | Reenfileira |
| `APPROVED` | > 2 min sem avançar | Reenfileira (retoma publicação) |

### Comportamento do reenfileiramento

```python
async def reenqueue(task_id: str):
    # Incrementa contador (protege contra loop infinito)
    attempts = await fetchval("""
        UPDATE tasks SET attempts = attempts + 1 
        WHERE task_id = $1 RETURNING attempts
    """, task_id)
    
    if attempts > 3:  # max_reaper_attempts (inicial, a medir)
        await transition(task_id, "FAILED", "reaper_max_attempts")
        return
    
    # Reenfileira no Celery (idempotente: task_id já existe)
    celery.send_task(
        "worker.execute_graph",
        args=[task_id],
        task_id=task_id,  # Mesmo ID = deduplicação broker
        queue="finagent"
    )
    await log_event(task_id, "REAPER_ACTION", {"action": "reenqueue", "attempts": attempts})
```

## 5. Heartbeat Thread (no worker)

```python
# Iniciada em worker_process_init, para em worker_process_shutdown
async def heartbeat_loop():
    while not shutdown_event.is_set():
        await asyncio.sleep(15)  # heartbeat_interval (inicial, a medir)
        if current_task_id:
            await execute("""
                UPDATE tasks SET heartbeat_at = NOW() 
                WHERE task_id = $1 AND status = 'RUNNING'
            """, current_task_id)
```

- **Importante**: Atualiza durante chamadas LLM longas (não só entre nós)
- Thread separada do grafo síncrono → não bloqueia execução

## 6. Failpoints (Chaos Testing)

```python
FAILPOINTS = {
    "KILL_AFTER_QUANT": "SIGKILL após checkpoint do analista quant",
    "KILL_AFTER_INTERRUPT": "SIGKILL após interrupt (await_approval)",
    "KILL_DURING_RESUME": "SIGKILL durante retomada (entre efeito e ack)",
}

def check_failpoints():
    if APP_ENV == "prod" and any(os.getenv(f"FAILPOINT_{k}") for k in FAILPOINTS):
        raise RuntimeError("Failpoints não permitidos em produção. Use APP_ENV=test.")
    if APP_ENV == "test":
        for k, desc in FAILPOINTS.items():
            if os.getenv(f"FAILPOINT_{k}"):
                register_failpoint(k)  # SIGKILL no próprio processo
```

- **Ativação**: `APP_ENV=test` + `FAILPOINT_KILL_AFTER_QUANT=1`
- **Produção**: Startup falha se qualquer failpoint ativo
- **Uso**: Spike + caos 100 execuções (failpoints + docker kill real misturados)

## 7. Configuração de ambiente (Worker)

```bash
# .env (worker)
APP_ENV=dev                    # prod | dev | test
DATABASE_URL=postgresql://app_user:senha@postgres:5432/agentpulse
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/1

# Timeouts (valores iniciais, a medir)
TASK_TIME_LIMIT=600
TASK_SOFT_TIME_LIMIT=540
VISIBILITY_TIMEOUT=900
HEARTBEAT_INTERVAL=15
REAPER_INTERVAL=60
MAX_REAPER_ATTEMPTS=3

# Observabilidade
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4318/v1/traces
PROMETHEUS_PORT=9090
LOG_LEVEL=INFO
```

## 8. Métricas Prometheus (Worker)

| Métrica | Tipo | Labels | Descrição |
|---------|------|--------|-----------|
| `tasks_completed_total` | Counter | `status` | Tarefas finalizadas por status |
| `task_retries_total` | Counter | `step`, `error_type` | Retentativas por nó/tipo erro |
| `task_duration_seconds` | Histogram | `status` | Duração total da tarefa |
| `step_duration_seconds` | Histogram | `step` | Duração por nó do grafo |
| `queue_wait_seconds` | Histogram | — | Tempo na fila antes de executar |
| `active_tasks` | Gauge | — | Tarefas em execução no worker |
| `workers_online` | Gauge | — | Workers ativos (heartbeat) |
| `llm_tokens_total` | Counter | `model`, `step` | Tokens consumidos |
| `llm_cost_usd_total` | Counter | `model` | Custo USD (do budget-control) |

## 9. Contrato de idempotência (Worker)

- **Celery task_id = `task_id`** → Broker deduplica reenfileiramento
- **`task_reject_on_worker_lost=True`** → Broker reentrega se worker morre antes de ack
- **`worker_prefetch_multiplier=1`** → Um task por worker por vez
- **Advisory lock** → Execução exclusiva por `task_id` (mesmo com reentrega)
- **Checkpointer Postgres** → Estado salvo a cada nó (`thread_id = task_id`)

## 10. Valores iniciais "a medir" (config/defaults.yaml)

```yaml
worker:
  task_time_limit: 600
  task_soft_time_limit: 540
  visibility_timeout: 900
  visibility_timeout_chaos: 30
  heartbeat_interval: 15
  reaper_interval: 60
  max_reaper_attempts: 3
  prefetch_multiplier: 1
  acks_late: true
  reject_on_worker_lost: true
```

*Etiqueta: Todos marcados como "valor inicial, a medir" no `HANDOFF_REPORT.md`.*