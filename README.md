# 📊 FinAgent — Agent-Based Financial Analysis with Deterministic Numbers

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](./LICENSE)

FinAgent analyzes market data (stocks and currencies) with a pipeline of specialized agents and produces an executive report in Markdown.
Its design principle: **every number in the report is computed by code** — a language model never does arithmetic.
Optionally, an LLM writes the analysis in natural language, and a **numeric guardrail blocks any number in that text that did not come from the calculation**.

It uses [AgentPulse API](https://github.com/alainy-rocha-dev/AgentPulse-API) (folder `automacao_agentes`, as a git submodule) as the execution layer.

---

## How it works

```
DataCollectorAgent  →  QuantAnalystAgent  →  ReportWriterAgent  →  numerical audit
  (prices: Yahoo         (mean, std dev,        (Markdown report)     (report cross-checked
   Finance or mock)       volatility, moving                           against the computed
                          averages)                                    metrics)
```

1. **Data collector** — fetches historical prices from Yahoo Finance, with automatic fallback to sample data. When sample data is used, the report shows a visible **"⚠️ SIMULATED DATA"** banner.
2. **Quant analyst** — computes mean, max/min, standard deviation, volatility (%) and moving averages with Pandas/NumPy/SciPy, falling back to Python's `statistics`/`math`.
3. **Report writer** — fills a fixed Markdown template with the computed metrics.
4. **Numerical audit** — extracts the decimal numbers from the report and compares them with the computed metrics. Today the key metrics (mean price and volatility) must be present for the report to be accepted, and any other number that does not match a metric is logged.

### Two orchestration patterns, built from scratch

| Pattern | Flag | Behavior |
|---|---|---|
| **StateGraph-style** (default) | `--engine stategraph` | Iterative state machine with a strict iteration limit (`max_iter = 3`) and a `MAX_ITER_REACHED` safeguard |
| **Chain-style** | `--engine chain` | Linear sequence of tasks passing context forward |

Both are own implementations of these patterns — they do **not** use the LangGraph or CrewAI libraries.

## LLM narrative with a numeric guardrail

With `--narrative llm`, an LLM writes the analysis section of the report. It only enters the report if it passes the guardrail:

```
metrics (JSON) → LLM writes 2 paragraphs → numeric guardrail ──ok──→ report
                        ▲                        │
                        └── blocked numbers ─────┘  (repair loop, up to 3 attempts)
                                                 │
                                       still invalid → template text + note in the report
```

- **The guardrail is deterministic, not another LLM.** It extracts every number from the text and accepts it only if it equals a computed value — exactly, rounded half-up to fewer decimals, with comma or dot as decimal separator, or as a percentage. Anything else (a forecast, a price target, "30 days", a year, a flipped sign, a mistyped digit) is blocked.
- **Repair loop:** when text is blocked, the LLM receives the exact list of rejected numbers and rewrites it.
- **Fail-safe:** if the LLM keeps inventing numbers or the provider is down, the report uses the template text and says so. **No unaudited number reaches the report.**
- The report records which model wrote the text and which numbers were blocked before approval.
- The asset symbol goes into the prompt as data inside the metrics JSON, never as a loose instruction.

### Guardrail evaluation

`python -m eval.guardrail_eval` builds sentences from the real metrics of 5 sample assets and checks what the guardrail blocks (deterministic, no LLM; results in [`eval/results/`](eval/results/)):

| Set | Sentences | Blocked | Rate |
|---|---|---|---|
| Adversarial (altered or invented numbers, 10 categories) | 50 | 49 | **98% detection** |
| Legitimate (exact, rounded, comma, integer, counts) | 40 | 0 | **0% false positives** |
| Known blind spot (right number, wrong metric) | 10 | 0 | 0% — see limitations |

The single miss is the blind spot in disguise: a "wrongly rounded" mean (5.16) happened to equal one of the real moving averages, so the number exists in the calculation — it is just attached to the wrong metric.

To measure a real LLM: `python -m eval.guardrail_eval --live --runs 5` (counts approvals on the first try, after repair, and fallbacks).

## Running

```bash
pip install -r requirements.txt

# StateGraph-style (default), sample data
python -m sisanalisefinanceira.cli --symbol AAPL --engine stategraph

# Chain-style
python -m sisanalisefinanceira.cli --symbol USD/BRL --engine chain

# Try live data from Yahoo Finance (may hit rate limits)
python -m sisanalisefinanceira.cli --symbol PETR4 --no-mock

# LLM-written analysis, audited by the numeric guardrail
export GROQ_API_KEY=...        # or OPENAI_API_KEY (Windows PowerShell: $env:GROQ_API_KEY="...")
python -m sisanalisefinanceira.cli --symbol AAPL --narrative llm
```

Default models: `openai/gpt-oss-120b` on Groq, `gpt-4o-mini` on OpenAI (override with `FINAGENT_LLM_MODEL`). Without a key, `--narrative llm` falls back to the template.

Reports are saved in `reports/`.

### Sample output (excerpt, sample data)

```markdown
## 2. Deterministic Quantitative Indicators

| Indicator      | Computed value | Source / method          |
|----------------|----------------|--------------------------|
| Mean price     | 153.2857       | Pandas / Math mean()     |
| Std deviation  | 2.288          | NumPy / Math std()       |
| Volatility (%) | 1.49%          | (Std / Mean) * 100       |
```

*(Reports are generated in Portuguese; translated here.)*

## Tests

```bash
pytest tests/ -v
```

Covers the data collector (including the sample-data fallback), quantitative calculations and edge cases (NaN values, windows larger than the data), the numeric guardrail (accepted formats and 8 kinds of invented numbers), the narrative agent with a fake LLM (approval, repair, fallback, provider failure, blocked text never reaching the report), configuration, and architecture boundaries.

## Roadmap

- **Semantic check:** catch a correct number attached to the wrong metric (the guardrail's blind spot), e.g. by asking the LLM for structured claims (`metric → value`) and checking each pair.
- **Live LLM measurements** with `eval.guardrail_eval --live` across providers.

In progress: infrastructure layer (`src/`) with PostgreSQL connection pools and a LangGraph checkpointer spike for resumable runs.

## Known limitations

| Item | Status | Detail |
|---|---|---|
| LLM narrative | ✅ Optional | `--narrative llm`; template remains the default |
| Right number, wrong metric | ⚠️ Not detected | The guardrail checks that a number exists in the calculation, not which metric it describes |
| Live LLM measurements | ❌ Not yet published | Offline guardrail evaluation only; run `--live` to measure a real model |
| LangGraph / CrewAI libraries | ❌ Not used | Orchestrators are own implementations of the patterns |
| Live data | ⚠️ Partial | Yahoo Finance is rate-limited; sample data is the safe default |
| Portfolio optimization | 🧪 Experimental | `optimize_weights_tool` uses SciPy when available, otherwise equal weights |
| Template report audit | ⚠️ Partial | The fixed template is checked for key metrics; the strict guardrail applies to LLM text |
| Human-in-the-loop | ❌ Not yet | Planned |
| Benchmark between the two patterns | ❌ Not measured | Both implemented, no automated comparison |

## Project structure

```
sisanalisefinanceira/
├── cli.py                   # command-line interface
├── config.py                # settings (max_iter, mock, paths)
├── models.py                # Pydantic schemas
├── agents/
│   ├── data_collector.py    # API + sample-data fallback
│   ├── quant_analyst.py     # deterministic calculations
│   ├── narrative_writer.py  # LLM narrative + repair loop + fallback
│   └── report_writer.py     # Markdown template + numerical audit
├── guardrails/
│   └── numeric.py           # deterministic numeric guardrail
├── llm/
│   └── client.py            # Groq / OpenAI chat-completions client
├── orchestrators/
│   ├── crewai_orchestrator.py     # chain-style pattern
│   └── langgraph_orchestrator.py  # stategraph-style pattern
└── utils/logging.py
src/                         # infrastructure layer (in progress)
eval/guardrail_eval.py       # guardrail evaluation (offline / live)
tests/                       # pytest suite
reports/                     # generated reports
```

## License

MIT — see [LICENSE](./LICENSE).
