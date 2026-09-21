"""
Testes unitários para o QuantAnalystAgent e suas ferramentas numéricas determinísticas.
"""

import unittest
from sisanalisefinanceira.models import MarketDataPayload, QuantAnalysisMetrics
from sisanalisefinanceira.agents.quant_analyst import QuantAnalystAgent, calculate_moving_average_tool


class TestQuantAnalyst(unittest.TestCase):
    def test_acceptance_moving_average(self):
        prices = [10.0, 12.0, 14.0, 16.0]
        ma = calculate_moving_average_tool(prices, window=2)
        self.assertEqual(ma, [11.0, 13.0, 15.0])

    def test_quant_metrics_calculation(self):
        agent = QuantAnalystAgent(window=2)
        payload = MarketDataPayload(
            symbol="TEST",
            price_history=[10.0, 20.0, 30.0]
        )
        metrics = agent.analyze(payload)
        self.assertEqual(metrics.symbol, "TEST")
        self.assertEqual(metrics.mean_price, 20.0)
        self.assertEqual(metrics.min_price, 10.0)
        self.assertEqual(metrics.max_price, 30.0)
        self.assertEqual(metrics.moving_average, [15.0, 25.0])
        self.assertIsNone(metrics.error_code)

    def test_insufficient_data_points(self):
        agent = QuantAnalystAgent(window=5)
        payload = MarketDataPayload(
            symbol="SHORT",
            price_history=[10.0]
        )
        metrics = agent.analyze(payload)
        self.assertEqual(metrics.error_code, "INSUFFICIENT_DATA_POINTS")


if __name__ == "__main__":
    unittest.main()
