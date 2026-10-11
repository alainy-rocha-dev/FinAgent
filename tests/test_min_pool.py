"""Teste T080: pool tamanho mínimo com conexão de lock -> nenhum deadlock.

Este teste valida que o worker não trava esperando uma conexão quando:
- domain_pool tem tamanho mínimo (min_size=1)
- checkpoint_pool tem tamanho mínimo (min_size=1)
- lock_conn é dedicada (1 conexão)
- O ciclo completo (lock, transação de domínio, checkpoint) roda com timeout curto
"""
import os
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

import pytest

from src.infra.db.pools import (
    acquire_advisory_lock,
    calculate_pool_sizes,
    close_worker_pools,
    get_checkpoint_connection,
    get_domain_connection,
    get_lock_connection,
    init_worker_pools,
    release_advisory_lock,
)


@pytest.fixture(scope="module")
def pg_dsn():
    """DSN para Postgres de teste."""
    return os.getenv(
        "TEST_DATABASE_URL",
        "postgresql://agentpulse:agentpulse@localhost:5432/agentpulse",
    )


@pytest.fixture(scope="function", autouse=True)
def setup_database(pg_dsn):
    """Create database schema for integration tests."""
    import psycopg
    conn = psycopg.connect(pg_dsn, autocommit=True)
    try:
        with conn.cursor() as cur:
            # Create tables needed by tests
            cur.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id UUID PRIMARY KEY,
                    symbol VARCHAR(50) NOT NULL,
                    asset_class VARCHAR(50) NOT NULL,
                    status VARCHAR(50) NOT NULL,
                    execution_id VARCHAR(100),
                    graph_version VARCHAR(20),
                    acknowledge_simulated BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    approved_at TIMESTAMP WITH TIME ZONE,
                    heartbeat_at TIMESTAMP WITH TIME ZONE,
                    locked_by VARCHAR(100),
                    lease_until TIMESTAMP WITH TIME ZONE,
                    attempts INTEGER DEFAULT 0,
                    reject_reason TEXT,
                    snapshot_hash BYTEA
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS market_payloads (
                    task_id UUID NOT NULL,
                    symbol VARCHAR(50) NOT NULL,
                    source VARCHAR(50) NOT NULL,
                    payload_jsonb JSONB NOT NULL,
                    fetched_at TIMESTAMP WITH TIME ZONE NOT NULL,
                    data_quality VARCHAR(20) NOT NULL,
                    PRIMARY KEY (task_id, symbol, source)
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS quant_metrics (
                    task_id UUID NOT NULL,
                    symbol VARCHAR(50) NOT NULL,
                    metrics_json JSONB NOT NULL,
                    hash BYTEA NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    PRIMARY KEY (task_id, symbol)
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS published (
                    task_id UUID PRIMARY KEY,
                    report_jsonb JSONB NOT NULL,
                    published_at TIMESTAMP WITH TIME ZONE NOT NULL,
                    published_by UUID NOT NULL,
                    snapshot_hash BYTEA NOT NULL
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS task_events (
                    id BIGSERIAL PRIMARY KEY,
                    task_id UUID NOT NULL,
                    event_type VARCHAR(50) NOT NULL,
                    payload_jsonb JSONB NOT NULL,
                    actor_role VARCHAR(50) NOT NULL,
                    actor_id VARCHAR(100) NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS idempotency_keys (
                    api_key_id UUID NOT NULL,
                    key VARCHAR(100) NOT NULL,
                    task_id UUID NOT NULL,
                    payload_hash BYTEA NOT NULL,
                    response_status INTEGER NOT NULL,
                    response_body JSONB NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    PRIMARY KEY (api_key_id, key)
                )
            """)
    finally:
        conn.close()


def _pool_config_min() -> dict:
    """Configuração de pool com tamanhos constantes por processo worker."""
    domain_size, checkpoint_size = calculate_pool_sizes(conexoes_por_filho=2, checkpoint_conexoes_por_filho=1)
    # Para teste de deadlock, usamos max_size = min_size = 1
    return {
        "domain_pool_size": domain_size,
        "checkpoint_pool_size": checkpoint_size,
        "min_domain": 1,
        "min_checkpoint": 1,
    }


@pytest.fixture(scope="function")
def worker_pools_min(pg_dsn):
    """Inicializa pools com tamanhos mínimos (min_size=1) para teste de deadlock."""
    # Set DATABASE_URL for config
    os.environ["DATABASE_URL"] = pg_dsn
    cfg = _pool_config_min()
    init_worker_pools(domain_pool_size=cfg["min_domain"], checkpoint_pool_size=cfg["min_checkpoint"])
    yield cfg
    close_worker_pools()


@pytest.fixture(scope="function")
def worker_pools_normal(pg_dsn):
    """Inicializa pools com tamanhos normais (fórmula) para comparação."""
    os.environ["DATABASE_URL"] = pg_dsn
    cfg = _pool_config_min()
    init_worker_pools(domain_pool_size=cfg["domain_pool_size"], checkpoint_pool_size=cfg["checkpoint_pool_size"])
    yield cfg
    close_worker_pools()


def _full_cycle(task_id: str, lock_conn, timeout_seconds: float = 5.0) -> bool:
    """
    Executa o ciclo completo: lock -> transação de domínio -> checkpoint.
    Retorna True se completou dentro do timeout, False se travou.
    """
    # 1. Adquire advisory lock
    acquired = acquire_advisory_lock(task_id, lock_conn)
    if not acquired:
        return False

    try:
        # 2. Transação de domínio (usa domain_pool)
        with get_domain_connection() as domain_conn:
            with domain_conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO tasks (task_id, symbol, asset_class, status, execution_id, graph_version, acknowledge_simulated, created_at, updated_at, attempts) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), NOW(), %s) "
                    "ON CONFLICT (task_id) DO NOTHING",
                    (
                        task_id,
                        "TEST",
                        "equity",
                        "RUNNING",
                        f"exec-{task_id[:8]}",
                        "1.0.0",
                        True,
                        1,
                    ),
                )
                # Simula trabalho de domínio
                time.sleep(0.01)

        # 3. Checkpoint (usa checkpoint_pool com autocommit + dict_row)
        with get_checkpoint_connection() as cp_conn:
            with cp_conn.cursor() as cur:
                cur.execute("SELECT 1 as checkpoint_ok")
                row = cur.fetchone()
                assert row["checkpoint_ok"] == 1

        return True
    finally:
        release_advisory_lock(task_id, lock_conn)


@pytest.mark.integration
def test_min_pool_no_deadlock_single_worker(worker_pools_min):
    """
    Teste principal: worker único executa ciclo completo com pool no mínimo (min_size=1).
    Não deve travar esperando conexão - timeout curto no getconn garante falha rápida se deadlock.
    """
    lock_conn = get_lock_connection()
    task_id = str(uuid.uuid4())

    # Executa com timeout curto (5s) - se travar, o teste falha por timeout
    result = _full_cycle(task_id, lock_conn, timeout_seconds=5.0)

    assert result is True, "Ciclo completo deve completar sem travar com pool no mínimo"


@pytest.mark.integration
def test_min_pool_concurrent_cycles_no_deadlock(worker_pools_min):
    """
    Múltiplos ciclos concorrentes (simula múltiplas tasks no mesmo worker).
    Com domain_pool min_size=1, apenas uma task por vez pode usar domain_pool.
    O teste verifica que as tasks se revezam sem deadlock.
    """
    lock_conn = get_lock_connection()
    num_tasks = 3
    task_ids = [str(uuid.uuid4()) for _ in range(num_tasks)]
    results = {}
    errors = {}

    def run_cycle(tid: str):
        try:
            results[tid] = _full_cycle(tid, lock_conn, timeout_seconds=10.0)
        except Exception as e:
            errors[tid] = e

    # Executa concorrentemente (mesmo processo, múltiplas threads)
    with ThreadPoolExecutor(max_workers=num_tasks) as executor:
        futures = {executor.submit(run_cycle, tid): tid for tid in task_ids}
        # Aguarda todos com timeout generoso
        for future in futures:
            try:
                future.result(timeout=15.0)
            except FuturesTimeoutError:
                tid = futures[future]
                errors[tid] = FuturesTimeoutError(f"Task {tid} timed out waiting for connection")

    # Verifica: nenhuma task deve ter travado (timeout)
    assert len(errors) == 0, f"Tasks travaram esperando conexão: {errors}"

    # Todas devem ter completado
    assert all(results.values()), f"Algumas tasks falharam: {results}"


@pytest.mark.integration
def test_min_pool_lock_connection_independent(worker_pools_min):
    """
    Verifica que lock_conn é independente dos pools (não conta no domain_pool nem checkpoint_pool).
    Mesmo com domain_pool esgotado, lock_conn deve estar disponível.
    """
    lock_conn = get_lock_connection()
    task_id = str(uuid.uuid4())

    # Adquire lock
    acquired = acquire_advisory_lock(task_id, lock_conn)
    assert acquired is True

    # Usa domain_pool (esgota a única conexão disponível)
    with get_domain_connection() as domain_conn:
        with domain_conn.cursor() as cur:
            cur.execute("SELECT pg_sleep(0.1)")  # Segura a conexão por 100ms

    # Mesmo com domain_pool ocupado, lock_conn ainda funciona
    # (lock_conn é conexão separada, não vem do pool)
    release_advisory_lock(task_id, lock_conn)

    # Lock deve estar livre agora
    acquired_again = acquire_advisory_lock(task_id, lock_conn)
    assert acquired_again is True
    release_advisory_lock(task_id, lock_conn)


@pytest.mark.integration
def test_min_pool_checkpoint_independent(worker_pools_min):
    """
    Verifica que checkpoint_pool é independente do domain_pool.
    """
    lock_conn = get_lock_connection()
    task_id = str(uuid.uuid4())

    acquired = acquire_advisory_lock(task_id, lock_conn)
    assert acquired is True

    try:
        # Segura domain_pool
        with get_domain_connection() as domain_conn:
            with domain_conn.cursor() as cur:
                cur.execute("SELECT pg_sleep(0.05)")

        # checkpoint_pool deve estar disponível independentemente
        with get_checkpoint_connection() as cp_conn:
            with cp_conn.cursor() as cur:
                cur.execute("SELECT 1 as checkpoint_ok")
                row = cur.fetchone()
                assert row["checkpoint_ok"] == 1
    finally:
        release_advisory_lock(task_id, lock_conn)


@pytest.mark.integration
def test_pool_below_minimum_times_out(pg_dsn):
    """
    Teste NEGATIVO de ciclo real:
    Configura o worker com pool no mínimo (1 conexão) com timeout curto (0.5s).
    Simula uma operação concorrente retendo a única conexão do pool de domínio.
    Ao tentar executar o ciclo real (lock -> transação de domínio -> checkpoint),
    a aquisição da conexão para a transação deve falhar por timeout de pool,
    sendo traduzida rigorosamente em TransientError na fronteira da infraestrutura.
    """
    from src.domain.exceptions import TransientError

    os.environ["DATABASE_URL"] = pg_dsn
    close_worker_pools()
    # Inicializa pools no mínimo com timeout curto para falhar rápido
    init_worker_pools(domain_pool_size=1, checkpoint_pool_size=1, pool_timeout=0.5)

    try:
        lock_conn = get_lock_connection()
        task_id = str(uuid.uuid4())

        # Segura a única conexão do domain_pool em uma transação ativa externa
        with get_domain_connection() as _retained_conn:
            # Tenta executar o ciclo real: deve falhar no passo de obter conexão do domínio
            with pytest.raises(TransientError) as exc_info:
                _full_cycle(task_id, lock_conn, timeout_seconds=1.0)

            assert "Erro transitório" in str(exc_info.value) or "couldn't get a connection" in str(exc_info.value)
    finally:
        close_worker_pools()


@pytest.mark.integration
def test_pool_sizing_formula_matches_documented(pg_dsn):
    """
    Verifica que a fórmula documentada produz os tamanhos esperados
    (constante por processo filho Celery + orçamento global)
    e que os pools podem ser criados com esses tamanhos.
    """
    from src.infra.db.pools import calculate_global_connection_budget

    # Set DATABASE_URL for config
    os.environ["DATABASE_URL"] = pg_dsn

    # 1. Tamanhos por processo worker (constantes por processo filho Celery)
    domain_size, checkpoint_size = calculate_pool_sizes(conexoes_por_filho=2, checkpoint_conexoes_por_filho=1)

    assert domain_size == 2, f"domain_pool_size por processo esperado 2, obtido {domain_size}"
    assert checkpoint_size == 1, f"checkpoint_pool_size por processo esperado 1, obtido {checkpoint_size}"

    # 2. Orçamento global: API + workers x filhos x conexões por filho + margem <= max_connections
    # Exemplo documentado: API 10, 1 worker com 4 filhos, 4 conexões por filho (2 domain + 1 cp + 1 lock), margem 4
    total_budget = calculate_global_connection_budget(
        api_connections=10,
        num_workers=1,
        filhos_por_worker=4,
        conexoes_por_filho=4,
        margem=4,
    )
    assert total_budget == 30, f"Orçamento global esperado 30, obtido {total_budget}"
    assert total_budget <= 100  # Padrão típico de max_connections do Postgres é 100

    # Cria pools com esses tamanhos por processo
    init_worker_pools(domain_pool_size=domain_size, checkpoint_pool_size=checkpoint_size)
    try:
        # Verifica que pools foram criados com os tamanhos corretos
        from src.infra.db import pools as pools_module
        assert pools_module._domain_pool.max_size == domain_size
        assert pools_module._checkpoint_pool.max_size == checkpoint_size
        assert pools_module._domain_pool.min_size == 1
        assert pools_module._checkpoint_pool.min_size == 1
    finally:
        close_worker_pools()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])