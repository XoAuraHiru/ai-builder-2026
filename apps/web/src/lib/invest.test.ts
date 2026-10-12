import { describe, expect, it } from "vitest";
import { riskState, type RiskReport } from "./invest";
import { currentMix, parseMoney, scenarioKey, toggleScenario, verdictText } from "./invest";

describe("currentMix", () => {
  it("turns fund values into weights", () => {
    expect(currentMix({ "ATR-BAL": "7500", "ATR-TEC": "2500" })).toEqual({ "ATR-BAL": 0.75, "ATR-TEC": 0.25 });
  });
  it("is null for an empty portfolio", () => {
    expect(currentMix({})).toBeNull();
    expect(currentMix({ "ATR-BAL": "0" })).toBeNull();
  });
});

describe("toggleScenario", () => {
  const bal = { allocation: { "ATR-BAL": 1 } };
  const grw = { allocation: { "ATR-GRW": 1 } };
  const tec = { allocation: { "ATR-TEC": 1 } };
  const inc = { allocation: { "ATR-INC": 1 } };
  it("adds and removes by allocation", () => {
    expect(toggleScenario([bal], grw).map(scenarioKey)).toEqual([scenarioKey(bal), scenarioKey(grw)]);
    expect(toggleScenario([bal, grw], { label: "same", allocation: { "ATR-GRW": 1 } })).toEqual([bal]);
  });
  it("keeps at least one and at most three", () => {
    expect(toggleScenario([bal], bal)).toEqual([bal]);
    expect(toggleScenario([bal, grw, tec], inc).map(scenarioKey)).toEqual([bal, grw, inc].map(scenarioKey));
  });
});

describe("verdictText", () => {
  it("compares the portfolio with the profile in words", () => {
    expect(verdictText("above", 4, 3)).toBe("Your portfolio behaves like band 4, above your profile's band 3.");
    expect(verdictText("no_profile", 3, null)).toContain("Set your risk profile");
  });
});

describe("parseMoney", () => {
  it("reads typed amounts", () => {
    expect(parseMoney("$12,500.50")).toBe(12500.5);
    expect(parseMoney("")).toBe(0);
  });
});

describe("riskState", () => {
  it("turns the risk check into a report or a reason, never neither", () => {
    const report = { verdict: "above", portfolio_band: 4, profile_band: 3 } as RiskReport;
    expect(riskState({ status: "fulfilled", value: report })).toEqual({ report });
    expect(riskState({ status: "rejected", reason: new Error("A price is unavailable right now.") }))
      .toEqual({ error: "A price is unavailable right now." });
    expect(riskState({ status: "rejected", reason: "boom" })).toEqual({ error: "Atrium could not check your mix right now." });
  });
});
