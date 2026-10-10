# Actions: Migração FinAgent para Infraestrutura AgentPulse

> Identificador: `002-finagent-agentpulse`
> Data: `2026-10-07`
> Roadmap: `_reversa_forward/002-finagent-agentpulse/roadmap.md`

## Resumo

| Métrica | Valor |
|---------|-------|
| Total de ações | 87 |
| Paralelizáveis (`[//]`) | 31 |
| Maior cadeia de dependência | 12 |

## Fase 1, Preparação

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T001 | Criar `config/defaults.yaml` com 28 parâmetros "a medir" + variáveis de ambiente | - | `[//]` | `config/defaults.yaml` | 🟢 | `[X]` |
| T002 | Fixar versões exatas no `pyproject.toml` (LangGraph, Celery, psycopg, SQLAlchemy, etc.) | - | `[//]` | `pyproject.toml` | 🟢 | `[X]` |
| T003 | Legacy-fix: corrigir typo "AgentPulse" no código e documentação | - | `[//]` | `**/*.py`, `**/*.md` | 🟢 | `[ ]` |
| T004 | Legacy-fix: atualizar diagrama de arquitetura no README | - | `[//]` | `README.md`, `docs/architecture.md` | 🟢 | `[ ]` |
| T005 | Legacy-fix: remover referências `file://` do FinAgent | - | `[//]` | `**/*.py`, `**/*.md` | 🟢 | `[ ]` |
| T006 | Legacy-fix: remover claim "determinístico" não comprovado | - | `[//]` | `README.md`, `docs/*.md` | 🟢 | `[ ]` |
| T007 | Legacy-fix: migrar testes de `unittest` para `pytest` | - | `[//]` | `tests/` | 🟢 | `[ ]` |
| T008 | Legacy-fix: padronizar mocks com `unittest.mock` padrão | - | `[//]` | `tests/` | 🟢 | `[ ]` |
| T009 | Legacy-fix: adicionar aviso no CLI legacy (`--legacy` não tem durabilidade/retomada/aprovação) | - | `[//]` | `sisanalisefinanceira/cli.py` | 🟢 | `[ ]` |
| T010 | Consulta doc: IETF Idempotency-Key draft (versão/status atual) — antes de `task-api` | - | `[//]` | `docs/research/ietf-idempotency-key.md` | 🟡 | `[ ]` |
| T011 | Consulta doc: Yahoo Finance Terms of Use + rate limits — antes de `data-collector` | - | `[//]` | `docs/research/yahoo-terms.md` | 🟡 | `[ ]` |
| T012 | Consulta doc: BCB API docs + termos — antes de `data-collector` | - | `[//]` | `docs/research/bcb-api.md` | 🟡 | `[ ]` |
| T013 | Consulta doc: Temporal docs (versão+data) para ADR — antes de ADR 001 | - | `[//]` | `docs/research/temporal.md` | 🟡 | `[ ]` |
| T014 | Consulta doc: LangGraph `Command(resume=...)` + checkpointer `autocommit`/`dict_row` — antes de `analysis-graph` | - | `[//]` | `docs/research/langgraph-checkpointer.md` | 🟡 | `[ ]` |
| T015 | Criar migrações SQL: 001_create_roles.sql | - | `[//]` | `migrations/001_create_roles.sql` | 🟢 | `[ ]` |
| T016 | Criar migrações SQL: 002_create_tasks_table.sql | T015 | - | `migrations/002_create_tasks_table.sql` | 🟢 | `[ ]` |
| T017 | Criar migrações SQL: 003_create_task_events.sql + trigger chain_hash | T016 | - | `migrations/003_create_task_events.sql` | 🟢 | `[ ]` |
| T018 | Criar migrações SQL: 004_create_idempotency_keys.sql | T016 | - | `migrations/004_create_idempotency_keys.sql` | 🟢 | `[ ]` |
| T019 | Criar migrações SQL: 005_create_market_payloads.sql | T016 | - | `migrations/005_create_market_payloads.sql` | 🟢 | `[ ]` |
| T020 | Criar migrações SQL: 006_create_quant_metrics.sql | T016 | - | `migrations/006_create_quant_metrics.sql` | 🟢 | `[ ]` |
| T021 | Criar migrações SQL: 007_create_published.sql | T016 | - | `migrations/007_create_published.sql` | 🟢 | `[ ]` |
| T022 | Criar migrações SQL: 008_create_api_keys.sql | T015 | - | `migrations/008_create_api_keys.sql` | 🟢 | `[ ]` |
| T023 | Criar migrações SQL: 009_langgraph_checkpointer.sql (PostgresSaver) | T016 | - | `migrations/009_langgraph_checkpointer.sql` | 🟢 | `[ ]` |
| T024 | Criar migrações SQL: 010_add_stale_config.sql | T016 | - | `migrations/010_add_stale_config.sql` | 🟢 | `[ ]` |
| T025 | Scaffold: estrutura de pastas `src/infra/` (pools, repositórios, checkpointer) | T001, T002 | - | `src/infra/__init__.py` | 🟢 | `[X]` |
| T026 | Scaffold: `src/infra/db/pools.py` — pools async (API) + psycopg (worker: domain_pool, checkpoint_pool, lock_conn) | T025 | - | `src/infra/db/pools.py` | 🟢 | `[ ]` |
| T027 | Scaffold: `src/infra/db/repositories.py` — repositórios injetados no domínio (TasksRepo, MarketRepo, QuantRepo, PublishedRepo, EventsRepo, IdempotencyRepo) | T025 | - | `src/infra/db/repositories.py` | 🟢 | `[ ]` |
| T028 | Scaffold: `src/infra/config.py` — carrega `config/defaults.yaml` + env vars, valida 28 parâmetros | T001, T025 | - | `src/infra/config.py` | 🟢 | `[ ]` |

## Fase 2, Testes

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T029 | Teste: `test_config_loads_defaults_and_env.py` — valida 28 parâmetros carregados | T028 | `[//]` | `tests/test_config.py` | 🟢 | `[ ]` |
| T030 | Teste: `test_pools_created_post_fork.py` — verifica pools criados em `worker_process_init`, não no import | T026 | `[//]` | `tests/test_pools.py` | 🟢 | `[ ]` |
| T031 | Teste: `test_advisory_lock_session.py` — lock por task_id funciona; fallback lease testado | T026 | `[//]` | `tests/test_lock.py` | 🟢 | `[ ]` |
| T032 | Teste: `test_checkpointer_autocommit_dict_row.py` — checkpointer falha sem autocommit/dict_row | T026 | `[//]` | `tests/test_checkpointer.py` | 🟢 | `[ ]` |
| T033 | Teste: `test_idempotency_key_scope.py` — escopo por `api_key_id`; replay 200; payload diferente → 409 | T018 | `[//]` | `tests/test_idempotency.py` | 🟢 | `[ ]` |
| T034 | Teste: `test_task_state_machine_transitions.py` — transições atômicas `UPDATE ... WHERE status = 'X'` | T016, T017 | `[//]` | `tests/test_state_machine.py` | 🟢 | `[ ]` |
| T035 | Teste: `test_market_payloads_on_conflict.py` — ON CONFLICT DO NOTHING garante idempotência | T019 | `[//]` | `tests/test_market_payloads.py` | 🟢 | `[ ]` |
| T036 | Teste: `test_quant_metrics_persisted.py` — métricas persistem; auditoria compara com esta tabela | T020 | `[//]` | `tests/test_quant_metrics.py` | 🟢 | `[ ]` |
| T037 | Teste: `test_published_unique_constraint.py` — UNIQUE task_id garante exactly-once | T021 | `[//]` | `tests/test_published.py` | 🟢 | `[ ]` |
| T038 | Teste: `test_data_quality_stale_per_class.py` — STALE por asset_class (dias), não minutos | T024 | `[//]` | `tests/test_data_quality.py` | 🟢 | `[ ]` |
| T039 | Teste: `test_simulated_blocked_in_prod.py` — APP_ENV=prod recusa SIMULATED; recusa startup se ALLOW_SIMULATED_PUBLICATION=true | T028 | `[//]` | `tests/test_simulated_block.py` | 🟢 | `[ ]` |
| T040 | Teste: `test_failpoints_only_in_test.py` — FAILPOINT_* só ativos com APP_ENV=test; prod recusa startup | T028 | `[//]` | `tests/test_failpoints.py` | 🟢 | `[ ]` |

## Fase 3, Núcleo

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T041 | Implementar `task-state-machine` — transições atômicas, advisory lock, motivos legíveis, estados terminais | T016, T017, T026, T027 | - | `src/infra/state_machine.py` | 🟢 | `[ ]` |
| T042 | Implementar `langgraph-checkpointer` — PostgresSaver com `checkpoint_pool` (autocommit + dict_row), `graph_version` | T023, T026, T027 | - | `src/infra/checkpointer.py` | 🟢 | `[ ]` |
| T043 | Implementar `worker-queue` — Celery acks_late, task_reject_on_worker_lost, prefetch=1, reaper (beat + lock), heartbeat thread | T026, T027, T028 | - | `src/infra/worker_queue.py` | 🟢 | `[ ]` |
| T044 | Implementar `ci-quality` — workflow PR (ruff, mypy, unit, integração, coverage 85%, pip-audit); fumaça caos em críticos; noturno 100 execs | T002, T028 | - | `.github/workflows/ci.yml` | 🟢 | `[ ]` |
| T045 | Spike de retomada: grafo 2 nós (collector→quant), `interrupt()`, Celery, Postgres, contador efeitos | T041, T042, T043 | - | `tests/chaos/resume_spike.py` | 🟢 | `[ ]` |
| T046 | Spike de retomada: harness mínimo caos C1 (kill após checkpoint quant) + C2 (kill entre interrupt e retomada) | T045 | - | `tests/chaos/harness_c1_c2.py` | 🟢 | `[ ]` |
| T047 | Spike de retomada: instrumentação contadores (S1-S5) + relatório do spike | T046 | - | `tests/chaos/spike_report.py` | 🟢 | `[ ]` |
| T048 | **Portão de decisão**: avaliar spike — 0 duplicadas/perdidas nos **cenários S1-S4**, 100% retomadas do último checkpoint; **S5 com comportamento definido e testado** (409 ou resposta idempotente conforme spec) | T047 | - | `docs/spike_decision.md` | 🟢 | `[ ]` |
| T049 | Implementar `budget-control` — teto por tarefa + mensal global; modelos separados; stub LLM; serviço injetado | T028, T027 | - | `src/domain/budget_control.py` | 🟢 | `[ ]` |
| T050 | Implementar `data-collector` — provider protocol plugável (Yahoo/BCB/Mock); `data_quality` 3 valores; `stale_max_age_days` por classe; `market_payloads` ON CONFLICT | T011, T012, T027, T049 | - | `src/domain/data_collector.py` | 🟢 | `[ ]` |
| T051 | Implementar `quant-analyst` — métricas determinísticas; `METRICS_REGISTRY` no código como fonte única; testes golden contra planilha | T027, T049 | - | `src/domain/quant_analyst.py` | 🟢 | `[ ]` |
| T052 | Testes golden: `test_quant_golden.py` — compara saída com planilha de referência | T051 | - | `tests/test_quant_golden.py` | 🟢 | `[ ]` |
| T053 | Implementar `analysis-graph` — grafo completo: Planner→Collector→Quant→Redator→Auditoria→Revisor→AuditGate→PrepareReview→AwaitApproval→Publish; checkpointer Postgres; `graph_version` | T041, T042, T048, T050, T051 | - | `src/infra/analysis_graph.py` | 🟢 | `[ ]` |
| T054 | Implementar `numeric-audit` — validador `isclose` + formato; classes mutação 7; 30 efetivas/classe; 50 limpos FP=0 | T051, T053 | - | `src/domain/numeric_audit.py` | 🟢 | `[ ]` |
| T055 | Testes mutação: `test_numeric_audit_mutations.py` — 7 classes × 30 efetivas + 50 limpos | T054 | - | `tests/test_numeric_audit_mutations.py` | 🟢 | `[ ]` |

## Fase 4, Integração

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T056 | Implementar `task-api` — FastAPI async; Idempotency-Key por `api_key_id`; roles analyst/approver (403 cruzado); limite ativas por chave | T010, T018, T022, T027, T028, T041, T048 | - | `src/api/tasks_api.py` | 🟢 | `[ ]` |
| T057 | Implementar `audit-trail` — `task_events` com hash encadeado; roles segregados (app_user/retention_role/migrator); retenção 365d | T017, T027, T041, T048 | - | `src/infra/audit_trail.py` | 🟢 | `[ ]` |
| T058 | Implementar `approval-flow` — `X-Snapshot-Hash` obrigatório; TTL 7d → EXPIRED; reject_reason enum; `await_approval` sem efeitos | T017, T041, T048, T056 | - | `src/infra/approval_flow.py` | 🟢 | `[ ]` |
| T059 | Implementar `publication` — tabela `published` UNIQUE; Publisher transacional (INSERT + UPDATE + evento); conferência hash | T021, T027, T048, T057, T058 | - | `src/infra/publication.py` | 🟢 | `[ ]` |
| T060 | ADR 001: esqueleto MADR **Proposed** — contexto, decisão (Celery), consequências, **tabela de evidência do spike vazia**, status mantido Proposed até noturnas | T048 | - | `docs/adr/001-celery-vs-temporal.md` | 🟡 | `[ ]` |
| T061 | Implementar `observability` — OTEL traces API→Celery→nós; propagação custom Celery signals; métricas Prometheus; Grafana JSON; failpoints test-only | T028, T043, T044, T048 | - | `src/infra/observability.py` | 🟢 | `[ ]` |
| T062 | Ampliar harness caos para 100 execuções C1-C5, métricas reais (entregas>1, hash divergente), pytest idempotência, Locust vazão | T046, T044, T048, T061 | - | `tests/chaos/full_harness.py` | 🟢 | `[ ]` |
| T063 | CI duas camadas: PR (rápido) + noturno (100 execs caos) | T044, T062 | - | `.github/workflows/chaos-nightly.yml` | 🟢 | `[ ]` |
| T064 | Implementar `approval-ui` — Jinja2 template FastAPI; badge data_quality; X-Snapshot-Hash no form; autoescape; CSP; aviso sem PII | T048, T058, T061 | - | `src/api/approval_ui.py`, `templates/approval.html` | 🟢 | `[ ]` |
| T065 | ADR 001: final Accepted com métricas spike + noturnas | T048, T060, T062 | - | `docs/adr/001-celery-vs-temporal.md` | 🟡 | `[ ]` |
| T066 | Legacy-fix: reescrita README (cenário no topo, resultados datados, vídeo 2min docker kill + approve) | T003, T004, T005, T006, T048, T062 | - | `README.md` | 🟢 | `[ ]` |
| T067 | Documentação final: onboarding atualizado, HANDOFF_REPORT.md com 28 parâmetros calibrados | T048, T065, T066 | `[//]` | `docs/HANDOFF_REPORT.md`, `onboarding.md` | 🟢 | `[ ]` |

## Fase 5, Polimento

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T068 | Logs estruturados JSON com `execution_id`, `step_name`, `attempt` em todo pipeline | T048, T061 | `[//]` | `src/infra/logging.py` | 🟢 | `[ ]` |
| T069 | Métricas Prometheus expostas: `tasks_total`, `tasks_duration_seconds`, `checkpoint_duration_seconds`, `retry_count`, `chaos_duplicates`, `chaos_lost` | T048, T061 | `[//]` | `src/infra/metrics.py` | 🟢 | `[ ]` |
| T070 | Health checks: `/health` (DB, Redis, worker vivo), `/ready` (migrações aplicadas) | T026, T043 | `[//]` | `src/api/health.py` | 🟢 | `[ ]` |
| T071 | CLI AgentPulse: `agentpulse run`, `status`, `approve`, `reject`, `replay` | T048, T056, T058 | - | `src/cli/agentpulse_cli.py` | 🟡 | `[ ]` |
| T072 | Modo legacy (`--legacy`) preserva comportamento bit-a-bit idêntico ao pré-migração | T009, T053 | `[//]` | `sisanalisefinanceira/cli.py` | 🟢 | `[ ]` |
| T073 | Testes regressão: `test_legacy_mode_identical_output.py` | T072 | - | `tests/test_legacy_mode.py` | 🟢 | `[ ]` |
| T074 | Testes integração: fluxo completo run→approve→published | T048, T056, T058, T059, T053 | - | `tests/test_full_flow.py` | 🟢 | `[ ]` |
| T075 | Testes regressão: `test_data_collector.py`, `test_quant_analyst.py` não quebram | T050, T051 | - | `tests/test_data_collector.py`, `tests/test_quant_analyst.py` | 🟢 | `[ ]` |
| T076 | Cobertura 85% no caminho crítico (medir no spike, ajustar se necessário) | T044, T029-T040 | - | `pytest.ini`, `.coveragerc` | 🟡 | `[ ]` |
| T077 | Validação orçamento conexões: `conexões_API + (filhos × conexões_por_filho × workers) + margem ≤ max_connections` | T026, T043 | `[//]` | `docs/connection_budget.md` | 🟢 | `[ ]` |
| T078 | Teste: matar conexões com `pg_terminate_backend` no meio de tarefa → retry/retomada sem duplicar | T026, T043, T048 | `[//]` | `tests/test_connection_loss.py` | 🟢 | `[ ]` |
| T079 | Teste: reiniciar container Postgres com tarefas em voo → workers se recuperam sem reinício | T026, T043, T048 | `[//]` | `tests/test_postgres_restart.py` | 🟢 | `[ ]` |
| T080 | Teste: pool tamanho mínimo com conexão de lock → nenhum deadlock | T026, T043, T048 | `[//]` | `tests/test_min_pool.py` | 🟢 | `[ ]` |
| T081 | Teste: número conexões abertas com N workers + API → dentro do orçamento | T026, T043, T048, T077 | `[//]` | `tests/test_connection_budget.py` | 🟢 | `[ ]` |
| T082 | Teste: checkpointer com conexão sem autocommit falha claramente | T042 | `[//]` | `tests/test_checkpointer_config.py` | 🟢 | `[ ]` |
| T083 | Validação spike: 0 duplicadas/perdidas nos **cenários S1-S4**, 100% retomadas do último checkpoint; **S5 comportamento definido e testado** | T048 | - | `spike_report.md` | 🟢 | `[ ]` |
| T084 | Caos noturno 100 execuções: 0 duplicadas, 0 perdidas (taxa < ~3% pela regra dos três) | T048, T062, T063 | - | `chaos_nightly_report.md` | 🟢 | `[ ]` |
| T085 | Cross-check final: `regression-watch.md` gerado, re-extração reversa sem regressão vermelha | T048, T067, T074, T075 | - | `regression-watch.md` | 🟢 | `[ ]` |
| T086 | Vídeo 2min: docker kill + approve demonstrando retomada | T048, T066, T084 | `[//]` | `demo_retomada.mp4` | 🟢 | `[ ]` |
| T087 | Handoff final: todas ações `[X]`, cross-check sem CRITICAL/HIGH, ADR 001 Accepted | T048, T065, T083, T084, T085 | - | `HANDOFF.md` | 🟢 | `[ ]` |
| T088 | Teste arquitetural: domínio não importa infra (import-linter ou grep no CI) | T025, T049 | - | `.github/workflows/arch-check.yml`, `tests/test_arch_boundaries.py` | 🟢 | `[ ]` |

## Notas de execução

<!--
Reservado para /reversa-coding registrar avisos ou observações que surgiram durante a execução.
Não use isso para corrigir ações, edits manuais ficam fora desse arquivo, vão direto no código.
-->

## Histórico de alterações

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-10-07 | Versão inicial gerada por `/reversa-to-do` | reversa |