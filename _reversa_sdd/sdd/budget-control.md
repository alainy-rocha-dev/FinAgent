# Spec: budget-control

> Selo 🟡 PLANEJADO. Componente gerado pelo reversa-spec-sdd a partir do PRD FinAgent + AgentPulse.

---

## 1. Resumo

🟡 Controle de orçamento de tokens/custo por tarefa e mensal global. Teto provisório conservador na etapa do budget-control; calibração com 20 execuções do grafo real depois. Estado `BUDGET_EXCEEDED` com motivo legível. Tentativas contam no orçamento. Serviço injetado na API (estimativa) e no grafo (contagem real).

---

## 2. Requisitos Funcionais

| ID | Requisito | Prioridade | Critério de Aceite |
|----|-----------|------------|---------------------|
| 🟡 RF-01 | Teto por tarefa: `token_budget_per_task` (provisório conservador; calibrar com 20 execuções reais do grafo depois) | Must | Contagem: tokens entrada + saída de todos LLMs (Planner, Redator, Revisor, Auditoria). Estouro → transição atômica `BUDGET_EXCEEDED` com motivo legível |
| 🟡 RF-02 | Limite mensal global: `monthly_token_budget` (baixo por padrão, elevado só por config explícita) | Must | Contador Redis com TTL 30 dias, `INCR` atômico. Atingido → novas tarefas 429 com `Retry-After` até virada do mês. Tarefas em andamento completam |
| 🟡 RF-03 | Modelos separados: `model_planner`, `model_redator`, `model_revisor`, `model_auditoria` | Must | Padrão: pequeno/barato para Planner, Redator, Revisor; maior só se auditoria mostrar ganho mensurável. Suporte opcional Ollama (`OLLAMA_BASE_URL`) |
| 🟡 RF-04 | Stub LLM para testes (sem custo, latência controlada 50ms) | Must | Usado em CI, caos, carga |
| 🟡 RF-05 | Middleware na API: estima tokens antes de enfileirar (baseado em símbolo, tamanho esperado) | Should | Se estimativa > teto → 422 `budget_exceeded_estimated` |
| 🟡 RF-06 | Guard no grafo: conta tokens reais a cada chamada LLM; aborta se excede | Must | `BudgetExceeded` exception → `task-state-machine` transiciona para `BUDGET_EXCEEDED` |
| 🟡 RF-07 | Tentativas (retries) contam no orçamento da tarefa | Must | Cada retry soma tokens; não zera contador |
| 🟡 RF-08 | Serviço injetado (não vive na API nem no grafo) | Must | `BudgetControl` protocol com `estimate()`, `consume()`, `check()`, `remaining()` |

---

## 3. Comportamentos

🟡 **Estimativa na API (pré-enfileiramento):**
```python
class BudgetControl:
    def estimate(self, symbol: str, model: str) -> TokenEstimate:
        # Heurística: base histórico por símbolo/modelo
        return TokenEstimate(input_tokens=..., output_tokens=..., estimated_cost_usd=...)
    
    def check_task_budget(self, api_key_id: str, estimate: TokenEstimate) -> BudgetCheck:
        # task_budget = token_budget_per_task (provisório)
        # monthly = monthly_token_budget (Redis INCR)
        if estimate.total_tokens > task_budget:
            return BudgetCheck(allowed=False, reason="task_budget_exceeded_estimated")
        if monthly_used + estimate.total_tokens > monthly_token_budget:
            return BudgetCheck(allowed=False, reason="monthly_budget_exceeded", retry_after=...)
        return BudgetCheck(allowed=True, remaining_task=..., remaining_monthly=...)
```

🟡 **Consumo real no grafo (por nó LLM):**
```python
def llm_call(node_name: str, prompt: str, model: str) -> LLMResponse:
    response = actual_llm_call(prompt, model)
    tokens = count_tokens(response)
    cost = calculate_cost(tokens, model)
    budget_control.consume(task_id, node_name, tokens, cost)
    return response
```

🟡 **Estouro:**
- `budget_control.check(task_id)` lança `BudgetExceeded(task_budget_exceeded | monthly_budget_exceeded)`
- Grafo captura → `task-state-machine.transition(task_id, current, 'BUDGET_EXCEEDED', reason, 'system', 'budget_control')`
- Evento em `task_events` com `{task_id, reason, tokens_used, cost_usd, limit_task, limit_monthly}`
- Tarefa **não retoma** (terminal)

🟡 **Modelos (configuráveis):**
```yaml
models:
  planner: "gpt-4o-mini"
  redator: "gpt-4o-mini"
  revisor: "gpt-4o-mini"
  auditoria: "gpt-4o-mini"  # maior só se ganho mensurável
  ollama_base_url: null  # opcional
```

---

## 4. Edge Cases

| Cenário | Comportamento |
|---------|---------------|
| 🟡 Estimativa API passa, mas grafo estoura no meio | Guard no grafo captura → `BUDGET_EXCEEDED` terminal |
| 🟡 Retry por erro transitório soma tokens | `consume()` chamado a cada chamada LLM real; retries contam |
| 🟡 Limite mensal atingido durante tarefa | Novas tarefas 429; tarefa atual completa (não interrompida no meio por limite mensal) |
| 🟡 Ollama configurado | `BudgetControl` usa endpoint local; custo = 0; tokens ainda contam para teto por tarefa |
| 🟡 Stub LLM em testes | `BudgetControl` modo stub: `consume()` soma tokens fixos (ex: 100 por chamada); custo = 0 |

---

## 5. Não-Gols

🟡 Não implementar máquina de estados (componente `task-state-machine`)
🟡 Não implementar API HTTP (componente `task-api` — usa budget-control via middleware)
🟡 Não implementar grafo LangGraph (componente `analysis-graph` — usa budget-control via guard)
🟡 Não definir valores finais de `token_budget_per_task` e `monthly_token_budget` (provisórios, calibrar depois)
🟡 Não implementar dashboard de custos (componente `observability` — consome métricas)

---

## 6. Interface de Integração

🟡 **Entrada:** `task_id`, `node_name`, `model`, `tokens`, `cost` (grafo); `symbol`, `model` (API estima)
🟡 **Saída:** `BudgetCheck` (allowed/remaining/reason), exceção `BudgetExceeded`, métricas `llm_tokens_total`, `llm_cost_usd_total`
🟡 **Dependências:** Redis (contador mensal), `task-state-machine` (transição terminal), `analysis-graph` (chama `consume`), `task-api` (chama `estimate`/`check`), `observability` (métricas)

---

## 7. Critérios de Aceite (Gherkin)

```gherkin
Cenário: Teto por tarefa respeitado
  Dado token_budget_per_task = 10000 (provisório)
  Quando grafo consome 9500 tokens no Planner + Redator
  E Revisor tentaria consumir 1000 tokens
  Então BudgetExceeded lançado
  E task-state-machine transiciona para BUDGET_EXCEEDED
  E evento gravado com tokens_used=9500, limit=10000

Cenário: Limite mensal bloqueia novas tarefas
  Dado monthly_token_budget = 100000 (baixo por padrão)
  E contador Redis = 99500
  Quando POST /tasks com estimativa 1000 tokens
  Então 422 budget_exceeded_estimated na API (antes de enfileirar)
  Quando tarefa em andamento consome últimos 500 tokens
  Então tarefa completa normalmente (não interrompida)

Cenário: Retry conta no orçamento
  Dado chamada LLM falha (erro transitório) e retenta
  Quando segunda tentativa sucede
  Então budget_control.consume() chamado duas vezes
  E tokens totais = soma das duas chamadas
```

---

## 8. Perguntas Abertas

⚠️ **ABERTO:** `token_budget_per_task` provisório — valor inicial conservador (ex: 50000 tokens)? Calibrar com 20 execuções reais do grafo completo
⚠️ **ABERTO:** `monthly_token_budget` baixo por padrão — valor inicial (ex: 1M tokens/mês)?
⚠️ **ABERTO:** Heurística de estimativa na API — baseada em histórico por símbolo ou valor fixo conservador?
⚠️ **ABERTO:** `model_auditoria` maior só se ganho mensurável — como medir "ganho mensurável"?

---

## 9. Valores Iniciais (a medir)

| Parâmetro | Valor Inicial | Fonte |
|-----------|---------------|-------|
| 🟡 `token_budget_per_task` (provisório) | 50000 tokens | Conservador |
| 🟡 `monthly_token_budget` (baixo) | 1_000_000 tokens | Arbitrário |
| 🟡 Modelos padrão | gpt-4o-mini (todos) | Custo/benefício |
| 🟡 Stub LLM tokens/chamada | 100 | Fixo para testes |

---

## 10. Relatório de Avaliação (Scoring)

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SCORE TOTAL: 85/100
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Breakdown:
  Completude:    85/100 (peso 30%)
  Testabilidade: 85/100 (peso 25%)
  Clareza:       85/100 (peso 20%)
  Escopo:        85/100 (peso 15%)
  Edge Cases:    85/100 (peso 10%)

Gaps críticos:
  - Valores de teto (task e mensal) são provisórios e precisam calibração real
  - Heurística de estimativa na API não definida
  - Critério "ganho mensurável" para modelo maior vago

Sugestões:
  1. Executar 20 runs do grafo real no spike para medir distribuição de tokens
  2. Definir `token_budget_per_task` = p99 medido × 1.5 (margem)
  3. Implementar `BudgetControl` como protocol injetável (facilita stub em testes)
```