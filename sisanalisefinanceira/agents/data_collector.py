"""
Componente DataCollectorAgent: Coleta e padronização de dados de mercado.
"""

import logging
from datetime import datetime
from typing import Optional

from sisanalisefinanceira.config import settings
from sisanalisefinanceira.models import MarketDataPayload

logger = logging.getLogger(__name__)


class DataCollectorAgent:
    """Agente Coletor de Dados de Mercado (APIs, Scraping e Mock Fallback)."""

    def __init__(self, use_mock: Optional[bool] = None):
        self.use_mock = settings.use_mock_fallback if use_mock is None else use_mock

    def fetch_data(self, symbol: str) -> MarketDataPayload:
        """Coleta dados brutos de mercado para o símbolo fornecido."""
        if not symbol or not symbol.strip():
            logger.warning("Símbolo inválido fornecido ao DataCollectorAgent.")
            return MarketDataPayload(
                symbol=symbol or "UNKNOWN",
                price_history=[],
                metadata={"status": "error", "error_code": "INVALID_SYMBOL"}
            )
        
        symbol_clean = symbol.strip().upper()

        if self.use_mock:
            return self._fetch_mock(symbol_clean)

        try:
            return self._fetch_web_or_api(symbol_clean)
        except Exception as e:
            logger.error(f"Falha na coleta online para {symbol_clean}: {e}. Ativando mock fallback.")
            return self._fetch_mock(symbol_clean, fallback_reason=str(e))

    def _fetch_mock(self, symbol: str, fallback_reason: Optional[str] = None) -> MarketDataPayload:
        """Gera dados mock simulados e validados."""
        mock_db = {
            "AAPL": [150.0, 152.5, 151.0, 153.8, 155.2, 154.0, 156.5],
            "USD/BRL": [5.10, 5.12, 5.15, 5.14, 5.18, 5.20, 5.17],
            "PETR4": [32.0, 32.5, 33.1, 32.8, 33.5, 34.0, 33.8],
            "VALE3": [60.0, 61.2, 60.8, 62.0, 61.5, 63.0, 62.4]
        }
        
        prices = mock_db.get(symbol, [100.0, 101.5, 100.8, 102.3, 103.0, 102.5, 104.0])
        volumes = [10000 + i * 500 for i in range(len(prices))]

        meta = {
            "source": "mock_fallback",
            "status": "success",
            "fetched_at": datetime.utcnow().isoformat()
        }
        if fallback_reason:
            meta["fallback_reason"] = fallback_reason

        return MarketDataPayload(
            symbol=symbol,
            price_history=prices,
            volume=volumes,
            metadata=meta
        )

    def _fetch_web_or_api(self, symbol: str) -> MarketDataPayload:
        """Tentativa de scraping/API simples."""
        try:
            import requests
        except ImportError:
            raise RuntimeError("Biblioteca 'requests' não encontrada para requisições online.")

        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        headers = {"User-Agent": "Mozilla/5.0"}
        
        response = requests.get(url, headers=headers, timeout=5)
        response.raise_for_status()
        
        data = response.json()
        result = data["chart"]["result"][0]
        quotes = result["indicators"]["quote"][0]
        close_prices = [p for p in quotes["close"] if p is not None]

        if not close_prices:
            raise ValueError("Nenhum preço de fechamento encontrado")

        return MarketDataPayload(
            symbol=symbol,
            price_history=[round(float(p), 4) for p in close_prices[-10:]],
            metadata={"source": "yahoo_finance_api", "status": "success"}
        )
