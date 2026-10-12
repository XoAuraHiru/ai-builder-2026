"""Spend guard for the public lead form: refuse floods before any AI call is made."""
import hashlib
from datetime import timedelta

from fastapi import HTTPException, Request
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import Lead
from app.models.base import utcnow

_SALT = "atrium-lead-capture"


def client_ip(request: Request) -> str:
    """Cloud Run appends the address it saw to any X-Forwarded-For the client sent; only the last entry is trusted."""
    forwarded = [part.strip() for part in request.headers.get("x-forwarded-for", "").split(",") if part.strip()]
    if forwarded:
        return forwarded[-1]
    return request.client.host if request.client else "unknown"


def ip_hash(request: Request) -> str:
    return hashlib.sha256(f"{_SALT}:{client_ip(request)}".encode()).hexdigest()[:32]


def check_capture_rate(db: Session, device_id: str, ip: str, limit: int, global_limit: int) -> None:
    """Per device or network, and a global hourly ceiling that bounds AI spend whatever identifiers a caller forges."""
    since = utcnow() - timedelta(hours=1)
    recent = db.scalar(select(func.count()).select_from(Lead).where(
        Lead.created_at >= since, or_(Lead.device_id == device_id, Lead.ip_hash == ip)))
    if (recent or 0) >= limit:
        raise HTTPException(status_code=429, detail="Too many submissions from this device; please try again later.")
    total = db.scalar(select(func.count()).select_from(Lead).where(Lead.created_at >= since, Lead.ip_hash != "seed"))
    if (total or 0) >= global_limit:
        raise HTTPException(status_code=429,
                            detail="We're receiving many applications right now; please try again later.")
