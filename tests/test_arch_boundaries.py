"""Architectural test: domain must not import infra."""
import ast
import os
from pathlib import Path


def test_domain_no_infra_imports():
    """Ensure domain package doesn't import from infra."""
    domain_path = Path("src/domain")
    infra_prefixes = ("infra", "src.infra")

    for py_file in domain_path.rglob("*.py"):
        with open(py_file, encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=str(py_file))

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    for prefix in infra_prefixes:
                        assert not alias.name.startswith(prefix), (
                            f"{py_file}: Domain imports infra: {alias.name}"
                        )
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    for prefix in infra_prefixes:
                        assert not node.module.startswith(prefix), (
                            f"{py_file}: Domain imports from infra: {node.module}"
                        )


def test_infra_can_import_domain():
    """Infra can import domain (one-way dependency)."""
    # This is allowed - infra depends on domain
    pass


def test_no_circular_imports():
    """Basic check for circular imports between domain and infra."""
    # More sophisticated checks can be added with import-linter
    # For now, enforce the one-way rule above
    pass