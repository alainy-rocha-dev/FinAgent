"""
Testes unitários para o QuantAnalystAgent e suas ferramentas numéricas determinísticas.
"""

import pytest
from sisanalisefinanceira.models import MarketDataPayload
from sisanalisefinanceira.agents.quant_analyst import QuantAnalystAgent, calculate_moving_average_tool


def test_acceptance_moving_average():
    prices = [10.0, 12.0, 14.0, 16.0]
    ma = calculate_moving_average_tool(prices, window=2)
    assert ma == [11.0, 13.0, 15.0]


def test_quant_metrics_calculation():
    agent = QuantAnalystAgent(window=2)
    payload = MarketDataPayload(
        symbol="TEST",
        price_history=[10.0, 20.0, 30.0]
    )
    metrics = agent.analyze(payload)
    assert metrics.symbol == "TEST"
    assert metrics.mean_price == 20.0
    assert metrics.min_price == 10.0
    assert metrics.max_price == 30.0
    assert metrics.moving_average == [15.0, 25.0]
    assert metrics.error_code is None


def test_insufficient_data_points():
    agent = QuantAnalystAgent(window=5)
    payload = MarketDataPayload(
        symbol="SHORT",
        price_history=[10.0]
    )
    metrics = agent.analyze(payload)
    assert metrics.error_code == "INSUFFICIENT_DATA_POINTS"


def test_quant_handles_nan_values():
    agent = QuantAnalystAgent(window=2)
    payload = MarketDataPayload(
        symbol="TEST",
        price_history=[10.0, float('nan'), 20.0, 30.0]
    )
    metrics = agent.analyze(payload)
    assert metrics.error_code is None
    assert metrics.mean_price == 20.0  # (10 + 20 + 30) / 3


def test_moving_average_empty_series():
    ma = calculate_moving_average_tool([], window=2)
    assert ma == []


def test_moving_average_window_larger_than_series():
    ma = calculate_moving_average_tool([10.0, 20.0], window=5)
    assert ma == []