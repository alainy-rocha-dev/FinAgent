"""
Exceções padronizadas do domínio AgentPulse (D-01).

O domínio define as exceções que serviços e lógica de negócio lançam e capturam.
Não possui dependências de driver ou infraestrutura externa.
"""

from __future__ import annotations


class AgentPulseError(Exception):
    """Exceção base do AgentPulse."""


class TransientError(AgentPulseError):
    """
    Erro transitório (conexão caída, timeout de pool, deadlock detectado).
    O chamador / worker deve tentar novamente com backoff.
    """


class PermanentError(AgentPulseError):
    """
    Erro permanente (violação de integridade, schema inválido, payload malformado).
    Não deve ser retentado automaticamente.
    """
