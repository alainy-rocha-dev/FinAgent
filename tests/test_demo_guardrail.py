"""The offline demo must keep matching what the README and the GIF show."""

from eval import demo_guardrail
from sisanalisefinanceira.agents.data_collector import DataCollectorAgent
from sisanalisefinanceira.agents.narrative_writer import NarrativeWriterAgent
from sisanalisefinanceira.agents.quant_analyst import QuantAnalystAgent


def test_demo_blocks_then_approves():
    raw = DataCollectorAgent(use_mock=True).fetch_data(demo_guardrail.SYMBOL)
    quant = QuantAnalystAgent().analyze(raw)
    llm = demo_guardrail.ScriptedLLM(demo_guardrail.SCRIPTED_ANSWERS)
    result = NarrativeWriterAgent(llm, max_attempts=3).write(raw, quant)

    assert result.status == "llm_repaired"
    assert result.attempts == 2
    assert sorted(result.blocked_per_attempt[0]) == ["1.35", "110", "30"]


def test_demo_runs(capsys, monkeypatch):
    monkeypatch.setattr("sys.argv", ["demo_guardrail"])
    assert demo_guardrail.main() == 0
    assert "APPROVED" in capsys.readouterr().out
