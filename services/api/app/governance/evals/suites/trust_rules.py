"""Trust Score stage 1: the demo fraud stories are caught, and genuine leads stay clear."""
from sqlalchemy import select

from app.governance import golden
from app.governance.evals.framework import CaseResult, EvalContext, SuiteResult, every_case, run_case, scratch_db, suite
from app.models import Lead
from app.seed.leads import seed_demo_leads
from app.services.trust import assess_trust


@suite("trust_rules")
def demo_stories(ctx: EvalContext) -> SuiteResult:
    cases = []
    with scratch_db() as db:
        seed_demo_leads(db)
        db.flush()
        for c in golden.load("trust_rules/stories")["cases"]:
            def check(c=c):
                lead = db.scalar(select(Lead).where(Lead.email == c["lead_email"]))
                if lead is None:
                    return CaseResult(c["id"], "fail", detail=f"No seeded lead with {c['lead_email']}")
                report = assess_trust(db, lead, lead.enrichment, None)
                codes = sorted({s.code for s in report.signals})
                band_ok = report.band in c["expect_band_in"] or (report.blocked and "blocked" in c["expect_band_in"])
                # A fraud story must raise the signals named; a genuine lead must raise none at all.
                signals_ok = set(c["expect_signals"]) <= set(codes) if c["expect_signals"] else not codes
                ok = band_ok and signals_ok and (c["expect_signals"] or not report.blocked)
                return CaseResult(c["id"], "pass" if ok else "fail",
                                  expected={"band_in": c["expect_band_in"], "signals": c["expect_signals"]},
                                  actual={"band": report.band, "score": report.score, "blocked": report.blocked,
                                          "signals": codes},
                                  detail=c["why"])
            cases.append(run_case(c["id"], check))
    return every_case("trust_rules", "golden", "free", cases,
                      bar="All three fraud stories are flagged and all six genuine leads stay clear")
