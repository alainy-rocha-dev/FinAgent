"""
Exceções padronizadas da infraestrutura AgentPulse.

Erros de conexão e timeouts viram TransientError na fronteira (passíveis de retry).
Erros de lógica de negócio e integridade viram PermanentError (não repetíveis).
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
