from app.seed.funds import house_fund_objects
from app.services.xray import xray

PROFILES = {
    "VOO": {"expense_ratio": 0.0003, "sectors": {"technology": 0.3, "healthcare": 0.7},
            "top_holdings": [{"symbol": "NVDA", "name": "NVIDIA", "weight": 0.08},
                             {"symbol": "AAPL", "name": "Apple", "weight": 0.07}]},
    "QQQ": {"expense_ratio": 0.002, "sectors": {"technology": 0.6, "communication_services": 0.4},
            "top_holdings": [{"symbol": "NVDA", "name": "NVIDIA", "weight": 0.09}]},
    "VUG": {"expense_ratio": 0.0004, "sectors": {"technology": 1.0}, "top_holdings": []},
    "XLK": {"expense_ratio": 0.0008, "sectors": {"technology": 1.0},
            "top_holdings": [{"symbol": "NVDA", "name": "NVIDIA", "weight": 0.15}]},
    "VGT": {"expense_ratio": 0.0009, "sectors": {"technology": 1.0},
            "top_holdings": [{"symbol": "NVDA", "name": "NVIDIA", "weight": 0.16}]},
    "VTI": {"expense_ratio": 0.0003, "sectors": {"technology": 0.3, "industrials": 0.7}, "top_holdings": []},
    "BND": {"expense_ratio": 0.0003, "sectors": {}, "top_holdings": []},
}
FUNDS = house_fund_objects()


def test_lookthrough_finds_companies_held_through_several_etfs():
    x = xray({"ATR-GRW": 10_000.0}, FUNDS, PROFILES)
    nvda = x.companies[0]
    assert nvda.symbol == "NVDA" and nvda.via == ["QQQ", "VOO"]
    assert (nvda.value_usd, nvda.pct) == (670.0, 6.7)  # 10,000 x (0.5 x 0.08 + 0.3 x 0.09)
    assert any(w.code == "CONC_COMPANY" and "QQQ and VOO" in w.message for w in x.warnings)
    assert any(w.code == "ONE_FUND" for w in x.warnings)


def test_sectors_regions_and_asset_classes_add_up():
    x = xray({"ATR-BAL": 6_000.0, "ATR-GRW": 4_000.0}, FUNDS, PROFILES)
    assert abs(sum(s.value_usd for s in x.sectors) - 10_000) < 0.05
    assert next(s for s in x.sectors if s.name == "Bonds").value_usd == 2400.0  # 40% of the Balanced fund
    assert {a.name for a in x.asset_classes} == {"Stocks", "Bonds"}


def test_fees_combine_atrium_and_etf_costs():
    x = xray({"ATR-BAL": 10_000.0}, FUNDS, PROFILES)
    assert (x.fees.atrium_annual_usd, x.fees.etf_annual_usd) == (35.0, 3.0)
    assert (x.fees.total_pct, x.fees.ten_year_usd) == (0.38, 380.0)


def test_overlap_between_funds_is_reported():
    x = xray({"ATR-GRW": 5_000.0, "ATR-TEC": 5_000.0}, FUNDS, PROFILES)
    pair = x.overlaps[0]
    assert pair.funds == ["ATR-GRW", "ATR-TEC"] and pair.shared_etfs_pct == 0.0
    # Growth holds 6.7% NVIDIA and Technology 15.4% (0.6 x 0.15 + 0.4 x 0.16): they share 6.7%.
    assert pair.shared_companies_pct == 6.7 and pair.top_shared == ["NVIDIA"]


def test_overlap_warnings_name_only_the_overlaps_that_exist():
    heavy = {**PROFILES, "VOO": {**PROFILES["VOO"], "top_holdings": [{"symbol": "NVDA", "name": "NVIDIA", "weight": 0.3}]},
             "XLK": {**PROFILES["XLK"], "top_holdings": [{"symbol": "NVDA", "name": "NVIDIA", "weight": 0.5}]}}
    x = xray({"ATR-GRW": 3_000.0, "ATR-TEC": 7_000.0}, FUNDS, heavy)  # they share 17.7% of their money in NVIDIA
    message = next(w.message for w in x.warnings if w.code == "OVERLAP")
    assert "same ETFs" not in message and "in the same companies" in message
