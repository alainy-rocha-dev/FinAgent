"""
Exceções padronizadas da infraestrutura AgentPulse.

TransientError e PermanentError residem em `src.domain.exceptions` (D-01).
Este módulo as reexporta para compatibilidade reversa.
"""

from __future__ import annotations

from src.domain.exceptions import AgentPulseError, PermanentError, TransientError

__all__ = ["AgentPulseError", "TransientError", "PermanentError"]

