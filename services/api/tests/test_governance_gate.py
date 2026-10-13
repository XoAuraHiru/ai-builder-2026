"""The deploy gate: every free-tier suite passes on the committed code. Each feature's golden sets are covered here
automatically, because suites register themselves."""
from app.governance.evals.__main__ import main
from app.governance.evals.runner import run_evals


def test_every_free_suite_passes():
    report = run_evals("free")
    assert report.suites, "no suites were found"
    failures = [(s.model_key, s.kind, s.metric, [(c.case_id, c.outcome, c.detail) for c in s.cases if c.outcome != "pass"])
                for s in report.failures()]
    assert failures == []


def test_the_gate_exits_zero_when_everything_passes(capsys):
    assert main(["--tier", "free"]) == 0
    assert "suites passed" in capsys.readouterr().out
