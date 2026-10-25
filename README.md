# 📊 FinAgent — Agent-Based Financial Analysis with Deterministic Numbers

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](./LICENSE)

FinAgent analyzes market data (stocks and currencies) with a pipeline of specialized agents and produces an executive report in Markdown.
Its design principle: **every number in the report is computed by code** — a language model never does arithmetic — and the report is cross-checked against the computed metrics.

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

## Running

```bash
pip install -r requirements.txt

# StateGraph-style (default), sample data
python -m sisanalisefinanceira.cli --symbol AAPL --engine stategraph

# Chain-style
python -m sisanalisefinanceira.cli --symbol USD/BRL --engine chain

# Try live data from Yahoo Finance (may hit rate limits)
python -m sisanalisefinanceira.cli --symbol PETR4 --no-mock
```

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

Covers the data collector (including the sample-data fallback), quantitative calculations and edge cases (NaN values, windows larger than the data), configuration, and architecture boundaries.

## Roadmap — LLM with a numerical guardrail

The next step is to let an LLM write the report narrative, with the audit turned into a strict **guardrail**: any number in the LLM's text that does not come from the calculation blocks the report (today such numbers are only logged). The deterministic pipeline already provides the computed metrics and the number extraction; the LLM slot and the strict mode are the missing pieces.

In progress: infrastructure layer (`src/`) with PostgreSQL connection pools and a LangGraph checkpointer spike for resumable runs.

## Known limitations

| Item | Status | Detail |
|---|---|---|
| LLM at runtime | ❌ Not yet | Report text is a fixed template; see roadmap |
| LangGraph / CrewAI libraries | ❌ Not used | Orchestrators are own implementations of the patterns |
| Live data | ⚠️ Partial | Yahoo Finance is rate-limited; sample data is the safe default |
| Portfolio optimization | 🧪 Experimental | `optimize_weights_tool` uses SciPy when available, otherwise equal weights |
| Strict numerical audit | ⚠️ Partial | Unmatched numbers are logged, not yet blocked |
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
│   └── report_writer.py     # Markdown template + numerical audit
├── orchestrators/
│   ├── crewai_orchestrator.py     # chain-style pattern
│   └── langgraph_orchestrator.py  # stategraph-style pattern
└── utils/logging.py
src/                         # infrastructure layer (in progress)
tests/                       # pytest suite
reports/                     # generated reports
```

## License

MIT — see [LICENSE](./LICENSE).
