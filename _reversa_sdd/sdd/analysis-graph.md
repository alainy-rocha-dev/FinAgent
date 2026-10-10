# Spec: analysis-graph

> Selo 🟡 PLANEJADO. Componente gerado pelo reversa-spec-sdd a partir do PRD FinAgent + AgentPulse.

---

## 1. Resumo

🟡 Grafo LangGraph: Planner → Coletor → Analista Quant → Redator → Auditoria Numérica → Revisor → **Auditoria (último portão)** → `prepare_review` (idempotente, monta snapshot) → `await_approval` (sem efeitos colaterais) → Publicar. Falha precoce `DATA_QUALITY_BLOCKED` após coletor. Retry só para erros transitórios.

---

## 2. Requisitos Funcionais

| ID | Requisito | Prioridade | Critério de Aceite |
|----|-----------|------------|---------------------|
| 🟡 RF-01 | Nós do grafo: `planner` → `collector` → `quant_analyst` → `redator` → `numeric_audit` → `revisor` → `audit_gate` (último portão) → `prepare_review` → `await_approval` → `publish` | Must | Ordem fixa; `audit_gate` roda **após** `revisor` e **antes** de `prepare_review` |
| 🟡 RF-02 | Nó `prepare_review`: monta snapshot idempotente para aprovação, grava `task_events` (`REVIEW_READY`) com `snapshot_hash` | Must | Não chama LLM; `{execution_id, step_name, market_payload_ref, quant_metrics_ref, report_draft_ref, audit_result_ref, data_quality, snapshot_hash}` |
| 🟡 RF-03 | Falha precoce `DATA_QUALITY_BLOCKED`: após `collector`, antes de `quant_analyst`; verifica `data_quality` | Must | Se `SIMULATED` sem `acknowledge_simulated` (ou `APP_ENV=prod`) → transição atômica `DATA_QUALITY_BLOCKED`; se `STALE` → `stale_warning=true` no snapshot |
| 🟡 RF-04 | Nó `await_approval` sem efeitos colaterais: apenas `interrupt()` | Must | Não grava, não chama LLM, não emite evento; snapshot já montado |
| 🟡 RF-05 | Retry com backoff exponencial + jitter **apenas** para erros transitórios (rede, HTTP 5xx, timeout LLM) | Must | Erros de validação (schema, números) **não** retentam; `attempt` incrementado no estado do checkpointer |
| 🟡 RF-06 | Auditoria numérica como último portão: roda após `revisor`; se `revisor` edita texto, auditoria roda de novo | Must | `audit_gate` compara `StructuredReport` com `quant_metrics` persistida; falha → 1 regeneração do `redator` (conta no orçamento) → persistindo → `FAILED` com código `AUDIT_FAILED` |
| 🟡 RF-07 | `graph_version` gravado no checkpoint e na `tasks`; retomada valida compatibilidade | Must | Igual ou em `COMPATIBLE_VERSIONS` → segue; incompatível → `FAILED` "versão do fluxo incompatível, reenvie" |
| 🟡 RF-08 | Checkpointer Postgres a cada nó (thread_id = task_id) | Must | Estado persistido automaticamente pelo `langgraph-checkpointer` |

---

## 3. Comportamentos

🟡 **Estrutura do estado do grafo (simplificada):**
```python
class AgentState(TypedDict):
    task_id: str
    symbol: str
    execution_id: str
    step_name: str  # nó atual
    attempt: int
    market_payload: MarketDataPayload | None
    quant_metrics: QuantAnalysisMetrics | None
    report_draft: StructuredReport | None
    audit_result: AuditResult | None
    review_snapshot: ReviewSnapshot | None
    data_quality: Literal["LIVE", "STALE", "SIMULATED"]
    stale_warning: bool
    graph_version: str
```

🟡 **Nós (resumo):**
| Nó | Função | Efeitos colaterais |
|----|--------|-------------------|
| `planner` | Planeja execução (modelo barato) | Nenhum |
| `collector` | Chama `data-collector` | `market_payloads` INSERT, `data_quality` |
| `quant_analyst` | Calcula métricas determinísticas | `quant_metrics` persistida (ON CONFLICT DO NOTHING) |
| `redator` | Gera `StructuredReport` com marcadores `{{SYMBOL.key}}` | LLM call (conta no budget) |
| `numeric_audit` | Valida `StructuredReport` vs `quant_metrics` | Comparação `isclose` + formato |
| `revisor` | Revisa prosa (modelo barato) | LLM call (conta no budget) |
| `audit_gate` | **Último portão**: roda `numeric_audit` de novo se `revisor` editou | Se falha → 1 regeneração `redator` → `FAILED` |
| `prepare_review` | Monta snapshot idempotente | `task_events` INSERT `REVIEW_READY` |
| `await_approval` | `interrupt()` | **Nenhum** |
| `publish` | Chama `publication` | Transação `published` + `tasks` UPDATE |

🟡 **Retry policy:**
```python
RETRYABLE_ERRORS = (httpx.RequestError, httpx.HTTPStatusError, asyncio.TimeoutError, LLMTimeoutError)
NON_RETRYABLE = (ValidationError, ValueError, KeyError, AuditFailed)

def should_retry(error: Exception) -> bool:
    return isinstance(error, RETRYABLE_ERRORS)
```

🟡 **Falha de auditoria (`audit_gate`):**
- Primeira falha → `BudgetExceeded` não, `AuditFailed` → regenera `redator` (1 tentativa extra, conta no orçamento)
- Segunda falha → `FAILED` com `transition_reason = "audit_failed"` + detalhe por chave no evento
- **Não** cria novo estado terminal (`FAILED` já existe)

---

## 4. Edge Cases

| Cenário | Comportamento |
|---------|---------------|
| 🟡 `revisor` reescreve texto e muda números | `audit_gate` detecta → regeneração `redator` |
| 🟡 `quant_analyst` falha (erro determinístico) | Não retentam → `FAILED` direto |
| 🟡 `collector` retorna `STALE` | `stale_warning=true` no snapshot; prossegue |
| 🟡 Retomada após `interrupt` | Checkpointer carrega estado; grafo retoma em `await_approval` (ou `prepare_review` se reexecutado — **verificar versão fixada**) |
| 🟡 `graph_version` incompatível no checkpoint | `FAILED` imediato na retomada; motivo legível |
| 🟡 Orçamento estourado no meio do grafo | `BudgetExceeded` → `BUDGET_EXCEEDED` terminal |

---

## 5. Não-Gols

🟡 Não implementar coletor (componente `data-collector`)
🟡 Não implementar auditoria numérica (componente `numeric-audit` — chamado pelo grafo)
🟡 Não implementar máquina de estados (componente `task-state-machine`)
🟡 Não implementar checkpointer (componente `langgraph-checkpointer`)
🟡 Não implementar fila/worker (componente `worker-queue`)
🟡 Não definir `COMPATIBLE_VERSIONS` final (convenção: mudanças aditivas = compatíveis)

---

## 6. Interface de Integração

🟡 **Entrada:** `task_id`, `symbol`, `execution_id`, `acknowledge_simulated`, `graph_version`
🟡 **Saída:** Estado final persistido via checkpointer; eventos via `audit-trail`; transições via `task-state-machine`
🟡 **Dependências:** `data-collector` (nó collector), `numeric-audit` (nós audit), `budget-control` (guards), `task-state-machine` (transições), `langgraph-checkpointer` (persistência), `approval-flow` (interrupt), `publication` (nó publish), `worker-queue` (execução)

---

## 7. Critérios de Aceite (Gherkin)

```gherkin
Cenário: Execução completa com aprovação
  Dado grafo inicia com symbol=PETR4
  Quando todos nós executam sem erro
  E auditoria passa (revisor não quebrou números)
  E prepare_review monta snapshot com hash H123
  E await_approval interrompe
  Então tarefa em AWAITING_APPROVAL
  Quando approve com X-Snapshot-Hash=H123
  Então publish executa e tarefa PUBLISHED

Cenário: Falha precoce DATA_QUALITY_BLOCKED
  Dado collector retorna SIMULATED sem acknowledge_simulated
  Quando grafo processa collector
  Então transição atômica para DATA_QUALITY_BLOCKED
  E quant_analyst NÃO executa
  E tarefa termina

Cenário: Auditora pega erro do revisor
  Dado redator gera relatório correto
  E revisor reescreve e muda volatilidade de 0.234 para 0.243
  Quando audit_gate roda após revisor
  Então falha detectada (isclose falha)
  E redator regenera 1 vez (conta no orçamento)
  E se falha de novo → FAILED com AUDIT_FAILED

Cenário: Retry só para transitórios
  Dado quant_analyst levanta ValidationError (dado inválido)
  Quando grafo captura erro
  Então NÃO retentam → FAILED direto
  Dado LLM levanta TimeoutError
  Quando grafo captura erro
  Então retentam com backoff exponencial + jitter
```

---

## 8. Perguntas Abertas

⚠️ **ABERTO:** Nó que contém `interrupt()` reexecuta desde o início na retomada, ou retoma do ponto de interrupção? (Verificar versão fixada do LangGraph)
⚠️ **ABERTO:** Assinatura de `Command(resume=...)` na versão fixada
⚠️ **ABERTO:** Tolerância do LangGraph a remoção/renomeação de nós com checkpoints existentes (define `COMPATIBLE_VERSIONS`)
⚠️ **ABERTO:** `COMPATIBLE_VERSIONS` convenção final (aditivas = compatíveis?)

---

## 9. Valores Iniciais (a medir)

| Parâmetro | Valor Inicial | Fonte |
|-----------|---------------|-------|
| 🟡 Max retries transitórios | 3 | Padrão |
| 🟡 Backoff base | 2s | Padrão |
| 🟡 Jitter | ± 0.5s | Padrão |
| 🟡 Regenerações redator pós-auditoria | 1 | Fixado |

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
  Escopo:        85/100 (peso 15%)
  Edge Cases:    90/100 (peso 10%)

Gaps críticos:
  - Comportamento de interrupt() na retomada depende de versão fixada LangGraph
  - COMPATIBLE_VERSIONS convenção precisa ser definida e testada (N → N+1)

Sugestões:
  1. Fixar versão LangGraph no spike e documentar comportamento de interrupt/resume
  2. Adicionar teste de retomada N → N+1 com nó aditivo no CI
  3. Validar que audit_gate roda após revisor e força re-auditoria se texto mudou
```