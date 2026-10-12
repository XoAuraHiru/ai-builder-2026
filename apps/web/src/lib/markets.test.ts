import { describe, expect, it } from "vitest";
import { compactCount, filterRows, priceSource, type MarketRow } from "./markets";

const row = (symbol: string, name: string, kind: "stock" | "etf", watched = false): MarketRow => ({
  symbol, name, kind, sector: null, risk_band: 4, price: "100", change_pct: 0, source: "live", watched });
const ROWS = [row("NVDA", "NVIDIA Corporation", "stock", true), row("KO", "The Coca-Cola Company", "stock"),
  row("QQQ", "Invesco QQQ Trust", "etf")];

describe("filterRows", () => {
  it("filters by kind and by the watchlist", () => {
    expect(filterRows(ROWS, "", "etf").map((r) => r.symbol)).toEqual(["QQQ"]);
    expect(filterRows(ROWS, "", "watchlist").map((r) => r.symbol)).toEqual(["NVDA"]);
    expect(filterRows(ROWS, "", "all")).toHaveLength(3);
  });
  it("matches the start of a symbol or any part of a name", () => {
    expect(filterRows(ROWS, " k", "all").map((r) => r.symbol)).toEqual(["KO"]);
    expect(filterRows(ROWS, "coca", "all").map((r) => r.symbol)).toEqual(["KO"]);
    expect(filterRows(ROWS, "zzz", "all")).toEqual([]);
  });
});

describe("priceSource", () => {
  it("says when a delayed price was read, in New York time", () => {
    expect(priceSource("live", "2026-10-12T14:32:00Z", new Date("2026-10-12T16:00:00Z")))
      .toBe("Delayed price from Yahoo Finance, read at 10:32 am New York time.");
  });
  it("adds the date when a delayed price was not read today", () => {
    expect(priceSource("live", "2026-10-09T19:55:00Z", new Date("2026-10-12T14:00:00Z")))
      .toBe("Delayed price from Yahoo Finance, read at 3:55 pm New York time on Oct 9.");
  });
  it("says plainly when it is only the last close", () => {
    expect(priceSource("close", "2026-10-09T20:00:00Z")).toBe("Last close, Oct 9, 2026. Live prices are unavailable right now.");
    expect(priceSource("live", null)).toBe("");
  });
});

describe("compactCount", () => {
  it("writes big counts the way people say them", () => {
    expect(compactCount(15_850_587)).toBe("15.9 million");
    expect(compactCount(378_839_465_984)).toBe("379 billion");
    expect(compactCount(4.2e12)).toBe("4.2 trillion");
    expect(compactCount(950)).toBe("950");
    expect(compactCount(null)).toBe("Not available");
  });
});
