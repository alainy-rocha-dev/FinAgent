# Unit: `agents` — Design Técnico

> Especificação de design dos componentes de agentes do sistema.

## Interface

### Classes e Métodos Públicos

| Símbolo | Assinatura | Retorno | Observação |
|---------|-----------|---------|------------|
| `DataCollectorAgent.fetch_data` | `(symbol: str)` | `MarketDataPayload` | Aceita qualquer símbolo; sanitiza com `strip().upper()`. |
| `QuantAnalystAgent.analyze` | `(payload: MarketDataPayload)` | `QuantAnalysisMetrics` | Executa ferramentas de cálculo estatístico. |
| `ReportWriterAgent.generate_report` | `(raw_data: MarketDataPayload, quant_data: QuantAnalysisMetrics)` | `Tuple[str, bool]` | Retorna tupla `(texto_markdown, is_valid)`. |
| `ReportWriterAgent.validate_anti_hallucination` | `(report_text: str, quant_data: QuantAnalysisMetrics)` | `bool` | Validação cruzada de números no texto. |
| `ReportWriterAgent.save_report_to_file` | `(symbol: str, content: str)` | `str` | Salva relatório no disco e retorna caminho do arquivo. |

## Fluxo Principal

1. **Coleta de Dados:**
   - `DataCollectorAgent` recebe o `symbol`.
   - Limpa o símbolo. Se `use_mock=True`, busca em `mock_db`. Caso contrário, dispara requisição HTTP para `https://query1.finance.yahoo.com/v8/finance/chart/{symbol}`.
   - Em caso de exceção HTTP, loga erro e invoca `_fetch_mock(symbol, fallback_reason=e)`.

2. **Análise Quantitativa:**
   - `QuantAnalystAgent` filtra preços válidos (remove `None` e `NaN`).
   - Invoca `calculate_moving_average_tool(clean_prices, window)` (Pandas ou Math pura).
   - Invoca `calculate_volatility_tool(clean_prices)` (NumPy ou Math pura).
   - Calcula estatísticas descritivas (`mean`, `max`, `min`, `std_dev`).
   - Retorna `QuantAnalysisMetrics`.

3. **Geração e Validação:**
   - `ReportWriterAgent` constrói o Markdown formatado preenchendo as métricas.
   - Executa `validate_anti_hallucination`. Se o texto contiver o `mean_price` e a `volatility` exatos, aprova (`is_valid = True`).

## Dependências

- `sisanalisefinanceira.config.settings`: Parâmetros de janelas, diretórios e flags.
- `sisanalisefinanceira.models`: Schemas `MarketDataPayload` e `QuantAnalysisMetrics`.
- `requests` / `beautifulsoup4` (opcional): Ingestão online.
- `pandas` / `numpy` / `scipy` (opcional): Cálculos otimizados.

## Decisões de Design Identificadas

| Decisão | Evidência no código | Confiança |
|---------|---------------------|-----------|
| Fallback gracioso para Math pura em ausência de Pandas/NumPy | `sisanalisefinanceira/agents/quant_analyst.py:25-31` | 🟢 |
| Ingestão Yahoo Finance sem autenticação via endpoint não oficial | `sisanalisefinanceira/agents/data_collector.py:76` | 🟢 |
| Regeração determinística automática em caso de falha de validação | `sisanalisefinanceira/agents/report_writer.py:35` | 🟢 |

## Observabilidade
- Emite logs via `logging.getLogger(__name__)`.
- Loga avisos quando fallback mock é ativado ou quando o símbolo é inválido.
