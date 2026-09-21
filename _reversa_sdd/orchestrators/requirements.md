# Unit: `orchestrators` — Requisitos do Módulo

> Módulo de motores de orquestração do fluxo multiagente (CrewAI e LangGraph).

## Visão Geral
O módulo `orchestrators` gerencia a condução e o encadeamento dos agentes do sistema. Ele implementa o paradigma de dupla orquestração, oferecendo suporte tanto ao encadeamento simples por tarefas (`CrewAIOrchestrator`) quanto a uma máquina de estados iterativa baseada em StateGraph (`LangGraphOrchestrator`) com salvaguarda estrita de iterações (`max_iter`).

## Responsabilidades
- Conduzir o fluxo sequencial de tarefas entre os agentes (`CrewAIOrchestrator`).
- Executar o loop iterativo com controle de estado, re-tentativa e teto de iterações (`LangGraphOrchestrator`).
- Controlar o estado compartilhado `AgentState` e registrar erros como `INVALID_SYMBOL`, `INSUFFICIENT_DATA_POINTS` e `MAX_ITER_REACHED`.

## Regras de Negócio
- **RN-OR-01:** O motor LangGraph deve incrementar `iteration_count` em cada ciclo e abortar a execução com `MAX_ITER_REACHED` caso atinja `max_iter` (padrão: 3) sem gerar um relatório válido. 🟢
- **RN-OR-02:** Se a coleta de dados retornar `INVALID_SYMBOL`, a orquestração é interrompida imediatamente sem tentar as etapas seguintes. 🟢
- **RN-OR-03:** Se a análise quantitativa retornar erro (`error_code`), a orquestração gera um relatório de erro formatado e encerra. 🟢

## Requisitos Funcionais

| ID | Requisito | Prioridade | Critério de Aceite |
|----|-----------|-----------|-------------------|
| RF-OR-01 | Orquestrar execução via encadeamento CrewAI | Must | Retornar `AgentState` final após 3 tarefas. |
| RF-OR-02 | Orquestrar execução via StateGraph LangGraph | Must | Respeitar limite `max_iter` e validar anti-alucinação. |

## Requisitos Não Funcionais

| Tipo | Requisito inferido | Evidência no código | Confiança |
|------|--------------------|---------------------|-----------|
| Confiabilidade | Abortagem segura ao atingir teto de iterações | `sisanalisefinanceira/orchestrators/langgraph_orchestrator.py:66` | 🟢 |

## Critérios de Aceitação

```gherkin
Dado um símbolo válido "AAPL" e max_iter=3
Quando LangGraphOrchestrator.run("AAPL") for executado
Então deve iterar até gerar relatório válido e retornar AgentState populado

Dado um símbolo "INVALID"
Quando CrewAIOrchestrator.run("INVALID") for executado
Então deve interromper no passo 1 e retornar error_state="INVALID_SYMBOL"
```

## Prioridade (MoSCoW)

| Requisito | MoSCoW | Justificativa |
|-----------|--------|---------------|
| Motor LangGraph | Must | Motor padrão configurado via CLI. |
| Motor CrewAI | Should | Motor secundário / alternativo. |

## Rastreabilidade de Código

| Arquivo | Função / Classe | Cobertura |
|---------|-----------------|-----------|
| `sisanalisefinanceira/orchestrators/crewai_orchestrator.py` | `CrewAIOrchestrator` | 🟢 |
| `sisanalisefinanceira/orchestrators/langgraph_orchestrator.py` | `LangGraphOrchestrator` | 🟢 |
