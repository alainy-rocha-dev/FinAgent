"""
Pools de conexão da infraestrutura AgentPulse.

Separação por papel de processo (D-01, D-02, D-03):
- API (assíncrona): SQLAlchemy async + asyncpg
- Worker (prefork, síncrono): dois pools psycopg + conexão dedicada para lock
  - domain_pool: transacional (market_payloads, published, tasks, task_events)
  - checkpoint_pool: autocommit + dict_row (exigido pelo PostgresSaver do LangGraph)
  - lock_conn: conexão dedicada para advisory lock por task_id

Pools criados em worker_process_init / fechados em worker_process_shutdown (pós-fork).
NUNCA no import do módulo.
"""

from __future__ import annotations

import atexit
import hashlib
import logging
import threading
import uuid
from collections.abc import AsyncGenerator, Generator
from contextlib import asynccontextmanager, contextmanager
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import psycopg
    from psycopg_pool import ConnectionPool as PsycopgPool

# async_sessionmaker added in SQLAlchemy 2.0; types stubs may lag
from sqlalchemy.ext.asyncio import (  # type: ignore[attr-defined]
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.infra.config import get_config

logger = logging.getLogger(__name__)

# Estado global dos pools (setado em worker_process_init / startup da API)
_async_engine: AsyncEngine | None = None
_async_session_factory: async_sessionmaker[AsyncSession] | None = None

_domain_pool: PsycopgPool | None = None
_checkpoint_pool: PsycopgPool | None = None
_lock_conn: psycopg.Connection | None = None

_pool_lock = threading.Lock()
_initialized = False


def _get_psycopg() -> Any:
    import psycopg
    return psycopg


def _get_dict_row() -> Any:
    from psycopg.rows import dict_row
    return dict_row


def _get_pool() -> Any:
    from psycopg_pool import ConnectionPool as PsycopgPool
    return PsycopgPool


def _advisory_lock_keys(task_id: str) -> tuple[int, int]:
    """
    Gera duas chaves int64 determinísticas a partir do task_id (UUID).
    Usa os bits do UUID (uuid.int) em vez de hash() do Python,
    pois hash() é randomizado por processo (PYTHONHASHSEED).
    """
    try:
        # Se task_id é UUID válido, usa seus bits diretamente
        u = uuid.UUID(task_id)
        uuid_int = u.int
    except ValueError:
        # Fallback: hashlib sha256 determinístico
        h = hashlib.sha256(task_id.encode()).digest()
        uuid_int = int.from_bytes(h, "big")

    # Split em dois int64 (31 bits cada, sinal positivo)
    key1 = uuid_int & 0x7FFFFFFF
    key2 = (uuid_int >> 31) & 0x7FFFFFFF
    return key1, key2


def _build_dsn() -> str:
    """Constrói DSN a partir da configuração."""
    cfg = get_config()
    return cfg.database_url


def init_api_pools() -> None:
    """Inicializa pools da API (assíncrona). Chamado no startup do FastAPI."""
    global _async_engine, _async_session_factory
    dsn = _build_dsn()
    # Converte para asyncpg DSN se necessário
    async_dsn = dsn.replace("postgresql://", "postgresql+asyncpg://")
    _async_engine = create_async_engine(
        async_dsn,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        echo=False,
    )
    _async_session_factory = async_sessionmaker(
        _async_engine, class_=AsyncSession, expire_on_commit=False
    )
    logger.info("API pools initialized (asyncpg)")


async def close_api_pools() -> None:
    """Fecha pools da API. Chamado no shutdown do FastAPI."""
    global _async_engine, _async_session_factory
    if _async_engine:
        await _async_engine.dispose()
        _async_engine = None
        _async_session_factory = None
        logger.info("API pools closed")


@asynccontextmanager
async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Obtém sessão assíncrona para operações da API."""
    if _async_session_factory is None:
        raise RuntimeError("API pools not initialized. Call init_api_pools() first.")
    async with _async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def init_worker_pools(
    domain_pool_size: int = 5,
    checkpoint_pool_size: int = 3,
) -> None:
    """
    Inicializa pools do worker (pós-fork).
    Chamado via sinal worker_process_init do Celery.
    """
    global _domain_pool, _checkpoint_pool, _lock_conn, _initialized
    with _pool_lock:
        if _initialized:
            return
        dsn = _build_dsn()

        PsycopgPool = _get_pool()
        dict_row = _get_dict_row()
        psycopg = _get_psycopg()

        # domain_pool: transacional, para machine, market_payloads, published, events
        _domain_pool = PsycopgPool(
            min_size=1,
            max_size=domain_pool_size,
            conninfo=dsn,
            autocommit=False,
        )

        # checkpoint_pool: autocommit + dict_row (exigido pelo PostgresSaver)
        _checkpoint_pool = PsycopgPool(
            min_size=1,
            max_size=checkpoint_pool_size,
            conninfo=dsn,
            autocommit=True,
            kwargs={"row_factory": dict_row},
        )

        # lock_conn: conexão dedicada para advisory lock por task_id
        _lock_conn = psycopg.connect(dsn, autocommit=True)
        _lock_conn.execute("SET LOCAL statement_timeout = '30s'")

        _initialized = True
        logger.info(
            "Worker pools initialized: domain_pool=%d, checkpoint_pool=%d, lock_conn=1",
            domain_pool_size,
            checkpoint_pool_size,
        )


def close_worker_pools() -> None:
    """Fecha pools do worker. Chamado via sinal worker_process_shutdown do Celery."""
    global _domain_pool, _checkpoint_pool, _lock_conn, _initialized
    with _pool_lock:
        if _domain_pool:
            _domain_pool.close()
            _domain_pool = None
        if _checkpoint_pool:
            _checkpoint_pool.close()
            _checkpoint_pool = None
        if _lock_conn:
            _lock_conn.close()
            _lock_conn = None
        _initialized = False
        logger.info("Worker pools closed")


@contextmanager
def get_domain_connection() -> Generator[psycopg.Connection, None, None]:
    """Obtém conexão do domain_pool (transacional)."""
    if _domain_pool is None:
        raise RuntimeError("Worker pools not initialized. Call init_worker_pools() first.")
    conn = _domain_pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        _domain_pool.putconn(conn)


@contextmanager
def get_checkpoint_connection() -> Generator[psycopg.Connection, None, None]:
    """Obtém conexão do checkpoint_pool (autocommit + dict_row)."""
    if _checkpoint_pool is None:
        raise RuntimeError("Worker pools not initialized. Call init_worker_pools() first.")
    conn = _checkpoint_pool.getconn()
    try:
        yield conn
    finally:
        _checkpoint_pool.putconn(conn)


def get_lock_connection() -> psycopg.Connection:
    """
    Retorna a conexão dedicada para advisory lock.
    O caller NÃO deve fechar esta conexão; ela vive durante todo o worker.
    """
    if _lock_conn is None:
        raise RuntimeError("Worker pools not initialized. Call init_worker_pools() first.")
    return _lock_conn


def acquire_advisory_lock(task_id: str, lock_conn: psycopg.Connection) -> bool:
    """
    Adquire advisory lock de sessão para task_id.
    Retorna True se adquirido, False se já detido por outra sessão.
    """
    # PostgreSQL advisory lock usa dois int64; usamos bits do UUID (determinístico)
    lock_key_1, lock_key_2 = _advisory_lock_keys(task_id)
    with lock_conn.cursor() as cur:
        cur.execute("SELECT pg_try_advisory_lock(%s, %s)", (lock_key_1, lock_key_2))
        result = cur.fetchone()
        return bool(result[0]) if result else False


def release_advisory_lock(task_id: str, lock_conn: psycopg.Connection) -> None:
    """Libera advisory lock para task_id."""
    lock_key_1, lock_key_2 = _advisory_lock_keys(task_id)
    with lock_conn.cursor() as cur:
        cur.execute("SELECT pg_advisory_unlock(%s, %s)", (lock_key_1, lock_key_2))


# Registro de cleanup automático (fallback)
atexit.register(close_worker_pools)
atexit.register(lambda: None)  # placeholder para close_api_pools (async)
