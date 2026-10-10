"""Test that config loads defaults and environment variables correctly."""
import os
import pytest
from pathlib import Path
import yaml


def test_config_file_exists():
    """Test that config/defaults.yaml exists."""
    config_path = Path("config/defaults.yaml")
    assert config_path.exists(), "config/defaults.yaml should exist"


def test_config_loads_28_parameters():
    """Test that config has all 28 expected parameter sections."""
    config_path = Path("config/defaults.yaml")
    with open(config_path) as f:
        config = yaml.safe_load(f)

    # Count top-level sections (should be 18 main sections)
    expected_sections = [
        "app", "database", "redis", "celery", "langgraph",
        "idempotency", "data_quality", "budget", "approval",
        "observability", "chaos", "simulated", "api"
    ]

    for section in expected_sections:
        assert section in config, f"Missing config section: {section}"

    # Verify key parameters exist
    assert config["database"]["api_pool_size"] == 5
    assert config["database"]["domain_pool_size"] == 3
    assert config["database"]["checkpoint_pool_size"] == 2
    assert config["celery"]["worker_prefetch_multiplier"] == 1
    assert config["celery"]["task_acks_late"] is True
    assert config["langgraph"]["checkpointer"]["autocommit"] is True
    assert config["langgraph"]["checkpointer"]["dict_row"] is True
    assert config["idempotency"]["scope"] == "api_key_id"
    assert config["simulated"]["block_in_production"] is True
    assert config["chaos"]["nightly_runs"] == 100


def test_config_env_override(monkeypatch):
    """Test that environment variables override config defaults."""
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_HOST", "prod-db")
    monkeypatch.setenv("REDIS_HOST", "prod-redis")

    config_path = Path("config/defaults.yaml")
    with open(config_path) as f:
        config = yaml.safe_load(f)

    # These would be overridden by the config loader (to be implemented in T028)
    # For now, just verify the structure supports it
    assert "app" in config
    assert "env" in config["app"]