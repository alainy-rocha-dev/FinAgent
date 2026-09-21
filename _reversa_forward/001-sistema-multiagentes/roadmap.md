# Roadmap: Sistema Multiagentes de Análise Financeira (CrewAI / LangGraph)

> Identificador: `001-sistema-multiagentes`
> Data: `2026-09-21`
> Requirements: `_reversa_forward/001-sistema-multiagentes/requirements.md`
> Confidência: 🟢 CONFIRMADO, 🟡 INFERIDO, 🔴 LACUNA

## 1. Resumo da abordagem

A abordagem técnica consiste na construção de um pacote modular Python (`sisanalisefinanceira`) estruturado com arquitetura desacoplada de agentes, ferramentas determinísticas e orquestradores. A pipeline executará em 3 camadas principais: (1) **Data Collector**, encarregado da ingestão via web scraping ou `yfinance`/API pública com suporte a mocks resilientes em JSON; (2) **Quant Analyst**, operando estritamente via ferramentas Python determinísticas (Pandas/NumPy/SciPy) expostas via Function Calling com trava anti-alucinação; e (3) **Report Writer**, que gera relatórios executivos formatados em Markdown. A camada de orquestração implementará uma interface abstrata comum permitindo o suporte duplo e permutável entre **CrewAI** (Task Chaining) e **LangGraph** (`StateGraph` com validação Pydantic e `max_iter = 3`).

## 2. Princípios aplicados

| Princípio | Como a feature se relaciona | Status |
|-----------|------------------------------|--------|
| I. Processamento Quantitativo Determinístico | Todo cálculo numérico (média, desvio padrão, volatilidade) é feito obrigatoriamente por ferramentas Python (Pandas/NumPy), isolando o LLM da manipulação direta de números. | respeita |
| II. Validação de Contratos Tipados | A comunicação inter-agentes e transições de estado são validadas usando schemas Pydantic tipados. | respeita |
| III. Controle de Iterações e Resiliência | Prevenção contra loops de execução com limite `max_iter = 3` e retentativas com tratamento gracioso de erro (`MAX_ITER_REACHED`). | respeita |

## 3. Decisões técnicas

| ID | Decisão | Justificativa | Alternativas descartadas | Confidência |
|----|---------|----------------|--------------------------|-------------|
| D-01 | Isolamento de Cálculos em Tools Python | Garante 0% de erro ou alucinação aritmética nos relatórios executivos | Deixar o LLM calcular médias diretamente no prompt | 🟢 |
| D-02 | Arquitetura de Orquestração Abstrata (`AgentOrchestrator`) | Permite alternar facilmente via linha de comando (`--engine crewai` vs `--engine langgraph`) | Acoplamento direto a um único framework de agentes | 🟢 |
| D-03 | Validação de Estado via Pydantic (`StateGraph`) | Garante que dados entre etapas estejam sempre estritamente formatados e tipados | Passagem de dicionários genéricos e não tipados (`dict`) | 🟢 |
| D-04 | Ingestão com Fallback Mock Local | Garante execução offline, testes unitários reproduzíveis e resiliência contra rate-limit de APIs | Dependência exclusiva de chamadas online em tempo real | 🟢 |

## 4. Premissas

| Premissa | Origem (`requirements.md` seção) | Risco se errada |
|----------|----------------------------------|-----------------|
| Ingestão primária pode ser realizada via `yfinance` ou scraping simples | Seção 4 (Regra 1) e Seção 5 (RF-01) | Baixo (caso haja alteração de layout HTML, o fallback de mock garante a execução) |

## 5. Delta arquitetural

| Componente | Arquivo de origem no legado | Tipo de mudança | Resumo |
|------------|------------------------------|-----------------|--------|
| `DataCollectorAgent` | `_reversa_sdd/sdd/data-collector-agent.md` | componente-novo | Módulo de scraping/API com fallback mock |
| `QuantAnalystAgent` | `_reversa_sdd/sdd/quant-analyst-agent.md` | componente-novo | Módulo de análise estatística com ferramentas Pandas/NumPy |
| `ReportWriterAgent` | `_reversa_sdd/sdd/report-writer-agent.md` | componente-novo | Módulo de síntese e formatação de relatório em Markdown |
| `MultiagentOrchestrator` | `_reversa_sdd/sdd/multiagent-orchestrator.md` | componente-novo | Camada de orquestração dupla (CrewAI / LangGraph) |

## 6. Delta no modelo de dados

- Resumo das mudanças: Adição das estruturas de estado Pydantic `MarketDataState`, `QuantAnalysisResult` e `FinancialReportOutput`.
- Detalhe completo em: `_reversa_forward/001-sistema-multiagentes/data-delta.md`

## 7. Delta de contratos externos

| Contrato | Tipo | Arquivo de detalhe |
|----------|------|--------------------|
| `MarketDataContract` | HTTP / API | `_reversa_forward/001-sistema-multiagentes/interfaces/market-data-api.md` |

## 8. Plano de migração

1. n/a - Projeto Greenfield/Evolução inicial de módulo sem necessidade de migração de banco pré-existente.

## 9. Riscos e mitigações

| Risco | Impacto | Probabilidade | Mitigação |
|-------|---------|---------------|-----------|
| Bloqueio por Rate Limit/Scraping em APIs financeiras | médio | média | Implementação de fallback automático para `MockMarketDataProvider` e cache local de payloads JSON |
| Loop de decisão entre agentes em caso de erro de parsing | alto | baixa | Limite estrito de iterações (`max_iter = 3`) com salvaguarda `MAX_ITER_REACHED` |
| Incompatibilidade de versão entre CrewAI e LangGraph | médio | baixa | Isolamento dos adapter layers de cada engine em submódulos distintos |

## 10. Critério de pronto

- [ ] Todas as ações do `actions.md` marcadas `[X]`
- [ ] Testes unitários para as ferramentas numéricas executando com 100% de precisão
- [ ] Execução da CLI gerando relatório Markdown válido tanto em modo `crewai` quanto em modo `langgraph`

## 11. Histórico de alterações

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-09-21 | Versão inicial gerada por `/reversa-plan` | reversa |
