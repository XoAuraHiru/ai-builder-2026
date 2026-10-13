"""Run the evaluation suites.

  uv run python -m app.governance.evals --tier free           the deploy gate: free suites only, exit 1 on a failure
  python -m app.governance.evals --tier live --store          the atrium-evals job: every suite, results stored
"""
import argparse
import sys

from app.governance.evals.runner import RunReport, adopt_or_start, finish_failed, run_evals, store_run


def print_report(report: RunReport) -> None:
    for s in report.suites:
        print(f"{'PASS' if s.passed else 'FAIL'}  {s.model_key:<20} {s.kind:<10} {s.tier:<4}  {s.metric}  (bar: {s.bar})")
        for c in s.cases:
            if c.outcome != "pass":
                print(f"        {c.outcome:<5} {c.case_id}: {c.detail[:160]}")
    print(f"{sum(s.passed for s in report.suites)} of {len(report.suites)} suites passed; "
          f"AI cost ${report.cost_usd:.4f}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.governance.evals")
    parser.add_argument("--tier", choices=("free", "live"), default="free")
    parser.add_argument("--store", action="store_true", help="store the results in the database")
    parser.add_argument("--trigger", choices=("deploy", "button", "local"), default="local")
    parser.add_argument("--with-documents", action="store_true", help="include Document AI reads (costs $0.20)")
    args = parser.parse_args(argv)
    if not args.store:
        if args.tier == "live":
            parser.error("live runs store their results: add --store")
        report = run_evals("free")
        print_report(report)
        return 0 if report.passed else 1
    from app.db import SessionLocal, init_db

    init_db()
    with SessionLocal() as db:
        run = adopt_or_start(db, tier=args.tier, trigger=args.trigger)
        db.commit()
        try:
            llm = agent_model = None
            if args.tier == "live":
                from app.agents.runtime import get_agent_model
                from app.ai.llm import get_llm

                llm, agent_model = get_llm(), get_agent_model()
            report = run_evals(args.tier, llm=llm, agent_model=agent_model, with_documents=args.with_documents)
            store_run(db, report, run)
            from app.governance import monitoring

            monitoring.apply_monitoring_breakers(db)  # people's decisions are evidence too
            db.commit()
        except Exception as e:
            db.rollback()
            finish_failed(db, run, e)
            db.commit()
            raise
    print_report(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
