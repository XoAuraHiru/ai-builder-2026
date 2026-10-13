"""Statement reading: the saved Bank Statement Parser output of the sample statement maps to its golden lines and the
balances reconcile; three messy CSVs parse to their golden lines. The PDF is never read live by default."""
from decimal import Decimal

from app.governance import golden
from app.governance.evals.framework import CaseResult, EvalContext, SuiteResult, every_case, run_case, suite
from app.services.statements import extraction_from_document, parse_csv


def _document():
    from google.cloud import documentai

    text = golden.path("statement_reader/docai_sample.json").read_text(encoding="utf-8")
    return documentai.Document.from_json(text, ignore_unknown_fields=True)


def _signed(line: dict) -> Decimal:
    amount = Decimal(line["amount"])
    return amount if line["side"] == "credit" else -amount


def _flat(text: str) -> str:
    return " ".join(text.split()).upper()


@suite("statement_reader")
def saved_document(ctx: EvalContext) -> SuiteResult:
    golden_data = golden.load("statement_reader/expected")
    extraction = extraction_from_document(_document())
    read = {_flat(x.description): x for x in extraction.lines}
    cases = []
    for c in golden_data["cases"]:
        def check(c=c):
            line = read.get(_flat(c["description"]))
            expected = {"date": c["date"], "amount": f"{_signed(c):.2f}"}
            if line is None:
                return CaseResult(c["id"], "fail", expected=expected, actual=None,
                                  detail=f"The mapping did not read {c['description']!r}. {c['why']}")
            actual = {"date": line.value_date.isoformat(), "amount": f"{line.amount:.2f}"}
            return CaseResult(c["id"], "pass" if actual == expected else "fail", expected=expected, actual=actual,
                              detail=c["why"])
        cases.append(run_case(c["id"], check))

    def balances():
        opening, closing = Decimal(golden_data["opening"]), Decimal(golden_data["closing"])
        total = sum((x.amount for x in extraction.lines), Decimal("0"))
        ok = opening + total == closing and len(extraction.lines) == len(golden_data["cases"])
        return CaseResult("balances", "pass" if ok else "fail",
                          expected={"closing": f"{closing:.2f}", "lines": len(golden_data["cases"])},
                          actual={"opening_plus_lines": f"{opening + total:.2f}", "lines": len(extraction.lines)},
                          detail="The opening balance plus the credits less the debits the mapping read must equal "
                                 "the closing balance, with no line missed or added.")
    cases.append(run_case("balances", balances))
    return every_case("statement_reader", "golden", "free", cases,
                      bar="Every line of the saved statement maps to its golden date, amount and side, and the "
                          "balances reconcile")


@suite("statement_reader")
def messy_csvs(ctx: EvalContext) -> SuiteResult:
    expected_all = golden.load("statement_reader/expected")["csv"]
    cases = []
    for name, spec in expected_all.items():
        def check(name=name, spec=spec):
            extraction = parse_csv(golden.path(f"statement_reader/{name}.csv").read_bytes())
            actual = [{"date": x.value_date.isoformat(), "amount": f"{x.amount:.2f}", "description": x.description}
                      for x in extraction.lines]
            expected = [{**x, "amount": f"{Decimal(x['amount']):.2f}"} for x in spec["lines"]]
            return CaseResult(name, "pass" if actual == expected else "fail", expected=expected, actual=actual,
                              detail=spec["why"])
        cases.append(run_case(name, check))
    return every_case("statement_reader", "golden", "free", cases, bar="All three messy CSVs parse to their golden lines")
