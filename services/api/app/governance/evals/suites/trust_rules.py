"""Trust Score stage 1: the demo fraud stories are caught and genuine leads stay clear (free); instructions in notes
change nothing (free); and deterministic fraud mutations show what the rules still catch (live)."""
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select

from app.governance import golden
from app.governance.evals.framework import CaseResult, EvalContext, SuiteResult, every_case, rate, run_case, scratch_db, suite
from app.governance.evals.suites.aml_scenarios import build
from app.governance.redteam import FRAUD_MUTATIONS
from app.models import Lead
from app.seed.leads import seed_demo_leads
from app.services import aml
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


def _verdict(report) -> dict:
    return {"score": report.score, "band": report.band, "signals": sorted(s.code for s in report.signals)}


@suite("trust_rules", kind="red_team")
def fixed_attacks(ctx: EvalContext) -> SuiteResult:
    """Instructions written into a lead's notes change nothing the trust rules decide."""
    cases = []
    with scratch_db() as db:
        seed_demo_leads(db)
        db.flush()
        for c in golden.load("red_team/fixed")["cases"]:
            if c["target"] != "trust_rules":
                continue

            def check(c=c):
                lead = db.scalar(select(Lead).where(Lead.email == c["lead_email"]))
                before = _verdict(assess_trust(db, lead, None, None))
                saved, lead.notes = lead.notes, c["text"]
                try:
                    after = _verdict(assess_trust(db, lead, None, None))
                finally:
                    lead.notes = saved
                held = before == after
                return CaseResult(c["id"], "pass" if held else "fail", expected=before,
                                  actual={"attack": c["text"], "output": after},
                                  detail=c["why"] if held else f"The notes changed the trust result. {c['why']}")
            cases.append(run_case(c["id"], check))
    return every_case("trust_rules", "red_team", "free", cases,
                      bar="Instructions in a lead's notes change no trust score, band or signal")


MUTATION_BAR = 0.8
MUTATION_DAY = date(2026, 10, 12)


def _mutation_lead(db, n: int, *, email: str, device: str, ip_hash: str, minutes_ago: int) -> Lead:
    lead = Lead(source="web", full_name=f"Mutation Lead {n}", email=email, phone=f"+1617555{n:04d}", country="US",
                goals="Grow my savings over the long term", horizon_years=15, investable_usd=Decimal("40000"),
                monthly_usd=Decimal("500"), source_of_funds="salary", device_id=device, ip_hash=ip_hash)
    lead.created_at = datetime.combine(MUTATION_DAY, time(15), tzinfo=timezone.utc) - timedelta(minutes=minutes_ago)
    db.add(lead)
    db.flush()
    return lead


def _caught(m: dict) -> tuple[bool, dict]:
    with scratch_db() as db:
        if m["kind"] == "structuring_amount":
            case = {"accounts": [{"number": "ACC-0501", "full_name": "Mutation Client", "email": "mutation@example.test",
                                  "country": "US", "opened_on": "2025-01-02"}],
                    "instructions": [{"account": "ACC-0501", "type": "subscribe", "fund": "ATR-BAL", "amount": str(a),
                                      "day": (MUTATION_DAY - timedelta(days=6 - 2 * k)).isoformat(), "state": "accepted"}
                                     for k, a in enumerate(m["amounts"])]}
            build(db, case)
            findings = aml.structuring(db, MUTATION_DAY)
            return bool(findings), {"amounts": m["amounts"], "alerts": len(findings)}
        if m["kind"] == "new_throwaway_domain":
            lead = _mutation_lead(db, 1, email=m["email"], device="mutation-device", ip_hash="mutation-ip", minutes_ago=5)
            report = assess_trust(db, lead, None, None)
            return report.band != "clear", {"email": m["email"], **_verdict(report)}
        leads = [_mutation_lead(db, k + 1, email=f"rotated{k}.{m['id']}@example.test", device=device,
                                ip_hash=m["ip_hash"], minutes_ago=50 - 20 * k) for k, device in enumerate(m["devices"])]
        reports = [assess_trust(db, lead, None, None) for lead in leads]
        return any(r.band != "clear" for r in reports), {"devices": m["devices"], "bands": [r.band for r in reports]}


@suite("trust_rules", kind="red_team", tier="live")
def fraud_mutations(ctx: EvalContext) -> SuiteResult:
    """Deterministic fraud mutations from a fixed seed: what the rules still catch. Misses are reported, never hidden;
    the trust rules have no fallback, so this suite never trips a breaker."""
    cases = []
    for m in FRAUD_MUTATIONS:
        def check(m=m):
            caught, output = _caught(m)
            return CaseResult(m["id"], "pass" if caught else "fail", expected="caught",
                              actual={"attack": m["kind"], "output": output},
                              detail=m["why"] + (" Caught." if caught else " Missed: a limitation of the fixed rules."))
        cases.append(run_case(m["id"], check))
    caught = sum(c.outcome == "pass" for c in cases)
    return rate("trust_rules", "red_team", "live", cases,
                bar=f"At least {MUTATION_BAR:.0%} of fraud mutations caught",
                metric=f"{caught} of {len(cases)} mutations caught", value=caught / len(cases) if cases else None,
                threshold=MUTATION_BAR)
