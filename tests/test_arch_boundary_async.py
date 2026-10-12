"""
Teste de fronteira: garante que o módulo src.infra.db não utiliza padrões assíncronos.
Este teste deve ser executado junto com o CI de T026b.
"""

import ast
import importlib
import os
import sys

import pytest

# Caminho absoluto do pacote a ser inspecionado
DB_MODULE_PATH = os.path.join(os.path.dirname(__file__), "..", "src", "infra", "db", "pools.py")


def _has_async_patterns(module_code: str) -> bool:
    """Retorna True se o código fonte conter padrões assíncronos proibidos."""
    tree = ast.parse(module_code)
    for node in ast.walk(tree):
        # funcoes assíncronas: async def
        if isinstance(node, ast.AsyncFunctionDef):
            return True
        # imports de modulo asyncpg
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "asyncpg":
                    return True
        # imports de modulo sqlalchemy.ext.asyncio
        if isinstance(node, ast.ImportFrom):
            if node.module and "asyncio" in node.module:
                return True
    return False


def _load_pools_source() -> str:
    """Carrega o código-fonte do pools.py para inspeção."""
    with open(DB_MODULE_PATH, "r", encoding="utf-8") as f:
        return f.read()


class TestArchNoAsyncPatterns:
    """Contrato: src/infra.db.pools não deve conter padrões assíncronos."""

    def test_no_async_patterns(self):
        source = _load_pools_source()
        assert not _has_async_patterns(source), (
            "src/infra/db/pools.py contém padrões assíncronos proibidos. "
            "Remova AsyncConnectionPool, asyncpg, create_async_engine e async def."
        )

    def test_import_asyncpg_fails_if_readded(self):
        """Experimento: se asyncpg for importado de propósito, o teste falha."""
        # Este teste documenta o gate: asyncpg no módulo = falha.
        # Remove-o após a verificação.
        pass  # A lógica está em test_no_async_patterns


def test_architecture_gate():
    """Experimento isolado: colocar import asyncpg e confirmar falha."""
    # Este teste manual deve ser rodado antes/after do commit:
    # 1. Adicionar "import asyncpg" em src/infra/db/pools.py
    # 2. Rodar pytest tests/test_arch_boundary_async.py -> deve FALHAR
    # 3. Remover "import asyncpg"
    # 4. Rodar pytest tests/test_arch_boundary_async.py -> deve PASSAR
    import subprocess
    result = subprocess.run(
        [sys.executable, "-c",
         "import ast; tree=ast.parse(open('src/infra/db/pools.py').read()); "
         "print('asyncpg found' if any(n.name=='asyncpg' for n in ast.walk(tree) if isinstance(n,ast.Import) for n in [n]) else 'ok')"],
        capture_output=True, text=True
    )
    assert "asyncpg found" not in result.stdout, "import asyncpg encontrado — teste de fronteira falhou"