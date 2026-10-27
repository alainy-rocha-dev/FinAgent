"""
Testes do guardrail numérico: todo número do texto precisa vir das métricas calculadas.
"""

import pytest

from sisanalisefinanceira.guardrails.numeric import NumericGuardrail, allowed_values_from_analysis
from sisanalisefinanceira.models import QuantAnalysisMetrics


@pytest.fixture
def quant():
    return QuantAnalysisMetrics(
        symbol="PETR4",
        moving_average=[151.25, 151.75, 152.4],
        volatility=1.49,
        mean_price=153.2857,
        max_price=156.5,
        min_price=150.0,
        std_dev=2.288,
    )


@pytest.fixture
def guardrail(quant):
    return NumericGuardrail(
        allowed_values_from_analysis(quant, n_points=7, window=2), ignore_terms=["PETR4"]
    )


@pytest.mark.parametrize(
    "text",
    [
        "O preço médio foi de 153.2857, com volatilidade de 1.49%.",  # exato
        "O preço médio ficou em torno de 153.29 e a máxima chegou a 156.5.",  # arredondado
        "Preço médio de 153,29 e mínima de 150.",  # vírgula / inteiro
        "Foram analisados 7 pontos com média móvel de janela 2.",  # contagem e janela
        "A última média móvel foi 152.4 e o desvio padrão 2.29.",  # média móvel / arredondado
        "PETR4 apresentou comportamento estável.",  # dígito do símbolo ignorado
        "O ativo oscilou pouco no período analisado.",  # sem números
    ],
)
def test_aceita_numeros_que_vieram_do_calculo(guardrail, text):
    result = guardrail.check(text)
    assert result.ok, result.violations


@pytest.mark.parametrize(
    "text,invented",
    [
        ("A expectativa é de alta de 12% nos próximos meses.", "12"),
        ("O preço-alvo para o ativo é 170.00.", "170.00"),
        ("Nos últimos 30 dias o ativo subiu.", "30"),
        ("A volatilidade foi de 1.94%.", "1.94"),  # dígitos trocados
        ("O preço médio foi de 153.3857.", "153.3857"),  # um dígito alterado
        ("Houve queda de -1.49% no período.", "-1.49"),  # sinal invertido
        ("Relatório referente a 2026.", "2026"),  # data
        ("O preço médio arredondado é 153.30.", "153.30"),  # arredondamento errado
    ],
)
def test_bloqueia_numero_inventado(guardrail, text, invented):
    result = guardrail.check(text)
    assert not result.ok
    assert invented in result.violations


def test_lista_todos_os_numeros_bloqueados(guardrail):
    result = guardrail.check("Alta de 12% em 30 dias, com preço médio de 153.29.")
    assert result.violations == ["12", "30"]
    assert any(m.startswith("153.29=") for m in result.matched)


def test_arredondamento_comercial_meio_para_cima():
    quant = QuantAnalysisMetrics(symbol="X", mean_price=2.675, volatility=1.0)
    g = NumericGuardrail(allowed_values_from_analysis(quant, n_points=3, window=2))
    assert g.check("Preço médio de 2.68.").ok  # round() do Python daria 2.67
    assert not g.check("Preço médio de 2.67.").ok
