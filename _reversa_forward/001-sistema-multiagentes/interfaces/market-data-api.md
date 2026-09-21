# Contrato de Interface Externa: Ingestão de Dados de Mercado

> Feature: `001-sistema-multiagentes`
> Arquivo: `interfaces/market-data-api.md`

## 1. Descrição do Contrato

Este contrato define a interface de ingestão de dados de mercado financeiro consumida pelo `DataCollectorAgent`.

## 2. Métodos e Endpoints

### 2.1 Web Scraping / Python SDK (`yfinance`)
- **Entrada**: Ticker (string, ex: `"PETR4"`), Período (string, ex: `"1mo"`).
- **Saída**: Payloads de cotação histórica (Preços de Fechamento, Histórico).
- **Tratamento de Erros**: Em caso de falha de conexão ou HTTP Status != 200/404, fallback imediato para `MockMarketDataProvider`.

## 3. Formato do Schema de Resposta (JSON / Dict)

```json
{
  "ticker": "PETR4",
  "period": "1mo",
  "source": "yfinance",
  "prices": [32.5, 33.1, 32.8, 34.0],
  "timestamps": ["2026-09-18", "2026-09-19", "2026-09-20", "2026-09-21"]
}
```
