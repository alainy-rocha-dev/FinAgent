# Relatório Consolidado de Handoff — SDD FinAgent + AgentPulse

> Gerado pelo reversa-spec-sdd em 2026-10-05  
> Pasta: `_reversa_sdd/sdd/`  
> Próximo passo: `/reversa-forward` (ciclo de evolução até código)

---

## 1. Specs Geradas (16 componentes + 2 itens de trabalho)

| # | Componente | Arquivo | Score | Iterações | Status |
|---|------------|---------|-------|-----------|--------|
| 1 | resume-spike | `resume-spike.md` | 87 | 1 | ✅ |
| 2 | task-state-machine | `task-state-machine.md` | 90 | 1 | ✅ |
| 3 | langgraph-checkpointer | `langgraph-checkpointer.md` | 88 | 1 | ✅ |
| 4 | worker-queue | `worker-queue.md` | 86 | 1 | ✅ |
| 5 | ci-quality | `ci-quality.md` | 89 | 1 | ✅ |
| 6 | task-api | `task-api.md` | 88 | 1 | ✅ |
| 7 | audit-trail | `audit-trail.md` | 87 | 1 | ✅ |
| 8 | approval-flow | `approval-flow.md` | 88 | 1 | ✅ |
| 9 | publication | `publication.md` | 87 | 1 | ✅ |
| 10 | budget-control | `budget-control.md` | 85 | 1 | ✅ |
| 11 | data-collector | `data-collector.md` | 88 | 1 | ✅ |
| 12 | analysis-graph | `analysis-graph.md` | 86 | 1 | ✅ |
| 13 | numeric-audit | `numeric-audit.md` | 87 | 1 | ✅ |
| 14 | observability | `observability.md` | 86 | 1 | ✅ |
| 15 | chaos-load-tests | `chaos-load-tests.md` | 88 | 1 | ✅ |
| 16 | approval-ui | `approval-ui.md` | 87 | 1 | ✅ |
| — | **ADR esqueleto** | `adr-celery-vs-temporal.md` | — | — | 🟡 Proposed |
| — | **Legacy fixes** | `legacy-fixes.md` | 90 | 1 | ✅ |

**Score médio:** 87.6/100  
**Todos itens marcados com selo 🟡 PLANEJADO.**

---

## 2. Itens Abertos

> **Lista antes de qualquer score.** Separados por tipo: consultas de documentação (fazer agora) e experimentos do spike (etapa 1).

### 2.1 Consultas de Documentação (Resolver Agora — Não Bloqueiam Forward)

| Item | O que Confirmar | Onde Impacta |
|------|-----------------|--------------|
| Rascunho IETF Idempotency-Key | Header, semântica replay, escopo, status atual | `task-api`, `audit-trail` |
| Termos de uso Yahoo Finance / BCB | Permitem produção? Rate limits, atribuição, cache | `data-collector` |
| Características Temporal no ADR | Cada afirmação verificável na doc vigente (registrar versão e data) | `adr-celery-vs-temporal` |
| Assinatura `Command(resume=...)` | Sintaxe exata na versão fixada do LangGraph | `analysis-graph` |

### 2.2 Experimentos do Spike (Etapa 1 — Tarefas do `resume-spike`)

| Item | O que Confirmar | Onde Impacta |
|------|-----------------|--------------|
| Serializador padrão LangGraph + checkpointer Postgres | Formato nativo usado; exige `autocommit` + `row_factory=dict_row`? | `langgraph-checkpointer`, `resume-spike` |
| Nó que contém `interrupt()` reexecuta desde o início na retomada? | Verificar versão fixada LangGraph | `analysis-graph`, `resume-spike` |
| Tolerância LangGraph a nós removidos/renomeados | Define política `COMPATIBLE_VERSIONS` | `langgraph-checkpointer`, `analysis-graph` |
| Advisory lock de sessão atrás de pooler | Confirmado não funcionar (MVP = conexão direta) | `task-state-machine`, `worker-queue` |
| Celery beat instância única para reaper | Advisory lock garante? | `worker-queue`, `ci-quality` |
| Retry com `countdown` no Redis vs `visibility_timeout` | Evitar reentrega antes do countdown expirar | `worker-queue`, `chaos-load-tests` |

### 2.3 Valores "Inicial, a Medir" (Etiquetados nas Specs)

| Parâmetro | Valor Inicial | Onde Definido | Como Medir |
|-----------|---------------|---------------|------------|
| `approval_ttl_hours` | 168 (7 dias) | `approval-flow`, `approval-ui` | Validar com persona aprovador |
| `monthly_token_budget` | Baixo por padrão (ex: 1M tokens) | `budget-control` | Calibrar com uso real |
| `token_budget_per_task` (provisório) | 50.000 tokens | `budget-control` | p99 × 1.5 após 20 runs do grafo real |
| `max_reaper_attempts` | 3 | `worker-queue`, `task-state-machine` | Testar no caos |
| `isclose rel_tol` | 1e-9 | `numeric-audit` | Testar com métricas reais |
| `isclose abs_tol` | 1e-12 | `numeric-audit` | Testar com métricas reais |
| Retenção eventos/checkpoints | 365 dias (mesmo banco) | `audit-trail`, `langgraph-checkpointer` | Confirmar compliance |
| `stale_max_age_days[equity]` | 5 dias | `data-collector` | Medir frescor Yahoo Finance |
| `stale_max_age_days[fx]` | 3 dias | `data-collector` | Medir frescor BCB |
| `stale_max_age_days[crypto]` | 1 dia | `data-collector` | Medir frescor provedor |
| `stale_max_age_days[other]` | 5 dias | `data-collector` | Medir frescor provedor |
| Limite motivo rejeição | min 10 / max 1000 chars | `approval-flow`, `approval-ui` | UX test |
| Rate limit baldes | POST /tasks: 10/s; GET: 30/s; approve: 20/s | `task-api` | Load test |
| `task_time_limit` | 600s | `worker-queue` | p99 duração nó no spike |
| `retry_backoff_max` | TBD | `worker-queue` | Medir no spike |
| `max_retries` | TBD | `worker-queue` | Medir no spike |
| Heartbeat interval | 15s | `worker-queue` | Validar no caos |
| `visibility_timeout` (prod) | 900s | `worker-queue`, `chaos-load-tests` | `task_time_limit` + backoff + margem |
| `visibility_timeout` (caos) | Reduzido (registrar valor) | `chaos-load-tests` | Forçar reentrega real |
| Mutações efetivas/classe | 30 | `numeric-audit` | Hypothesis test |
| Relatórios limpos (FP) | 50 | `numeric-audit` | Golden set versionado |
| Cobertura mínima caminho crítico | 85% | `ci-quality` (único) | `pytest-cov --cov-fail-under=85` |
| Sampler rate prod | 0.1 | `observability` | Ajustar após volume real |
| Alerta taxa falha | > 5% em 5 min | `observability` | Validar ruído |
| Alerta fila pending | > 100 | `observability` | Capacidade workers |
| Alerta worker offline | > 2 min | `observability` | Beat interval |

---

## 3. Decisões Arquiteturais Fixadas (Não Reabrir)

| Decisão | Componente(s) | Resumo |
|---------|---------------|--------|
| Domain não cria pool; Infra (AgentPulse) dona dos pools | `worker-queue`, `langgraph-checkpointer`, `task-api` | API: SQLAlchemy async + asyncpg; Worker: 2 pools psycopg (domain + checkpoint) + 1 lock connection |
| Advisory lock sessão por task_id (conexão dedicada) | `task-state-machine`, `worker-queue` | Fallback: lease em `tasks` (locked_by, lease_until) se pooler |
| Pools criados no `worker_process_init` (pós-fork) | `worker-queue` | Nunca no import |
| `data_quality` = LIVE \| STALE \| SIMULATED (3 valores) | `data-collector`, `analysis-graph`, `approval-ui` | STALE = provedor mas > TTL; SIMULATED = mock |
| `acknowledge_simulated` flag; prod sempre bloqueia SIMULATED | `data-collector`, `legacy-fixes` | `ALLOW_SIMULATED_PUBLICATION` fora prod exige flag; prod recusa iniciar |
| Auditoria = último portão (pós-Revisor); falha = 1 regeneração → FAILED | `analysis-graph`, `numeric-audit` | `AUDIT_FAILED` código, sem novo estado |
| `StructuredReport` com marcadores `{{SYMBOL.key}}`; varredura anti-literal | `numeric-audit`, `analysis-graph` | Lista permitida: datas ISO, anos, nomes ativos |
| `quant_metrics` persistida (ON CONFLICT DO NOTHING) | `numeric-audit`, `analysis-graph` | Auditoria compara com esta, não só checkpoint |
| `X-Snapshot-Hash` obrigatório no approve/reject | `approval-flow`, `approval-ui`, `publication` | Mismatch → 409 |
| Publicação única: `published` UNIQUE + Publisher transacional | `publication`, `approval-flow` | Hash conferido antes de publicar |
| Failpoints só `APP_ENV=test`; recusados em prod | `worker-queue`, `observability`, `chaos-load-tests` | Startup falha se ativo em prod |
| CI: workflow sempre roda; job detecta arquivos alterados | `ci-quality`, `chaos-load-tests` | Flaky: 1 retry → falha = falhou |
| ADR 001 Proposed → Accepted só após spike + noturnas | `adr-celery-vs-temporal` | Se portão fecha → ADR 002 substitui |

---

## 4. Ordem de Construção (5 Etapas)

| Etapa | Componentes | Observação |
|-------|-------------|------------|
| 1 | resume-spike (+ harness mínimo de caos), task-state-machine, langgraph-checkpointer, worker-queue, ci-quality | Fundação: spike valida premissa + fumaça de caos (C1+C2); CI roda desde o início |
| 2 | task-api, audit-trail, approval-flow, publication, **ADR esqueleto** | API + auditoria + aprovação + publicação; ADR Status=Proposed |
| 3 | budget-control, data-collector, **Quant com registro de métricas e testes golden**, analysis-graph (com auditoria integrada), numeric-audit (suíte de mutações) | **Budget antes do grafo**; collector com 3 qualidades; Quant produz `quant_metrics` + registry + golden tests **antes** do grafo; grafo já nasce com auditoria como último portão |
| 4 | observability, chaos-load-tests (amplia para 100 cenários) | Observabilidade propaga trace pelo Celery; caos amplia harness da etapa 1 para 100 execuções |
| 5 | approval-ui, **ADR final**, legacy-fixes (precisão: typo, claim, caminho local, mock padrão, pytest), README final + vídeo | Legacy-fixes de precisão **antes** do trabalho pesado (semanas 1-2); reescrita final do README + vídeo na etapa 5 |

---

## 5. Próximos Passos Imediatos

1. **Fixar versões exatas** no `pyproject.toml`/`requirements.txt`: LangGraph, Celery, Redis, Postgres, psycopg, SQLAlchemy, Pydantic, OpenTelemetry, pytest, Locust
2. **Resolver consultas de documentação** (IETF Idempotency-Key, termos Yahoo/BCB, Temporal doc versão+data, Command(resume=...))
3. **Executar spike** (`resume-spike`) com grafo mínimo (2-3 nós) + harness mínimo de caos (C1+C2) para validar premissa e medir timeouts/retries
4. **Preencher ADR 001** com evidências do spike (tabela C1-C5)
5. **Iniciar `/reversa-forward`** com a feature `002-finagent-agentpulse` (já tem `requirements.md` em `_reversa_forward/`)

---

## 6. Arquivos de Entrada para `/reversa-forward`

- `_reversa_forward/002-finagent-agentpulse/requirements.md` — já existe com decisões incorporadas (seção 10+11)
- `_reversa_sdd/sdd/*.md` — 16 specs + ADR + legacy-fixes
- `_reversa_sdd/prd.md`, `architecture.md`, `domain.md`, `code-analysis.md` — extração reversa base

---

**Digite CONTINUAR para iniciar `/reversa-forward`, ou pause aqui.**