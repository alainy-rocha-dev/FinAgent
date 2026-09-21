# Unit: `agents` — Tarefas de Implementação

> Lista de tarefas rastreáveis para reimplementação ou evolução do módulo de agentes.

## Pré-requisitos
- [x] Python 3.10+ configurado.
- [x] Bibliotecas `pydantic`, `pandas`, `numpy`, `scipy`, `requests` disponíveis (com suporte a fallback em math pura).

## Tarefas

- [ ] T-AG-01, Reimplementar `DataCollectorAgent` com suporte a Mock e Web Scraping
  - Origem no legado: `sisanalisefinanceira/agents/data_collector.py:15-95`
  - Critério de pronto: Chamadas com `symbol` válido retornam `MarketDataPayload`; exceções acionam `_fetch_mock`.
  - Confiança: 🟢

- [ ] T-AG-02, Reimplementar `QuantAnalystAgent` e ferramentas determinísticas
  - Origem no legado: `sisanalisefinanceira/agents/quant_analyst.py:15-139`
  - Critério de pronto: Cálculos de média móvel, volatilidade e desvio padrão batem exatamente com testes de precisão.
  - Confiança: 🟢

- [ ] T-AG-03, Reimplementar `ReportWriterAgent` com camada de validação anti-alucinação
  - Origem no legado: `sisanalisefinanceira/agents/report_writer.py:17-140`
  - Critério de pronto: Relatório Markdown é sintetizado e passa em `validate_anti_hallucination`.
  - Confiança: 🟢

## Tarefas de Teste

- [ ] TT-AG-01, Executar suíte de testes do DataCollector (`tests/test_data_collector.py`)
- [ ] TT-AG-02, Executar suíte de testes do QuantAnalyst (`tests/test_quant_analyst.py`)
- [ ] TT-AG-03, Criar testes unitários para o `ReportWriterAgent` (cobertura de validação anti-alucinação)

## Ordem Sugerida
1. Reimplementar `DataCollectorAgent` (fonte de dados inicial).
2. Reimplementar `QuantAnalystAgent` (cálculos determinísticos).
3. Reimplementar `ReportWriterAgent` (síntese e validação de relatório).
