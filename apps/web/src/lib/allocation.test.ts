import { describe, expect, it } from "vitest";
import { formatUsd, toAllocationSeries } from "./allocation";

describe("toAllocationSeries", () => {
  it("turns an API map of decimal strings into sorted series with percentages", () => {
    const series = toAllocationSeries({ "ATR-TEC": "2100.00", "ATR-BAL": "10400.00" });
    expect(series).toEqual([
      { name: "ATR-BAL", value: 10400, pct: 83.2 },
      { name: "ATR-TEC", value: 2100, pct: 16.8 },
    ]);
  });
  it("returns an empty series for an empty map", () => {
    expect(toAllocationSeries({})).toEqual([]);
  });
});

describe("formatUsd", () => {
  it("formats decimal strings as US dollars", () => {
    expect(formatUsd("12500.5")).toBe("$12,500.50");
    expect(formatUsd("-3.2")).toBe("-$3.20");
  });
});
