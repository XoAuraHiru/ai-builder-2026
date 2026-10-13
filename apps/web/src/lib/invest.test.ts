import { describe, expect, it } from "vitest";
import { riskState, type RiskReport } from "./invest";
import { currentMix, parseMoney, scenarioKey, toggleScenario, verdictText } from "./invest";
import { copilotHref, findingCard, findingCards, heat, overlapLine, questionFrom, scaleMarks, sectorRows, shortName, topExposures,
  type XRay } from "./invest";

const SECTORS = [
  { name: "Cash and T-bills", value_usd: 20000, pct: 43.8 }, { name: "Technology", value_usd: 9406, pct: 20.6 },
  { name: "Bonds", value_usd: 4645, pct: 10.2 }, { name: "Communication", value_usd: 2213, pct: 4.9 },
  { name: "Financials", value_usd: 1832, pct: 4.0 }, { name: "Health care", value_usd: 1641, pct: 3.6 },
];
const OVERLAPS: XRay["overlaps"] = [{ funds: ["ATR-BAL", "ATR-GRW"], names: ["Atrium Balanced", "Atrium Growth"],
  shared_etfs_pct: 0, shared_companies_pct: 20.1, top_shared: ["NVIDIA Corp", "Apple Inc", "Microsoft Corp"] }];
const COMPANIES: XRay["companies"] = [{ symbol: "NVDA", name: "NVIDIA Corp", value_usd: 3000, pct: 6.2, via: ["QQQ", "VOO"] }];
const X = { overlaps: OVERLAPS, companies: COMPANIES };

describe("scaleMarks", () => {
  it("fills the profile's band green and a portfolio above it amber, each with a chip", () => {
    const marks = scaleMarks(3, 4);
    expect(marks.map((m) => m.fill)).toEqual(["none", "none", "profile", "above", "none"]);
    expect(marks[2].chip).toEqual({ text: "Your profile", short: "Profile", tone: "gain" });
    expect(marks[3].chip).toEqual({ text: "Your portfolio now", short: "Now", tone: "caution" });
    expect(marks[4].label).toBe("5 Adventurous");
  });
  it("marks one band when they match, and a calmer portfolio or a missing profile without amber", () => {
    expect(scaleMarks(3, 3).filter((m) => m.chip).map((m) => m.chip?.text)).toEqual(["Your profile and portfolio"]);
    expect(scaleMarks(4, 2)[1]).toMatchObject({ fill: "calm", chip: { tone: "neutral" } });
    expect(scaleMarks(null, 4)[3]).toMatchObject({ fill: "calm", chip: { text: "Your portfolio now", tone: "neutral" } });
  });
});

describe("topExposures and sectorRows", () => {
  it("takes the largest exposures, widths relative to the widest", () => {
    const rows = topExposures(SECTORS);
    expect(rows.map((r) => r.name)).toEqual(["Cash and T-bills", "Technology", "Bonds", "Communication"]);
    expect(rows[0].width).toBe(100);
    expect(rows[1].width).toBe(47);
  });
  it("sums the rest of the sectors as one row", () => {
    const rows = sectorRows(SECTORS);
    expect(rows).toHaveLength(5);
    expect(rows[4]).toMatchObject({ name: "Other sectors", other: true, pct: 8.7 });
    expect(sectorRows(SECTORS.slice(0, 5)).at(-1)).toMatchObject({ name: "Financials", other: false });
    expect(sectorRows([])).toEqual([]);
  });
});

describe("overlapLine and shortName", () => {
  it("says the largest overlap in one line", () => {
    expect(overlapLine(OVERLAPS)).toBe("Atrium Balanced and Atrium Growth overlap by 20.1%.");
    expect(overlapLine([])).toBeNull();
  });
  it("drops the corporate suffix", () => {
    expect(["NVIDIA Corp", "Apple Inc", "Alphabet Inc Class A", "Amazon.com Inc", "Meta Platforms Inc Class A"].map(shortName))
      .toEqual(["NVIDIA", "Apple", "Alphabet", "Amazon.com", "Meta Platforms"]);
  });
});

describe("findingCard", () => {
  it("sets the figure large and keeps the rest as a sentence", () => {
    expect(findingCard({ code: "HOME_BIAS", severity: "info", title: "Mostly in the US",
      message: "100.0% of your money is in US stocks, bonds and T-bills." }, X))
      .toMatchObject({ tone: "note", figure: "100.0%", sentence: "of your money is in US stocks, bonds and T-bills.", chips: [] });
  });
  it("names the companies two funds share as chips", () => {
    const card = findingCard({ code: "OVERLAP", severity: "caution", title: "Two funds own the same things",
      message: "Atrium Balanced and Atrium Growth overlap: 20.1% in the same companies. Both hold NVIDIA Corp, Apple Inc and Microsoft Corp." }, X);
    expect(card).toMatchObject({ tone: "look", figure: "20.1%", sentence: "overlap between Atrium Balanced and Atrium Growth" });
    expect(card.chips.map((c) => c.text)).toEqual(["NVIDIA", "Apple", "Microsoft"]);
  });
  it("rewrites concentration warnings around their figure", () => {
    expect(findingCard({ code: "CONC_COMPANY", severity: "caution", title: "One company is a large share",
      message: "NVIDIA Corp is 6.2% of your portfolio, held through QQQ and VOO." }, X))
      .toMatchObject({ figure: "6.2%", sentence: "of your portfolio is NVIDIA Corp, held through", chips: [{ text: "QQQ", mono: true }, { text: "VOO", mono: true }] });
    expect(findingCard({ code: "CONC_SECTOR", severity: "caution", title: "Concentrated in one sector",
      message: "Technology is 41.0% of your portfolio." }, X)).toMatchObject({ figure: "41.0%", sentence: "of your portfolio is in Technology." });
    expect(findingCard({ code: "ONE_FUND", severity: "info", title: "All of your money is in one fund",
      message: "Everything is in Atrium Growth. That keeps things simple." }, X))
      .toMatchObject({ figure: "100%", sentence: "of your money is in Atrium Growth. That keeps things simple." });
  });
  it("folds several large companies into one card, keeping the other findings in order", () => {
    const big = (name: string, pct: string) => ({ code: "CONC_COMPANY", severity: "caution" as const, title: "One company is a large share",
      message: `${name} is ${pct}% of your portfolio, held through QQQ.` });
    const cards = findingCards({ ...X, warnings: [big("Apple Inc.", "14.5"), big("NVIDIA Corp", "14.7"),
      { code: "HOME_BIAS", severity: "info", title: "Mostly in the US", message: "95.0% of your money is in US stocks, bonds and T-bills." }] });
    expect(cards).toHaveLength(2);
    expect(cards[0]).toMatchObject({ title: "Two companies are each a large share", figure: "14.7%",
      sentence: "of your portfolio is NVIDIA Corp, the largest of them" });
    expect(cards[0].chips.map((c) => c.text)).toEqual(["Apple", "NVIDIA"]);
    expect(cards[1].title).toBe("Mostly in the US");
    expect(findingCards({ ...X, warnings: [big("Apple Inc.", "14.5")] })[0].figure).toBe("14.5%");
  });
  it("falls back to the message when it cannot find a figure", () => {
    expect(findingCard({ code: "NEW_RULE", severity: "info", title: "Something", message: "Plain words." }, X))
      .toMatchObject({ figure: null, sentence: "Plain words." });
  });
});

describe("copilot questions", () => {
  it("carries a question to the copilot and reads it back", () => {
    const href = copilotHref("Why is my portfolio in band 4?");
    expect(href).toBe("/investor/copilot?q=Why%20is%20my%20portfolio%20in%20band%204%3F");
    expect(questionFrom(href.slice(href.indexOf("?")))).toBe("Why is my portfolio in band 4?");
    expect(questionFrom("")).toBe("");
  });
});

describe("heat", () => {
  it("shades in forest green, stronger as the correlation grows", () => {
    expect(heat(1)).toBe("rgba(63, 129, 96, 0.320)");
    expect(heat(-0.5)).toBe("rgba(63, 129, 96, 0.160)");
  });
});

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
