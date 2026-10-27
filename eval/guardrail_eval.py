"""
Avaliação do guardrail numérico.

Modo offline (padrão, determinístico, sem LLM):
    python -m eval.guardrail_eval
  Gera frases legítimas (números certos, com arredondamento e vírgula) e frases adversariais
  (números alterados ou inventados) a partir das métricas de cada ativo de exemplo e mede:
    - taxa de detecção (frases adversariais bloqueadas)
    - taxa de falso positivo (frases legítimas bloqueadas)
  Inclui de propósito uma categoria que o guardrail NÃO pega (número certo na métrica errada),
  para deixar o ponto cego medido e documentado.

Modo live (usa o LLM configurado em GROQ_API_KEY ou OPENAI_API_KEY):
    python -m eval.guardrail_eval --live --runs 5
  Pede a narrativa ao LLM para cada ativo e registra quantas foram aprovadas de primeira,
  aprovadas após reparo ou bloqueadas (fallback para o template).
"""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter, defaultdict
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

from sisanalisefinanceira.agents.data_collector import DataCollectorAgent
from sisanalisefinanceira.agents.quant_analyst import QuantAnalystAgent
from sisanalisefinanceira.config import settings
from sisanalisefinanceira.guardrails.numeric import NumericGuardrail, allowed_values_from_analysis

SYMBOLS = ["AAPL", "PETR4", "USD/BRL", "MSFT", "VALE3"]


def _fmt(value: float, places: int, comma: bool = False) -> str:
    # Arredondamento comercial (156.5 -> 157), o mesmo que uma pessoa usaria ao escrever o relatório.
    text = str(Decimal(repr(value)).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP))
    return text.replace(".", ",") if comma else text


def legit_sentences(q, n_points: int, window: int) -> list[tuple[str, str]]:
    s = []
    s.append(("exato", f"O preço médio foi {q.mean_price} e a volatilidade {q.volatility}%."))
    s.append(("arredondado", f"O preço médio ficou próximo de {_fmt(q.mean_price, 2)}."))
    s.append(("arredondado", f"O desvio padrão foi de aproximadamente {_fmt(q.std_dev, 1)}."))
    s.append(
        (
            "inteiro",
            f"A máxima foi cerca de {_fmt(q.max_price, 0)} e a mínima {_fmt(q.min_price, 0)}.",
        )
    )
    s.append(("virgula", f"Preço médio de {_fmt(q.mean_price, 2, comma=True)} no período."))
    s.append(
        ("contagem", f"Foram analisados {n_points} pontos, com média móvel de janela {window}.")
    )
    if q.moving_average:
        s.append(("media_movel", f"A última média móvel foi {q.moving_average[-1]}."))
    s.append(("sem_numero", f"O ativo {q.symbol} mostrou oscilação moderada."))
    return s


def adversarial_sentences(q) -> list[tuple[str, str]]:
    m = q.mean_price
    v = q.volatility
    s = []
    s.append(("digito_alterado", f"O preço médio foi {_fmt(m + 0.1, 4)}."))
    s.append(("ultima_casa", f"O preço médio foi {_fmt(m + 0.0001, 4)}."))
    s.append(("arredondamento_errado", f"O preço médio ficou em {_fmt(m + 0.01, 2)}."))
    s.append(("sinal_invertido", f"A variação foi de -{v}%."))
    s.append(("escala_10x", f"A volatilidade foi de {_fmt(v * 10, 2)}%."))
    s.append(("percentual_inventado", "A expectativa é de valorização de 12% no trimestre."))
    s.append(("prazo_inventado", "Nos últimos 30 dias o ativo acumulou alta."))
    s.append(("preco_alvo", f"O preço-alvo projetado é {_fmt(q.max_price * 1.1, 2)}."))
    s.append(("data", "A análise considera o fechamento de 2026."))
    s.append(("milhar_inventado", "O volume negociado superou 1.500 contratos."))
    return s


def blind_spot_sentences(q) -> list[tuple[str, str]]:
    # Número legítimo usado para a métrica errada: o guardrail confere o número, não o significado.
    return [
        ("metrica_trocada", f"A volatilidade foi de {q.max_price}%."),
        ("metrica_trocada", f"O preço médio foi {q.min_price}."),
    ]


def run_offline() -> dict:
    collector = DataCollectorAgent(use_mock=True)
    analyst = QuantAnalystAgent()
    window = settings.default_moving_average_window

    totals = {"legit": [0, 0], "adversarial": [0, 0], "blind_spot": [0, 0]}  # [bloqueadas, total]
    by_cat: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    false_positives = []

    for symbol in SYMBOLS:
        raw = collector.fetch_data(symbol)
        q = analyst.analyze(raw)
        if q.error_code:
            continue
        g = NumericGuardrail(
            allowed_values_from_analysis(q, n_points=len(raw.price_history), window=window),
            ignore_terms=[q.symbol],
        )
        for group, sentences in (
            ("legit", legit_sentences(q, len(raw.price_history), window)),
            ("adversarial", adversarial_sentences(q)),
            ("blind_spot", blind_spot_sentences(q)),
        ):
            for cat, text in sentences:
                blocked = not g.check(text).ok
                totals[group][0] += int(blocked)
                totals[group][1] += 1
                by_cat[f"{group}:{cat}"][0] += int(blocked)
                by_cat[f"{group}:{cat}"][1] += 1
                if group == "legit" and blocked:
                    false_positives.append({"symbol": symbol, "text": text})

    def rate(pair):
        return round(pair[0] / pair[1], 4) if pair[1] else None

    return {
        "mode": "offline",
        "symbols": SYMBOLS,
        "detection_rate": rate(totals["adversarial"]),
        "false_positive_rate": rate(totals["legit"]),
        "blind_spot_detection_rate": rate(totals["blind_spot"]),
        "counts": {k: {"blocked": v[0], "total": v[1]} for k, v in totals.items()},
        "by_category": {k: {"blocked": v[0], "total": v[1]} for k, v in sorted(by_cat.items())},
        "false_positives": false_positives,
    }


def run_live(runs: int) -> dict:
    from sisanalisefinanceira.agents.narrative_writer import NarrativeWriterAgent
    from sisanalisefinanceira.llm.client import client_from_env

    llm = client_from_env()
    if llm is None:
        raise SystemExit("Defina GROQ_API_KEY ou OPENAI_API_KEY para o modo --live.")
    collector = DataCollectorAgent(use_mock=True)
    analyst = QuantAnalystAgent()
    writer = NarrativeWriterAgent(llm, window=settings.default_moving_average_window)

    statuses: Counter = Counter()
    blocked_numbers: Counter = Counter()
    samples = []
    for symbol in SYMBOLS:
        raw = collector.fetch_data(symbol)
        q = analyst.analyze(raw)
        if q.error_code:
            continue
        for _ in range(runs):
            r = writer.write(raw, q)
            statuses[r.status] += 1
            for attempt in r.blocked_per_attempt:
                blocked_numbers.update(attempt)
            samples.append(
                {
                    "symbol": symbol,
                    "status": r.status,
                    "attempts": r.attempts,
                    "blocked": r.blocked_per_attempt,
                    "text": r.text,
                }
            )
    total = sum(statuses.values())
    return {
        "mode": "live",
        "model": llm.label,
        "runs_per_symbol": runs,
        "total": total,
        "statuses": dict(statuses),
        "approved_first_try": round(statuses["llm"] / total, 4) if total else None,
        "approved_after_repair": round(statuses["llm_repaired"] / total, 4) if total else None,
        "fell_back_to_template": round(statuses["fallback_template"] / total, 4) if total else None,
        "most_blocked_numbers": blocked_numbers.most_common(10),
        "samples": samples,
    }


def main():
    parser = argparse.ArgumentParser(description="Avaliação do guardrail numérico do FinAgent")
    parser.add_argument("--live", action="store_true", help="Usa o LLM real (requer chave de API)")
    parser.add_argument("--runs", type=int, default=5, help="Execuções por ativo no modo live")
    args = parser.parse_args()

    report = run_live(args.runs) if args.live else run_offline()
    os.makedirs("eval/results", exist_ok=True)
    path = f"eval/results/guardrail_{report['mode']}_{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    summary = {
        k: v for k, v in report.items() if k not in ("samples", "by_category", "false_positives")
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if report["mode"] == "offline":
        print("\nPor categoria (bloqueadas/total):")
        for cat, c in report["by_category"].items():
            print(f"  {cat:40s} {c['blocked']}/{c['total']}")
    print(f"\nRelatório salvo em {path}")


if __name__ == "__main__":
    main()
