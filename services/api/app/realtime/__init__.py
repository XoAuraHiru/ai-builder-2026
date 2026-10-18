"""The live inbox: what each person should know, as it happens, delivered through Cloud Firestore.

A service raises a notice (notices.py) beside the domain event it belongs to. The items wait on the database session
and leave only once it commits, from a background thread (inbox.py): a rolled-back request tells no one anything, and
a slow or failing Firestore never slows or fails a request. The browser signs in to Firebase with a custom token from
GET /me/realtime and listens to people/{person_id}/inbox; firestore.rules lets a person read their own items and
change nothing but `read`.

Importing this package registers the session hooks: delivery after commit, and the watch on leads' trust bands.
"""
from app.realtime import notices  # noqa: F401
