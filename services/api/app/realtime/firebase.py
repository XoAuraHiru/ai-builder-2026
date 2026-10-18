"""The process's one firebase_admin app: Firebase sign-in (app/auth.py), inbox writes and the inbox's custom tokens."""
from __future__ import annotations

import threading

from app.config import get_settings

_lock = threading.Lock()


def firebase_app():
    """The default app, initialised once. Credentials come from the environment (the service account on Cloud Run).
    Cloud Run's credentials hold no private key, so `serviceAccountId` names the account that signs custom tokens
    through the IAM API."""
    import firebase_admin

    with _lock:
        try:
            return firebase_admin.get_app()
        except ValueError:  # not initialised yet
            settings = get_settings()
            options = {key: value for key, value in (("projectId", settings.gcp_project),
                                                      ("serviceAccountId", settings.firebase_service_account))
                       if value}
            return firebase_admin.initialize_app(options=options or None)


def custom_token(person_id: str, role: str) -> str:
    """A Firebase custom token for this person. Their browser signs in with it, and firestore.rules lets its `pid`
    claim read people/{pid}/inbox and nothing else."""
    from firebase_admin import auth

    token = auth.create_custom_token(f"person-{person_id}", {"pid": person_id, "role": role}, app=firebase_app())
    return token.decode() if isinstance(token, bytes) else token
