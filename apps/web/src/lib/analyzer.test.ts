import { describe, expect, it } from "vitest";
import {
  applyLink, disclosure, fundOrderLink, readApply, readFundOrder, readShareOrder, shareOrderLink, unitRange, unitStats,
  validate, wholeShares, type Analysis, type AnalyzerOptions, type UnitPoint,
} from "./analyzer";

const OPTIONS: AnalyzerOptions = {
  funds: [{ code: "ATR-BAL", name: "Atrium Balanced", risk_band: 3, fee_bps: 35, min_investment: 500 }],
  shares: [{ symbol: "NVDA", name: "NVIDIA", kind: "stock", history_start: "2007-06" }],
  min_share_years: 10, monthly_minimum: 50,
};
const trust = { kind: "unit_trust" as const, code: "ATR-BAL", initial: 1000, monthly: 0, years: 10 };
const share = { kind: "share" as const, code: "NVDA", initial: 1000, monthly: 0, years: 10 };
const ID = "0123456789abcdef0123456789abcdef";

function analysis(kind: "unit_trust" | "share", monthly = 0): Analysis {
  return {
    id: ID, kind, code: kind === "share" ? "NVDA" : "ATR-BAL", name: "x", fee_bps: kind === "share" ? 0 : 35,
    min_investment: 500, comparison: null,
    result: { initial_usd: 5000, monthly_usd: monthly, years: 12, goal_usd: null, contributed: 0, window_start: "2007-06",
      window_end: "2026-09", months: 230, paths: 10000, method: "", scenarios: [] },
  };
}

describe("validate", () => {
  it("accepts a good unit trust and a good share", () => {
    expect(validate(trust, OPTIONS)).toBeNull();
    expect(validate({ ...trust, monthly: 50 }, OPTIONS)).toBeNull();
    expect(validate(share, OPTIONS)).toBeNull();
  });
  it("answers each rule in the API's words", () => {
    expect(validate({ ...trust, initial: 0, monthly: 100 }, OPTIONS)).toBe("Enter a one-time amount to invest.");
    expect(validate({ ...trust, initial: 499 }, OPTIONS)).toBe("Atrium Balanced needs at least $500 to start.");
    expect(validate({ ...trust, monthly: 49 }, OPTIONS)).toBe("Monthly amounts start at $50.");
    expect(validate({ ...trust, years: 41 }, OPTIONS)).toBe("Choose 1 to 40 years.");
    expect(validate({ ...trust, years: 0 }, OPTIONS)).toBe("Choose 1 to 40 years.");
    expect(validate({ ...trust, code: "NOPE" }, OPTIONS)).toBe("Choose one of Atrium's funds.");
    expect(validate({ ...share, monthly: 10 }, OPTIONS)).toContain("unit trusts only");
    expect(validate({ ...share, code: "SGOV" }, OPTIONS)).toBe("Choose one of the shares.");
  });
});

describe("wholeShares", () => {
  it("buys whole shares and reports what is left", () => {
    expect(wholeShares(1000, 300)).toEqual({ shares: 3, cost: 900, left: 100 });
    expect(wholeShares(900, 300)).toEqual({ shares: 3, cost: 900, left: 0 });
    expect(wholeShares(1000, 186.37)).toEqual({ shares: 5, cost: 931.85, left: 68.15 });
  });
  it("is zero shares when the amount is under one share or the price is missing", () => {
    expect(wholeShares(100, 300)).toEqual({ shares: 0, cost: 0, left: 100 });
    expect(wholeShares(100, 0)).toEqual({ shares: 0, cost: 0, left: 100 });
  });
});

function params(link: string): URLSearchParams {
  return new URLSearchParams(link.split("?")[1]);
}

describe("links", () => {
  it("round-trip a fund order with and without a monthly amount", () => {
    expect(fundOrderLink(analysis("unit_trust", 200)).startsWith("/investor/orders?")).toBe(true);
    expect(readFundOrder(params(fundOrderLink(analysis("unit_trust", 200)))))
      .toEqual({ analysis: ID, fund: "ATR-BAL", amount: 5000, monthly: 200 });
    expect(readFundOrder(params(fundOrderLink(analysis("unit_trust"))))!.monthly).toBeNull();
  });
  it("round-trip a share order as whole shares", () => {
    const link = shareOrderLink(analysis("share"), 186.37);
    expect(link.startsWith("/investor/markets/NVDA?")).toBe(true);
    expect(readShareOrder(params(link))).toEqual({ analysis: ID, qty: 26 });
  });
  it("round-trip an application", () => {
    expect(readApply(params(applyLink(analysis("unit_trust", 200)))))
      .toEqual({ analysis: ID, amount: 5000, monthly: 200, years: 12 });
  });
  it("read junk as nothing, never throwing", () => {
    expect(readFundOrder(new URLSearchParams("analysis=<script>&fund=ATR-BAL&amount=5"))).toBeNull();
    expect(readFundOrder(new URLSearchParams(`analysis=${ID}&fund=ATR-BAL&amount=-5`))).toBeNull();
    expect(readFundOrder(new URLSearchParams(`analysis=${ID}&fund=bad code&amount=5`))).toBeNull();
    expect(readShareOrder(new URLSearchParams(`analysis=${ID}&qty=2.5`))).toBeNull();
    expect(readShareOrder(new URLSearchParams(""))).toBeNull();
    expect(readApply(new URLSearchParams(`analysis=${ID}&amount=1000&years=abc&monthly=x`)))
      .toEqual({ analysis: ID, amount: 1000, monthly: null, years: null });
  });
});

describe("disclosure", () => {
  it("names the selection effect only for shares", () => {
    const shares = disclosure(analysis("share")).join(" ");
    const trusts = disclosure(analysis("unit_trust")).join(" ");
    expect(shares).toContain("chosen today");
    expect(trusts).not.toContain("chosen today");
    expect(trusts).toContain("0.35% annual fee");
  });
  it("always says it is hypothetical, varies and has limits", () => {
    for (const kind of ["unit_trust", "share"] as const) {
      const text = disclosure(analysis(kind)).join(" ");
      expect(text).toContain("hypothetical");
      expect(text).toContain("not guarantees of future results");
      expect(text).toContain("Results vary");
      expect(text).toContain("Jun 2007 to Sep 2026");
    }
  });
});

const POINTS: UnitPoint[] = [
  { date: "2023-01-31", price: 100, backtest: true },
  { date: "2024-06-30", price: 120, backtest: true },
  { date: "2025-01-02", price: 90, backtest: false },
  { date: "2025-06-02", price: 110, backtest: false },
  { date: "2026-01-02", price: 99, backtest: false },
];

describe("unit price ranges and stats", () => {
  it("keeps the last one or two years", () => {
    expect(unitRange(POINTS, "1y").map((p) => p.date)).toEqual(["2025-01-02", "2025-06-02", "2026-01-02"]);
    expect(unitRange(POINTS, "2y").map((p) => p.date)).toEqual(["2024-06-30", "2025-01-02", "2025-06-02", "2026-01-02"]);
    expect(unitRange(POINTS, "all")).toHaveLength(5);
  });
  it("finds the change and the largest fall from a high", () => {
    expect(unitStats(POINTS)).toEqual({ changePct: -1, fallPct: -25, fallFrom: "2024-06-30", fallTo: "2025-01-02" });
    expect(unitStats(POINTS.slice(0, 1))).toBeNull();
  });
});
