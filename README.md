# 📊 FinAgent — Sistema Multiagentes de Análise Financeira

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](./LICENSE)

Este projeto integra o AgentPulse API (pasta automacao_agentes, como submódulo) como camada de execução e o módulo de análise sisanalisefinanceira.

> **FinAgent** é um sistema de análise estatística de dados de mercado e finanças em arquitetura multiagente com **pipeline determinístico** (coleta → cálculo → template) e **validação cruzada anti-alucinação numérica** (cálculos 100% determinísticos via Python/Pandas/NumPy).

---

## 🌟 Destaques da Arquitetura

1. **🤖 Coletor de Dados (`DataCollectorAgent`):**
   - Ingestão de cotações históricas via API (Yahoo Finance) com fallback automático para dados simulados (*Mock Fallback*).
   - **Aviso visível no relatório quando dados simulados são usados** (banner `⚠️ DADOS SIMULADOS`).

2. **📈 Analista Quantitativo (`QuantAnalystAgent`):**
   - Cálculos estatísticos determinísticos: Média Móvel, Volatilidade %, Desvio Padrão, Extremos.
   - Implementados com `Pandas`/`NumPy`/`SciPy` com fallback transparente para funções nativas Python (`statistics`, `math`).
   - **Cálculos 100% determinísticos: todo número é calculado por código Python, sem LLM**.

3. **✍️ Redator Executivo (`ReportWriterAgent`):**
   - Geração de relatórios em Markdown via **template fixo (não LLM)**.
   - Camada de auditoria que valida correspondência numérica exata entre métricas calculadas e números no relatório.

4. **⚙️ Dois Padrões de Orquestração (implementados do zero):**
   - **StateGraph-style:** Máquina de estados iterativa com limite estrito de iterações (`max_iter = 3`) e salvaguarda `MAX_ITER_REACHED`.
   - **Task Chaining-style:** Encadeamento sequencial linear de contextos de tarefas.
   - *Nota: não usam as bibliotecas `langgraph` nem `crewai` — são implementações próprias seguindo esses padrões.*

> **Nota sobre "Agentes":** Atualmente o sistema opera como **pipeline determinístico** (coleta → cálculo → template). Não há chamadas a LLM em tempo de execução. A arquitetura prevê slots para LLM (ex: geração de narrativa textual, decisão de alocação) que podem ser ativados futuramente via flags de feature.

---

## 🌐 Documentação Interativa & Visualizações

O projeto conta com um **mini-site de documentação visual** gerado pelo framework **Reversa** (`_reversa_docs/`):

- 🌆 **Cidade do Código 3D** (`arquitetura.html`): Visualização Three.js onde prédios representam volume de código por módulo
- 🔗 **Grafo de Módulos 2D** (`modulos.html`): Grafo de força em D3.js com acoplamentos e dependências
- 📊 **Painel de Métricas** (`metricas.html`): Dashboards Highcharts (treemap LOC, complexidade, sankey, confiança 95.7%)
- 📖 **Glossário de Termos** (`glossario.html`): Conceitos financeiros, salvaguardas e termos do ecossistema
- 📜 **Especificações por Feature** (`features/`): Agentes, Orquestradores, Utilitários

### 💡 Como abrir a documentação visual:

> ⚠️ **Nota:** Clicar no link Markdown no IDE abre o código-fonte. Para ver o site formatado, abra no navegador.

```bash
# Opção 1: Windows
start _reversa_docs/index.html

# Opção 2: Servidor HTTP local (recomendado para JS/CORS)
python -m http.server 8080 --directory _reversa_docs
# Abra http://localhost:8080
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

#### Pipeline StateGraph-style (padrão)
```bash
python -m sisanalisefinanceira.cli --symbol AAPL --engine langgraph
```

#### Pipeline Task Chaining-style
```bash
python -m sisanalisefinanceira.cli --symbol USD/BRL --engine crewai
```

#### Execução Online (tenta Yahoo Finance, falha se rate-limited)
```bash
python -m sisanalisefinanceira.cli --symbol PETR4 --no-mock
```

**Saída esperada (exemplo com mock):**
```
SISTEMA MULTIAGENTES DE ANALISE FINANCEIRA
Simbolo: AAPL | Engine: LANGGRAPH | Mock: True

[LangGraph] Iteração 1/3 iniciada para símbolo: AAPL
[LangGraph] Relatório final gerado com sucesso e validado anti-alucinação.

RELATORIO FINAL GERADO:
# 📊 Relatório Executivo de Análise Financeira
> **Ativo / Símbolo:** `AAPL`
> **Fonte dos Dados:** `mock_fallback`
> **⚠️ DADOS SIMULADOS (MOCK FALLBACK)`
> **Garantia Numérica:** 🟢 Cálculos 100% Determinísticos...
...
```

---

## 🧪 Testes Automatizados

```bash
pytest tests/ -v
```
**Resultado atual:** 10/10 testes passando (cobertura: coletor mock, validação quantitativa, edge cases NaN/janelas)

---

## 📁 Estrutura do Repositório

```
sisanalisefinanceira/
├── cli.py                     # Interface de linha de comando
├── config.py                  # Configurações globais (max_iter, mock, paths)
├── models.py                  # Schemas Pydantic (MarketDataPayload, QuantAnalysisMetrics, AgentState)
├── agents/                    # Agentes Especialistas
│   ├── data_collector.py      # Coleta API + mock fallback
│   ├── quant_analyst.py       # Cálculos determinísticos (Pandas/NumPy/Math)
│   └── report_writer.py       # Template Markdown + validação numérica
├── orchestrators/             # Padrões de Orquestração
│   ├── crewai_orchestrator.py # Task Chaining (sequencial)
│   └── langgraph_orchestrator.py # StateGraph (iterativo c/ max_iter)
└── utils/                     
    └── logging.py             # Logging estruturado
_reversa_sdd/                  # Specs SDD da Engenharia Reversa
_reversa_docs/                 # Mini-site docs visual (HTML/JS standalone)
tests/                         # Testes pytest (10 passing)
reports/                       # Relatórios gerados (.md)
```

---

## ⚠️ Limitações Conhecidas (Honestidade para Recrutadores)

| Item | Status | Detalhe |
|------|--------|---------|
| **LLM em produção** | ❌ Não implementado | Pipeline 100% determinístico; texto é template fixo |
| **CrewAI / LangGraph libs** | ❌ Não usadas | Orquestradores são *pattern implementations* próprias |
| **Dados reais** | ⚠️ Parcial | Yahoo Finance API sujeita a rate limit; mock é default seguro |
| **Otimização de carteira** | 🧪 Tool presente | `optimize_weights_tool` usa SciPy se disponível, senão equal-weight |
| **A2A / Human-in-the-loop** | ❌ Não implementado | Arquitetura prevê, mas não codado |
| **Comparativo LangGraph vs CrewAI** | ❌ Não medido | Dois padrões implementados, mas sem benchmark automatizado |

---

## 📄 Licença

Este projeto está licenciado sob a licença **MIT** — consulte o arquivo [LICENSE](./LICENSE) para mais detalhes.