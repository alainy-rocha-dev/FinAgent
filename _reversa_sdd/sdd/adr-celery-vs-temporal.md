# ADR 001: Celery vs Temporal para Orquestração do FinAgent

> Status: **Proposed**  
> Data: 2026-10-05  
> Formato: MADR (Markdown Architectural Decision Records)

---

## Contexto e Problema

O FinAgent precisa de orquestração resiliente com:
- Retomada sem duplicação após falha catastrófica (kill worker, reentrega broker)
- Aprovação humana com interrupt/resume (pausas de dias)
- Idempotência ponta a ponta (chave de idempotência, publicação única)
- Observabilidade (traces, métricas, logs)
- Execução de grafo LangGraph com checkpointer Postgres

Duas opções principais:
1. **Celery + Redis + PostgreSQL** (stack atual do AgentPulse)
2. **Temporal** (workflow engine dedicado)

---

## Critérios de Decisão

| Critério | Peso | Descrição |
|----------|------|-----------|
| Garantia de retomada sem duplicação | 30% | Comportamento sob kill, reentrega, concorrência |
| Aprovação humana (pausas longas) | 20% | Interrupt/resume nativo vs implementação própria |
| Idempotência e publicação única | 15% | Facilidade de implementar corretamente |
| Observabilidade nativa | 10% | Traces, métricas, visibilidade de execução |
| Curva de aprendizado / time-to-market | 10% | Tempo para produtividade da equipe |
| Operacionalidade (deploy, scaling, debugging) | 10% | Complexidade operacional em produção |
| Custo de infraestrutura | 5% | Recursos necessários |

---

## Opções Consideradas

### Opção A: Celery + Redis + PostgreSQL (Stack AgentPulse)

**Descrição:** Usar a infraestrutura já existente no AgentPulse (FastAPI + Celery + Redis + Postgres). Implementar reaper, advisory lock, idempotência, interrupt/resume customizados.

| Aspecto | Avaliação |
|---------|-----------|
| Retomada sem duplicação | 🟡 **A validar no spike** — requer reaper, lock advisory, transações atômicas, idempotência cuidadosa |
| Aprovação humana | 🟡 **Custom** — interrupt LangGraph + reenfileiramento com mesmo thread_id; TTL 7 dias |
| Idempotência | 🟡 **Custom** — tabela idempotency_keys, published UNIQUE, ON CONFLICT DO NOTHING |
| Observabilidade | 🟡 **Custom** — OpenTelemetry + Prometheus + Grafana (instrumentação manual Celery signals) |
| Curva de aprendizado | 🟢 **Baixa** — equipe já conhece Celery/Redis/Postgres |
| Operacionalidade | 🟡 **Média** — componentes conhecidos; reaper/lock adicionam complexidade |
| Custo infra | 🟢 **Baixo** — Redis + Postgres já provisionados |

**Evidência do spike (a preencher):**
| Métrica | C1 | C2 | C3 | C4 | C5 |
|---------|-----|-----|-----|-----|-----|
| Kills testados | 20 | 21 | 20 | 20 | 19 |
| Duplicadas | — | — | — | — | — |
| Perdidas | — | — | — | — | — |
| Tempo recuperação (p50/p95) | — | — | — | — | — |
| `task_reject_on_worker_lost` comportamento | — | — | — | — | — |
| Esforço lock/idempotência/reaper (linhas, bugs) | — | — | — | — | — |
| Problemas inesperados | — | — | — | — | — |

---

### Opção B: Temporal

**Descrição:** Migrar para Temporal como workflow engine. Retomada, durabilidade, sinais (interrupt), visibilidade nativas.

| Aspecto | Avaliação |
|---------|-----------|
| Retomada sem duplicação | 🟢 **Nativo** — [da documentação vigente na data da consulta (registrar número e data)] "exactly-once execution semantics" |
| Aprovação humana | 🟢 **Nativo** — `workflow.await_signal()` / `signal` para aprovação; pausas ilimitadas sem ocupar worker |
| Idempotência | 🟢 **Nativo** — deduplication por Workflow ID; side-effects idempotentes via `local_activity` |
| Observabilidade | 🟢 **Nativo** — Web UI, traces, métricas, replay, stack traces |
| Curva de aprendizado | 🔴 **Alta** — novo paradigma (workflows, activities, signals); SDK Python |
| Operacionalidade | 🔴 **Alta** — cluster Temporal (4+ serviços), Cassandra/Postgres, visibilidade operacional nova |
| Custo infra | 🔴 **Médio-Alto** — cluster dedicado, mais recursos |

**Fontes (documentação Temporal — versão vigente na data da consulta, registrar número e data):**
- Exactly-once: https://docs.temporal.io/docs/concepts/what-is-temporal#exactly-once-execution
- Signals: https://docs.temporal.io/docs/concepts/signals
- Observability: https://docs.temporal.io/docs/observability

---

### Opções Não Avaliadas (limite de escopo)

| Opção | Motivo |
|-------|--------|
| Inngest | Não avaliada por limite de escopo |
| Restate | Não avaliada por limite de escopo |
| Prefect | Não avaliada por limite de escopo |

---

## Resultado da Decisão

**Status: Proposed** — Decisão registrada **após** o spike e as primeiras execuções noturnas.

> **Não preencher agora.** A decisão só será registrada quando tivermos números do spike.
> 
> Se o spike validar Celery (0 duplicadas/perdidas em 100 execuções, lock/reaper/idempotência funcionando):
> - Status → **Accepted**
> - Consequências documentadas com base em medições
> 
> Se o portão fechar e migrarmos para Temporal:
> - Este ADR 001 mantém sua evidência (Status → **Superseded**)
> - Cria-se **ADR 002** que substitui o 001

---

## Consequências (a preencher após decisão)

### Se Accepted (Celery):
- **Positivas (medidas no spike/noturno):**
  - Retomada sem duplicação validada em produção (métricas: 0 em 100 caos, 0 em 100 noturno)
  - Lock advisory + reaper + idempotência: X linhas, Y bugs corrigidos no spike
  - Tempo recuperação p95: Z segundos
  - Equipe produtiva desde dia 1 (stack conhecido)
- **Negativas (medidas):**
  - Reaper custom: X linhas, manutenção contínua
  - Lock advisory: não funciona atrás de pooler transaction mode (MVP = conexão direta)
  - Interrupt/resume: implementação custom (TTL, reenfileiramento) vs nativo
  - Visibilidade: requer instrumentação manual (Celery signals + OpenTelemetry)

### Se Superseded (Temporal):
- **Positivas (da documentação vigente na data da consulta, registrar número e data):**
  - Retomada nativa exactly-once
  - Signals nativos para aprovação humana
  - Observabilidade nativa (Web UI, replay)
- **Negativas (medidas/estimadas):**
  - Curva de aprendizado: X semanas para produtividade
  - Operacionalidade: cluster Temporal (4 serviços), novo runbook
  - Custo infra: +Y% recursos
  - Migração de código: reescrever grafo como Workflow Temporal

---

## Prós e Contras (a preencher com base em medições/documentação)

| Item | Celery (medido) | Temporal (doc: versão vigente na data da consulta) |
|------|-----------------|----------------------|
| Retomada exatamente uma vez | [medido: 0/100 duplicadas] | [doc: exactly-once semantics] |
| Aprovação humana | [medido: interrupt + reenfileiramento, TTL 7d] | [doc: await_signal nativo] |
| Observabilidade | [medido: OTEL custom + Grafana] | [doc: Web UI nativa, replay] |
| Curva de aprendizado | [medido: 0 — stack conhecido] | [estimado: X semanas] |
| Operacionalidade | [medido: Redis+Postgres conhecidos + reaper/lock] | [doc: cluster 4 serviços] |
| Custo infra | [medido: baixo] | [estimado: médio-alto] |

> **Regra:** Cada afirmação marcada como **medido** (Celery, no spike e no noturno) ou **da documentação (versão X)** (Temporal, se não implementado). Sem alegar medição que não houve.

---

## Gatilhos para Reavaliar

1. Duplicadas ou perdidas na suíte noturna que exijam mais que um ajuste pontual
2. Código de lock, reaper e idempotência ultrapassar limite fixado (ex: > 500 linhas ou > 3 bugs/ciclo)
3. Necessidade de compensação em fluxos de várias etapas, que o modelo atual expressa mal

> **Removidos:** números inventados ("fila > 10k"), "pausas humanas > 24h" (coberto pelo interrupt com TTL 7 dias), "multi-região".

---

## Métricas Noturnas (a preencher)

| Métrica | Valor | Notas |
|---------|-------|-------|
| Duplicadas em 100 execuções | — | 0 em 100 sustenta taxa < ~3% (regra dos três) |
| Perdidas em 100 execuções | — | — |
| p95 tempo recuperação | — | — |
| Falhas aquisição lock | — | — |
| Retomadas bloqueadas indevidamente | — | — |
| Locks órfãos após kill | — | — |
| `visibility_timeout` ambiente de caos | — | Valor reduzido registrado |

---

## Links

- [Relatório do Spike](../tests/chaos/spike-report.md) (a criar)
- [Relatório de Caos Noturno](../tests/chaos/nightly-report-YYYY-MM-DD.md) (branch reports ou GitHub Pages)
- [Badge Workflow Noturno](https://github.com/.../actions/workflows/nightly-chaos.yml) (GitHub Actions badge)
- [ADR Template](https://adr.github.io/madr/)

---

## Histórico

| Data | Status | Autor | Observação |
|------|--------|-------|------------|
| 2026-10-05 | Proposed | reversa-spec-sdd | Esqueleto criado; aguardando spike |