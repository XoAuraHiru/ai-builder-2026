import hashlib
from datetime import timedelta

from fastapi import HTTPException, Request
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import Lead
from app.models.base import utcnow

_SALT = "atrium-lead-capture"


def ip_hash(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    ip = forwarded.split(",")[0].strip() or (request.client.host if request.client else "unknown")
    return hashlib.sha256(f"{_SALT}:{ip}".encode()).hexdigest()[:32]


def check_capture_rate(db: Session, device_id: str, ip: str, limit: int) -> None:
    """Refuse before any AI spend when one device or network floods the public form."""
    since = utcnow() - timedelta(hours=1)
    recent = db.scalar(select(func.count()).select_from(Lead).where(
        Lead.created_at >= since, or_(Lead.device_id == device_id, Lead.ip_hash == ip)))
    if (recent or 0) >= limit:
        raise HTTPException(status_code=429, detail="Too many submissions from this device; please try again later.")
