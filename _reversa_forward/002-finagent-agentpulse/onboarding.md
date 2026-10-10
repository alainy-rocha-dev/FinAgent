# Onboarding: Migração FinAgent para Infraestrutura AgentPulse

> Feature: `002-finagent-agentpulse`
> Data: `2026-10-05`
> Objetivo: Passo a passo executável para testar a feature pela primeira vez

## 1. Pré-requisitos

### 1.1 Ambiente
- Docker + Docker Compose v2
- Python 3.11+
- `make` (opcional, atalhos no `Makefile`)
- Git

### 1.2 Configuração inicial (uma vez)

```bash
# Clone e entre no projeto
git clone <repo-url>
cd sisanalisefinanceira

# Copie arquivo de ambiente
cp .env.example .env

# Edite .env com suas chaves (mínimo para rodar)
# OPENAI_API_KEY=sk-...          # para LLM real (opcional, usa stub se vazio)
# ANTHROPIC_API_KEY=sk-ant-...   # alternativa
# DATABASE_URL=postgresql://app_user:senha@localhost:5432/agentpulse
# REDIS_URL=redis://localhost:6379/0
# APP_ENV=dev
# ALLOW_SIMULATED_PUBLICATION=true
# STALE_MAX_AGE_EQUITY=5
# STALE_MAX_AGE_FX=3
# STALE_MAX_AGE_CRYPTO=1
# STALE_MAX_AGE_OTHER=5
```

### 1.3 Subir infraestrutura

```bash
# Sobe Postgres + Redis + API + Worker (via Docker Compose)
docker compose up -d --build

# Verifica saúde
curl http://localhost:8000/health
# {"status":"ok","checks":{"database":true,"redis":true}}

# Verifica worker Celery
docker compose logs worker | grep "celery@worker ready"
```

## 2. Criar API Keys (dois papéis)

```bash
# Analyst (cria tarefas)
curl -X POST http://localhost:8000/api-keys \
  -H "Content-Type: application/json" \
  -d '{"name": "analista-teste", "role": "analyst"}'
# Retorna: {"api_key_id": "...", "key": "ak_live_..."}  <-- GUARDE ESTA CHAVE

# Approver (aprova/rejeita)
curl -X POST http://localhost:8000/api-keys \
  -H "Content-Type: application/json" \
  -d '{"name": "aprovador-teste", "role": "approver"}'
# Retorna: {"api_key_id": "...", "key": "ak_live_..."}  <-- GUARDE ESTA CHAVE
```

## 3. Executar primeira análise (fluxo completo)

### 3.1 Submeter tarefa (papel `analyst`)

```bash
export ANALYST_KEY="ak_live_..."  # chave do analyst
export IDEMPOTENCY_KEY="test-$(date +%s)"

curl -X POST http://localhost:8000/tasks \
  -H "Authorization: Bearer $ANALYST_KEY" \
  -H "Idempotency-Key: $IDEMPOTENCY_KEY" \
  -H "Content-Type: application/json" \
  -d '{"symbol": "PETR4", "acknowledge_simulated": true}'
```

**Resposta esperada (202):**
```json
{
  "task_id": "uuid-da-tarefa",
  "status": "PENDING"
}
```

### 3.2 Acompanhar execução

```bash
export TASK_ID="uuid-da-tarefa"

# Poll até AWAITING_APPROVAL
while true; do
  curl -s -H "Authorization: Bearer $ANALYST_KEY" \
    "http://localhost:8000/tasks/$TASK_ID" | jq '.status'
  sleep 2
done
```

### 3.3 Ver detalhes antes de aprovar

```bash
curl -H "Authorization: Bearer $ANALYST_KEY" \
  "http://localhost:8000/tasks/$TASK_ID" | jq .
```

Campos importantes:
- `data_quality`: `LIVE` | `STALE` | `SIMULATED` (badge na UI)
- `quant_metrics`: métricas determinísticas calculadas
- `report_draft`: relatório preliminar (HTML)
- `audit_result`: resultado da auditoria numérica
- `snapshot_hash`: **copie este valor** para aprovação

### 3.4 Aprovar via API (papel `approver`)

```bash
export APPROVER_KEY="ak_live_..."  # chave do approver
export SNAPSHOT_HASH="<hash-copiado-do-passo-3.3>"

curl -X POST "http://localhost:8000/tasks/$TASK_ID/approve" \
  -H "Authorization: Bearer $APPROVER_KEY" \
  -H "X-Snapshot-Hash: $SNAPSHOT_HASH" \
  -H "Content-Type: application/json" \
  -d '{"justification": "Métricas conferem, dados atuais"}'
```

**Resposta esperada (200):**
```json
{
  "task_id": "uuid",
  "status": "PUBLISHED",
  "published_at": "2026-10-05T...",
  "published_by": "approver-api-key-id"
}
```

### 3.5 Ver resultado final

```bash
curl -H "Authorization: Bearer $ANALYST_KEY" \
  "http://localhost:8000/tasks/$TASK_ID" | jq '{status, published_at, report_final: .report_final}'
```

## 4. Testar cenários de borda

### 4.1 Idempotência (mesma chave = mesmo resultado)

```bash
# Primeira request
curl -X POST http://localhost:8000/tasks \
  -H "Authorization: Bearer $ANALYST_KEY" \
  -H "Idempotency-Key: mesma-chave-123" \
  -d '{"symbol": "AAPL", "acknowledge_simulated": true}'

# Segunda request (mesma chave, mesmo payload) → 200 Replay
curl -X POST http://localhost:8000/tasks \
  -H "Authorization: Bearer $ANALYST_KEY" \
  -H "Idempotency-Key: mesma-chave-123" \
  -d '{"symbol": "AAPL", "acknowledge_simulated": true}'
# Header: Idempotent-Replay: true

# Terceira request (mesma chave, payload diferente) → 409
curl -X POST http://localhost:8000/tasks \
  -H "Authorization: Bearer $ANALYST_KEY" \
  -H "Idempotency-Key: mesma-chave-123" \
  -d '{"symbol": "GOOGL", "acknowledge_simulated": true}'
# {"error": "idempotency_key_reused_with_different_payload"}
```

### 4.2 Papéis cruzados (403)

```bash
# Approver tentando criar tarefa
curl -X POST http://localhost:8000/tasks \
  -H "Authorization: Bearer $APPROVER_KEY" \
  -H "Idempotency-Key: teste-403" \
  -d '{"symbol": "PETR4"}'
# 403: "analyst role required"

# Analyst tentando aprovar
curl -X POST "http://localhost:8000/tasks/$TASK_ID/approve" \
  -H "Authorization: Bearer $ANALYST_KEY" \
  -H "X-Snapshot-Hash: $SNAPSHOT_HASH"
# 403: "approver role required"
```

### 4.3 Rejeição com categoria obrigatória

```bash
curl -X POST "http://localhost:8000/tasks/$TASK_ID/reject" \
  -H "Authorization: Bearer $APPROVER_KEY" \
  -H "X-Snapshot-Hash: $SNAPSHOT_HASH" \
  -H "Content-Type: application/json" \
  -d '{"reject_reason": "data_quality", "justification": "Dados simulados não permitidos"}'
# Status final: REJECTED
```

### 4.4 Dados SIMULADOS em produção (bloqueio)

```bash
# Altere .env: APP_ENV=prod
# Reinicie: docker compose restart api worker

curl -X POST http://localhost:8000/tasks \
  -H "Authorization: Bearer $ANALYST_KEY" \
  -H "Idempotency-Key: sim-prod" \
  -d '{"symbol": "PETR4", "acknowledge_simulated": true}'
# 422 ou DATA_QUALITY_BLOCKED (worker não inicia se ALLOW_SIMULATED_PUBLICATION=true)
```

### 4.5 UI de aprovação (navegador)

```bash
# Abra no navegador (requer login via header Authorization)
# http://localhost:8000/approval/<TASK_ID>
# 
# Ou use curl com Accept: text/html:
curl -H "Authorization: Bearer $APPROVER_KEY" \
  -H "Accept: text/html" \
  "http://localhost:8000/approval/$TASK_ID"
```

A página mostra:
- Badge `data_quality` (verde/amarelo/vermelho)
- Métricas quantitativas formatadas
- Relatório preliminar (HTML seguro)
- Resultado da auditoria numérica
- `snapshot_hash` em código + campo hidden no form
- Botões "Aprovar" / "Rejeitar" com modal de confirmação
- Aviso: "Não insira dados pessoais no motivo da rejeição"

## 5. Executar testes de caos (validação da premissa nº 1)

```bash
# Ambiente de teste
export APP_ENV=test
docker compose -f docker-compose.yml -f docker-compose.chaos.yml up -d --build

# Spike mínimo (grafo 2 nós + harness C1+C2)
python -m tests.chaos_runner --executions 10 --scenarios C1,C2 --seed 42

# Caos completo (100 execuções, C1-C5)
python -m tests.chaos_runner --executions 100 --seed 42

# Relatório
cat chaos-report.md
# Esperado: 0 duplicadas, 0 perdidas, retomadas do último checkpoint
```

### Cenários cobertos:
- **C1**: Kill após checkpoint quant (antes interrupt)
- **C2**: Kill entre interrupt checkpoint e RUNNING→AWAITING_APPROVAL; durante retomada; entre commit decisão e enfileiramento resume
- **C3**: Reentrega real broker (visibility_timeout reduzido)
- **C4**: Decisões concorrentes (approve × approve, approve × reject, approve × expiração)
- **C5**: Dois workers mesmo `thread_id` (race de lock)

## 6. Verificar observabilidade

```bash
# Métricas Prometheus
curl http://localhost:8000/metrics | grep tasks_
curl http://localhost:9090/metrics | grep tasks_

# Logs estruturados (JSON)
docker compose logs -f api | jq .
docker compose logs -f worker | jq .

# Traces (se OTLP collector configurado)
# Ver no Jaeger/Grafana Tempo: serviço "finagent-api", "finagent-worker"
```

## 7. Testar modo legacy (compatibilidade)

```bash
# Sem AgentPulse/Postgres
python -m sisanalisefinanceira.cli --symbol PETR4 --legacy

# Deve imprimir relatório idêntico ao pré-migração
# AVISO no --help: "Modo legacy NÃO tem durabilidade, retomada nem aprovação"
```

## 8. Configuração centralizada (28 parâmetros "a medir")

Arquivo único: `config/defaults.yaml` + variáveis de ambiente (`.env` sobrescreve).

```yaml
# Valores iniciais (arbitrários, calibrar no spike/uso real)
approval_ttl_hours: 168                    # 7 dias
monthly_token_budget: 1000000              # baixo por padrão
token_budget_per_task: 50000               # provisório conservador
max_reaper_attempts: 3
isclose_rel_tol: 1e-9
isclose_abs_tol: 1e-12
retention_days: 365
stale_max_age_days:
  equity: 5
  fx: 3
  crypto: 1
  other: 5
reject_reason_min_chars: 10
reject_reason_max_chars: 1000
rate_limit:
  tasks_post: 10      # req/s por api_key_id
  tasks_get: 30
  approve_reject: 20
task_time_limit: 600
retry_backoff_max: 60
max_retries: 3
heartbeat_interval: 15
visibility_timeout: 900
visibility_timeout_chaos: 30   # reduzido para forçar reentrega real
mutations_per_class: 30
clean_reports_for_fp: 50
coverage_min: 85
sampler_rate_prod: 0.1
alert_failure_rate_pct: 5
alert_queue_pending: 100
alert_worker_offline_min: 2
```

**Etiqueta**: Todos marcados como "valor inicial, a medir" no `HANDOFF_REPORT.md`.

## 9. Troubleshooting rápido

| Sintoma | Verificação | Ação |
|---------|-------------|------|
| Worker não inicia | `docker compose logs worker` | Ver `APP_ENV`, failpoints, conexão Postgres |
| Tarefa travada em PENDING | `curl /tasks/{id}` + logs worker | Ver Celery beat, reaper, Redis |
| Aprovação 409 hash mismatch | `X-Snapshot-Hash` confere com `task_events` | Reabrir página, copiar hash atual |
| `DATA_QUALITY_BLOCKED` inesperado | `data_quality` no `/tasks/{id}` | Ver `acknowledge_simulated`, `APP_ENV`, `ALLOW_SIMULATED_PUBLICATION` |
| Métricas não aparecem | `/metrics` exposto? | Ver `PROMETHEUS_PORT`, `prometheus.yml` |
| Traces não propagam | Header `traceparent` no Celery? | Ver signals `task_prerun`/`task_postrun` em `observability` |

## 10. Próximos passos após validar

1. Rodar suite completa de testes: `pytest -v --cov=src --cov-fail-under=85`
2. Executar caos noturno: `python -m tests.chaos_runner --executions 100`
3. Preencher ADR 001 com métricas do spike
4. Aplicar legacy-fixes precisão (semanas 1-2)
5. Iniciar etapa 2: `task-api`, `audit-trail`, `approval-flow`, `publication`