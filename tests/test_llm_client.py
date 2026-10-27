"""
Testes do cliente LLM sem rede: nova tentativa em limite de uso (429) e erro claro em chave inválida (401).
"""

import pytest

from sisanalisefinanceira.llm import client as llm_client
from sisanalisefinanceira.llm.client import ChatCompletionsClient, LLMError


class FakeResponse:
    def __init__(self, status_code, body=None, headers=None):
        self.status_code = status_code
        self._body = body or {}
        self.headers = headers or {}
        self.text = str(self._body)

    def json(self):
        return self._body


OK = FakeResponse(200, {"choices": [{"message": {"content": "OK"}}]})


def make_client(sleeps):
    return ChatCompletionsClient("groq", "chave-teste", sleep=sleeps.append)


def test_tenta_de_novo_quando_atinge_limite_de_uso(monkeypatch):
    responses = iter([FakeResponse(429, headers={"retry-after": "3"}), FakeResponse(503), OK])
    monkeypatch.setattr(llm_client.requests, "post", lambda *a, **k: next(responses))
    sleeps = []
    assert make_client(sleeps)("sistema", "usuario") == "OK"
    assert sleeps == [3.0, 4.0]  # Retry-After do provedor, depois recuo exponencial


def test_chave_invalida_falha_na_hora_com_mensagem_clara(monkeypatch):
    body = {"error": {"message": "Invalid API Key", "code": "invalid_api_key"}}
    calls = []

    def post(*a, **k):
        calls.append(1)
        return FakeResponse(401, body)

    monkeypatch.setattr(llm_client.requests, "post", post)
    sleeps = []
    with pytest.raises(LLMError) as exc:
        make_client(sleeps)("sistema", "usuario")
    assert "HTTP 401" in str(exc.value)
    assert "Invalid API Key" in str(exc.value)
    assert len(calls) == 1  # 401 não é repetido
    assert sleeps == []


def test_desiste_depois_do_limite_de_tentativas(monkeypatch):
    monkeypatch.setattr(llm_client.requests, "post", lambda *a, **k: FakeResponse(429))
    sleeps = []
    client = ChatCompletionsClient("groq", "chave-teste", max_retries=2, sleep=sleeps.append)
    with pytest.raises(LLMError, match="HTTP 429"):
        client("sistema", "usuario")
    assert len(sleeps) == 2
