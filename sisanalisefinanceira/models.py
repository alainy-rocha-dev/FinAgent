"""
Schemas Pydantic de dados, análises e estado do orquestrador.
"""

from datetime import datetime
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class MarketDataPayload(BaseModel):
    """Payload de dados brutos coletados pelo DataCollectorAgent."""
    symbol: str = Field(description="Símbolo do ativo ou par de moedas (ex: AAPL, USD/BRL)")
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    price_history: List[float] = Field(description="Série histórica de preços")
    volume: Optional[List[float]] = Field(default=None, description="Série de volume negociado")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadados da fonte e coleta")


class QuantAnalysisMetrics(BaseModel):
    """Métricas determinísticas calculadas pelo QuantAnalystAgent."""
    symbol: str = Field(description="Símbolo do ativo analisado")
    moving_average: List[float] = Field(default_factory=list, description="Média móvel calculada via Pandas")
    volatility: float = Field(default=0.0, description="Volatilidade percentual")
    mean_price: float = Field(default=0.0, description="Preço médio da série")
    max_price: float = Field(default=0.0, description="Preço máximo")
    min_price: float = Field(default=0.0, description="Preço mínimo")
    std_dev: float = Field(default=0.0, description="Desvio padrão")
    warnings: List[str] = Field(default_factory=list, description="Alertas (ex: NaNs sanitizados, dados insuficientes)")
    error_code: Optional[str] = Field(default=None, description="Código de erro se houver falha (ex: INSUFFICIENT_DATA_POINTS)")


class AgentState(BaseModel):
    """Estado global compartilhado no orquestrador multiagente (LangGraph / CrewAI)."""
    input_params: Dict[str, Any] = Field(default_factory=dict, description="Parâmetros de entrada")
    raw_data: Optional[MarketDataPayload] = Field(default=None, description="Dados brutos coletados")
    quant_analysis: Optional[QuantAnalysisMetrics] = Field(default=None, description="Resultados quantitativos")
    final_report: Optional[str] = Field(default=None, description="Texto final do relatório em Markdown")
    error_state: Optional[str] = Field(default=None, description="Mensagem ou código de erro se houver falha")
    iteration_count: int = Field(default=0, description="Contador de iterações do orquestrador")
