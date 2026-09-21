# Regression Watch: Sistema Multiagentes de Análise Financeira

> Identificador: `001-sistema-multiagentes`  
> Data: `2026-09-21`  
> Âncora: Greenfield (prd.md + specs SDD)

---

## Tabela de Vigilância Principal

| ID | Origem (arquivo, seção) | Regra esperada após mudança | Tipo de verificação | Sinal de violação |
|---|---|---|---|---|
| - | - | - | - | - |

*(Nenhum watch principal ativo no momento. Projeto em modo greenfield inicial sem extração prévia de código legado).*

---

## Observações e Requisitos Implementados (Greenfield)

Os requisitos funcionais das especificações SDD implementados nesta entrega foram registrados abaixo sem peso de regressão. Eles passarão a integrar a tabela de vigilância principal após uma futura execução do `/reversa` sobre o novo código:

1. **RF-01 (`data-collector-agent`)**: Extração de dados de mercado com fallback simulado para evitar bloqueios de API.
2. **RF-02 (`quant-analyst-agent`)**: Análise estatística 100% determinística via funções Python (Pandas/NumPy/Math).
3. **RF-03 (`report-writer-agent`)**: Sintetizador de relatórios Markdown com verificação anti-alucinação.
4. **RF-04 (`multiagent-orchestrator`)**: Suporte a motores LangGraph (`StateGraph`) e CrewAI com limite estrito de iterações (`max_iter = 3`).

---

## Histórico de re-extrações

_Nenhuma re-extração registrada até o momento._

---

## Arquivadas

_Nenhum item arquivado._
