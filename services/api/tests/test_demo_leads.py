from sqlalchemy import func, select

from app.config import get_settings
from app.models import Lead, Person
from app.seed.bootstrap import bootstrap_database
from app.seed.leads import DEMO_LEADS, seed_demo_leads


def test_seed_demo_leads_inserts_unscored_stories_once(db, people):
    assert seed_demo_leads(db) == len(DEMO_LEADS) == 12
    db.commit()
    assert seed_demo_leads(db) == 0
    leads = db.scalars(select(Lead)).all()
    assert all(lead.scored_at is None for lead in leads)
    ring = [lead for lead in leads if lead.device_id == "dev-ring-0001"]
    assert len(ring) == 4  # Alex Mercer plus the three-person ring
    chen = [lead for lead in leads if lead.phone == "+16175550142"]
    assert len(chen) == 2
    assert all(lead.owner_id == people["advisor"].id for lead in leads)


def test_bootstrap_seeds_demo_leads_even_when_people_exist(db, people, monkeypatch):
    monkeypatch.setattr(get_settings(), "auto_seed", True)
    bootstrap_database(get_settings())
    assert db.scalar(select(func.count()).select_from(Lead)) == 12 + 1  # and Ruth Alvarez, the pressure call's lead
    assert db.scalar(select(func.count()).select_from(Person)) == 2  # people were already there; not re-seeded
