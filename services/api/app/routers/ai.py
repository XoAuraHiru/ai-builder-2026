from collections import defaultdict
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import CurrentUser, require_roles
from app.db import get_db
from app.models import AIDecision

router = APIRouter(prefix="/ai", tags=["ai"])


@router.get("/usage")
def usage(db: Session = Depends(get_db), user: CurrentUser = Depends(require_roles("staff"))):
    """What the AI layer has done and what it cost, from the AI decision log."""
    rows = db.scalars(select(AIDecision)).all()
    by_purpose: dict[str, dict] = defaultdict(lambda: {"count": 0, "cost_usd": Decimal("0")})
    for d in rows:
        by_purpose[d.purpose]["count"] += 1
        by_purpose[d.purpose]["cost_usd"] += d.cost_usd
    return {"decisions": len(rows), "tokens_in": sum(d.tokens_in for d in rows),
            "tokens_out": sum(d.tokens_out for d in rows),
            "cost_usd": str(sum((d.cost_usd for d in rows), Decimal("0"))),
            "by_purpose": {k: {"count": v["count"], "cost_usd": str(v["cost_usd"])} for k, v in by_purpose.items()}}
