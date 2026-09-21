# Delta no Modelo de Dados: Sistema Multiagentes

> Feature: `001-sistema-multiagentes`
> Data: `2026-09-21`

## 1. Visão Geral

Como o projeto opera em modo pipeline e CLI sem persistência em banco relacional complexo, o modelo de dados é composto pelos contratos de estado em memória representados por schemas **Pydantic**.

## 2. Novos Schemas de Dados

### `MarketDataPayload` (Pydantic Model)
Representa a resposta bruta capturada pelo Agente Coletor.

```python
class MarketDataPayload(BaseModel):
    ticker: str
    period: str
    prices: List[float]
    timestamps: List[str]
    source: str  # "api", "scraping" ou "mock"
```

### `QuantAnalysisMetrics` (Pydantic Model)
Representa as métricas calculadas deterministicamente pelo Agente Analista.

```python
class QuantAnalysisMetrics(BaseModel):
    ticker: str
    mean_price: float
    std_dev: float
    volatility: float
    min_price: float
    max_price: float
    calculated_at: str
```

### `AgentState` (Pydantic Model / TypedDict para LangGraph)
Estado compartilhado ao longo do grafo de execução.

```python
class AgentState(BaseModel):
    ticker: str
    raw_data: Optional[MarketDataPayload] = None
    metrics: Optional[QuantAnalysisMetrics] = None
    final_report_md: Optional[str] = None
    iter_count: int = 0
    error: Optional[str] = None
```
