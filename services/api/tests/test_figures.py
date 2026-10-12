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
