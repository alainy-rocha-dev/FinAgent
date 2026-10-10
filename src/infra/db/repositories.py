"""
Repositórios injetados no código de domínio (D-01).

O domínio NÃO cria pools nem importa drivers.
Recebe repositórios por injeção de dependência.
"""

from __future__ import annotations

import json
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from psycopg.rows import dict_row

from src.infra.db.pools import get_domain_connection

# ============================================================================
# Domain Models (tipos que o domínio conhece)
# ============================================================================

@dataclass
class TaskRecord:
    task_id: uuid.UUID
    symbol: str
    asset_class: str
    status: str
    execution_id: str
    graph_version: str
    acknowledge_simulated: bool
    created_at: datetime
    updated_at: datetime
    approved_at: datetime | None
    heartbeat_at: datetime | None
    locked_by: str | None
    lease_until: datetime | None
    attempts: int
    reject_reason: str | None
    snapshot_hash: bytes | None


@dataclass
class MarketPayloadRecord:
    task_id: uuid.UUID
    symbol: str
    source: str
    payload_json: dict
    fetched_at: datetime
    data_quality: str


@dataclass
class QuantMetricsRecord:
    task_id: uuid.UUID
    symbol: str
    metrics_json: dict
    metrics_hash: bytes
    created_at: datetime


@dataclass
class PublishedRecord:
    task_id: uuid.UUID
    report_json: dict
    published_at: datetime
    published_by: uuid.UUID
    snapshot_hash: bytes


@dataclass
class IdempotencyKeyRecord:
    api_key_id: uuid.UUID
    key: str
    task_id: uuid.UUID
    payload_hash: bytes
    response_status: int
    response_body: dict
    created_at: datetime


# ============================================================================
# Repository Interfaces (Protocolos)
# ============================================================================

class TasksRepo(ABC):
    @abstractmethod
    def create(self, task: TaskRecord) -> None: ...

    @abstractmethod
    def get(self, task_id: uuid.UUID) -> TaskRecord | None: ...

    @abstractmethod
    def update_status(
        self,
        task_id: uuid.UUID,
        new_status: str,
        expected_status: str,
        **extra_fields,
    ) -> bool: ...

    @abstractmethod
    def update_heartbeat(self, task_id: uuid.UUID, worker_id: str) -> bool: ...


class MarketRepo(ABC):
    @abstractmethod
    def upsert(self, payload: MarketPayloadRecord) -> bool: ...

    @abstractmethod
    def get(self, task_id: uuid.UUID, symbol: str, source: str) -> MarketPayloadRecord | None: ...


class QuantRepo(ABC):
    @abstractmethod
    def upsert(self, metrics: QuantMetricsRecord) -> bool: ...

    @abstractmethod
    def get(self, task_id: uuid.UUID, symbol: str) -> QuantMetricsRecord | None: ...


class PublishedRepo(ABC):
    @abstractmethod
    def insert(self, published: PublishedRecord) -> bool: ...

    @abstractmethod
    def get(self, task_id: uuid.UUID) -> PublishedRecord | None: ...


class EventsRepo(ABC):
    @abstractmethod
    def append(
        self,
        task_id: uuid.UUID,
        event_type: str,
        payload: dict,
        actor_role: str,
        actor_id: str,
    ) -> None: ...


class IdempotencyRepo(ABC):
    @abstractmethod
    def get(self, api_key_id: uuid.UUID, key: str) -> IdempotencyKeyRecord | None: ...

    @abstractmethod
    def insert(self, record: IdempotencyKeyRecord) -> None: ...


# ============================================================================
# Implementações PostgreSQL
# ============================================================================

class PgTasksRepo(TasksRepo):
    def create(self, task: TaskRecord) -> None:
        with get_domain_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO tasks (
                        task_id, symbol, asset_class, status, execution_id, graph_version,
                        acknowledge_simulated, created_at, updated_at, approved_at,
                        heartbeat_at, locked_by, lease_until, attempts, reject_reason, snapshot_hash
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    """,
                    (
                        task.task_id,
                        task.symbol,
                        task.asset_class,
                        task.status,
                        task.execution_id,
                        task.graph_version,
                        task.acknowledge_simulated,
                        task.created_at,
                        task.updated_at,
                        task.approved_at,
                        task.heartbeat_at,
                        task.locked_by,
                        task.lease_until,
                        task.attempts,
                        task.reject_reason,
                        task.snapshot_hash,
                    ),
                )

    def get(self, task_id: uuid.UUID) -> TaskRecord | None:
        with get_domain_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute("SELECT * FROM tasks WHERE task_id = %s", (task_id,))
                row = cur.fetchone()
                if row:
                    return TaskRecord(**row)
                return None

    def update_status(
        self,
        task_id: uuid.UUID,
        new_status: str,
        expected_status: str,
        **extra_fields,
    ) -> bool:
        """Transição atômica: UPDATE ... WHERE status = expected_status."""
        set_clauses = ["status = %s", "updated_at = NOW()"]
        params = [new_status]

        for k, v in extra_fields.items():
            set_clauses.append(f"{k} = %s")
            params.append(v)

        params.append(task_id)
        params.append(expected_status)

        sql = f"UPDATE tasks SET {', '.join(set_clauses)} WHERE task_id = %s AND status = %s"
        with get_domain_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return cur.rowcount > 0

    def update_heartbeat(self, task_id: uuid.UUID, worker_id: str) -> bool:
        with get_domain_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE tasks
                    SET heartbeat_at = NOW(), locked_by = %s, lease_until = NOW() + INTERVAL '2 minutes'
                    WHERE task_id = %s AND status IN ('RUNNING', 'AWAITING_APPROVAL')
                    """,
                    (worker_id, task_id),
                )
                return cur.rowcount > 0


class PgMarketRepo(MarketRepo):
    def upsert(self, payload: MarketPayloadRecord) -> bool:
        """ON CONFLICT DO NOTHING garante idempotência por execução."""
        with get_domain_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO market_payloads (task_id, symbol, source, payload_jsonb, fetched_at, data_quality)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (task_id, symbol, source) DO NOTHING
                    """,
                    (
                        payload.task_id,
                        payload.symbol,
                        payload.source,
                        json.dumps(payload.payload_json),
                        payload.fetched_at,
                        payload.data_quality,
                    ),
                )
                return cur.rowcount > 0

    def get(self, task_id: uuid.UUID, symbol: str, source: str) -> MarketPayloadRecord | None:
        with get_domain_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    "SELECT * FROM market_payloads WHERE task_id = %s AND symbol = %s AND source = %s",
                    (task_id, symbol, source),
                )
                row = cur.fetchone()
                if row:
                    return MarketPayloadRecord(
                        task_id=row["task_id"],
                        symbol=row["symbol"],
                        source=row["source"],
                        payload_json=row["payload_jsonb"],
                        fetched_at=row["fetched_at"],
                        data_quality=row["data_quality"],
                    )
                return None


class PgQuantRepo(QuantRepo):
    def upsert(self, metrics: QuantMetricsRecord) -> bool:
        """ON CONFLICT DO NOTHING - métricas persistem para auditoria."""
        with get_domain_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO quant_metrics (task_id, symbol, metrics_json, hash, created_at)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (task_id, symbol) DO NOTHING
                    """,
                    (
                        metrics.task_id,
                        metrics.symbol,
                        json.dumps(metrics.metrics_json),
                        metrics.metrics_hash,
                        metrics.created_at,
                    ),
                )
                return cur.rowcount > 0

    def get(self, task_id: uuid.UUID, symbol: str) -> QuantMetricsRecord | None:
        with get_domain_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    "SELECT * FROM quant_metrics WHERE task_id = %s AND symbol = %s",
                    (task_id, symbol),
                )
                row = cur.fetchone()
                if row:
                    return QuantMetricsRecord(
                        task_id=row["task_id"],
                        symbol=row["symbol"],
                        metrics_json=row["metrics_json"],
                        metrics_hash=row["hash"],
                        created_at=row["created_at"],
                    )
                return None


class PgPublishedRepo(PublishedRepo):
    def insert(self, published: PublishedRecord) -> bool:
        """UNIQUE task_id garante exactly-once."""
        with get_domain_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO published (task_id, report_jsonb, published_at, published_by, snapshot_hash)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        published.task_id,
                        json.dumps(published.report_json),
                        published.published_at,
                        published.published_by,
                        published.snapshot_hash,
                    ),
                )
                return cur.rowcount > 0

    def get(self, task_id: uuid.UUID) -> PublishedRecord | None:
        with get_domain_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute("SELECT * FROM published WHERE task_id = %s", (task_id,))
                row = cur.fetchone()
                if row:
                    return PublishedRecord(
                        task_id=row["task_id"],
                        report_json=row["report_jsonb"],
                        published_at=row["published_at"],
                        published_by=row["published_by"],
                        snapshot_hash=row["snapshot_hash"],
                    )
                return None


class PgEventsRepo(EventsRepo):
    def append(
        self,
        task_id: uuid.UUID,
        event_type: str,
        payload: dict,
        actor_role: str,
        actor_id: str,
    ) -> None:
        with get_domain_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO task_events (task_id, event_type, payload_jsonb, actor_role, actor_id)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (task_id, event_type, json.dumps(payload), actor_role, actor_id),
                )


class PgIdempotencyRepo(IdempotencyRepo):
    def get(self, api_key_id: uuid.UUID, key: str) -> IdempotencyKeyRecord | None:
        with get_domain_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    "SELECT * FROM idempotency_keys WHERE api_key_id = %s AND key = %s",
                    (api_key_id, key),
                )
                row = cur.fetchone()
                if row:
                    return IdempotencyKeyRecord(
                        api_key_id=row["api_key_id"],
                        key=row["key"],
                        task_id=row["task_id"],
                        payload_hash=row["payload_hash"],
                        response_status=row["response_status"],
                        response_body=row["response_body"],
                        created_at=row["created_at"],
                    )
                return None

    def insert(self, record: IdempotencyKeyRecord) -> None:
        with get_domain_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO idempotency_keys (api_key_id, key, task_id, payload_hash, response_status, response_body, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        record.api_key_id,
                        record.key,
                        record.task_id,
                        record.payload_hash,
                        record.response_status,
                        json.dumps(record.response_body),
                        record.created_at,
                    ),
                )


# ============================================================================
# Factory para injeção de dependência
# ============================================================================

@dataclass
class Repositories:
    tasks: TasksRepo
    market: MarketRepo
    quant: QuantRepo
    published: PublishedRepo
    events: EventsRepo
    idempotency: IdempotencyRepo


def create_repositories() -> Repositories:
    """Factory que cria todas as implementações PostgreSQL."""
    return Repositories(
        tasks=PgTasksRepo(),
        market=PgMarketRepo(),
        quant=PgQuantRepo(),
        published=PgPublishedRepo(),
        events=PgEventsRepo(),
        idempotency=PgIdempotencyRepo(),
    )
