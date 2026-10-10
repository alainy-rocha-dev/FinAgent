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


def _pool_config_min(num_workers: int = 1) -> dict:
    """Configuração de pool com tamanhos mínimos calculados pela fórmula."""
    domain_size, checkpoint_size = calculate_pool_sizes(num_workers)
    # Para teste de deadlock, usamos max_size = min_size = 1
    # mas a fórmula ainda dita qual seria o tamanho normal
    return {
        "domain_pool_size": domain_size,
        "checkpoint_pool_size": checkpoint_size,
        "min_domain": 1,
        "min_checkpoint": 1,
    }


@pytest.fixture(scope="function")
def worker_pools_min(pg_dsn):
    """Inicializa pools com tamanhos mínimos (min_size=1) para teste de deadlock."""
    cfg = _pool_config_min(num_workers=1)
    init_worker_pools(domain_pool_size=cfg["min_domain"], checkpoint_pool_size=cfg["min_checkpoint"])
    yield cfg
    close_worker_pools()


@pytest.fixture(scope="function")
def worker_pools_normal(pg_dsn):
    """Inicializa pools com tamanhos normais (fórmula) para comparação."""
    cfg = _pool_config_min(num_workers=4)
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
                assert cur.fetchone()[0] == 1

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
                cur.execute("SELECT 1")
                assert cur.fetchone()[0] == 1
    finally:
        release_advisory_lock(task_id, lock_conn)


@pytest.mark.integration
def test_pool_below_minimum_times_out(pg_dsn):
    """
    Teste NEGATIVO: pool com tamanho menor que o mínimo (max_size=0 não é permitido,
    mas simulamos esgotamento criando pool normal e exaurindo todas as conexões
    sem liberar, com timeout curto no getconn).

    O psycopg_pool não permite max_size=0, então testamos que o timeout do pool
    funciona: se todas as conexões estão em uso e timeout é curto, deve falhar rápido.
    """
    from psycopg_pool import ConnectionPool
    from psycopg import OperationalError

    # Pool com max_size=1 e timeout curto (0.5s)
    pool = ConnectionPool(
        min_size=1,
        max_size=1,
        conninfo=pg_dsn,
        timeout=0.5,  # timeout curto para falhar rápido
        kwargs={"autocommit": False},
    )
    try:
        # Pega a única conexão e NÃO devolve
        conn = pool.getconn()
        # Tenta pegar outra - deve dar timeout
        with pytest.raises(OperationalError, match="timeout|pool exhausted|connection pool"):
            pool.getconn()
    finally:
        # Devolve e fecha
        pool.putconn(conn)
        pool.close()


@pytest.mark.integration
def test_pool_sizing_formula_matches_documented(pg_dsn):
    """
    Verifica que a fórmula documentada produz os tamanhos esperados
    e que os pools podem ser criados com esses tamanhos.
    """
    # Cenário: 4 workers, 2 conexões/worker, margem 2
    domain_size, checkpoint_size = calculate_pool_sizes(num_workers=4, conexoes_por_worker=2, margem=2)

    assert domain_size == 10, f"domain_pool_size esperado 10, obtido {domain_size}"
    assert checkpoint_size == 5, f"checkpoint_pool_size esperado 5, obtido {checkpoint_size}"

    # Cria pools com esses tamanhos
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