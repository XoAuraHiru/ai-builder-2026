"""Blind indexes (blueprint §9): an HMAC of an identifier such as a bank account number, so accounts that share one can
be linked without the number itself being stored. The key comes from Secret Manager in production."""
import hashlib
import hmac
import re

from app.config import get_settings


def blind_index(value: str) -> str:
    normalised = re.sub(r"[\s-]", "", value or "")
    return hmac.new(get_settings().blind_index_key.encode(), normalised.encode(), hashlib.sha256).hexdigest()
