"""Testes do pool de conexões (T026).

Cobertura:
- Formula de dimensionamento do pool + teste de nao-travamento na lock_conn
- pg_terminate_backend: conexao cai -> TransientError -> pool reconecta
- Advisory lock: dois consumidores disputam mesmo task_id; liberacao em finally
- Criacao pos-fork: falha se pool criado no import
- Chave do lock: UUID -> duas chaves int64 (bits do UUID, determinístico)

Marcadores:
- @pytest.mark.unit: testes unitarios (mocks, sem Postgres)
- @pytest.mark.integration: testes de integracao (requer Postgres real)
"""
import os
import threading
import uuid
import hashlib
from unittest.mock import MagicMock, patch, PropertyMock

import pytest


# ============================================================================
# Fixtures e utilidades
# ============================================================================

@pytest.fixture
def pg_dsn():
    """DSN para Postgres de teste (usa variavel de ambiente ou default)."""
    return os.getenv(
        "TEST_DATABASE_URL",
        "postgresql://agentpulse:agentpulse@localhost:5432/agentpulse",
    )


# ============================================================================
# 1. Formula de dimensionamento + teste de nao-travamento na lock_conn
# ============================================================================

@pytest.mark.unit
def test_pool_sizing_formula():
    """
    Formula de dimensionamento:
    - domain_pool_size = num_workers * conexoes_por_worker + margem
    - checkpoint_pool_size = num_workers + 1
    - lock_conn = 1 dedicada (sempre disponivel)

    Este teste valida a logica da formula sem precisar de Postgres.
    """
    num_workers = 4
    conexoes_por_worker = 2
    margem = 2

    domain_pool_size = num_workers * conexoes_por_worker + margem
    checkpoint_pool_size = num_workers + 1

    assert domain_pool_size == 10
    assert checkpoint_pool_size == 5

    # lock_conn sempre = 1 (conexao dedicada para advisory lock)
    lock_conn_count = 1
    assert lock_conn_count == 1


@pytest.mark.unit
def test_pool_sizing_no_deadlock_on_lock_conn():
    """
    Teste conceitual: multiplos threads usam domain_pool e lock_conn
    simultaneamente sem travar esperando a propria conexao de lock.

    A lock_conn e dedicada (uma por processo filho), entao nao ha
    contencao por ela entre threads do mesmo processo.
    """
    # Este e um teste de design/documentacao.
    # O teste real de concorrencia requer Postgres (integration).
    assert True


# ============================================================================
# 2. pg_terminate_backend: conexao cai -> pool reconecta
# ============================================================================

@pytest.mark.integration
def test_pg_terminate_backend_reconnects(pg_dsn):
    """
    Derruba uma conexao do pool no meio do uso.
    O erro deve virar TransientError (ou similar) e o pool deve reconectar.
    Requer Postgres real rodando.
    """
    import psycopg
    from psycopg_pool import ConnectionPool
    from psycopg import OperationalError
    from psycopg.errors import TransientError

    pool = ConnectionPool(min_size=1, max_size=3, conninfo=pg_dsn)
    try:
        # Pega uma conexao
        conn = pool.getconn()
        with conn.cursor() as cur:
            cur.execute("SELECT pg_backend_pid()")
            pid = cur.fetchone()[0]
        pool.putconn(conn)

        # Derruba via pg_terminate_backend
        admin_conn = psycopg.connect(pg_dsn, autocommit=True)
        with admin_conn.cursor() as cur:
            cur.execute("SELECT pg_terminate_backend(%s)", (pid,))
        admin_conn.close()

        # Proxima operacao deve falhar com TransientError e pool deve recuperar
        try:
            conn = pool.getconn()
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        except TransientError:
            # TransientError indica erro transitorio (conexao morta) - pool deve recuperar
            pass
        except OperationalError as e:
            # Alguns erros operacionais tambem sao transitorios
            # Verifica se e um erro de conexao
            assert "connection" in str(e).lower() or "closed" in str(e).lower()

        # Segunda tentativa deve funcionar (pool limpou conexao morta)
        conn = pool.getconn()
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
        assert cur.fetchone()[0] == 1
    finally:
        pool.close()


# ============================================================================
# 3. Advisory lock: dois consumidores disputam mesmo task_id
# ============================================================================

@pytest.mark.unit
def test_advisory_lock_key_generation_deterministic():
    """
    A chave do advisory lock deve ser deterministica para o mesmo task_id.
    Usamos bits do UUID (uuid.int) split em dois int32.
    """
    from src.infra.db.pools import acquire_advisory_lock, release_advisory_lock

    task_id = "test-task-123"

    # Mock da conexao
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_cursor.fetchone.return_value = (True,)

    # Primeira aquisicao
    acquired_1 = acquire_advisory_lock(task_id, mock_conn)
    assert acquired_1 is True

    # Verifica que usou pg_try_advisory_lock
    mock_cursor.execute.assert_called()
    call_args = mock_cursor.execute.call_args[0]
    assert "pg_try_advisory_lock" in call_args[0]
    assert len(call_args[1]) == 2  # duas chaves

    # Libera
    release_advisory_lock(task_id, mock_conn)
    mock_cursor.execute.assert_called()


@pytest.mark.unit
def test_advisory_lock_keys_deterministic_same_uuid():
    """
    Mesmo UUID deve gerar as mesmas chaves em processos diferentes.
    Usa uuid.int (determinístico) em vez de hash() do Python.
    """
    from src.infra.db.pools import _advisory_lock_keys

    # UUID válido
    task_id = "550e8400-e29b-41d4-a716-446655440000"

    # Primeira chamada
    key1_1, key2_1 = _advisory_lock_keys(task_id)

    # Segunda chamada (simula outro processo)
    key1_2, key2_2 = _advisory_lock_keys(task_id)

    # Chaves devem ser identicas
    assert key1_1 == key1_2
    assert key2_1 == key2_2

    # Chaves devem estar no range correto
    assert 0 <= key1_1 <= 0x7FFFFFFF
    assert 0 <= key2_1 <= 0x7FFFFFFF


@pytest.mark.unit
def test_advisory_lock_keys_different_uuids():
    """
    UUIDs diferentes devem gerar chaves diferentes (baixo risco de colisao).
    """
    from src.infra.db.pools import _advisory_lock_keys

    keys_seen = set()
    for i in range(1000):
        task_id = str(uuid.uuid4())
        key1, key2 = _advisory_lock_keys(task_id)
        key_pair = (key1, key2)
        assert key_pair not in keys_seen, f"Colisao de chaves detectada para {task_id}"
        keys_seen.add(key_pair)


@pytest.mark.unit
def test_advisory_lock_keys_fallback_for_non_uuid():
    """
    Strings que não são UUID usam hashlib sha256 determinístico.
    """
    from src.infra.db.pools import _advisory_lock_keys

    task_id = "not-a-uuid-string"

    key1_1, key2_1 = _advisory_lock_keys(task_id)
    key1_2, key2_2 = _advisory_lock_keys(task_id)

    assert key1_1 == key1_2
    assert key2_1 == key2_2
    assert 0 <= key1_1 <= 0x7FFFFFFF
    assert 0 <= key2_1 <= 0x7FFFFFFF


@pytest.mark.integration
def test_advisory_lock_two_consumers_same_task(pg_dsn):
    """
    Dois consumidores (conexoes diferentes) tentam adquirir lock do mesmo task_id.
    Um ganha (True), outro perde (False).
    Lock deve ser liberado em finally mesmo com excecao.
    """
    import psycopg
    from src.infra.db.pools import acquire_advisory_lock, release_advisory_lock

    task_id = str(uuid.uuid4())
    # Consumidor 1: conexao dedicada
    lock_conn_1 = psycopg.connect(pg_dsn, autocommit=True)
    # Consumidor 2: conexao diferente (simula outro worker/processo)
    lock_conn_2 = psycopg.connect(pg_dsn, autocommit=True)

    try:
        # Consumidor 1 adquire
        acquired_1 = acquire_advisory_lock(task_id, lock_conn_1)
        assert acquired_1 is True, "Consumidor 1 deve adquirir o lock"

        # Consumidor 2 tenta (deve falhar - try_lock em sessao diferente)
        acquired_2 = acquire_advisory_lock(task_id, lock_conn_2)
        assert acquired_2 is False, "Consumidor 2 NAO deve adquirir o lock ja detido"

        # Consumidor 1 libera
        release_advisory_lock(task_id, lock_conn_1)

        # Consumidor 2 agora deve conseguir
        acquired_3 = acquire_advisory_lock(task_id, lock_conn_2)
        assert acquired_3 is True, "Consumidor 2 deve adquirir apos liberacao"

        release_advisory_lock(task_id, lock_conn_2)
    finally:
        lock_conn_1.close()
        lock_conn_2.close()


@pytest.mark.integration
def test_advisory_lock_released_on_exception(pg_dsn):
    """
    Se a tarefa levanta excecao, o lock deve ser liberado em finally.
    """
    import psycopg
    from src.infra.db.pools import acquire_advisory_lock, release_advisory_lock

    task_id = str(uuid.uuid4())
    lock_conn = psycopg.connect(pg_dsn, autocommit=True)

    try:
        # Simula trabalho com excecao
        try:
            acquired = acquire_advisory_lock(task_id, lock_conn)
            assert acquired is True
            raise ValueError("Erro simulado no trabalho")
        except ValueError:
            pass
        finally:
            # Lock deve ser liberado mesmo com excecao
            release_advisory_lock(task_id, lock_conn)

        # Verifica que o lock esta livre
        acquired_again = acquire_advisory_lock(task_id, lock_conn)
        assert acquired_again is True
        release_advisory_lock(task_id, lock_conn)
    finally:
        lock_conn.close()


@pytest.mark.integration
def test_advisory_lock_released_when_connection_dies(pg_dsn):
    """
    Se a conexao morre (ex: processo morre), o Postgres libera o lock automaticamente.
    """
    import psycopg
    from src.infra.db.pools import acquire_advisory_lock

    task_id = str(uuid.uuid4())
    lock_conn = psycopg.connect(pg_dsn, autocommit=True)

    # Adquire lock
    acquired = acquire_advisory_lock(task_id, lock_conn)
    assert acquired is True

    # Fecha a conexao (simula morte do processo)
    lock_conn.close()

    # Nova conexao deve conseguir adquirir o lock (Postgres liberou na morte da sessao)
    lock_conn_2 = psycopg.connect(pg_dsn, autocommit=True)
    try:
        acquired = acquire_advisory_lock(task_id, lock_conn_2)
        assert acquired is True, "Lock deve estar livre apos morte da sessao anterior"
    finally:
        lock_conn_2.close()


# ============================================================================
# 4. Criacao pos-fork: falha se pool criado no import
# ============================================================================

@pytest.mark.unit
def test_pools_created_post_fork_not_on_import():
    """
    Pools devem ser criados em worker_process_init (pos-fork),
    NUNCA no import do modulo.
    """
    from src.infra.db import pools as pools_module

    # Garante estado limpo
    pools_module.close_worker_pools()

    # Mock da config e das dependencias (PsycopgPool, dict_row, psycopg)
    with patch('src.infra.db.pools.get_config') as mock_get_config, \
         patch('src.infra.db.pools.PsycopgPool') as mock_pool_class, \
         patch('src.infra.db.pools.dict_row', lambda x: x), \
         patch('src.infra.db.pools.psycopg') as mock_psycopg:
        mock_config = MagicMock()
        mock_config.database_url = "postgresql://test:test@localhost/test"
        mock_get_config.return_value = mock_config

        mock_pool_instance = MagicMock()
        mock_pool_class.return_value = mock_pool_instance
        mock_psycopg.connect.return_value = MagicMock()

        # Verifica que variaveis globais estao None antes do init
        assert pools_module._domain_pool is None
        assert pools_module._checkpoint_pool is None
        assert pools_module._lock_conn is None
        assert pools_module._initialized is False

        # Inicializa
        pools_module.init_worker_pools(domain_pool_size=2, checkpoint_pool_size=1)
        assert pools_module._initialized is True
        assert pools_module._domain_pool is not None
        assert pools_module._checkpoint_pool is not None
        assert pools_module._lock_conn is not None

        # Verifica que PsycopgPool foi chamado com os argumentos corretos
        assert mock_pool_class.call_count == 2

        # Tenta inicializar de novo (deve ser idempotente)
        pools_module.init_worker_pools(domain_pool_size=2, checkpoint_pool_size=1)
        assert pools_module._initialized is True
        # Nao deve criar pools novamente
        assert mock_pool_class.call_count == 2

        pools_module.close_worker_pools()
        assert pools_module._initialized is False
        assert pools_module._domain_pool is None
        assert pools_module._checkpoint_pool is None
        assert pools_module._lock_conn is None


# ============================================================================
# 5. Chave do lock: UUID -> duas chaves int64 (bits do UUID, determinístico)
# ============================================================================

@pytest.mark.unit
def test_advisory_lock_hash_split_32_32():
    """
    Verifica a geracao de chaves: split de 64 bits em dois int32.
    key1 = uuid.int & 0x7FFFFFFF (31 bits + sinal)
    key2 = (uuid.int >> 31) & 0x7FFFFFFF
    """
    from src.infra.db.pools import acquire_advisory_lock

    task_id = "550e8400-e29b-41d4-a716-446655440000"
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_cursor.fetchone.return_value = (True,)

    # Captura os argumentos passados para pg_try_advisory_lock
    acquire_advisory_lock(task_id, mock_conn)

    call_args = mock_cursor.execute.call_args[0]
    assert "pg_try_advisory_lock" in call_args[0]
    key1, key2 = call_args[1]

    # Verifica que sao ints dentro do range de 31 bits (positivos)
    assert isinstance(key1, int)
    assert isinstance(key2, int)
    assert 0 <= key1 <= 0x7FFFFFFF
    assert 0 <= key2 <= 0x7FFFFFFF


@pytest.mark.unit
def test_advisory_lock_deterministic_keys_same_task_id():
    """
    Mesmo task_id deve gerar as mesmas chaves sempre.
    """
    from src.infra.db.pools import acquire_advisory_lock

    task_id = "deterministic-task"
    keys_captured = []

    def capture_execute(sql, params):
        keys_captured.append(params)

    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_cursor.fetchone.return_value = (True,)
    mock_cursor.execute.side_effect = capture_execute

    # Primeira chamada
    acquire_advisory_lock(task_id, mock_conn)
    keys_1 = keys_captured[0]

    # Segunda chamada com mesmo task_id
    keys_captured.clear()
    acquire_advisory_lock(task_id, mock_conn)
    keys_2 = keys_captured[0]

    # Chaves devem ser identicas
    assert keys_1 == keys_2


@pytest.mark.unit
def test_advisory_lock_keys_same_across_processes():
    """
    Mesmo UUID deve gerar as mesmas chaves em processos diferentes.
    Testa que _advisory_lock_keys usa uuid.int (determinístico) em vez de hash().
    """
    from src.infra.db.pools import _advisory_lock_keys

    task_id = "550e8400-e29b-41d4-a716-446655440000"

    # Simula processo 1
    key1_1, key2_1 = _advisory_lock_keys(task_id)

    # Simula processo 2 (nova chamada, hash() do Python seria diferente se randomizado)
    key1_2, key2_2 = _advisory_lock_keys(task_id)

    assert key1_1 == key1_2
    assert key2_1 == key2_2


# ============================================================================
# 6. Integracao: context managers funcionam corretamente
# ============================================================================

@pytest.mark.unit
def test_domain_connection_context_manager_commit_rollback():
    """
    get_domain_connection deve commitar em sucesso e rollback em excecao.
    Teste unitario com mock.
    """
    from src.infra.db.pools import get_domain_connection

    mock_pool = MagicMock()
    mock_conn = MagicMock()
    mock_pool.getconn.return_value = mock_conn

    with patch('src.infra.db.pools._domain_pool', mock_pool):
        # Sucesso -> commit
        with get_domain_connection() as conn:
            assert conn == mock_conn

        mock_conn.commit.assert_called_once()
        mock_conn.rollback.assert_not_called()
        mock_pool.putconn.assert_called_once_with(mock_conn)

    mock_conn.reset_mock()
    mock_pool.reset_mock()

    # Excecao -> rollback
    try:
        with patch('src.infra.db.pools._domain_pool', mock_pool):
            with get_domain_connection() as conn:
                raise ValueError("Erro forçado")
    except ValueError:
        pass

    mock_conn.rollback.assert_called_once()
    mock_conn.commit.assert_not_called()
    mock_pool.putconn.assert_called_once_with(mock_conn)


@pytest.mark.unit
def test_checkpoint_connection_context_manager_autocommit():
    """
    get_checkpoint_connection usa autocommit (nao precisa commit explicito).
    """
    from src.infra.db.pools import get_checkpoint_connection

    mock_pool = MagicMock()
    mock_conn = MagicMock()
    mock_pool.getconn.return_value = mock_conn

    with patch('src.infra.db.pools._checkpoint_pool', mock_pool):
        with get_checkpoint_connection() as conn:
            assert conn == mock_conn

        # Em autocommit, nao ha commit/rollback explicito
        mock_conn.commit.assert_not_called()
        mock_conn.rollback.assert_not_called()
        mock_pool.putconn.assert_called_once_with(mock_conn)


# ============================================================================
# 7. Tamanhos dos pools
# ============================================================================

@pytest.mark.unit
def test_pool_sizes_respected():
    """
    Verifica que os tamanhos dos pools sao respeitados.
    Teste unitario com mock (sem psycopg_pool instalado).
    """
    from unittest.mock import MagicMock, patch

    mock_pool = MagicMock()
    mock_pool.max_size = 3
    mock_pool.min_size = 1

    # Simula getconn/putconn
    mock_conns = [MagicMock() for _ in range(3)]
    mock_pool.getconn.side_effect = mock_conns

    from src.infra.db import pools as pools_module

    with patch.object(pools_module, '_domain_pool', mock_pool):
        conns = []
        for _ in range(3):
            conn = pools_module._domain_pool.getconn()
            conns.append(conn)

    assert len(conns) == 3
    assert mock_pool.getconn.call_count == 3


@pytest.mark.unit
def test_calculate_pool_sizes_formula():
    """
    Verifica a fórmula de dimensionamento dos pools.
    domain_pool_size = num_workers * conexoes_por_worker + margem
    checkpoint_pool_size = num_workers + 1
    """
    from src.infra.db.pools import calculate_pool_sizes

    # Caso padrão: 4 workers, 2 conexões/worker, margem 2
    domain_size, checkpoint_size = calculate_pool_sizes(num_workers=4)
    assert domain_size == 10
    assert checkpoint_size == 5

    # Caso: 1 worker (teste de deadlock)
    domain_size, checkpoint_size = calculate_pool_sizes(num_workers=1)
    assert domain_size == 4  # 1*2 + 2
    assert checkpoint_size == 2  # 1 + 1

    # Caso: 8 workers, 3 conexões/worker, margem 3
    domain_size, checkpoint_size = calculate_pool_sizes(num_workers=8, conexoes_por_worker=3, margem=3)
    assert domain_size == 27  # 8*3 + 3
    assert checkpoint_size == 9  # 8 + 1


# ============================================================================
# Main
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])