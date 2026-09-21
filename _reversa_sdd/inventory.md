# Inventário do Sistema — sisanalisefinanceira

## 📌 Visão Geral
- **Projeto:** `sisanalisefinanceira`
- **Linguagem Principal:** Python 3.10+
- **Arquitetura:** Sistema Multiagentes de Análise Financeira
- **Entry Point Principal:** `sisanalisefinanceira/cli.py`

---

## 📁 Estrutura de Diretórios

```
sisanalisefinanceira/
├── __init__.py
├── cli.py                 # Interface de linha de comando (CLI)
├── config.py              # Parâmetros e configurações globais
├── models.py              # Schemas Pydantic (DataPayload, Metrics, AgentState)
├── agents/                # Agentes Especialistas
│   ├── __init__.py
│   ├── data_collector.py  # Coleta de dados de mercado (API/Scraping/Mock)
│   ├── quant_analyst.py   # Análise estatística e quantitativa (Pandas/NumPy)
│   └── report_writer.py   # Geração de relatórios e validação cruzada
├── orchestrators/         # Motores de Orquestração
│   ├── __init__.py
│   ├── crewai_orchestrator.py    # Orquestração em cadeia (CrewAI style)
│   └── langgraph_orchestrator.py # Orquestração baseada em estado com limite max_iter
└── utils/                 # Utilitários e Logs
    ├── __init__.py
    └── logging.py         # Formatação de logs e alertas
tests/                     # Suíte de Testes Unitários
├── __init__.py
├── test_data_collector.py # Testes do agente coletor
└── test_quant_analyst.py  # Testes do agente analista quantitativo
```

---

## 🎯 Componentes e Módulos Identificados

1. **`agents`**: Módulo que agrupa a inteligência especializada do sistema.
   - `data_collector.py`: Coleta de preços históricos e cotações.
   - `quant_analyst.py`: Cálculo de médias móveis, volatilidade e séries temporais.
   - `report_writer.py`: Formatação de Markdown e verificação anti-alucinação.
2. **`orchestrators`**: Motores de fluxo de trabalho multiagente.
   - `langgraph_orchestrator.py`: Grafo iterativo com limite de iterações e salvaguarda `MAX_ITER_REACHED`.
   - `crewai_orchestrator.py`: Pipeline sequencial simples.
3. **`utils`**: Utilitários transversais de suporte.
   - `logging.py`: Registrador de eventos e alertas de execução.

---

## 🧪 Testes Unitários
- Framework: `unittest` (nativo do Python)
- Arquivos de Teste: 2 (`tests/test_data_collector.py`, `tests/test_quant_analyst.py`)
