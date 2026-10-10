# Roadmap: Migração FinAgent para Infraestrutura AgentPulse

> Identificador: `002-finagent-agentpulse`
> Data: `2026-10-05`
> Requirements: `_reversa_forward/002-finagent-agentpulse/requirements.md`
> Confidência: 🟢 CONFIRMADO, 🟡 INFERIDO, 🔴 LACUNA

## 1. Resumo da abordagem

Esta feature migra os 3 agentes do FinAgent (Coletor, Analista Quant, Relator) para executarem como serviços independentes sobre a infraestrutura do AgentPulse (FastAPI + Celery + Redis + PostgreSQL). A migração introduz: persistência de checkpoints em PostgreSQL via checkpointer do LangGraph, retry idempotente com chaves de idempotência, aprovação humana via interrupt/resume com TTL de 7 dias, e um teste de caos que comprova retomada sem duplicação após falha catastrófica do worker.

A abordagem técnica divide responsabilidades: **o código de domínio não cria pools de conexão** — recebe repositórios por injeção. A infraestrutura (AgentPulse) é dona dos pools, um conjunto por papel de processo: API assíncrona com SQLAlchemy async + asyncpg; Worker (prefork, grafo síncrono) com dois pools psycopg (`domain_pool` transacional + `checkpoint_pool` autocommit/dict_row) + 1 conexão dedicada para advisory lock por `task_id`. Pools criados em `worker_process_init` (pós-fork), nunca no import.

A ordem de construção segue 5 etapas, com o **spike de retomada** (retomada sem condição de corrida) como primeira entrega e **portão de decisão explícito** ao fim da etapa 1. Se o portão fechar, reavalia-se a arquitetura (Temporal → ADR 002 condicional) antes de prosseguir.

## 2. Princípios aplicados

| Princípio | Como a feature se relaciona | Status |
|-----------|------------------------------|--------|
| Código de domínio não cria infraestrutura | Domínio recebe repositórios por injeção; pools pertencem à infra (AgentPulse) | respeita |
| Transições atômicas de estado | `task-state-machine` centraliza transições via `UPDATE ... WHERE status = 'X'` | respeita |
| Idempotência ponta a ponta | `idempotency_key` em API, `ON CONFLICT DO NOTHING` em tabelas, Publisher transacional | respeita |
| Observabilidade nativa | OpenTelemetry traces API→Celery→nós; métricas Prometheus; logs JSON estruturados | respeita |
| Failpoints só em teste | `APP_ENV=test` habilita; `APP_ENV=prod` recusa startup | respeita |
| Métricas sobre alegações | "0 duplicadas e 0 perdidas em 100 execuções" medido, não alegado | respeita |

## 3. Decisões técnicas

| ID | Decisão | Justificativa | Alternativas descartadas | Confidência |
|----|---------|----------------|--------------------------|-------------|
| D-01 | Domínio não cria pools; infra dona dos pools (API async + Worker 2 pools psycopg + lock conn) | Separação de responsabilidades; testabilidade do domínio; reuso de pools do AgentPulse | FinAgent cria próprio pool; pool único compartilhado | 🟢 |
| D-02 | Advisory lock de sessão por `task_id` em conexão dedicada (fallback: lease em `tasks`) | Garante execução exclusiva por task_id; lock liberado ao fechar conexão | Lock em tabela sem conexão dedicada; lock distribuído externo | 🟢 |
| D-03 | Pools criados em `worker_process_init` / fechados em `worker_process_shutdown` | Evita herança de sockets do pai no prefork | Pools no import do módulo | 🟢 |
| D-04 | `data_quality` = LIVE \| STALE \| SIMULATED (3 valores); STALE por classe de ativo (dias) | Dados diários → minutos não faz sentido; câmbio/ações têm calendários diferentes | STALE por TTL fixo em minutos | 🟢 |
| D-05 | `acknowledge_simulated` flag; `APP_ENV=prod` sempre bloqueia SIMULATED; prod recusa iniciar se `ALLOW_SIMULATED_PUBLICATION=true` | Segurança: nada ignorado em silêncio; comportamento explícito em todos ambientes | Flag ignorada em prod | 🟢 |
| D-06 | Auditoria numérica = último portão (pós-Revisor); falha = 1 regeneração → `FAILED` com código `AUDIT_FAILED` | Revisor pode alterar números; auditoria deve rodar após; sem novo estado terminal | Auditoria antes do Revisor; estado terminal `AUDIT_FAILED` | 🟢 |
| D-07 | `StructuredReport` com marcadores `{{SYMBOL.key}}`; varredura rejeita literal fora de lista permitida | LLM não digita números; código substitui por valor formatado; proveniência rastreável | LLM escreve números livres no texto | 🟢 |
| D-08 | `quant_metrics` persistida (ON CONFLICT DO NOTHING); auditoria compara com esta, não só checkpoint | Checkpoint é podado; métricas persistem para auditoria e golden tests | Auditoria só contra checkpoint | 🟢 |
| D-09 | `X-Snapshot-Hash` obrigatório em approve/reject; mismatch → 409 | Aprovador vê exatamente o que foi auditado; previne decisões sobre snapshot antigo | Sem hash; hash opcional | 🟢 |
| D-10 | Publicação única: `published` UNIQUE + Publisher transacional (INSERT + UPDATE + evento) | Garante exactly-once; retry seguro se worker morre no meio | Apenas constraint UNIQUE sem transação | 🟢 |
| D-11 | Failpoints (`FAILPOINT_KILL_*`) só com `APP_ENV=test`; `APP_ENV=prod` recusa startup | Segurança: código de teste não roda em produção | Failpoints sempre ativos | 🟢 |
| D-12 | CI: workflow sempre roda; job detecta arquivos alterados e pula pesados se não crítico; flaky = 1 retry | Check não fica pendente; não mascara instabilidade | Check apenas em arquivos alterados (fica pendente) | 🟢 |
| D-13 | Spike de retomada primeiro (etapa 1) com harness mínimo de caos (C1+C2); portão de decisão explícito ao fim | Valida premissa nº1 antes de investir no resto; evita construir sobre base inválida | Spike opcional / no fim | 🟢 |
| D-14 | Consultas de documentação como tarefas com dono/data antes dos componentes que bloqueiam | Resolve ambiguidades antes de codar; não bloqueia início do Forward | Consultas deixadas para depois | 🟡 |
| D-15 | Legacy-fixes de precisão nas semanas 1-2; reescrita README + vídeo na etapa 5 | Correções baratas antes do trabalho pesado; README final reflete resultados | Todos os fixes no fim | 🟢 |
| D-16 | Ordem etapa 3: budget-control → collector → Quant (registry + golden tests) → grafo (auditoria integrada) → mutações | Quant produz artefatos que grafo e auditoria consomem; registry é fonte única | Grafo antes do Quant registry | 🟢 |
| D-17 | Arquivo único de configuração (`config/defaults.yaml` + env vars) para 28 parâmetros "a medir" | Ajuste centralizado; evita caçar valores em 16 specs | Valores espalhados pelas specs | 🟢 |
| D-18 | Primeiro coding = esqueleto do spike de retomada (grafo 2 nós, interrupt, Celery, Postgres, contador efeitos) | Entrega valor em dias; valida premissa nº1 antes de código de domínio | Código de domínio primeiro | 🟢 |
| D-19 | RF-09 (Modo Legado): manter apenas aviso no `--help` de que modo legacy não tem durabilidade, retomada nem aprovação; padrão CLI sem fallback de mock | Reduz escopo; legado é apenas compatibilidade de saída, não de infra | CLI legacy com mock fallback | 🟢 |
| D-20 | RF-08 (CLI AgentPulse): marcar como opcional, última prioridade, fora do MVP; primeiro corte se prazo apertar | CLI de cliente da API não é diferencial; API HTTP já expõe tudo | CLI obrigatório no MVP | 🟢 |

## 4. Premissas

| Premissa | Origem (`requirements.md` seção) | Risco se errada |
|----------|----------------------------------|-----------------|
| Checkpointer do LangGraph exige `autocommit` + `dict_row` | Decisões 10.1, D-01 | Pool `checkpoint_pool` mal configurado → erros na retomada |
| Nó com `interrupt()` reexecuta desde o início na retomada | D-03 (experimento do spike) | Retomada pula nós ou duplica execução |
| Tolerância do LangGraph a nós removidos/renomeados define `COMPATIBLE_VERSIONS` | D-03 | `graph_version` mal definida → falhas de retomada desnecessárias |
| Advisory lock de sessão não funciona atrás de pooler transaction mode | D-02 | MVP exige conexão direta ao Postgres; PgBouncer não suportado |
| Celery beat instância única via advisory lock garante reaper único | Worker-queue spec | Reaper duplicado → reenfileiramento incorreto |
| Retry com `countdown` no Redis vs `visibility_timeout` não causa reentrega prematura | Worker-queue spec | Tarefa reentregue antes do countdown expirar → duplicação |
| Rascunho IETF Idempotency-Key define header/semântica/escopo | task-api spec | Header não padrão → quebra idempotência cross-client |
| Termos Yahoo Finance / BCB permitem uso em produção | data-collector spec | Provedor padrão inviável → troca tardia de implementação |
| Características Temporal no ADR verificáveis na doc vigente (registrar versão+data) | ADR 001 | ADR alega o que não mediu → decisão enviesada |

## 5. Delta arquitetural

| Componente | Arquivo de origem no legado | Tipo de mudança | Resumo |
|------------|------------------------------|-----------------|--------|
| `data_collector` | `_reversa_sdd/architecture.md#4` | componente-novo | Novo provider protocol plugável (Yahoo/BCB/Mock); `data_quality` 3 valores; `stale_max_age_days` por classe; `market_payloads` ON CONFLICT |
| `quant_analyst` | `_reversa_sdd/architecture.md#4` | componente-novo | Métricas determinísticas persistem em `quant_metrics`; `METRICS_REGISTRY` no código como fonte única; testes golden contra planilha |
| `report_writer` | `_reversa_sdd/architecture.md#4` | componente-novo | Gera `StructuredReport` com marcadores `{{SYMBOL.key}}`; varredura anti-literal; proveniência via registry |
| `langgraph_orchestrator` | `_reversa_sdd/architecture.md#4` | regra-alterada | Grafo: Planner→Collector→Quant→Redator→Auditoria→Revisor→AuditGate→PrepareReview→AwaitApproval→Publish; checkpointer Postgres; `graph_version` |
| `task-state-machine` | (novo) | componente-novo | Centraliza transições atômicas; advisory lock por task_id; motivo legível; estados terminais |
| `worker-queue` | (novo) | componente-novo | Celery acks_late + task_reject_on_worker_lost + prefetch=1; reaper (beat, lock); heartbeat thread; pools pós-fork |
| `task-api` | (novo) | componente-novo | FastAPI async; Idempotency-Key por `api_key_id`; roles analyst/approver (403 cruzado); limite ativas por chave |
| `approval-flow` | (novo) | componente-novo | `X-Snapshot-Hash` obrigatório; TTL 7d → EXPIRED; reject_reason enum; `await_approval` sem efeitos |
| `publication` | (novo) | componente-novo | Tabela `published` UNIQUE; Publisher transacional; conferência de hash |
| `audit-trail` | (novo) | componente-novo | `task_events` com hash encadeado; roles segregados (app_user/retention_role/migrator); retenção 365d |
| `numeric-audit` | (novo) | componente-novo | Validador `isclose` + formato; classes mutação 7; 30 efetivas/classe; 50 limpos FP=0 |
| `observability` | (novo) | componente-novo | OTEL traces API→Celery→nós; propagação custom Celery signals; métricas Prometheus; Grafana JSON; failpoints test-only |
| `chaos-load-tests` | (novo) | componente-novo | Caos 100 execs (C1-C5, failpoints + docker kill); métricas reais (entregas>1, hash divergente); pytest idempotência; Locust vazão; CI duas camadas |
| `approval-ui` | (novo) | componente-novo | Jinja2 template servido por FastAPI; badge data_quality; X-Snapshot-Hash no form; autoescape; CSP; aviso sem PII |
| `budget-control` | (novo) | componente-novo | Teto por tarefa (provisório) + mensal global (baixo p/ padrão); modelos separados; stub LLM; serviço injetado |
| `ci-quality` | (novo) | componente-novo | PR workflow (ruff, mypy, unit, integração, coverage 85%, pip-audit); fumaça caos em críticos; noturno 100 execs |
| `adr-celery-vs-temporal` | (novo) | componente-novo | MADR Proposed → Accepted após spike de retomada+noturnas; **ADR 002 condicional** substitui se portão fechar |
| `legacy-fixes` | (novo) | trabalho | Typo AgentPulse; diagrama; file:// FinAgent; claim determinístico; unittest→pytest; mock padrão; CLI legacy aviso |

## 6. Delta no modelo de dados

- Resumo das mudanças: Novas tabelas `tasks`, `task_events`, `idempotency_keys`, `market_payloads`, `quant_metrics`, `published`, `api_keys`; colunas `graph_version`, `heartbeat_at`, `locked_by`, `lease_until`, `attempts`, `reject_reason`, `snapshot_hash`, `data_quality` em `tasks`; roles Postgres segregadas (`app_user`, `retention_role`, `migrator`).
- Detalhe completo em: `_reversa_forward/002-finagent-agentpulse/data-delta.md`

## 7. Delta de contratos externos

| Contrato | Tipo | Arquivo de detalhe |
|----------|------|--------------------|
| `POST /tasks` | HTTP | `_reversa_forward/002-finagent-agentpulse/interfaces/tasks-api.md` |
| `GET /tasks/{id}` | HTTP | `_reversa_forward/002-finagent-agentpulse/interfaces/tasks-api.md` |
| `POST /tasks/{id}/approve` | HTTP | `_reversa_forward/002-finagent-agentpulse/interfaces/approval-api.md` |
| `POST /tasks/{id}/reject` | HTTP | `_reversa_forward/002-finagent-agentpulse/interfaces/approval-api.md` |
| `GET /approval/{task_id}` | HTTP (HTML) | `_reversa_forward/002-finagent-agentpulse/interfaces/approval-ui.md` |
| Celery task `execute_graph` | Fila | `_reversa_forward/002-finagent-agentpulse/interfaces/worker-queue.md` |

## 8. Plano de migração

1. **Semana 1-2 (Precisão + Fundação)**: Legacy-fixes precisão (typo, diagrama, file://, claim, unittest→pytest, mock padrão, CLI aviso); fixar versões exatas no `pyproject.toml`; consultas de documentação (IETF, Yahoo/BCB terms, Temporal doc versão+data, Command(resume=...)); criar `config/defaults.yaml` com 28 parâmetros "a medir".
2. **Etapa 1 - Fundação + Spike de Retomada (Semana 2-3)**: `task-state-machine`, `langgraph-checkpointer`, `worker-queue`, `ci-quality` + **spike de retomada** (grafo 2 nós, interrupt, Celery, Postgres, contador efeitos) + **harness mínimo de caos (C1+C2)**. **Portão de decisão**: spike valida premissa nº1 (0 duplicadas/perdidas nos **cenários S1-S4**, 100% retomadas do último checkpoint; **S5 com comportamento definido e testado** — 409 ou resposta idempotente conforme spec). Se fechar → reavaliar Temporal (ADR 002 condicional).
3. **Etapa 2 - API + Auditoria + Aprovação + Publicação (Semana 3-4)**: `task-api`, `audit-trail`, `approval-flow`, `publication`; ADR 001 esqueleto (Proposed).
4. **Etapa 3 - Core do Grafo (Semana 4-5)**: `budget-control` → `data-collector` → **Quant com `METRICS_REGISTRY` + testes golden** → `analysis-graph` (auditoria integrada como último portão) → `numeric-audit` (suíte mutações 7 classes, 30 efetivas/classe, 50 limpos FP=0).
5. **Etapa 4 - Observabilidade + Caos Completo (Semana 5-6)**: `observability` (OTEL traces, propagação Celery, failpoints test-only) → `chaos-load-tests` (amplia harness de caos para 100 execuções C1-C5, métricas reais, pytest idempotência, Locust vazão, CI duas camadas).
6. **Etapa 5 - Entrega (Semana 6-7)**: `approval-ui`; ADR 001 final (Accepted com métricas); legacy-fixes reescrita README (cenário no topo, resultados datados, vídeo 2min docker kill + approve); documentação final.

## 9. Riscos e mitigações

| Risco | Impacto | Probabilidade | Mitigação |
|-------|---------|---------------|-----------|
| Spike falha (portão fecha) | Alto | Médio | ADR 002 condicional preparado; reavaliar Temporal antes de seguir; tempo reservado na etapa 1 |
| Advisory lock não funciona (pooler) | Alto | Baixo | MVP = conexão direta; lease fallback documentado e testado no spike |
| Auditoria numérica frágil (LLM escapa números) | Alto | Médio | Registry no código + marcadores + varredura anti-literal; 100% mutações efetivas detectadas |
| Termos Yahoo Finance impedem uso | Médio | Médio | BCB como fallback; MockProvider só com flag; `ALLOW_SIMULATED_PUBLICATION` controlado |
| `visibility_timeout` / `countdown` interagem mal | Médio | Médio | Spike mede `task_time_limit`, `retry_backoff_max`, `max_retries`; valores no config único |
| Cobertura 85% no caminho crítico inatingível | Baixo | Médio | Meta única em `ci-quality`; medir no spike; ajustar se necessário |
| 28 parâmetros "a medir" ficam desatualizados | Baixo | Médio | Arquivo único `config/defaults.yaml` + env vars; documentado no onboarding |

## 10. Critério de pronto

- [ ] Todas as ações do `actions.md` marcadas `[X]`
- [ ] `cross-check.md` (se executado) sem CRITICAL nem HIGH
- [ ] `regression-watch.md` gerado
- [ ] Re-extração reversa executada e sem regressão vermelha (recomendado)
- [ ] **Spike de retomada passou: 0 duplicadas/perdidas nos cenários S1-S4; 100% retomadas do último checkpoint; S5 com comportamento definido e testado (409 ou resposta idempotente conforme spec)**
- [ ] Execução de caos noturna 100 execuções: 0 duplicadas, 0 perdidas (taxa < ~3% pela regra dos três)
- [ ] ADR 001 Accepted com métricas do spike de retomada e noturnas
- [ ] Legacy-fixes precisão aplicados; README final + vídeo publicados

## 11. Histórico de alterações

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-10-05 | Versão inicial gerada por `/reversa-plan` | reversa |
| 2026-10-07 | Adicionadas D-19, D-20; padronizada terminologia (spike de retomada, harness de caos, execução de caos); ADR 002 condicional | reversa |