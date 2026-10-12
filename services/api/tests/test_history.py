import pandas as pd
from sqlalchemy import select

from app.models import Fund
from app.seed.funds import house_fund_objects, seed_funds
from app.seed.history import history_tickers, load_etf_document, load_etf_profiles, load_monthly_history
from app.services.fund_returns import (backfill_notes, benchmark_returns, constituent_weights, fund_return_frame,
                                       fund_returns, mix_returns, monthly_returns)


def test_committed_history_covers_every_fund_etf_and_the_benchmark():
    history = load_monthly_history()
    assert set(history_tickers()) <= set(history.columns)
    assert history.index[0].year == 2007 and history.index.is_monotonic_increasing
    assert len(history) >= 200
    assert history["SPY"].notna().all() and history["BIL"].notna().all()


def test_a_missing_constituent_weight_is_spread_over_the_others():
    idx = pd.date_range("2020-01-01", periods=4, freq="MS")
    prices = pd.DataFrame({"AAA": [100, 110, 121, 133.1], "BBB": [None, None, 50, 60]}, index=idx, dtype="float64")
    out = fund_returns({"AAA": 0.5, "BBB": 0.5}, monthly_returns(prices))
    assert [round(x, 6) for x in out] == [0.1, 0.1, 0.15]


def test_every_house_fund_has_a_continuous_history_from_2007():
    for code, fund in house_fund_objects().items():
        r = fund_returns(constituent_weights(fund))
        assert r.index[0].year == 2007, code
        assert r.notna().all() and len(r) >= 200, code


def test_a_mix_of_one_fund_equals_that_fund():
    funds = house_fund_objects()
    mix = mix_returns(funds, {"ATR-BAL": 1.0})
    alone = fund_returns(constituent_weights(funds["ATR-BAL"]))
    assert (mix - alone.loc[mix.index]).abs().max() < 1e-12


def test_fund_frame_aligns_funds_on_common_months():
    funds = house_fund_objects()
    frame = fund_return_frame(funds, ["ATR-CASH", "ATR-GLB"])
    assert list(frame.columns) == ["ATR-CASH", "ATR-GLB"] and frame.notna().all().all()
    assert len(benchmark_returns()) >= len(frame)


def test_backfill_notes_name_late_etfs():
    notes = backfill_notes(house_fund_objects()["ATR-CASH"])
    assert any("backtest starts" in n for n in notes)
    assert any("SGOV" in n and "2020" in n for n in notes)


def test_db_funds_and_transient_funds_agree(db):
    seed_funds(db)
    stored = {f.code: constituent_weights(f) for f in db.scalars(select(Fund)).all()}
    assert stored == {code: constituent_weights(f) for code, f in house_fund_objects().items()}


def test_profiles_have_lookthrough_for_equity_etfs_and_costs_for_all():
    profiles = load_etf_profiles()
    voo = profiles["VOO"]
    assert len(voo["top_holdings"]) >= 5 and 0 < voo["top_holdings"][0]["weight"] < 0.2
    assert abs(sum(voo["sectors"].values()) - 1) < 0.02
    assert profiles["BND"]["top_holdings"] == [] and profiles["BND"]["expense_ratio"] > 0
    assert all(p["expense_ratio"] is not None for p in profiles.values())
    assert load_etf_document()["as_of"] >= "2026-10-01"
