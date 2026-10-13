"""Golden data: synthetic cases with known right answers. Every case says why its answer is right."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def load(name: str) -> dict:
    """Read golden/<name>.json; every case must carry a non-empty "why"."""
    data = json.loads((ROOT / f"{name}.json").read_text(encoding="utf-8"))
    missing = [c.get("id", "?") for c in data.get("cases", []) if not c.get("why")]
    if missing:
        raise ValueError(f"golden/{name}.json: cases without a why: {missing}")
    return data


def path(name: str) -> Path:
    return ROOT / name
