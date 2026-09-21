# Unit: `agents` — Requisitos do Módulo

> Módulo central de especialistas autônomos para coleta de dados de mercado, análise quantitativa e redação de relatórios.

## Visão Geral
O módulo `agents` agrupa a lógica de domínio especializada do sistema. Ele é composto por 3 agentes independentes que cobrem o ciclo completo de vida dos dados: desde a ingestão (online/mock), passando pelos cálculos estatísticos determinísticos, até a síntese e validação do relatório final em Markdown.

## Responsabilidades
- Ingestão resiliente de preços e volumes com suporte a Mock Fallback (`DataCollectorAgent`).
- Processamento quantitativo determinístico sem alucinações de LLM (`QuantAnalystAgent`).
- Redação de relatórios Markdown executivos e validação anti-alucinação (`ReportWriterAgent`).

## Regras de Negócio
- **RN-AG-01:** Se a chamada para a Yahoo Finance API falhar ou se `use_mock=True`, o sistema deve utilizar automaticamente os dados simulados contidos na base mock (`AAPL`, `USD/BRL`, `PETR4`, `VALE3`). 🟢
- **RN-AG-02:** A análise de média móvel exige quantidade de pontos de preço limpos maior ou igual à janela $W$. Caso contrário, retorna o erro `INSUFFICIENT_DATA_POINTS`. 🟢
- **RN-AG-03:** O desvio padrão e a volatilidade são calculados com amostra populacional/amostral $ddof=1$. Valores de preço `NaN` ou nulos são expurgados antes do cálculo. 🟢
- **RN-AG-04:** O relatório só é aprovado se contiver os valores exatos de `mean_price` e `volatility` produzidos pelas ferramentas Python. 🟢

## Requisitos Funcionais

| ID | Requisito | Prioridade | Critério de Aceite |
|----|-----------|-----------|-------------------|
| RF-01 | Coletar dados brutos de mercado por símbolo | Must | Retornar `MarketDataPayload` com `price_history` válido. |
| RF-02 | Calcular média móvel simples, volatilidade e extremos | Must | Retornar `QuantAnalysisMetrics` com precisão de 4 casas decimais. |
| RF-03 | Gerar relatório em Markdown formatado | Must | Retornar texto em Markdown com tabelas e selo determinístico. |
| RF-04 | Validar anti-alucinação | Must | Retornar `True` apenas se números chave no relatório conferirem com a análise. |

## Requisitos Não Funcionais

| Tipo | Requisito inferido | Evidência no código | Confiança |
|------|--------------------|---------------------|-----------|
| Performance | Timeout de 5s em chamadas externas HTTP | `sisanalisefinanceira/agents/data_collector.py:79` | 🟢 |
| Resiliência | Fallback automático para dados mock em exceções | `sisanalisefinanceira/agents/data_collector.py:38-40` | 🟢 |
| Integridade | Regeração determinística do relatório se reprovado na validação | `sisanalisefinanceira/agents/report_writer.py:35` | 🟢 |

## Critérios de Aceitação

```gherkin
Dado um símbolo válido "AAPL"
Quando DataCollectorAgent.fetch_data("AAPL") for chamado
Então deve retornar MarketDataPayload com 7 preços de fechamento

Dado um payload com preços válidos e janela 2
Quando QuantAnalystAgent.analyze(payload) for chamado
Então deve calcular moving_average, mean_price, std_dev e volatility %

Dado um relatório rascunhado com métricas válidas
Quando ReportWriterAgent.validate_anti_hallucination(relatorio, metricas) for chamado
Então deve retornar True se mean_price e volatility estiverem presentes no texto
```

## Prioridade (MoSCoW)

| Requisito | MoSCoW | Justificativa |
|-----------|--------|---------------|
| Coleta resiliente de dados (`DataCollectorAgent`) | Must | Início do pipeline de dados, bloqueante. |
| Cálculo estatístico determinístico (`QuantAnalystAgent`) | Must | Core de inteligência quantitativa do sistema. |
| Geração e validação de relatório (`ReportWriterAgent`) | Must | Entrega final de valor para o usuário. |

## Rastreabilidade de Código

| Arquivo | Função / Classe | Cobertura |
|---------|-----------------|-----------|
| `sisanalisefinanceira/agents/data_collector.py` | `DataCollectorAgent` | 🟢 |
| `sisanalisefinanceira/agents/quant_analyst.py` | `QuantAnalystAgent`, `calculate_moving_average_tool`, `calculate_volatility_tool`, `optimize_weights_tool` | 🟢 |
| `sisanalisefinanceira/agents/report_writer.py` | `ReportWriterAgent` | 🟢 |
