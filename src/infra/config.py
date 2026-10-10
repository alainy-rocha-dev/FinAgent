"""
Configuração centralizada - carrega config/defaults.yaml + variáveis de ambiente.

28 parâmetros "a medir" (D-17).
Variáveis de ambiente (.env) sobrescrevem valores do YAML.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any

import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict


@dataclass
class StaleConfig:
    equity: int = 5
    fx: int = 3
    crypto: int = 1
    other: int = 5


@dataclass
class RateLimitConfig:
    tasks_post: int = 10
    tasks_get: int = 30
    approve_reject: int = 20


@dataclass
class Config:
    # Aprovação
    approval_ttl_hours: int = 168

    # Orçamento
    monthly_token_budget: int = 1_000_000
    token_budget_per_task: int = 50_000

    # Reaper
    max_reaper_attempts: int = 3

    # Auditoria numérica
    isclose_rel_tol: float = 1e-9
    isclose_abs_tol: float = 1e-12

    # Retenção
    retention_days: int = 365

    # Data quality
    stale_max_age_days: StaleConfig = StaleConfig()

    # Rejeição
    reject_reason_min_chars: int = 10
    reject_reason_max_chars: int = 1000

    # Rate limiting
    rate_limit: RateLimitConfig = RateLimitConfig()

    # Worker / Celery
    task_time_limit: int = 600
    retry_backoff_max: int = 60
    max_retries: int = 3
    heartbeat_interval: int = 15
    visibility_timeout: int = 900
    visibility_timeout_chaos: int = 30

    # Testes / auditoria
    mutations_per_class: int = 30
    clean_reports_for_fp: int = 50

    # Cobertura
    coverage_min: int = 85

    # Observabilidade
    sampler_rate_prod: float = 0.1
    alert_failure_rate_pct: int = 5
    alert_queue_pending: int = 100
    alert_worker_offline_min: int = 2

    # Banco de dados (obrigatório via env)
    database_url: str = ""

    # App
    app_env: str = "dev"
    allow_simulated_publication: bool = False

    # OpenAI / LLM (opcional)
    openai_api_key: str = ""
    anthropic_api_key: str = ""

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Versões fixadas (metadados)
    versions: dict = None  # type: ignore

    def __post_init__(self) -> None:
        if self.versions is None:
            self.versions = {}

    def validate(self) -> list[str]:
        """Valida configuração e retorna lista de erros (vazio = OK)."""
        errors = []

        if not self.database_url:
            errors.append("DATABASE_URL é obrigatório (defina no .env)")

        if self.app_env == "prod" and self.allow_simulated_publication:
            errors.append("APP_ENV=prod não permite ALLOW_SIMULATED_PUBLICATION=true")

        if self.coverage_min < 0 or self.coverage_min > 100:
            errors.append("coverage_min deve estar entre 0 e 100")

        if self.mutations_per_class <= 0:
            errors.append("mutations_per_class deve ser > 0")

        if self.clean_reports_for_fp <= 0:
            errors.append("clean_reports_for_fp deve ser > 0")

        # Valida stale config
        for asset_class, days in [
            ("equity", self.stale_max_age_days.equity),
            ("fx", self.stale_max_age_days.fx),
            ("crypto", self.stale_max_age_days.crypto),
            ("other", self.stale_max_age_days.other),
        ]:
            if days <= 0:
                errors.append(f"stale_max_age_days.{asset_class} deve ser > 0")

        return errors

    def param_count(self) -> int:
        """Conta parâmetros 'a medir' (exclui metadados e secrets)."""
        count = 0
        for field in fields(self):
            if field.name in ("database_url", "app_env", "allow_simulated_publication",
                              "openai_api_key", "anthropic_api_key", "redis_url", "versions"):
                continue
            if field.name == "stale_max_age_days":
                count += 4  # equity, fx, crypto, other
            elif field.name == "rate_limit":
                count += 3  # tasks_post, tasks_get, approve_reject
            else:
                count += 1
        return count


class Settings(BaseSettings):
    """Configuração via variáveis de ambiente (pydantic-settings)."""
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Aprovação
    APPROVAL_TTL_HOURS: int | None = None

    # Orçamento
    MONTHLY_TOKEN_BUDGET: int | None = None
    TOKEN_BUDGET_PER_TASK: int | None = None

    # Reaper
    MAX_REAPER_ATTEMPTS: int | None = None

    # Auditoria
    ISCLOSE_REL_TOL: float | None = None
    ISCLOSE_ABS_TOL: float | None = None

    # Retenção
    RETENTION_DAYS: int | None = None

    # Data quality
    STALE_MAX_AGE_EQUITY: int | None = None
    STALE_MAX_AGE_FX: int | None = None
    STALE_MAX_AGE_CRYPTO: int | None = None
    STALE_MAX_AGE_OTHER: int | None = None

    # Rejeição
    REJECT_REASON_MIN_CHARS: int | None = None
    REJECT_REASON_MAX_CHARS: int | None = None

    # Rate limit
    RATE_LIMIT_TASKS_POST: int | None = None
    RATE_LIMIT_TASKS_GET: int | None = None
    RATE_LIMIT_APPROVE_REJECT: int | None = None

    # Worker
    TASK_TIME_LIMIT: int | None = None
    RETRY_BACKOFF_MAX: int | None = None
    MAX_RETRIES: int | None = None
    HEARTBEAT_INTERVAL: int | None = None
    VISIBILITY_TIMEOUT: int | None = None
    VISIBILITY_TIMEOUT_CHAOS: int | None = None

    # Testes
    MUTATIONS_PER_CLASS: int | None = None
    CLEAN_REPORTS_FOR_FP: int | None = None

    # Cobertura
    COVERAGE_MIN: int | None = None

    # Observabilidade
    SAMPLER_RATE_PROD: float | None = None
    ALERT_FAILURE_RATE_PCT: int | None = None
    ALERT_QUEUE_PENDING: int | None = None
    ALERT_WORKER_OFFLINE_MIN: int | None = None

    # Obrigatórios
    DATABASE_URL: str = ""
    APP_ENV: str = "dev"
    ALLOW_SIMULATED_PUBLICATION: bool = False
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    REDIS_URL: str = "redis://localhost:6379/0"


_config_instance: Config | None = None


def load_config(config_path: str | None = None) -> Config:
    """
    Carrega configuração: defaults.yaml + .env (env vars sobrescrevem YAML).
    Deve ser chamado uma vez no startup.
    """
    global _config_instance

    if _config_instance is not None:
        return _config_instance

    # 1. Carrega YAML
    if config_path is None:
        config_path = str(Path(__file__).parent.parent.parent / "config" / "defaults.yaml")

    with open(config_path, encoding="utf-8") as f:
        yaml_data = yaml.safe_load(f) or {}

    # 2. Carrega env vars
    settings = Settings()

    # 3. Merge: YAML -> env vars (env vence)
    def get_env(key: str, default: Any) -> Any:
        value = getattr(settings, key, None)
        return value if value is not None else default

    stale = StaleConfig(
        equity=get_env("STALE_MAX_AGE_EQUITY", yaml_data.get("stale_max_age_days", {}).get("equity", 5)),
        fx=get_env("STALE_MAX_AGE_FX", yaml_data.get("stale_max_age_days", {}).get("fx", 3)),
        crypto=get_env("STALE_MAX_AGE_CRYPTO", yaml_data.get("stale_max_age_days", {}).get("crypto", 1)),
        other=get_env("STALE_MAX_AGE_OTHER", yaml_data.get("stale_max_age_days", {}).get("other", 5)),
    )

    rate_limit = RateLimitConfig(
        tasks_post=get_env("RATE_LIMIT_TASKS_POST", yaml_data.get("rate_limit", {}).get("tasks_post", 10)),
        tasks_get=get_env("RATE_LIMIT_TASKS_GET", yaml_data.get("rate_limit", {}).get("tasks_get", 30)),
        approve_reject=get_env("RATE_LIMIT_APPROVE_REJECT", yaml_data.get("rate_limit", {}).get("approve_reject", 20)),
    )

    # Extrai versões do YAML (comentários no final do arquivo)
    versions = {}
    for key, value in yaml_data.items():
        if key.endswith("_version") or key in ("Celery", "Redis", "LangGraph", "Postgres"):
            versions[key] = value

    _config_instance = Config(
        approval_ttl_hours=get_env("APPROVAL_TTL_HOURS", yaml_data.get("approval_ttl_hours", 168)),
        monthly_token_budget=get_env("MONTHLY_TOKEN_BUDGET", yaml_data.get("monthly_token_budget", 1_000_000)),
        token_budget_per_task=get_env("TOKEN_BUDGET_PER_TASK", yaml_data.get("token_budget_per_task", 50_000)),
        max_reaper_attempts=get_env("MAX_REAPER_ATTEMPTS", yaml_data.get("max_reaper_attempts", 3)),
        isclose_rel_tol=get_env("ISCLOSE_REL_TOL", yaml_data.get("isclose_rel_tol", 1e-9)),
        isclose_abs_tol=get_env("ISCLOSE_ABS_TOL", yaml_data.get("isclose_abs_tol", 1e-12)),
        retention_days=get_env("RETENTION_DAYS", yaml_data.get("retention_days", 365)),
        stale_max_age_days=stale,
        reject_reason_min_chars=get_env("REJECT_REASON_MIN_CHARS", yaml_data.get("reject_reason_min_chars", 10)),
        reject_reason_max_chars=get_env("REJECT_REASON_MAX_CHARS", yaml_data.get("reject_reason_max_chars", 1000)),
        rate_limit=rate_limit,
        task_time_limit=get_env("TASK_TIME_LIMIT", yaml_data.get("task_time_limit", 600)),
        retry_backoff_max=get_env("RETRY_BACKOFF_MAX", yaml_data.get("retry_backoff_max", 60)),
        max_retries=get_env("MAX_RETRIES", yaml_data.get("max_retries", 3)),
        heartbeat_interval=get_env("HEARTBEAT_INTERVAL", yaml_data.get("heartbeat_interval", 15)),
        visibility_timeout=get_env("VISIBILITY_TIMEOUT", yaml_data.get("visibility_timeout", 900)),
        visibility_timeout_chaos=get_env("VISIBILITY_TIMEOUT_CHAOS", yaml_data.get("visibility_timeout_chaos", 30)),
        mutations_per_class=get_env("MUTATIONS_PER_CLASS", yaml_data.get("mutations_per_class", 30)),
        clean_reports_for_fp=get_env("CLEAN_REPORTS_FOR_FP", yaml_data.get("clean_reports_for_fp", 50)),
        coverage_min=get_env("COVERAGE_MIN", yaml_data.get("coverage_min", 85)),
        sampler_rate_prod=get_env("SAMPLER_RATE_PROD", yaml_data.get("sampler_rate_prod", 0.1)),
        alert_failure_rate_pct=get_env("ALERT_FAILURE_RATE_PCT", yaml_data.get("alert_failure_rate_pct", 5)),
        alert_queue_pending=get_env("ALERT_QUEUE_PENDING", yaml_data.get("alert_queue_pending", 100)),
        alert_worker_offline_min=get_env("ALERT_WORKER_OFFLINE_MIN", yaml_data.get("alert_worker_offline_min", 2)),
        database_url=settings.DATABASE_URL,
        app_env=settings.APP_ENV,
        allow_simulated_publication=settings.ALLOW_SIMULATED_PUBLICATION,
        openai_api_key=settings.OPENAI_API_KEY,
        anthropic_api_key=settings.ANTHROPIC_API_KEY,
        redis_url=settings.REDIS_URL,
        versions=versions,
    )

    # Valida
    errors = _config_instance.validate()
    if errors:
        raise ValueError(f"Configuração inválida: {'; '.join(errors)}")

    return _config_instance


def get_config() -> Config:
    """Retorna instância já carregada (deve chamar load_config() antes)."""
    if _config_instance is None:
        return load_config()
    return _config_instance


def reset_config() -> None:
    """Útil para testes."""
    global _config_instance
    _config_instance = None
