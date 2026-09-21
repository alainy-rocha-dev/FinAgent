"""
Componente QuantAnalystAgent: Cálculos estatísticos e otimização determinística (Pandas/NumPy/SciPy com fallback em Math pura).
"""

import math
import logging
from typing import List, Dict, Any, Optional

from sisanalisefinanceira.config import settings
from sisanalisefinanceira.models import MarketDataPayload, QuantAnalysisMetrics

logger = logging.getLogger(__name__)


def calculate_moving_average_tool(series: List[float], window: int = 2) -> List[float]:
    """Calcula média móvel simples (usa Pandas se disponível, senão Math pura)."""
    if not series or len(series) < window or window <= 0:
        return []
    
    try:
        import pandas as pd
        s = pd.Series(series)
        ma = s.rolling(window=window).mean().dropna().tolist()
        return [round(float(x), 4) for x in ma]
    except ImportError:
        ma = []
        for i in range(len(series) - window + 1):
            sub = series[i:i + window]
            avg = sum(sub) / float(window)
            ma.append(round(avg, 4))
        return ma


def calculate_volatility_tool(series: List[float]) -> float:
    """Calcula volatilidade percentual (desvio padrão / média)."""
    prices = [p for p in series if p is not None and not (isinstance(p, float) and math.isnan(p))]
    if len(prices) < 2:
        return 0.0
    
    try:
        import numpy as np
        mean_val = float(np.mean(prices))
        if mean_val == 0:
            return 0.0
        std_val = float(np.std(prices, ddof=1))
        return round(float((std_val / mean_val) * 100), 2)
    except ImportError:
        mean_val = sum(prices) / float(len(prices))
        if mean_val == 0:
            return 0.0
        variance = sum((x - mean_val) ** 2 for x in prices) / float(len(prices) - 1)
        std_val = math.sqrt(variance)
        return round((std_val / mean_val) * 100.0, 2)


def optimize_weights_tool(returns: List[List[float]]) -> List[float]:
    """Tool determinística: otimização de pesos de carteira."""
    if not returns or len(returns) == 0:
        return []
    n = len(returns)
    try:
        import numpy as np
        from scipy.optimize import minimize
        cov_matrix = np.cov(returns)

        def portfolio_variance(weights):
            return weights.T @ cov_matrix @ weights

        init_weights = np.ones(n) / n
        bounds = tuple((0, 1) for _ in range(n))
        constraints = ({'type': 'eq', 'fun': lambda w: np.sum(w) - 1})

        res = minimize(portfolio_variance, init_weights, method='SLSQP', bounds=bounds, constraints=constraints)
        if res.success:
            return [round(float(w), 4) for w in res.x]
    except ImportError:
        pass
    
    return [round(1.0 / n, 4) for _ in range(n)]


class QuantAnalystAgent:
    """Agente Analista Quantitativo determinístico (sem alucinações numéricas)."""

    def __init__(self, window: Optional[int] = None):
        self.window = window if window is not None else settings.default_moving_average_window

    def analyze(self, payload: MarketDataPayload) -> QuantAnalysisMetrics:
        """Executa análise quantitativa completa sobre o payload de dados brutos."""
        if not payload or not payload.price_history:
            return QuantAnalysisMetrics(
                symbol=payload.symbol if payload else "UNKNOWN",
                error_code="INSUFFICIENT_DATA_POINTS",
                warnings=["Nenhum dado historico recebido para analise."]
            )

        # Sanitização de NaNs / Nulos
        raw_prices = payload.price_history
        clean_prices = [
            float(p) for p in raw_prices 
            if p is not None and not (isinstance(p, float) and math.isnan(p))
        ]
        warnings = []

        if len(clean_prices) < len(raw_prices):
            warnings.append("Valores nulos ou NaN foram descartados da serie.")

        if len(clean_prices) < self.window:
            return QuantAnalysisMetrics(
                symbol=payload.symbol,
                warnings=warnings,
                error_code="INSUFFICIENT_DATA_POINTS"
            )

        moving_avg = calculate_moving_average_tool(clean_prices, window=self.window)
        volatility = calculate_volatility_tool(clean_prices)
        
        mean_p = sum(clean_prices) / float(len(clean_prices))
        max_p = max(clean_prices)
        min_p = min(clean_prices)
        
        if len(clean_prices) > 1:
            variance = sum((x - mean_p) ** 2 for x in clean_prices) / float(len(clean_prices) - 1)
            std_p = math.sqrt(variance)
        else:
            std_p = 0.0

        return QuantAnalysisMetrics(
            symbol=payload.symbol,
            moving_average=moving_avg,
            volatility=volatility,
            mean_price=round(mean_p, 4),
            max_price=round(max_p, 4),
            min_price=round(min_p, 4),
            std_dev=round(std_p, 4),
            warnings=warnings,
            error_code=None
        )
