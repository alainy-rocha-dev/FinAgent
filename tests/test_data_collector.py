"""
Testes unitários para o DataCollectorAgent e a camada de ingestão de dados / mock fallback.
"""

import pytest
from sisanalisefinanceira.models import MarketDataPayload
from sisanalisefinanceira.agents.data_collector import DataCollectorAgent


@pytest.fixture
def collector():
    return DataCollectorAgent(use_mock=True)


def test_mock_fetch_known_symbol(collector):
    payload = collector.fetch_data("AAPL")
    assert payload.symbol == "AAPL"
    assert len(payload.price_history) > 0
    assert payload.metadata["status"] == "success"
    assert payload.metadata["source"] == "mock_fallback"


def test_mock_fetch_invalid_symbol(collector):
    payload = collector.fetch_data("")
    assert payload.metadata["error_code"] == "INVALID_SYMBOL"
    assert len(payload.price_history) == 0


def test_mock_fetch_unknown_symbol_uses_default(collector):
    payload = collector.fetch_data("UNKNOWN_TICKER")
    assert payload.symbol == "UNKNOWN_TICKER"
    assert len(payload.price_history) > 0
    assert payload.metadata["source"] == "mock_fallback"


def test_mock_fallback_includes_fallback_reason(collector):
    payload = collector.fetch_data("AAPL")
    assert "fallback_reason" not in payload.metadata or payload.metadata.get("fallback_reason") is None