"""
Interfaces de repositório do domínio (D-01).

O domínio define os contratos (ABCs/Protocols) que a infraestrutura deve implementar.
NENHUM tipo de driver (psycopg, asyncpg, SQLAlchemy) pode aparecer aqui.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

# ============================================================================
# Protocolo de conexão abstrato (sem dependência de driver)
# ============================================================================

class DomainConnection(Protocol):
    """Protocolo de conexão abstrato para o domínio. Implementado pela infraestrutura."""
    def cursor(self, *, row_factory: Any = None) -> Any: ...
    def commit(self) -> None: ...
    def rollback(self) -> None: ...
    def close(self) -> None: ...


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
# Repository Interfaces (Protocolos/ABCs) - CONTRATOS DO DOMÍNIO
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
        **extra_fields: object,
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
# Factory protocol para injeção de dependência
# ============================================================================

@dataclass
class Repositories:
    tasks: TasksRepo
    market: MarketRepo
    quant: QuantRepo
    published: PublishedRepo
    events: EventsRepo
    idempotency: IdempotencyRepo
