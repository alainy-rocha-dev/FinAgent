# 📊 FinAgent — Sistema Multiagentes de Análise Financeira (CrewAI / LangGraph)

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![LangGraph](https://img.shields.io/badge/Orchestrator-LangGraph-FF6F00?style=for-the-badge)](https://github.com/langchain-ai/langgraph)
[![CrewAI](https://img.shields.io/badge/Orchestrator-CrewAI-0052CC?style=for-the-badge)](https://github.com/joaomdmoura/crewAI)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](./LICENSE)

> **FinAgent** é um sistema autônomo de análise estatística de dados de mercado e finanças, construído em arquitetura multiagente com suporte a **duplo motor de orquestração (LangGraph e CrewAI)** e camada de **validação cruzada anti-alucinação 100% determinística**.

---

## 🌟 Destaques da Arquitetura

1. **🤖 Coletor de Dados (`DataCollectorAgent`):**
   - Ingestão de cotações históricas via APIs de mercado (Yahoo Finance) com fallback automático para dados simulados (*Mock Fallback*).
2. **📈 Analista Quantitativo (`QuantAnalystAgent`):**
   - Cálculos estatísticos determinísticos sem risco de alucinação de LLM (Média Móvel, Volatilidade %, Desvio Padrão e Extremos) via `Pandas`, `NumPy` e `SciPy` com fallback transparente para funções nativas Python.
3. **✍️ Redator Executivo (`ReportWriterAgent`):**
   - Síntese de relatórios operacionais em Markdown com camada de auditoria anti-alucinação que exige correspondência numérica biunívoca antes da publicação.
4. **⚙️ Dupla Orquestração Modulável:**
   - **LangGraph (StateGraph):** Máquina de estados iterativa com limite estrito de iterações (`max_iter = 3`) e salvaguarda `MAX_ITER_REACHED`.
   - **CrewAI (Task Chaining):** Encadeamento sequencial linear de contextos de tarefas.

---

## 🌐 Documentação Interativa & Cidade do Código 3D

O projeto conta com um **mini-site interativo de documentação visual e arquitetura 3D** gerado pelo framework **Reversa**:

- 🌆 **Cidade do Código 3D (Code City em Three.js):** Navegação tridimensional onde a altura dos edifícios representa o LOC e a área representa a densidade de código dos módulos.
- 🔗 **Grafo de Módulos 2D (D3.js):** Mapeamento dinâmico de dependências e acoplamentos.
- 📊 **Painel de Métricas (Highcharts):** Dashboards de distribuição de código e complexidade.
- 📖 **Glossário de Termos:** Conceitos e termos do ecossistema multiagente.

### 💡 Como abrir a documentação visual:
Abra o arquivo [`_reversa_docs/index.html`](./_reversa_docs/index.html) diretamente no seu navegador (suporta abertura offline via `file://` sem necessidade de servidor).

```bash
# No Windows PowerShell:
start _reversa_docs/index.html

# Ou subindo um servidor HTTP local:
python -m http.server 8080 --directory _reversa_docs
```

---

## 🚀 Como Executar

### 1. Pré-requisitos
- Python 3.10+
- Instalar dependências:
```bash
pip install -r requirements.txt
```

### 2. Execução via CLI

#### Execução com LangGraph (padrão)
```bash
python -m sisanalisefinanceira.cli --symbol AAPL --engine langgraph
```

#### Execução com CrewAI
```bash
python -m sisanalisefinanceira.cli --symbol USD/BRL --engine crewai
```

#### Execução Online (sem dados mock)
```bash
python -m sisanalisefinanceira.cli --symbol PETR4 --no-mock
```

---

## 🧪 Suíte de Testes Automatizados

Para executar os testes unitários e validar a precisão determinística dos cálculos estatísticos:

```bash
python -m unittest discover tests
```

---

## 📁 Estrutura do Repositório

```
sisanalisefinanceira/
├── cli.py                     # Interface de linha de comando (CLI)
├── config.py                  # Parâmetros e configurações globais
├── models.py                  # Schemas Pydantic (MarketDataPayload, QuantAnalysisMetrics, AgentState)
├── agents/                    # Agentes Especialistas
│   ├── data_collector.py      # Coleta de dados de mercado (API / Mock Fallback)
│   ├── quant_analyst.py       # Cálculos quantitativos determinísticos (Pandas/NumPy)
│   └── report_writer.py       # Geração de Markdown e validação anti-alucinação
├── orchestrators/             # Motores de Orquestração
│   ├── crewai_orchestrator.py # Task Chaining estilo CrewAI
│   └── langgraph_orchestrator.py # StateGraph estilo LangGraph com max_iter
└── utils/                     # Utilitários
    └── logging.py             # Logging estruturado e salvaguardas
_reversa_sdd/                  # Especificações técnicas e SDD da Engenharia Reversa
_reversa_docs/                 # Mini-site da documentação visual e Code City 3D
tests/                         # Suíte de testes unitários
```

---

## 📄 Licença

Este projeto está licenciado sob a licença **MIT** — consulte o arquivo [LICENSE](./LICENSE) para mais detalhes.
