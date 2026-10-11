"""
Pools de conexão da infraestrutura AgentPulse.

Separação por papel de processo (D-01, D-02, D-03):
- API (assíncrona): SQLAlchemy async + asyncpg
- Worker (prefork, síncrono): dois pools psycopg + conexão dedicada para lock
  - domain_pool: transacional (market_payloads, published, tasks, task_events)
  - checkpoint_pool: autocommit + dict_row (exigido pelo PostgresSaver do LangGraph)
  - lock_conn: conexão dedicada para advisory lock por task_id

Fórmula de dimensionamento e orçamento de conexões:
- Por processo worker (constante por processo filho Celery):
  - domain_pool: min_size=1, max_size=conexoes_por_filho (padrão 2)
  - checkpoint_pool: min_size=1, max_size=conexoes_checkpoint_por_filho (padrão 1)
  - lock_conn: 1 conexão dedicada para advisory lock por task_id
  - Total por processo worker filho = 2 + 1 + 1 = 4 conexões
- Orçamento global (Postgres max_connections):
  - conexões_API + (num_workers * filhos_por_worker * conexões_por_filho) + margem <= max_connections
  - Exemplo: API (10) + (1 worker * 4 filhos * 4 conexões/filho) + margem (4) = 30 <= max_connections

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
from psycopg_pool import ConnectionPool as PsycopgPool
from psycopg_pool import PoolTimeout
from sqlalchemy.ext.asyncio import (  # type: ignore[attr-defined]
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.domain.exceptions import PermanentError, TransientError
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


def calculate_pool_sizes(
    conexoes_por_filho: int = 2,
    checkpoint_conexoes_por_filho: int = 1,
) -> tuple[int, int]:
    """
    Calcula tamanhos dos pools por processo worker (constante por filho Celery).

    Em arquitetura prefork, cada processo filho instancia seus próprios pools.
    Portanto, os tamanhos dos pools por processo são constantes e não multiplicam
    quadraticamente pelo número de workers.

    Args:
        conexoes_por_filho: Conexões máximas de domínio por filho (padrão 2)
        checkpoint_conexoes_por_filho: Conexões de checkpoint por filho (padrão 1)

    Returns:
        Tupla (domain_pool_size, checkpoint_pool_size)
    """
    return conexoes_por_filho, checkpoint_conexoes_por_filho


def calculate_global_connection_budget(
    api_connections: int = 10,
    num_workers: int = 1,
    filhos_por_worker: int = 4,
    conexoes_por_filho: int = 4,
    margem: int = 4,
) -> int:
    """
    Calcula o orçamento total de conexões abertas no PostgreSQL:
    orçamento = conexões_API + (num_workers * filhos_por_worker * conexões_por_filho) + margem

    Args:
        api_connections: Conexões reservadas para o pool da API
        num_workers: Número de nós/instâncias Celery worker
        filhos_por_worker: Concurrency / número de processos filhos Celery por worker
        conexoes_por_filho: Total de conexões de cada filho (domain + checkpoint + lock_conn)
        margem: Margem de conexões para migrações, conexões de admin ou picos

    Returns:
        Total estimado de conexões no PostgreSQL
    """
    return api_connections + (num_workers * filhos_por_worker * conexoes_por_filho) + margem


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
    Traduz exceções de banco para a taxonomia do domínio/infra com base no SQLSTATE:
    - Conexão perdida (08xxx, 57P01, 57P02, 57P03), timeout de pool e deadlock/concorrência (40P01, 40001) -> TransientError
    - Autenticação e configuração (28xxx, 3Dxxx, 42xxx, 53xxx) -> PermanentError
    - Erros de integridade/dados (23xxx, 22xxx) -> PermanentError
    - Desconhecido -> PermanentError (default seguro para falhas permanentes/inesperadas)
    """
    if isinstance(exc, TransientError | PermanentError):
        return exc

    if isinstance(exc, PoolTimeout):
        err_transient = TransientError(f"Erro transitorio: timeout ao obter conexao do pool: {exc}")
        err_transient.__cause__ = exc
        return err_transient

    # Se for psycopg.Error, inspecionamos o sqlstate de 5 caracteres
    sqlstate = getattr(exc, "sqlstate", None)

    if sqlstate is not None:
        sqlstate_str = str(sqlstate).upper()

        # 1. Conexão perdida / shutdown / falha de rede:
        # 08xxx (Connection Exception), 57P01 (admin_shutdown), 57P02 (crash_shutdown), 57P03 (cannot_connect_now)
        # 53200 (too_many_connections - transitório sob carga)
        # 40P01 (deadlock_detected), 40001 (serialization_failure)
        if (
            sqlstate_str.startswith("08")
            or sqlstate_str in {"57P01", "57P02", "57P03", "40P01", "40001", "53200"}
        ):
            err_trans = TransientError(f"Erro transitorio de conexao/deadlock (SQLSTATE {sqlstate_str}): {exc}")
            err_trans.__cause__ = exc
            return err_trans

        # 2. Autenticação, configuração, tabela ausente, credencial inválida, violação de integridade:
        # 28xxx (invalid_authorization_specification), 3Dxxx (invalid_catalog_name / database does not exist)
        # 42xxx (syntax_error_or_access_rule_violation), 23xxx (integrity_constraint_violation)
        # 22xxx (data_exception)
        if (
            sqlstate_str.startswith("28")
            or sqlstate_str.startswith("3D")
            or sqlstate_str.startswith("42")
            or sqlstate_str.startswith("23")
            or sqlstate_str.startswith("22")
            or sqlstate_str.startswith("53")
        ):
            err_perm = PermanentError(f"Erro permanente de autenticacao/config/dados (SQLSTATE {sqlstate_str}): {exc}")
            err_perm.__cause__ = exc
            return err_perm

    # Se a conexão foi fechada/quebrada durante a operação (InterfaceError/OperationalError sem sqlstate específico)
    if isinstance(exc, psycopg.Error) and conn is not None and (conn.closed or getattr(conn, "broken", False)):
        err_conn_lost = TransientError(f"Erro transitorio: conexao perdida/fechada durante operacao: {exc}")
        err_conn_lost.__cause__ = exc
        return err_conn_lost

    if isinstance(exc, psycopg.OperationalError):
        # OperationalError sem SQLSTATE (ex.: connection dropped sem código SQL retornado pelo server)
        err_op = TransientError(f"Erro transitorio de comunicacao/operacao: {exc}")
        err_op.__cause__ = exc
        return err_op

    if isinstance(exc, psycopg.IntegrityError | psycopg.DataError):
        err_data = PermanentError(f"Erro permanente de dados/integridade: {exc}")
        err_data.__cause__ = exc
        return err_data

    # Se for outra subclasse de psycopg.Error não mapeada explicitamente
    if isinstance(exc, psycopg.Error):
        err_unknown = PermanentError(f"Erro permanente desconhecido de banco de dados: {exc}")
        err_unknown.__cause__ = exc
        return err_unknown

    # Exceções não relacionadas ao banco (ex: ValueError, KeyError, etc. do código da aplicação) passam intocadas
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
