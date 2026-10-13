"""One-off cleanup of what testing left in the demo data for the fraud ring radar to read as a ring: browser devices
shared by several demo accounts. Before devices were kept per persona, a smoke test (and a person trying several
personas in one browser) signed every persona in with one device id. The seeded ring device on Sofia Rossi's account
is the story and is kept; every other device the seed creates belongs to one account.

    python -m app.ops.cleanup_artefacts            # dry run: lists what it would delete
    python -m app.ops.cleanup_artefacts --apply    # deletes it

Run in production as a one-off execution of the day-end job with these arguments.
"""
import argparse
import sys

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Account, AccountDevice
from app.seed.rings import RING_DEVICE
from app.services.devices import device_hash


def shared_device_rows(db: Session) -> list[AccountDevice]:
    """Device rows whose device is also on another account, except the seeded ring device."""
    shared = (select(AccountDevice.device_hash).group_by(AccountDevice.device_hash)
              .having(func.count(func.distinct(AccountDevice.account_id)) > 1))
    return db.scalars(select(AccountDevice).where(AccountDevice.device_hash.in_(shared),
                                                  AccountDevice.device_hash != device_hash(RING_DEVICE))
                      .order_by(AccountDevice.device_hash, AccountDevice.first_seen)).all()


def main(argv: list[str] | None = None, db: Session | None = None) -> int:
    """Lists (and with --apply deletes) the shared device rows. Returns how many it found."""
    parser =argparse.ArgumentParser(description="Remove device rows testing shared across demo accounts.")
    parser.add_argument("--apply", action="store_true", help="delete the rows (without it, a dry run)")
    args = parser.parse_args(argv)
    own = db is None
    if own:
        from app.db import SessionLocal

        db = SessionLocal()
    try:
        rows = shared_device_rows(db)
        numbers = dict(db.execute(select(Account.id, Account.number)).all())
        for row in rows:
            print(f"device …{row.device_hash[-4:]} ({row.label or 'no label'}) on {numbers.get(row.account_id, row.account_id)}"
                  f", first seen {row.first_seen:%Y-%m-%d}")
        if args.apply:
            for row in rows:
                db.delete(row)
            db.commit()
            print(f"Deleted {len(rows)} shared device rows.")
        else:
            print(f"Dry run: {len(rows)} shared device rows would be deleted. Run again with --apply to delete them.")
        return len(rows)
    finally:
        if own:
            db.close()


if __name__ == "__main__":
    main(sys.argv[1:])
