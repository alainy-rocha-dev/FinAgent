# Unit: `orchestrators` — Design Técnico

> Especificação de design dos motores de orquestração do sistema.

## Interface

| Símbolo | Assinatura | Retorno | Observação |
|---------|-----------|---------|------------|
| `CrewAIOrchestrator.run` | `(symbol: str)` | `AgentState` | Encadeamento linear sequencial. |
| `LangGraphOrchestrator.run` | `(symbol: str)` | `AgentState` | Máquina de estados iterativa com `max_iter`. |

## Fluxo Principal

### `LangGraphOrchestrator`
1. Inicializa `AgentState` com `iteration_count = 0`.
2. Enquanto `iteration_count < max_iter`:
   - Incrementa `iteration_count`.
   - Se `state.raw_data` for nulo: Invoca `DataCollectorAgent.fetch_data(symbol)`.
   - Se `state.quant_analysis` for nulo: Invoca `QuantAnalystAgent.analyze(state.raw_data)`.
   - Se `state.final_report` for nulo: Invoca `ReportWriterAgent.generate_report(...)`.
   - Se o relatório for validado (`is_valid = True`), encerra o loop.
3. Se o loop encerrar sem relatório final e sem erro registrado, define `error_state = "MAX_ITER_REACHED"`.

### `CrewAIOrchestrator`
1. Executa coleta de dados $\rightarrow$ verifica erro.
2. Executa análise quantitativa $\rightarrow$ verifica erro.
3. Executa redação de relatório $\rightarrow$ retorna `AgentState`.

## Dependências

- `sisanalisefinanceira.agents.data_collector.DataCollectorAgent`
- `sisanalisefinanceira.agents.quant_analyst.QuantAnalystAgent`
- `sisanalisefinanceira.agents.report_writer.ReportWriterAgent`
- `sisanalisefinanceira.models.AgentState`
- `sisanalisefinanceira.config.settings`

## Decisões de Design Identificadas

| Decisão | Evidência no código | Confiança |
|---------|---------------------|-----------|
| Abstração de motores sem dependência direta dos frameworks externos (Custom Adapters) | `sisanalisefinanceira/orchestrators/langgraph_orchestrator.py:17-25` | 🟢 |
| Salvaguarda `MAX_ITER_REACHED` para prevenir loops infinitos em falhas repetidas | `sisanalisefinanceira/orchestrators/langgraph_orchestrator.py:66` | 🟢 |
