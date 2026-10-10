# Investigation: Migração FinAgent para Infraestrutura AgentPulse

> Feature: `002-finagent-agentpulse`
> Data: `2026-10-05`
> Fonte: `requirements.md` + extração reversa (`_reversa_sdd/`)

## 1. Pesquisa de fundo

### 1.1 Contexto do legado (FinAgent)
- **Arquitetura atual**: Sistema multiagentes standalone (CLI) sem infraestrutura de produção
- **3 agentes**: `DataCollectorAgent` (Yahoo Finance + mock fallback), `QuantAnalystAgent` (Pandas/NumPy determinístico), `ReportWriterAgent` (Markdown + validação anti-alucinação)
- **2 orquestradores**: `LangGraphOrchestrator` (grafo iterativo, `max_iter=3`), `CrewAIOrchestrator` (sequencial)
- **Dívidas**: sem `requirements.txt`/`pyproject.toml`; testes parciais (só collector + quant); rate limit sem retry exponencial
- **Schemas Pydantic**: `MarketDataPayload`, `QuantAnalysisMetrics`, `AgentState` (imutáveis)

### 1.2 Contexto da infraestrutura (AgentPulse)
- **Stack**: FastAPI + Celery + Redis + PostgreSQL
- **API assíncrona**: SQLAlchemy async + asyncpg
- **Worker**: Celery prefork, execução síncrona de grafo LangGraph
- **Já possui**: autenticação API key, rate limiting, observabilidade básica

### 1.3 Gap a preencher
| Capacidade | FinAgent (atual) | AgentPulse (infra) | Necessário implementar |
|------------|------------------|---------------------|------------------------|
| Fila/resiliência | ❌ | ✅ Celery + Redis | Integração worker + grafo |
| Checkpoints | ❌ | ❌ | LangGraph Postgres checkpointer |
| Aprovação humana | ❌ | ❌ | Interrupt/resume + UI |
| Idempotência | ❌ | Parcial | Chaves + tabelas + Publisher |
| Caos/retomada | ❌ | ❌ | Spike + 100 execs + harness |
| Orçamento tokens | ❌ | ❌ | Budget-control service |
| Auditoria numérica | Parcial (anti-hallucination) | ❌ | Registry + marcadores + validador último portão |

## 2. Alternativas avaliadas

### 2.1 Orquestração: Celery vs Temporal
- **Celery (escolhido)**: Stack já existe no AgentPulse; equipe conhece; spike valida retomada sem duplicação; reaper/lock/idempotência customizados
- **Temporal**: Nativo exactly-once, signals, observabilidade; mas curva alta, cluster 4+ serviços, custo infra maior
- **Decisão**: Spike com Celery primeiro (D-13). Se portão fechar → ADR 002 para Temporal

### 2.2 Checkpointer: LangGraph nativo vs custom
- **Nativo PostgresSaver**: Mantém compatibilidade com versão fixada; exige `autocommit` + `dict_row`; `graph_version` para compatibilidade
- **Custom**: Controle total mas reimplementa lógica complexa de snapshot/restore
- **Decisão**: Nativo com pool dedicado `checkpoint_pool` (D-01)

### 2.3 Advisory lock vs Lease em tabela
- **Advisory lock sessão (escolhido)**: Liberado automaticamente ao fechar conexão; sem TTL; performático
- **Lease em tabela (`locked_by`, `lease_until`)**: Fallback se pooler; exige heartbeat + reaper cleanup
- **Decisão**: Advisory lock padrão; lease fallback documentado (D-02)

### 2.4 Aprovação: Interrupt LangGraph + reenfileiramento vs Signals nativos
- **Interrupt + reenfileiramento (escolhido)**: Funciona com Celery; TTL 7 dias; `X-Snapshot-Hash` garante decisão sobre snapshot visto
- **Signals Temporal**: Nativo pausas ilimitadas; não disponível no Celery
- **Decisão**: Custom com polling 5s no worker (D-10, D-11)

### 2.5 `data_quality` STALE: minutos vs dias por classe
- **Dias por classe de ativo (escolhido)**: Cotações diárias → STALE em minutos não faz sentido; equity=5d, fx=3d, crypto=1d, other=5d
- **Minutos fixos**: Simples mas inadequado para dados diários
- **Decisão**: `stale_max_age_days[asset_class]` configurável (D-04)

## 3. Padrões aplicáveis

| Padrão | Onde aplica | Referência |
|--------|-------------|------------|
| Adapter Pattern | Orquestração intercambiável (LangGraph/CrewAI) | `_reversa_sdd/architecture.md#4` |
| Strategy Pattern | Tools determinísticas (Pandas/Math fallback) | `_reversa_sdd/architecture.md#4` |
| Anti-Hallucination Guardrail | Validação numérica relatório vs métricas | `_reversa_sdd/architecture.md#4` |
| Idempotency Key | `POST /tasks` + Celery task deduplication | IETF draft (registrar versão) |
| Advisory Lock | Execução exclusiva por `task_id` | PostgreSQL docs |
| Saga / Transação compensatória | Publisher (INSERT published + UPDATE tasks + evento) | `_reversa_sdd/architecture.md#4` |
| Circuit Breaker | Coleta Yahoo Finance (retry exponencial + fallback mock) | `_reversa_sdd/architecture.md#5` |
| Canary / Smoke test | CI fumaça caos (~5 execs) em PRs críticos | `ci-quality` spec |
| Config as Code | `config/defaults.yaml` + env vars para 28 parâmetros | D-17 |

## 4. Links para fontes externas

| Tópico | Link | Versão/Data consulta |
|--------|------|---------------------|
| LangGraph Postgres Checkpointer | https://langchain-ai.github.io/langgraph/reference/checkpointers/ | (registrar) |
| Celery `task_reject_on_worker_lost` | https://docs.celeryq.dev/en/stable/userguide/tasks.html | (registrar) |
| PostgreSQL Advisory Locks | https://www.postgresql.org/docs/current/explicit-locking.html#ADVISORY-LOCKS | (registrar) |
| IETF Idempotency-Key Draft | https://datatracker.ietf.org/doc/draft-ietf-httpapi-idempotency-key-headers/ | (registrar status atual) |
| Yahoo Finance Terms of Use | https://finance.yahoo.com/ | (registrar) |
| BCB API Docs | https://dadosabertos.bcb.gov.br/ | (registrar) |
| Temporal Docs (exactly-once) | https://docs.temporal.io/docs/concepts/what-is-temporal | (registrar versão+data) |
| OpenTelemetry Python Celery Instrumentation | https://opentelemetry-python.readthedocs.io/en/latest/instrumentation/celery/ | (registrar) |
| Hypothesis Property-Based Testing | https://hypothesis.readthedocs.io/ | (registrar) |

## 5. Perguntas abertas (para `/reversa-clarify` se necessário)

| Pergunta | Bloqueia | Prioridade |
|----------|----------|------------|
| Formato exato do serializador nativo do LangGraph + exigência `autocommit`/`dict_row`? | `langgraph-checkpointer`, spike | Alta |
| Nó com `interrupt()` reexecuta desde o início na retomada? | `analysis-graph`, spike | Alta |
| Assinatura `Command(resume=...)` na versão fixada? | `analysis-graph`, `approval-flow` | Alta |
| Tolerância LangGraph a nós removidos/renomeados com checkpoints existentes? | `langgraph-checkpointer`, `graph_version` | Alta |
| `task_reject_on_worker_lost` + tempo recuperação após SIGKILL com `visibility_timeout` Redis? | `worker-queue`, spike | Alta |
| Retry `countdown` no Redis vs `visibility_timeout` interação? | `worker-queue`, spike | Média |
| Rascunho IETF Idempotency-Key header/semântica/escopo/status? | `task-api` | Média |
| Termos Yahoo Finance / BCB permitem produção? Rate limits? | `data-collector` | Média |
| Características Temporal no ADR verificáveis na doc vigente (qual versão+data)? | ADR 001 | Baixa (pós-spike) |

## 5. Referências aos artefatos da extração

- `_reversa_sdd/architecture.md` — componentes, adapter/strategy/guardrail, dívidas
- `_reversa_sdd/domain.md` — RN-01 a RN-06, glossário
- `_reversa_sdd/inventory.md` — estrutura diretórios, módulos, testes
- `_reversa_sdd/c4-context.md` — diagrama contexto C4
- `_reversa_sdd/state-machines.md` — `AgentState` máquina de estados
- `_reversa_sdd/dependencies.md` — bibliotecas (pydantic, pandas, numpy, scipy, requests, bs4, unittest)
- `_reversa_sdd/code-analysis.md` — análise detalhada agentes e orquestradores
- `_reversa_sdd/prd.md` — Projeto 4: métricas, personas, escopo, restrições, riscos
- `_reversa_sdd/addenda/001-sistema-multiagentes.md` — entrega anterior greenfield