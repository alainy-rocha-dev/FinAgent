"""
Cliente LLM mínimo, compatível com a API de chat da OpenAI (funciona com Groq e OpenAI).

Configuração por variáveis de ambiente:
    GROQ_API_KEY        -> usa Groq (https://api.groq.com/openai/v1)
    OPENAI_API_KEY      -> usa OpenAI (se não houver chave do Groq)
    FINAGENT_LLM_MODEL  -> sobrescreve o modelo padrão do provedor

Qualquer função `(system: str, user: str) -> str` pode substituir este cliente
(é assim que os testes usam um LLM falso, sem rede).
"""

from __future__ import annotations

import os
from collections.abc import Callable

import requests

LLMCallable = Callable[[str, str], str]

PROVIDERS = {
    "groq": {
        "url": "https://api.groq.com/openai/v1/chat/completions",
        "key_env": "GROQ_API_KEY",
        "default_model": "openai/gpt-oss-120b",
    },
    "openai": {
        "url": "https://api.openai.com/v1/chat/completions",
        "key_env": "OPENAI_API_KEY",
        "default_model": "gpt-4o-mini",
    },
}


class LLMError(Exception):
    """Falha ao chamar o provedor de LLM."""


class ChatCompletionsClient:
    """Chamada simples a um endpoint de chat completions."""

    def __init__(self, provider: str, api_key: str, model: str | None = None, timeout_s: int = 30):
        if provider not in PROVIDERS:
            raise ValueError(f"Provedor desconhecido: {provider}")
        self.provider = provider
        self.url = PROVIDERS[provider]["url"]
        self.api_key = api_key
        self.model = (
            model or os.getenv("FINAGENT_LLM_MODEL") or PROVIDERS[provider]["default_model"]
        )
        self.timeout_s = timeout_s

    @property
    def label(self) -> str:
        return f"{self.provider}:{self.model}"

    def __call__(self, system: str, user: str) -> str:
        payload = {
            "model": self.model,
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        try:
            resp = requests.post(
                self.url,
                json=payload,
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=self.timeout_s,
            )
        except requests.RequestException as exc:
            raise LLMError(
                f"Erro de rede ao chamar {self.label}: {exc.__class__.__name__}"
            ) from exc
        if resp.status_code != 200:
            # Não registra o corpo da requisição (dados) nem a chave.
            raise LLMError(f"{self.label} respondeu HTTP {resp.status_code}: {resp.text[:200]}")
        try:
            return resp.json()["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise LLMError(f"Resposta inesperada de {self.label}") from exc


def client_from_env() -> ChatCompletionsClient | None:
    """Cria o cliente a partir das chaves disponíveis no ambiente; None se não houver chave."""
    for provider in ("groq", "openai"):
        key = os.getenv(PROVIDERS[provider]["key_env"], "").strip()
        if key:
            return ChatCompletionsClient(provider, key)
    return None
