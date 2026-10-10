# Matriz de Rastreabilidade Decisão → Tarefa

> Feature: `002-finagent-agentpulse`
> Data: `2026-10-07`
> Objetivo: Garantir que cada decisão técnica no roadmap tenha pelo menos uma tarefa executável no actions.md

---

## Decisões D-01 a D-20 → Tarefas

| Decisão | Descrição | Tarefa(s) Executora(s) | Status |
|---------|-----------|------------------------|--------|
| D-01 | Domínio não cria pools; infra dona dos pools (API async + Worker 2 pools psycopg + lock conn) | T026, T027, T041, T049-T054, T088 | `[ ]` |
| D-02 | Advisory lock de sessão por `task_id` em conexão dedicada (fallback: lease em `tasks`) | T026, T031, T041, T043 | `[ ]` |
| D-03 | Pools criados em `worker_process_init` / fechados em `worker_process_shutdown` | T026, T030, T043 | `[ ]` |
| D-04 | `data_quality` = LIVE \| STALE \| SIMULATED (3 valores); STALE por classe de ativo (dias) | T024, T038, T050 | `[ ]` |
| D-05 | `acknowledge_simulated` flag; `APP_ENV=prod` sempre bloqueia SIMULATED; prod recusa iniciar se `ALLOW_SIMULATED_PUBLICATION=true` | T028, T039, T050 | `[ ]` |
| D-06 | Auditoria numérica = último portão (pós-Revisor); falha = 1 regeneração → `FAILED` com código `AUDIT_FAILED` | T053, T054, T055 | `[ ]` |
| D-07 | `StructuredReport` com marcadores `{{SYMBOL.key}}`; varredura rejeita literal fora de lista permitida | T051, T053 | `[ ]` |
| D-08 | `quant_metrics` persistida (ON CONFLICT DO NOTHING); auditoria compara com esta, não só checkpoint | T020, T036, T051, T054 | `[ ]` |
| D-09 | `X-Snapshot-Hash` obrigatório em approve/reject; mismatch → 409 | T058, T059, T064 | `[ ]` |
| D-10 | Publicação única: `published` UNIQUE + Publisher transacional (INSERT + UPDATE + evento) | T021, T037, T059 | `[ ]` |
| D-11 | Failpoints (`FAILPOINT_KILL_*`) só com `APP_ENV=test`; `APP_ENV=prod` recusa startup | T028, T040, T061 | `[ ]` |
| D-12 | CI: workflow sempre roda; job detecta arquivos alterados e pula pesados se não crítico; flaky = 1 retry | T044, T063 | `[ ]` |
| D-13 | Spike de retomada primeiro (etapa 1) com harness mínimo de caos (C1+C2); portão de decisão explícito ao fim | T045, T046, T047, T048 | `[ ]` |
| D-14 | Consultas de documentação como tarefas com dono/data antes dos componentes que bloqueiam | T010, T011, T012, T013, T014 | `[ ]` |
| D-15 | Legacy-fixes de precisão nas semanas 1-2; reescrita README + vídeo na etapa 5 | T003-T009, T066, T086 | `[ ]` |
| D-16 | Ordem etapa 3: budget-control → collector → Quant (registry + golden tests) → grafo (auditoria integrada) → mutações | T049, T050, T051, T052, T053, T054, T055 | `[ ]` |
| D-17 | Arquivo único de configuração (`config/defaults.yaml` + env vars) para 28 parâmetros "a medir" | T001, T028, T029 | `[ ]` |
| D-18 | Primeiro coding = esqueleto do spike de retomada (grafo 2 nós, interrupt, Celery, Postgres, contador efeitos) | T045 | `[ ]` |
| D-19 | RF-09 (Modo Legado): manter apenas aviso no `--help` de que modo legacy não tem durabilidade, retomada nem aprovação; padrão CLI sem fallback de mock | T009, T072, T073 | `[ ]` |
| D-20 | RF-08 (CLI AgentPulse): marcar como opcional, última prioridade, fora do MVP; primeiro corte se prazo apertar | T071 | `[ ]` |

---

## Verificação de Cobertura

- ✅ **20 decisões** mapeadas
- ✅ **88 tarefas** no actions.md (T001-T088)
- ✅ Cada decisão tem ≥1 tarefa
- ✅ Cada tarefa Fase 3-5 que constrói sobre retomada depende de T048 (portão)

---

## Decisões sem Tarefa Direta (Herança)

| Decisão | Herda de | Nota |
|---------|----------|------|
| D-01 | Princípio "Código de domínio não cria infraestrutura" | Testado indiretamente via T088 |
| D-12 | Princípio "Observabilidade nativa" | Testado via T044, T061, T063 |

---

## Próximos Passos

1. `/reversa-audit` para confirmar 0 HIGH
2. `/reversa-coding` iniciando com T025 (scaffold serial)