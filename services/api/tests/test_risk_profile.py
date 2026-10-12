from app.ai.llm import FakeLLM, get_llm
from app.events import current_bus
from app.services.risk_profile import ChatAnswers, RiskAnswers, normalise, score_profile

INVESTOR = {"X-Dev-User": "priya@atrium.demo"}
STAFF = {"X-Dev-User": "daniel@atrium.demo"}


def answers(**overrides) -> RiskAnswers:
    base = dict(horizon_years=20, withdraw_within_2y="none", max_loss_pct=40, reaction_to_drop="buy_more",
                experience="experienced")
    base.update(overrides)
    return RiskAnswers(**base)


def test_long_horizon_and_high_tolerance_give_band_5():
    assert score_profile(answers()).band == 5


def test_selling_after_a_drop_caps_tolerance():
    r = score_profile(answers(reaction_to_drop="sell_all"))
    assert (r.band, r.tolerance_band) == (2, 2)
    assert any("Selling everything" in reason for reason in r.reasons)


def test_a_short_horizon_caps_capacity():
    r = score_profile(answers(horizon_years=2, reaction_to_drop="hold"))
    assert (r.band, r.capacity_band) == (2, 2)


def test_the_band_is_the_lower_of_capacity_and_tolerance():
    r = score_profile(answers(horizon_years=10, withdraw_within_2y="some", max_loss_pct=30, reaction_to_drop="hold",
                              experience="none"))
    assert (r.capacity_band, r.tolerance_band, r.band) == (3, 4, 3)
    assert "capacity" in r.reasons[-1]


def test_needing_most_of_the_money_soon_caps_capacity_at_2():
    assert score_profile(answers(horizon_years=10, withdraw_within_2y="most")).capacity_band == 2


def test_values_from_the_conversation_are_normalised_not_trusted():
    p = normalise(ChatAnswers(horizon_years=12, max_loss_pct=25, withdraw_within_2y="maybe", reaction_to_drop="hold",
                              experience="expert"))
    assert (p.horizon_years, p.max_loss_pct, p.withdraw_within_2y, p.reaction_to_drop, p.experience) == \
        (12, 20, None, "hold", None)


def test_questionnaire_saves_the_profile_and_band(client, db, people):
    r = client.post("/me/risk-profile", json={"answers": answers(reaction_to_drop="hold").model_dump()}, headers=INVESTOR)
    assert r.status_code == 201, r.text
    assert r.json()["band"] == 5 and r.json()["source"] == "questionnaire"
    state = client.get("/me/risk-profile", headers=INVESTOR).json()
    assert state["current_band"] == 5 and state["profile"]["band"] == 5 and len(state["questions"]) == 5
    db.refresh(people["investor"])
    assert people["investor"].risk_band == 5
    assert any(e.type == "RiskProfileSet" for e in current_bus().history)


def test_risk_profiles_are_for_investors_only(client, people):
    assert client.get("/me/risk-profile", headers=STAFF).status_code == 403


def test_conversation_collects_answers_and_previews_without_saving(client, db, people):
    turns = iter([
        {"answers": {"horizon_years": 15, "withdraw_within_2y": "none", "max_loss_pct": 30},
         "reply": "Thanks. If your investments fell 20% in a month, what would you do?"},
        {"answers": {"reaction_to_drop": "hold", "experience": "some"}, "reply": "Thank you. Your result is ready."}])
    client.app.dependency_overrides[get_llm] = lambda: FakeLLM({"risk_profile_chat": lambda prompt: next(turns)})
    first = client.post("/me/risk-profile/chat", headers=INVESTOR, json={
        "messages": [{"role": "user", "text": "15 years, I won't touch it, a 30% fall is fine"}]}).json()
    assert first["complete"] is False and first["missing"] == ["reaction_to_drop", "experience"]
    assert first["reply"].startswith("Thanks.")
    second = client.post("/me/risk-profile/chat", headers=INVESTOR, json={
        "messages": [{"role": "user", "text": "I'd hold, and I have some experience"}], "known": first["answers"]}).json()
    assert second["complete"] is True and second["preview"]["band"] == 4
    assert client.get("/me/risk-profile", headers=INVESTOR).json()["profile"] is None


def test_conversation_failure_points_to_the_questionnaire(client, people):
    client.app.dependency_overrides[get_llm] = lambda: FakeLLM({})
    r = client.post("/me/risk-profile/chat", json={"messages": [{"role": "user", "text": "hi"}]}, headers=INVESTOR)
    assert r.status_code == 503 and "five questions" in r.json()["detail"]
