"""
Pools de conexão da infraestrutura AgentPulse.

Separação por papel de processo (D-01, D-02, D-03):
- API (assíncrona): SQLAlchemy async + asyncpg
- Worker (prefork, síncrono): dois pools psycopg + conexão dedicada para lock
  - domain_pool: transacional (market_payloads, published, tasks, task_events)
  - checkpoint_pool: autocommit + dict_row (exigido pelo PostgresSaver do LangGraph)
  - lock_conn: conexão dedicada para advisory lock por task_id

Fórmula de dimensionamento (D-04):
- domain_pool_size = num_workers * conexoes_por_worker + margem
- checkpoint_pool_size = num_workers + 1
- lock_conn = 1 (dedicada, não conta no pool)

Exemplo: 4 workers, 2 conexões/worker, margem 2
- domain_pool_size = 4 * 2 + 2 = 10 (min_size=1, max_size=10)
- checkpoint_pool_size = 4 + 1 = 5 (min_size=1, max_size=5)

Tamanhos mínimos (para testar ausência de deadlock):
- domain_pool: min_size=1, max_size calculado pela fórmula
- checkpoint_pool: min_size=1, max_size calculado pela fórmula
- lock_conn: 1 conexão dedicada (sempre disponível)

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

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool as PsycopgPool, PoolTimeout
from sqlalchemy.ext.asyncio import (  # type: ignore[attr-defined]
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.infra.config import get_config
from src.infra.exceptions import PermanentError, TransientError

logger = logging.getLogger(__name__)

# Estado global dos pools (setado em worker_process_init / startup da API)
_async_engine: AsyncEngine | None = None
_async_session_factory: async_sessionmaker[AsyncSession] | None = None

_domain_pool: PsycopgPool | None = None
_checkpoint_pool: PsycopgPool | None = None
_lock_conn: psycopg.Connection | None = None

_pool_lock = threading.Lock()
_initialized = False


def calculate_pool_sizes(num_workers: int, conexoes_por_worker: int = 2, margem: int = 2) -> tuple[int, int]:
    """
    Calcula tamanhos dos pools conforme fórmula documentada.

    Args:
        num_workers: Número de processos worker (filhos do Celery)
        conexoes_por_worker: Conexões de domínio por worker (padrão 2)
        margem: Margem de segurança (padrão 2)

    Returns:
        Tupla (domain_pool_size, checkpoint_pool_size)
    """
    domain_pool_size = num_workers * conexoes_por_worker + margem
    checkpoint_pool_size = num_workers + 1
    return domain_pool_size, checkpoint_pool_size


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
    pool_timeout: float = 5.0,
) -> None:
    """
    Inicializa pools do worker (pós-fork).
    Chamado via sinal worker_process_init do Celery.

    Args:
        domain_pool_size: Tamanho máximo do pool de domínio
        checkpoint_pool_size: Tamanho máximo do pool de checkpoint
        pool_timeout: Timeout em segundos para obter conexão do pool (padrão 5s)
    """
    global _domain_pool, _checkpoint_pool, _lock_conn, _initialized
    with _pool_lock:
        if _initialized:
            return
        dsn = _build_dsn()

        # domain_pool: transacional, para machine, market_payloads, published, events
        _domain_pool = PsycopgPool(
            min_size=1,
            max_size=domain_pool_size,
            conninfo=dsn,
            timeout=pool_timeout,
            check=PsycopgPool.check_connection,
            kwargs={"autocommit": False},
        )

        # checkpoint_pool: autocommit + dict_row (exigido pelo PostgresSaver)
        _checkpoint_pool = PsycopgPool(
            min_size=1,
            max_size=checkpoint_pool_size,
            conninfo=dsn,
            timeout=pool_timeout,
            check=PsycopgPool.check_connection,
            kwargs={"autocommit": True, "row_factory": dict_row},
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


def _translate_db_error(exc: Exception, conn: psycopg.Connection | None = None) -> Exception:
    """
    Traduz exceções de banco para a taxonomia do domínio/infra:
    - OperationalError, PoolTimeout, ou conexões caídas/fechadas -> TransientError
    - IntegrityError, DataError -> PermanentError
    """
    if isinstance(exc, (TransientError, PermanentError)):
        return exc

    if isinstance(exc, (psycopg.OperationalError, PoolTimeout)):
        err = TransientError(f"Erro transitorio de banco/conexao: {exc}")
        err.__cause__ = exc
        return err

    if isinstance(exc, psycopg.InterfaceError):
        # Conexão fechada/quebrada durante operação
        if conn is not None and (conn.closed or getattr(conn, "broken", False)):
            err = TransientError(f"Conexao perdida/fechada: {exc}")
            err.__cause__ = exc
            return err
        return exc

    if isinstance(exc, (psycopg.IntegrityError, psycopg.DataError)):
        err = PermanentError(f"Erro permanente de dados/integridade: {exc}")
        err.__cause__ = exc
        return err

    return exc


@contextmanager
def get_domain_connection() -> Generator[psycopg.Connection, None, None]:
    """Obtém conexão do domain_pool (transacional) com tradução de erros na fronteira."""
    if _domain_pool is None:
        raise RuntimeError("Worker pools not initialized. Call init_worker_pools() first.")
    try:
        conn = _domain_pool.getconn()
    except Exception as e:
        raise _translate_db_error(e) from e

    try:
        yield conn
        conn.commit()
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        raise _translate_db_error(e, conn) from e
    finally:
        _domain_pool.putconn(conn)


@contextmanager
def get_checkpoint_connection() -> Generator[psycopg.Connection, None, None]:
    """Obtém conexão do checkpoint_pool (autocommit + dict_row) com tradução de erros na fronteira."""
    if _checkpoint_pool is None:
        raise RuntimeError("Worker pools not initialized. Call init_worker_pools() first.")
    try:
        conn = _checkpoint_pool.getconn()
    except Exception as e:
        raise _translate_db_error(e) from e

    try:
        yield conn
    except Exception as e:
        raise _translate_db_error(e, conn) from e
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
