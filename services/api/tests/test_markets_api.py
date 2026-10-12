import pandas as pd
import pytest

from app.markets.quotes import CommittedQuotes, quote_book

DAILY = pd.DataFrame({"KO": [60.0, 61.0], "TSLA": [400.0, 400.0], "NVDA": [200.0, 210.0]},
                     index=pd.to_datetime(["2026-10-08", "2026-10-09"]))
HDR = {"X-Dev-User": "priya@example.test"}


@pytest.fixture()
def api(client, account):
    client.app.dependency_overrides[quote_book] = lambda: CommittedQuotes(DAILY)
    return client


def test_markets_list_every_priced_symbol_with_its_band(api):
    body = api.get("/markets", headers=HDR).json()
    assert [r["symbol"] for r in body["rows"]] == ["NVDA", "TSLA", "KO"]
    ko = body["rows"][2]
    assert (ko["source"], ko["change_pct"], ko["risk_band"], ko["watched"]) == ("close", 1.67, 4, False)
    assert ko["sector"] == "Consumer staples" and body["session"]["label"]


def test_a_symbol_page_has_its_quote_history_and_facts(api):
    detail = api.get("/markets/ko", headers=HDR).json()
    assert detail["symbol"] == "KO" and detail["quote"]["price"] == "61.0000"
    assert [p["close"] for p in detail["history"]] == [60.0, 61.0] and detail["history"][0]["day"] == "2026-10-08"
    assert detail["avg_volume"] > 0 and detail["summary"]
    assert api.get("/markets/ZZZZ", headers=HDR).status_code == 404


def test_the_watchlist_adds_and_removes_symbols(api):
    assert api.put("/me/watchlist/ko", headers=HDR).status_code == 204
    assert api.put("/me/watchlist/KO", headers=HDR).status_code == 204
    assert api.get("/me/watchlist", headers=HDR).json() == ["KO"]
    assert api.get("/markets/KO", headers=HDR).json()["watched"] is True
    assert api.delete("/me/watchlist/KO", headers=HDR).status_code == 204
    assert api.get("/me/watchlist", headers=HDR).json() == []
    assert api.put("/me/watchlist/ZZZZ", headers=HDR).status_code == 404
