"""Gemini explains numbers; it must not invent them.

Every dollar or percentage figure in AI-written prose must round to a figure the deterministic engines produced, at
the precision it was written to: "$1.2 million" matches 1,234,567 and "72%" matches 72.4. Anything else is reported,
and the prose is shown as unverified.
"""
from __future__ import annotations

import re
from collections.abc import Iterable
from decimal import Decimal

FIGURE = re.compile(
    r"(?P<usd>(?:US\$|\$|USD\s?)(?P<amount>\d[\d,]*(?:\.\d+)?)(?:\s?(?P<unit>thousand|million|billion|[kKmMbB])\b)?)"
    r"|(?P<usd_after>(?P<amount2>\d[\d,]*(?:\.\d+)?)\s?(?P<unit2>thousand|million|billion)?\s?(?:USD|dollars)\b)"
    r"|(?P<pct>(?P<percent>\d+(?:\.\d+)?)\s?(?:%|percent\b))")
UNITS = {"k": 1e3, "thousand": 1e3, "m": 1e6, "million": 1e6, "b": 1e9, "billion": 1e9}
ALWAYS_ALLOWED = {0.0, 100.0}


def _decimals(digits: str) -> int:
    return len(digits.split(".")[1]) if "." in digits else 0


def figures_in(text: str) -> list[tuple[str, float, float]]:
    """Each money or percentage figure as (as written, value, half the precision it was written to)."""
    found = []
    for m in FIGURE.finditer(text):
        if m.group("usd") or m.group("usd_after"):
            digits = (m.group("amount") or m.group("amount2")).replace(",", "")
            unit = UNITS.get((m.group("unit") or m.group("unit2") or "").lower(), 1.0)
            value, half = float(digits) * unit, 0.5 * 10 ** -_decimals(digits) * unit
        else:
            digits = m.group("percent")
            value, half = float(digits), 0.5 * 10 ** -_decimals(digits)
        found.append((m.group(0).strip().rstrip(","), value, half))
    return found


def collect_numbers(facts) -> set[float]:
    """Every number in a facts structure (dicts, lists, numbers, numeric strings), as absolute values."""
    out: set[float] = set()
    stack = [facts]
    while stack:
        item = stack.pop()
        if item is None or isinstance(item, bool):
            continue
        if isinstance(item, (int, float, Decimal)):
            out.add(abs(float(item)))
        elif isinstance(item, str):
            out.update(value for _, value, _ in figures_in(item))
            try:
                out.add(abs(float(item.replace(",", ""))))
            except ValueError:
                pass
        elif isinstance(item, dict):
            stack.extend(item.values())
        elif isinstance(item, (list, tuple, set)):
            stack.extend(item)
    return out


def _is_figure_key(key) -> bool:
    k = str(key).lower()
    return k in ("usd", "pct") or k.endswith(("_usd", "_pct")) or k.startswith("pct_") or "_usd_" in k or "_pct_" in k


def collect_figures(facts) -> set[float]:
    """The numbers that may vouch for a $ or % figure in prose: values under money or percentage keys ("_usd",
    "_pct") and $ or % figures written inside strings. Counts such as years or simulated paths cannot vouch for one."""
    out: set[float] = set()
    stack = [(facts, False)]
    while stack:
        item, figure = stack.pop()
        if item is None or isinstance(item, bool):
            continue
        if isinstance(item, (int, float, Decimal)):
            if figure:
                out.add(abs(float(item)))
        elif isinstance(item, str):
            out.update(value for _, value, _ in figures_in(item))
            if figure:
                try:
                    out.add(abs(float(item.replace(",", "").replace("$", "").rstrip("%"))))
                except ValueError:
                    pass
        elif isinstance(item, dict):
            stack.extend((value, figure or _is_figure_key(key)) for key, value in item.items())
        elif isinstance(item, (list, tuple, set)):
            stack.extend((value, figure) for value in item)
    return out


def unsupported_figures(text: str, allowed: Iterable[float]) -> list[str]:
    pool = set(allowed) | ALWAYS_ALLOWED
    bad = []
    for written, value, half in figures_in(text):
        if not any(abs(value - a) <= half + 1e-9 or abs(value - a) <= 0.005 * a for a in pool):
            bad.append(written)
    return bad
