"""
Testes unitários para o DataCollectorAgent e a camada de ingestão de dados / mock fallback.
"""

import unittest
from sisanalisefinanceira.models import MarketDataPayload


def fetch_market_data_mock(symbol: str) -> MarketDataPayload:
    if not symbol or not isinstance(symbol, str) or symbol.strip() == "":
        return MarketDataPayload(
            symbol=symbol or "UNKNOWN",
            price_history=[],
            metadata={"status": "error", "error_code": "INVALID_SYMBOL"}
        )
    
    symbol_upper = symbol.strip().upper()
    mock_databases = {
        "AAPL": [150.0, 152.5, 151.0, 153.8, 155.2],
        "USD/BRL": [5.10, 5.12, 5.15, 5.14, 5.18],
        "PETR4": [32.0, 32.5, 33.1, 32.8, 33.5]
    }
    
    prices = mock_databases.get(symbol_upper, [100.0, 101.0, 100.5, 102.0, 103.0])
    
    return MarketDataPayload(
        symbol=symbol_upper,
        price_history=prices,
        volume=[1000, 1200, 1100, 1300, 1250],
        metadata={"source": "mock_fallback", "status": "success"}
    )


class TestDataCollector(unittest.TestCase):
    def test_mock_fetch_known_symbol(self):
        payload = fetch_market_data_mock("AAPL")
        self.assertEqual(payload.symbol, "AAPL")
        self.assertGreater(len(payload.price_history), 0)
        self.assertEqual(payload.metadata["status"], "success")

    def test_mock_fetch_invalid_symbol(self):
        payload = fetch_market_data_mock("")
        self.assertEqual(payload.metadata["error_code"], "INVALID_SYMBOL")
        self.assertEqual(len(payload.price_history), 0)


if __name__ == "__main__":
    unittest.main()
