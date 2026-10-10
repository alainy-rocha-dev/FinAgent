# Spec: observability

> Selo 🟡 PLANEJADO. Componente gerado pelo reversa-spec-sdd a partir do PRD FinAgent + AgentPulse.

---

## 1. Resumo

🟡 Observabilidade completa: OpenTelemetry traces (API → Celery → nós), propagação de contexto pelo Celery (não automática), métricas Prometheus, logs estruturados JSON, dashboard Grafana provisionado, custos LLM. Failpoints ativáveis só com `APP_ENV=test`, recusados no startup em prod.

---

## 2. Requisitos Funcionais

| ID | Requisito | Prioridade | Critério de Aceite |
|----|-----------|------------|---------------------|
| 🟡 RF-01 | Traces OpenTelemetry: propagação `traceparent`/`tracestate` da API → Celery (headers da task) → nós do grafo (span por nó) | Must | Exporters: OTLP/HTTP para collector (configurável), console no dev. Sampler: `TraceIdRatioBased` (1.0 dev, 0.1 prod inicial) |
| 🟡 RF-02 | Propagação de trace pelo Celery: injetar `traceparent` no header da task Celery; worker extrai e continua span | Must | Não é automático — instrumentação customizada no `task_postrun` / `task_prerun` signals |
| 🟡 RF-03 | Métricas Prometheus expostas em `/metrics` (API porta 8000, worker porta 9090) | Must | Contadores: `tasks_created_total{role}`, `tasks_completed_total{status}`, `task_retries_total{step,error_type}`, `llm_tokens_total{model,step}`, `llm_cost_usd_total{model}`, `approval_duration_seconds`, `publish_duration_seconds`. Histogramas: `task_duration_seconds{status}`, `step_duration_seconds{step}`, `queue_wait_seconds`. Gauges: `active_tasks`, `workers_online` |
| 🟡 RF-04 | Logs estruturados JSON: `trace_id`, `span_id`, `task_id`, `step_name`, `attempt`, `level`, `message`, `attrs` | Must | Nível padrão `INFO`; `DEBUG` inclui payloads truncados. Correlation ID propagado em headers HTTP de saída (provedores, LLM) |
| 🟡 RF-05 | Dashboard Grafana provisionado (JSON) com painéis: taxa sucesso por status, p50/p95/p99 duração por etapa, retries por tipo erro, tokens/custo por modelo, fila (pending/running), workers online, aprovações pendentes, publicações/hora | Should | Alertas: taxa falha > 5% em 5min, fila > 100 pending, worker offline > 2min |
| 🟡 RF-06 | Custos LLM: `llm_cost_usd_total` alimentado pelo `budget-control` (mesmo contador) | Must | Dashboard mostra custo por tarefa, por modelo, acumulado mensal vs orçamento |
| 🟡 RF-07 | Failpoints: `FAILPOINT_KILL_AFTER_QUANT`, `FAILPOINT_KILL_AFTER_INTERRUPT`, etc. — só ativáveis com `APP_ENV=test` | Must | `APP_ENV=prod` + failpoint ativo → erro de startup claro; recusados antes de criar pools |
| 🟡 RF-08 | Configuração de ambiente centralizada: `APP_ENV`, `LOG_LEVEL`, `OTEL_EXPORTER_OTLP_ENDPOINT`, `PROMETHEUS_PORT` | Must | Validada no startup; valores padrão sensatos |

---

## 3. Comportamentos

🟡 **Instrumentação OpenTelemetry (API):**
```python
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import TraceIdRatioBased

provider = TracerProvider(sampler=TraceIdRatioBased(0.1 if APP_ENV=="prod" else 1.0))
provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=OTEL_EXPORTER_OTLP_ENDPOINT)))
trace.set_tracer_provider(provider)
```

🟡 **Propagação Celery (custom):**
```python
# API: antes de enfileirar
from celery import current_task
headers = {}
trace.get_current_span().get_span_context().inject(headers)
task = celery.send_task("worker.execute_graph", args=[...], headers=headers)

# Worker: no task_prerun signal
@signals.task_prerun.connect
def extract_trace_context(sender=None, headers=None, **kwargs):
    ctx = trace.get_current_span().get_span_context().extract(headers)
    trace.set_span_in_context(ctx)
```

🟡 **Métricas (Prometheus client):**
```python
from prometheus_client import Counter, Histogram, Gauge

tasks_created_total = Counter("tasks_created_total", "Tasks created", ["role"])
tasks_completed_total = Counter("tasks_completed_total", "Tasks completed", ["status"])
task_retries_total = Counter("task_retries_total", "Task retries", ["step", "error_type"])
llm_tokens_total = Counter("llm_tokens_total", "LLM tokens", ["model", "step"])
llm_cost_usd_total = Counter("llm_cost_usd_total", "LLM cost USD", ["model"])
task_duration_seconds = Histogram("task_duration_seconds", "Task duration", ["status"])
step_duration_seconds = Histogram("step_duration_seconds", "Step duration", ["step"])
queue_wait_seconds = Histogram("queue_wait_seconds", "Queue wait time")
active_tasks = Gauge("active_tasks", "Active tasks")
workers_online = Gauge("workers_online", "Workers online")
```

🟡 **Failpoints (só `APP_ENV=test`):**
```python
FAILPOINTS = {
    "KILL_AFTER_QUANT": "SIGKILL após checkpoint do analista quant",
    "KILL_AFTER_INTERRUPT": "SIGKILL após interrupt",
    "KILL_DURING_RESUME": "SIGKILL durante retomada",
}

def check_failpoints():
    if APP_ENV == "prod" and any(os.getenv(f"FAILPOINT_{k}") for k in FAILPOINTS):
        raise RuntimeError("Failpoints não permitidos em produção. Use APP_ENV=test.")
    if APP_ENV == "test":
        for k, desc in FAILPOINTS.items():
            if os.getenv(f"FAILPOINT_{k}"):
                register_failpoint(k)
```

---

## 4. Edge Cases

| Cenário | Comportamento |
|---------|---------------|
| 🟡 Collector OTLP indisponível | BatchSpanProcessor faz buffer; spans não perdidos; loga warning |
| 🟡 Trace ID não propagado no Celery | Span do worker inicia novo trace (órfão); loga warning; métricas ainda funcionam |
| 🟡 Métricas Prometheus não acessíveis | `/metrics` retorna 500; alerta Grafana "scrape failed" |
| 🟡 Failpoint ativado em prod | Startup falha antes de qualquer processamento; mensagem clara |
| 🟡 Log level `DEBUG` em prod | Payloads truncados (ex: primeiros 500 chars); não vaza dados sensíveis |

---

## 5. Não-Gols

🟡 Não implementar alertas além dos 3 básicos (taxa falha, fila, worker offline)
🟡 Não implementar distributed tracing além do escopo (API → Celery → nós)
🟡 Não implementar log aggregation (ELK/Loki) — fora de escopo
🟡 Não definir `OTEL_EXPORTER_OTLP_ENDPOINT` padrão (configurável)
🟡 Não implementar profiling contínuo (py-spy, etc.)

---

## 6. Interface de Integração

🟡 **Entrada:** Código instrumentado em API, worker, grafo; config via env
🟡 **Saída:** Traces (OTLP), métricas (`/metrics`), logs (stdout JSON), dashboard (Grafana JSON)
🟡 **Dependências:** `budget-control` (alimenta `llm_cost_usd_total`), `worker-queue` (instrumenta Celery signals), `analysis-graph` (spans por nó), `task-api` (spans HTTP), `ci-quality` (dashboard provisionado no CI)

---

## 7. Critérios de Aceite (Gherkin)

```gherkin
Cenário: Trace propagado API → Celery → nó
  Dado requisição POST /tasks com traceparent
  Quando worker pega task e executa grafo
  Então span do nó collector tem trace_id = trace_id da API
  E span do nó quant_analyst tem mesmo trace_id
  E trace completo visível no collector OTLP

Cenário: Métricas expostas e coletadas
  Dado API e worker rodando
  Quando curl /metrics na API e no worker
  Então contadores, histogramas, gauges presentes
  E labels corretos (role, status, step, model, error_type)

Cenário: Failpoint recusado em prod
  Dado APP_ENV=prod e FAILPOINT_KILL_AFTER_QUANT=1
  Quando worker inicia
  Então erro: "Failpoints não permitidos em produção. Use APP_ENV=test."
  E worker não processa tarefas

Cenário: Custo LLM no dashboard
  Dado budget-control consome tokens
  Quando dashboard Grafana carrega
  Então painel "LLM Cost USD por modelo" mostra valores
  E painel "Custo acumulado mensal vs orçamento" atualizado
```

---

## 8. Perguntas Abertas

⚠️ **ABERTO:** `OTEL_EXPORTER_OTLP_ENDPOINT` padrão (ex: `http://otel-collector:4318/v1/traces`)
⚠️ **ABERTO:** Sampler rate prod (0.1 inicial) — ajustar após medir volume
⚠️ **ABERTO:** Retenção de traces no collector (fora de escopo deste componente)
⚠️ **ABERTO:** Dashboard Grafana JSON — versionado no repo ou provisionado via API?

---

## 9. Valores Iniciais (a medir)

| Parâmetro | Valor Inicial | Fonte |
|-----------|---------------|-------|
| 🟡 Sampler rate dev | 1.0 | Fixado |
| 🟡 Sampler rate prod | 0.1 | Arbitrário |
| 🟡 Alerta taxa falha | > 5% em 5 min | Arbitrário |
| 🟡 Alerta fila pending | > 100 | Arbitrário |
| 🟡 Alerta worker offline | > 2 min | Arbitrário |
| 🟡 Log truncation DEBUG | 500 chars | Arbitrário |

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
  - Propagação de trace pelo Celery requer instrumentação customizada (signals)
  - Failpoints precisam ser registrados no código de produção (desligados por padrão)
  - Dashboard Grafana JSON: versionado no repo vs provisionado via API

Sugestões:
  1. Implementar signals Celery `task_prerun`/`task_postrun` para propagação de trace
  2. Adicionar teste de integração: trace completo API → worker → nó
  3. Validar failpoints em CI (APP_ENV=test) e bloqueio em prod
```