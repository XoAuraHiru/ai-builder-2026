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
    r"(?P<usd>(?:US)?\$\s?(?P<amount>\d[\d,]*(?:\.\d+)?)(?:\s?(?P<unit>thousand|million|billion|[kKmMbB])\b)?)"
    r"|(?P<pct>(?P<percent>\d+(?:\.\d+)?)\s?(?:%|percent\b))")
UNITS = {"k": 1e3, "thousand": 1e3, "m": 1e6, "million": 1e6, "b": 1e9, "billion": 1e9}
ALWAYS_ALLOWED = {0.0, 100.0}


def _decimals(digits: str) -> int:
    return len(digits.split(".")[1]) if "." in digits else 0


def figures_in(text: str) -> list[tuple[str, float, float]]:
    """Each money or percentage figure as (as written, value, half the precision it was written to)."""
    found = []
    for m in FIGURE.finditer(text):
        if m.group("usd"):
            digits = m.group("amount").replace(",", "")
            unit = UNITS.get((m.group("unit") or "").lower(), 1.0)
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


def unsupported_figures(text: str, allowed: Iterable[float]) -> list[str]:
    pool = set(allowed) | ALWAYS_ALLOWED
    bad = []
    for written, value, half in figures_in(text):
        if not any(abs(value - a) <= half + 1e-9 or abs(value - a) <= 0.005 * a for a in pool):
            bad.append(written)
    return bad
