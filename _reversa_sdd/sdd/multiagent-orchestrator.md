# Spec SDD: Multiagent Orchestrator (`multiagent-orchestrator`)

> Selo 🟡 PLANEJADO em todos os requisitos, comportamentos e critérios de aceite.

**Versão:** 1.0  
**Data:** 2026-09-21T20:26:00Z  
**Componente:** `multiagent-orchestrator`  
**Status:** 🟡 PLANEJADO  

---

## 1. Visão Geral e Objetivo

🟡 O `multiagent-orchestrator` é a engine de orquestração responsável pelo ciclo de vida, gerenciamento de estado e fluxo de mensagens entre os 3 agentes do sistema. Suporta duplo mecanismo de execução: **CrewAI** (Task Chaining sequencial/hierárquico) e **LangGraph** (`StateGraph` baseado em nós e arestas com estado compartilhado). Implementa controle rigoroso de iterações (`max_iter`) e transmissão de estado tipado via Pydantic.

---

## 2. Requisitos Funcionais

- 🟡 **RF-01 (Suporte a CrewAI):** Definir `Crew`, `Agents` e `Tasks` encadeadas onde a saída do `data-collector-agent` serve como `context` para o `quant-analyst-agent`, e deste para o `report-writer-agent`.
- 🟡 **RF-02 (Suporte a LangGraph):** Implementar um `StateGraph` contendo o estado global do pipeline (`input_params`, `raw_data`, `quant_analysis`, `final_report`, `error_state`, `iteration_count`).
- 🟡 **RF-03 (Controle de Loop e Trava `max_iter`):** Garantir limite máximo configurável de iterações (ex: `max_iter = 3`) para evitar loops infinitos ou re-execuções sem convergência.
- 🟡 **RF-04 (Garantia de Contrato Pydantic entre Nós):** Validar a entrada e saída de cada agente contra schemas Pydantic explícitos antes de avançar o estado.

---

## 3. Comportamentos e Regras de Negócio

- 🟡 O `report-writer-agent` só é acionado se a saída do `quant-analyst-agent` for validada como não-vazia e aprovada pelo schema Pydantic.
- 🟡 O orquestrador registra logs detalhados de transição de estado para auditoria no README e rastreamento de alucinações/erros.

---

## 4. Edge Cases e Tratamento de Erros

- 🟡 **Estouro de Iterações (`max_iter` excedido):** Interrompe a execução, grava o estado atual e gera relatório de falha controlada `MAX_ITER_REACHED`.
- 🟡 **Falha de Schema em Etapa Intermediária:** Redireciona o fluxo para tratamento de erro sem causar crash não tratado na aplicação.

---

## 5. Non-Goals (Fora de Escopo)

- 🟡 Conter lógica de negócios específica de finanças ou logística dentro do código de orquestração (deve ser totalmente delegado aos agentes e ferramentas).

---

## 6. Critérios de Aceite

- 🟡 **Dado** a execução via CrewAI ou LangGraph, **Quando** o pipeline for acionado com parâmetros válidos, **Então** o estado deve fluir sequencialmente pelos 3 nós até o relatório final.
- 🟡 **Dado** uma falha proposital simulada no nó de análise quantitativa, **Quando** o orquestrador atingir `max_iter`, **Then** a execução deve ser encerrada com código de saída de erro legível.

---

## 7. Avaliação de Qualidade

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SCORE TOTAL: 95/100
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Breakdown:
  Completude:    95/100 (peso 30%)
  Testabilidade: 95/100 (peso 25%)
  Clareza:       95/100 (peso 20%)
  Escopo:        95/100 (peso 15%)
  Edge Cases:    95/100 (peso 10%)

Gaps críticos:
  Nenhum gap bloqueador identificado.

Sugestões:
  1. Fornecer script de comparação simples no CLI para chavear entre `--engine crewai` e `--engine langgraph`.
```

---

Gerado por reversa-spec-sdd em 2026-09-21T20:26:00Z  
Fonte: prd.md
