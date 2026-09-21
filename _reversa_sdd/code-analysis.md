# Análise Técnica de Código (Code Analysis) — sisanalisefinanceira

> **Status:** 🟢 CONFIRMADO  
> **Nível de Documentação:** Essencial  
> **Gerado por:** Archaeologist  

---

## 1. Visão Geral da Arquitetura de Código

O sistema `sisanalisefinanceira` é implementado em **Python 3.10+**, utilizando o paradigma de orientação a objetos e tipagem estruturada via `Pydantic` v2. 

A arquitetura desacopla a inteligência dos **agentes de domínio** (`agents/`) dos **mecanismos de orquestração** (`orchestrators/`), permitindo alternar de forma transparente entre encadeamento de tarefas (`CrewAIOrchestrator`) e máquina de estados iterativa (`LangGraphOrchestrator`).

---

## 2. Análise Detalhada dos Módulos

### 2.1 Módulo `agents`
Contém as três unidades especializadas de execução:

1. **`DataCollectorAgent` (`data_collector.py`)**:
   - **Propósito:** Ingestão de dados de mercado (preços históricos e volumes).
   - **Fluxo de Controle:** Recebe o símbolo `symbol`. Valida se o símbolo é não-vazio. Se `use_mock=True`, consulta base local `mock_db` (`AAPL`, `USD/BRL`, `PETR4`, `VALE3`). Caso contrário, realiza requisição HTTP para a Yahoo Finance API. Se a requisição online falhar, aciona o fallback automático para dados mock registrando a razão no campo `metadata.fallback_reason`.
   - **Confiança:** 🟢 CONFIRMADO

2. **`QuantAnalystAgent` (`quant_analyst.py`)**:
   - **Propósito:** Cálculos quantitativos e estatísticos determinísticos sem risco de alucinação numérica.
   - **Algoritmos e Tools:**
     - `calculate_moving_average_tool`: Média móvel simples sobre a janela `window`. Tenta usar `pandas.Series.rolling()`; em caso de insucesso ou ausência do Pandas, executa cálculo em Python puro (`sum(sub)/window`).
     - `calculate_volatility_tool`: Volatilidade percentual ($StdDev / Mean \times 100$). Tenta utilizar `numpy.std` e `numpy.mean`; se indisponível, calcula variância e raiz quadrada com `math.sqrt`.
     - `optimize_weights_tool`: Otimização de carteira por minimização de variância (SLSQP via `scipy.optimize.minimize`). Fallback para pesos iguais ($1/n$).
   - **Confiança:** 🟢 CONFIRMADO

3. **`ReportWriterAgent` (`report_writer.py`)**:
   - **Propósito:** Geração de relatórios executivos em Markdown e validação cruzada anti-alucinação.
   - **Validação Anti-Alucinação (`validate_anti_hallucination`):** Verifica se o relatório gerado contém os valores exatos de `mean_price` e `volatility`. Se reprovado na primeira tentativa, dispara uma regeração determinística antes de concluir.
   - **Confiança:** 🟢 CONFIRMADO

---

### 2.2 Módulo `orchestrators`
Responsável pela condução do fluxo de trabalho multiagente.

1. **`LangGraphOrchestrator` (`langgraph_orchestrator.py`)**:
   - **Propósito:** Orquestração inspirada em StateGraph com limite estrito de iterações.
   - **Fluxo em Texto:**
     - Inicializa `AgentState` com `iteration_count = 0`.
     - Loop `while iteration_count < max_iter`:
       - Incrementa `iteration_count`.
       - Se `raw_data` for nulo: Executa `DataCollectorAgent.fetch_data()`.
       - Se `quant_analysis` for nulo e `raw_data` existir: Executa `QuantAnalystAgent.analyze()`.
       - Se `final_report` for nulo e análise concluída: Executa `ReportWriterAgent.generate_report()`. Valida anti-alucinação; se aprovado, encerra loop.
     - Se o loop terminar sem `final_report` e sem `error_state`, atribui `error_state = "MAX_ITER_REACHED"`.
   - **Confiança:** 🟢 CONFIRMADO

2. **`CrewAIOrchestrator` (`crewai_orchestrator.py`)**:
   - **Propósito:** Orquestração sequencial estilo Task Chaining.
   - **Fluxo em Texto:** Executa Task 1 (Coleta) $\rightarrow$ Task 2 (Análise) $\rightarrow$ Task 3 (Relatório) em sequência linear sem tentativas iterativas de re-validação.
   - **Confiança:** 🟢 CONFIRMADO

---

### 2.3 Módulo `utils`
- **`logging.py`**: Configuração centralizada de logs no formato `[datetime] [level] [logger] message` e gerador de alerta para a salvaguarda `handle_max_iter_reached`.

---

## 3. Dicionário de Dados Resumido (Data Dictionary)

| Entidade / Model | Campo | Tipo | Obrigatoriedade | Descrição |
|---|---|---|---|---|
| `MarketDataPayload` | `symbol` | `str` | Sim | Símbolo do ativo financeiro |
| `MarketDataPayload` | `price_history` | `List[float]` | Sim | Série temporal de preços de fechamento |
| `MarketDataPayload` | `volume` | `List[float]` | Não | Volume negociado correspondente |
| `MarketDataPayload` | `metadata` | `Dict[str, Any]` | Não | Origem dos dados, status e timestamp |
| `QuantAnalysisMetrics` | `symbol` | `str` | Sim | Símbolo do ativo |
| `QuantAnalysisMetrics` | `moving_average` | `List[float]` | Não | Série temporal calculada da média móvel |
| `QuantAnalysisMetrics` | `volatility` | `float` | Não | Volatilidade percentual |
| `QuantAnalysisMetrics` | `mean_price` | `float` | Não | Preço médio no período |
| `QuantAnalysisMetrics` | `max_price` | `float` | Não | Preço máximo no período |
| `QuantAnalysisMetrics` | `min_price` | `float` | Não | Preço mínimo no período |
| `QuantAnalysisMetrics` | `std_dev` | `float` | Não | Desvio padrão populacional/amostral |
| `QuantAnalysisMetrics` | `error_code` | `str` | Não | Código de erro (ex: `INSUFFICIENT_DATA_POINTS`) |
| `AgentState` | `input_params` | `Dict[str, Any]` | Sim | Parâmetros de entrada da execução |
| `AgentState` | `raw_data` | `MarketDataPayload` | Não | Dados brutos coletados |
| `AgentState` | `quant_analysis` | `QuantAnalysisMetrics` | Não | Métricas calculadas |
| `AgentState` | `final_report` | `str` | Não | Relatório final em Markdown |
| `AgentState` | `iteration_count` | `int` | Sim | Contador de iterações do grafo |
| `AgentState` | `error_state` | `str` | Não | Estado de erro final ou salvaguarda |
