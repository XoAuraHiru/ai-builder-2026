from app.ai.figures import collect_numbers, unsupported_figures


def test_rounded_figures_match_engine_values():
    allowed = collect_numbers({"median": 412_345.67, "chance": 72.4, "p10": "1,234,567"})
    text = "A median of $412,346, about $412k or $0.4 million, a 72% chance, and $1.2 million at the low end."
    assert unsupported_figures(text, allowed) == []


def test_invented_figures_are_reported_as_written():
    assert unsupported_figures("You could reach $500,000, growing 433% a year.", {412_345.67, 72.4}) == ["$500,000", "433%"]


def test_currency_prefixes_and_percent_words():
    assert unsupported_figures("It fell 31.2 percent in 2008 and lost US$4,100.", {31.2, 4100.0}) == []


def test_numbers_are_collected_from_nested_facts():
    facts = {"a": [1, {"b": "2,500"}], "c": "worst month -8.1%", "d": True, "e": None}
    assert collect_numbers(facts) == {1.0, 2500.0, 8.1}


def test_amounts_written_with_usd_are_checked_too():
    allowed = {118_605.0, 354_245.0}
    text = "You pay in 118605 USD and the middle outcome is USD 354,245, but 999,999 dollars is not in the facts."
    assert unsupported_figures(text, allowed) == ["999,999 dollars"]


def test_facts_are_presented_with_their_units_for_the_model():
    from app.services.narrative import present

    facts = {"median_outcome_usd": 354245, "chance_of_goal_pct": 72.4, "years": 15, "worst_12_months_pct": -33.7,
             "scenarios": [{"fees_cost_over_period_usd": 9918.4, "name": "Balanced"}], "goal_usd": None}
    assert present(facts) == {"median_outcome_usd": "$354,245", "chance_of_goal_pct": "72.4%", "years": 15,
                              "worst_12_months_pct": "-33.7%",
                              "scenarios": [{"fees_cost_over_period_usd": "$9,918", "name": "Balanced"}], "goal_usd": None}


def test_only_money_and_percentage_facts_can_vouch_for_a_figure():
    from app.ai.figures import collect_figures

    facts = {"simulated_paths": 10000, "years": 15, "reader_risk_band": 3, "median_outcome_usd": 354245,
             "worst_month": {"month": "2008-10", "pct": -14.2}, "share_of_risk_pct": {"Atrium Growth": 66.8},
             "warnings": ["NVIDIA Corp is 6.9% of your portfolio."], "history_window": "July 2007 to September 2026"}
    pool = collect_figures(facts)
    assert unsupported_figures("an invented $10,000 and 15%", pool) == ["$10,000", "15%"]
    assert unsupported_figures("$354,245, a 14.2% fall, 66.8% of the risk and 6.9% in NVIDIA", pool) == []
