"""
Guardrail numérico: bloqueia qualquer número de um texto que não tenha vindo do cálculo determinístico.

Regra: todo número citado no texto precisa corresponder a um valor permitido (métricas calculadas,
contagem de pontos, janela da média móvel), aceitando apenas:
  - o valor exato, ou
  - o valor arredondado para menos casas decimais (ex.: 153.2857 -> 153.29 ou 153),
  - vírgula ou ponto como separador decimal (ex.: 153,29),
  - sufixo de porcentagem (ex.: 1.49%).

Qualquer outro número (prazo inventado, preço-alvo, percentual de retorno, data) é uma violação.
O guardrail não usa LLM: é uma verificação determinística e auditável.
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

# Número com separador decimal opcional (ponto ou vírgula) e sinal opcional.
# Não captura dígitos colados em letras (ex.: o "4" de PETR4 ou o "3" de "gpt3").
_NUMBER_RE = re.compile(r"(?<![\w])-?\d+(?:[.,]\d+)?(?![\w])")

_TOLERANCE = 1e-9


@dataclass
class AllowedValue:
    """Valor que o texto pode citar, com o nome da métrica de origem."""

    name: str
    value: float


@dataclass
class GuardrailResult:
    """Resultado da verificação de um texto."""

    ok: bool
    violations: list[str] = field(default_factory=list)
    matched: list[str] = field(default_factory=list)

    def violation_message(self) -> str:
        return ", ".join(self.violations)


def _decimals(token: str) -> int:
    for sep in (".", ","):
        if sep in token:
            return len(token.split(sep, 1)[1])
    return 0


def _to_float(token: str) -> float:
    return float(token.replace(",", "."))


def _round_half_up(value: float, places: int) -> Decimal:
    """Arredonda como uma pessoa faria (2.675 -> 2.68), sem o viés binário do round() do Python."""
    quantum = Decimal(1).scaleb(-places)
    return Decimal(repr(value)).quantize(quantum, rounding=ROUND_HALF_UP)


class NumericGuardrail:
    """Confere se todo número de um texto pertence ao conjunto de valores permitidos."""

    def __init__(self, allowed: Iterable[AllowedValue], ignore_terms: Iterable[str] | None = None):
        self.allowed = [a for a in allowed if a.value is not None and not math.isnan(a.value)]
        # Termos removidos antes da extração (ex.: o símbolo do ativo "PETR4", "USD/BRL").
        self.ignore_terms = [t for t in (ignore_terms or []) if t]

    def _strip_ignored(self, text: str) -> str:
        for term in sorted(self.ignore_terms, key=len, reverse=True):
            text = re.sub(re.escape(term), " ", text, flags=re.IGNORECASE)
        return text

    def _match(self, token: str) -> AllowedValue | None:
        # O sinal conta: "-1.49%" não é a volatilidade de 1.49%.
        number = _to_float(token)
        places = _decimals(token)
        for candidate in self.allowed:
            target = candidate.value
            if abs(number - target) <= _TOLERANCE:
                return candidate
            # Arredondamento comercial (meio para cima) para menos casas decimais.
            if abs(float(_round_half_up(target, places)) - number) <= _TOLERANCE:
                return candidate
        return None

    def check(self, text: str) -> GuardrailResult:
        cleaned = self._strip_ignored(text)
        violations: list[str] = []
        matched: list[str] = []
        for token in _NUMBER_RE.findall(cleaned):
            hit = self._match(token)
            if hit is None:
                if token not in violations:
                    violations.append(token)
            else:
                matched.append(f"{token}={hit.name}")
        return GuardrailResult(ok=not violations, violations=violations, matched=matched)


def allowed_values_from_analysis(quant, n_points: int, window: int) -> list[AllowedValue]:
    """Monta o conjunto de valores permitidos a partir das métricas calculadas."""
    values = [
        AllowedValue("preco_medio", quant.mean_price),
        AllowedValue("preco_maximo", quant.max_price),
        AllowedValue("preco_minimo", quant.min_price),
        AllowedValue("desvio_padrao", quant.std_dev),
        AllowedValue("volatilidade_pct", quant.volatility),
        AllowedValue("pontos_de_dados", float(n_points)),
        AllowedValue("janela_media_movel", float(window)),
    ]
    for i, ma in enumerate(quant.moving_average, start=1):
        values.append(AllowedValue(f"media_movel_{i}", ma))
    if quant.moving_average:
        values.append(AllowedValue("media_movel_ultima", quant.moving_average[-1]))
    return values
