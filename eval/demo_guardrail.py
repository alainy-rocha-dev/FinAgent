"""
Offline demo of the numeric guardrail — no API key needed.

Runs the real pipeline pieces (data collector with sample data, quant analyst, NarrativeWriterAgent,
NumericGuardrail). Only the LLM is scripted: its two answers are fixed strings, so the demo is
reproducible. The first answer contains the kinds of errors seen in practice (a truncated number,
an invented price target and an invented horizon); the second is the rewrite after the repair prompt.

For results with a real model, see `python -m eval.guardrail_eval --live`.

Usage:
    python -m eval.demo_guardrail
    python -m eval.demo_guardrail --delay 0.6   # slower, for screen recordings
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
import time

from sisanalisefinanceira.agents.data_collector import DataCollectorAgent
from sisanalisefinanceira.agents.narrative_writer import NarrativeWriterAgent
from sisanalisefinanceira.agents.quant_analyst import QuantAnalystAgent

SYMBOL = "MSFT"

SCRIPTED_ANSWERS = [
    # Attempt 1: std dev truncated (1.3558 -> 1.35 instead of 1.36), invented target and horizon.
    "O ativo MSFT teve preço médio de 102.0143, desvio padrão de 1.35 e volatilidade de 1.33%. "
    "Mantida a tendência, o preço pode chegar a 110 em 30 dias.",
    # Attempt 2: rewritten after receiving the list of blocked numbers.
    "O ativo MSFT teve preço médio de 102.0143, desvio padrão de 1.36 e volatilidade de 1.33%. "
    "As médias móveis subiram de 100.75 para 103.25 ao longo do período.",
]

USE_COLOR = sys.stdout.isatty()


def _c(text: str, code: str) -> str:
    return f"\033[{code}m{text}\033[0m" if USE_COLOR else text


class ScriptedLLM:
    """Stands in for the LLM client: returns the scripted answers in order."""

    label = "scripted LLM (offline demo)"

    def __init__(self, answers: list[str]):
        self.answers = list(answers)
        self.calls = 0

    def __call__(self, system_prompt: str, user_prompt: str) -> str:
        answer = self.answers[min(self.calls, len(self.answers) - 1)]
        self.calls += 1
        return answer


def _highlight(text: str, blocked: list[str]) -> str:
    """Marks blocked numbers in red so they stand out in the terminal."""
    if not blocked:
        return text
    pattern = r"(?<![\w.,])(" + "|".join(re.escape(b) for b in blocked) + r")(?![\w]|[.,]\d)"
    return re.sub(pattern, lambda m: _c(f"[{m.group(1)}]", "1;31"), text)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--delay", type=float, default=0.0, help="pause between steps (seconds)")
    args = parser.parse_args()
    logging.disable(logging.CRITICAL)

    def step() -> None:
        if args.delay:
            time.sleep(args.delay)

    print(_c("FinAgent — numeric guardrail demo (offline, scripted LLM)", "1"))
    print()

    raw = DataCollectorAgent(use_mock=True).fetch_data(SYMBOL)
    quant = QuantAnalystAgent().analyze(raw)
    print(_c("1. Metrics computed by code", "1;36"))
    print(f"   mean price {quant.mean_price} | std dev {quant.std_dev} | volatility {quant.volatility}%")
    step()

    llm = ScriptedLLM(SCRIPTED_ANSWERS)
    agent = NarrativeWriterAgent(llm, max_attempts=3)
    result = agent.write(raw, quant)

    for i, blocked in enumerate(result.blocked_per_attempt, start=1):
        print()
        print(_c(f"2. LLM draft — attempt {i}", "1;36"))
        print("   " + _highlight(SCRIPTED_ANSWERS[i - 1], blocked))
        step()
        print(_c(f"   ✗ BLOCKED: {', '.join(blocked)} — not in the computed metrics", "1;31"))
        print("   → blocked numbers sent back to the LLM (repair loop)")
        step()

    print()
    if result.accepted:
        print(_c(f"3. LLM draft — attempt {result.attempts}", "1;36"))
        print("   " + result.text)
        step()
        print(_c("   ✓ APPROVED: every number matches a computed metric", "1;32"))
        print(f"   status: {result.status} | attempts: {result.attempts}")
    else:
        print(_c("3. Every attempt blocked — report falls back to the template text", "1;33"))
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
