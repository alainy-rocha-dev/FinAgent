"""
Pools de conexão da infraestrutura AgentPulse.

Separação por papel de processo (D-01, D-02, D-03):
- API (síncrona): psycopg_pool.ConnectionPool
- Worker (prefork, síncrono): dois pools psycopg + conexão dedicada para lock
  - domain_pool: transacional (market_payloads, published, tasks, task_events)
  - checkpoint_pool: autocommit + dict_row (exigido pelo PostgresSaver do LangGraph)
  - lock_conn: conexão dedicada para advisory lock por task_id

Fórmula de dimensionamento e orçamento de conexões:
- Por processo worker (constante por processo filho Celery):
  - domain_pool: min_size=1, max_size=conexoes_por_filho (padrão 2)
    * Razão de 2 conexões mínimas: 1 conexão fica presa na transação do nó do grafo,
      enquanto a 2ª conexão é usada pela thread de heartbeat para atualizar 'heartbeat_at'
      e renovar o lease da task em 'tasks' (dependência do reaper para não considerar worker morto).
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
from collections.abc import Generator
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool as PsycopgPool
from psycopg_pool import PoolTimeout

from src.domain.exceptions import PermanentError, TransientError
from src.infra.config import get_config

logger = logging.getLogger(__name__)

# Estado global dos pools (setado em worker_process_init / startup da API)
_pool_api: PsycopgPool | None = None

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
    """Inicializa pool da API (síncrono). Chamado no startup da API."""
    global _pool_api
    dsn = _build_dsn()
    _pool_api = PsycopgPool(
        min_size=1,
        max_size=10,
        conninfo=dsn,
        timeout=5.0,
        check=PsycopgPool.check_connection,
        kwargs={"autocommit": False},
    )
    logger.info("API pool initialized (psycopg_pool)")


def close_api_pools() -> None:
    """Fecha pool da API. Chamado no shutdown da API."""
    global _pool_api
    if _pool_api:
        _pool_api.close()
        _pool_api = None
        logger.info("API pool closed")


@contextmanager
def get_api_session() -> Generator[psycopg.Connection, None, None]:
    """Obtém conexão do pool da API (síncrona) para operações da API."""
    global _pool_api
    if _pool_api is None:
        raise RuntimeError("API pool not initialized. Call init_api_pools() first.")
    try:
        conn = _pool_api.getconn()
    except Exception as e:
        raise _translate_db_error(e) from e
    try:
        yield conn
    finally:
        _pool_api.putconn(conn)


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

        # 08P01 (protocol_violation) é violação de protocolo (bug/incompatibilidade);
        # não adianta retry, deve ser PermanentError mesmo iniciando com 08.
        if sqlstate_str == "08P01":
            err_proto = PermanentError(f"Erro permanente de protocolo (SQLSTATE {sqlstate_str}): {exc}")
            err_proto.__cause__ = exc
            return err_proto

        # 1. Transitórios:
        # - Conexão perdida: 08xxx (Connection Exception, exceto 08P01)
        # - Shutdown de servidor: 57P01 (admin_shutdown), 57P02 (crash_shutdown), 57P03 (cannot_connect_now)
        # - Query cancelada: 57014 (query_canceled, ex: statement_timeout)
        # - Sobrecarga de recursos / conexões: 53300 (too_many_connections), 53200 (out_of_memory)
        # - Deadlock e concorrência: 40P01 (deadlock_detected), 40001 (serialization_failure)
        if (
            sqlstate_str.startswith("08")
            or sqlstate_str in {"57P01", "57P02", "57P03", "57014", "40P01", "40001", "53300", "53200"}
        ):
            err_trans = TransientError(f"Erro transitorio de conexao/concorrencia/recurso (SQLSTATE {sqlstate_str}): {exc}")
            err_trans.__cause__ = exc
            return err_trans

        # 2. Permanentes:
        # - Autenticação: 28xxx (invalid_authorization_specification)
        # - Catálogo/DB ausente: 3Dxxx (invalid_catalog_name)
        # - Erro de sintaxe ou tabela ausente: 42xxx (syntax_error_or_access_rule_violation)
        # - Violação de integridade: 23xxx (integrity_constraint_violation)
        # - Erro de dados/tipo: 22xxx (data_exception)
        # - Outros de recursos de configuração (classe 53 exceto 53200 e 53300)
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
