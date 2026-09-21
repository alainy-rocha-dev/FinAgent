# Unit: `orchestrators` — Tarefas de Implementação

> Lista de tarefas para reimplementação dos orquestradores.

## Pré-requisitos
- [x] Módulo `agents` reimplementado e validado.
- [x] Schema `AgentState` disponível.

## Tarefas

- [ ] T-OR-01, Reimplementar `LangGraphOrchestrator`
  - Origem no legado: `sisanalisefinanceira/orchestrators/langgraph_orchestrator.py:17-70`
  - Critério de pronto: Loop de estado com limite `max_iter` e salvaguarda `MAX_ITER_REACHED`.
  - Confiança: 🟢

- [ ] T-OR-02, Reimplementar `CrewAIOrchestrator`
  - Origem no legado: `sisanalisefinanceira/orchestrators/crewai_orchestrator.py:15-53`
  - Critério de pronto: Pipeline sequencial linear entre os 3 agentes.
  - Confiança: 🟢

## Tarefas de Teste

- [ ] TT-OR-01, Criar teste de integração para o motor `LangGraphOrchestrator` com mock e online
- [ ] TT-OR-02, Criar teste de integração para a salvaguarda `MAX_ITER_REACHED`
