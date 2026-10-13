import { describe, expect, it } from "vitest";
import { ANALOGUE_TITLE, bounds, clampedNote, clampShock, EXAMPLES, FACTOR_LABEL, formatShock, impactTitle, recoveryText,
  sliderRows, windowText, type MapResult } from "./scenarios";

describe("FACTOR_LABEL", () => {
  it("names every factor in plain words", () => {
    expect(FACTOR_LABEL).toEqual({
      us_equity: "US stocks", intl_equity: "International stocks", bonds: "Bonds", cash: "Cash",
      technology: "Technology", communication_services: "Communication services", consumer_cyclical: "Consumer cyclical",
      consumer_defensive: "Consumer staples", energy: "Energy", financial_services: "Financials", healthcare: "Health care",
      industrials: "Industrials", basic_materials: "Materials", realestate: "Real estate", utilities: "Utilities",
    });
  });
});

describe("bounds and clampShock", () => {
  it("gives each factor the server's bounds", () => {
    expect(bounds("bonds")).toEqual([-30, 20]);
    expect(bounds("cash")).toEqual([-5, 5]);
    expect(bounds("us_equity")).toEqual([-70, 50]);
    expect(bounds("energy")).toEqual([-70, 50]);
  });
  it("holds a shock within them", () => {
    expect(clampShock("cash", 9)).toBe(5);
    expect(clampShock("technology", -500)).toBe(-70);
    expect(clampShock("bonds", -12)).toBe(-12);
  });
  it("says why a clamped shock sits at its limit", () => {
    expect(clampedNote("technology", -70)).toBe("Held to −70%, the limit for this kind of shock");
    expect(clampedNote("bonds", 20)).toBe("Held to +20%, the limit for this kind of shock");
  });
});

describe("formatShock", () => {
  it("signs every shock with a true minus", () => {
    expect(formatShock(-12.5)).toBe("−12.5%");
    expect(formatShock(10)).toBe("+10%");
    expect(formatShock(0)).toBe("0%");
  });
});

describe("recoveryText", () => {
  it("says how long the portfolio took to get back", () => {
    expect(recoveryText(null)).toBe("Not recovered within the data");
    expect(recoveryText(14)).toBe("Recovered in 14 months");
    expect(recoveryText(1)).toBe("Recovered in 1 month");
    expect(recoveryText(0)).toBe("Never fell below its starting value");
  });
});

describe("impactTitle and windowText", () => {
  it("puts the total change in dollars and as a share of the portfolio", () => {
    expect(impactTitle(-7420, -15.3)).toBe("−$7,420, or −15.3% of your portfolio");
    expect(impactTitle(1250.4, 2.06)).toBe("+$1,250, or +2.1% of your portfolio");
  });
  it("names a replay's window by its month-end closes", () => {
    expect(windowText("2007-10", "2009-02")).toBe("End of Oct 2007 to end of Feb 2009");
  });
});

describe("EXAMPLES", () => {
  it("offers the three spec examples", () => {
    expect(EXAMPLES).toEqual(["Oil at $150 and a US recession", "AI stocks fall 40%", "The Fed cuts rates to zero"]);
    expect(Object.keys(ANALOGUE_TITLE)).toEqual(["crisis_2008", "pandemic_2020", "rates_2022"]);
  });
});

describe("sliderRows", () => {
  const result = {
    proposal: {
      in_scope: true, refusal: "", title: "AI stocks fall", horizon_months: 12, analogue: "rates_2022", analogue_reason: "",
      assumptions: [], shocks: [{ factor: "technology", pct: -70, reason: "AI leaders reprice." },
        { factor: "us_equity", pct: -10, reason: "The market follows." }],
    },
    shocks: { technology: -70, us_equity: -10, intl_equity: 0, bonds: 0, cash: 0 },
    clamped: ["technology"], dropped: [], sources: [], sources_note: null, impact: null,
  } satisfies MapResult;

  it("lists Gemini's shocks first with their reasons, then the other asset classes at the values in play", () => {
    const rows = sliderRows(result, { ...result.shocks, bonds: -4 });
    expect(rows.map((r) => [r.factor, r.pct, r.reason, r.clamped])).toEqual([
      ["technology", -70, "AI leaders reprice.", true],
      ["us_equity", -10, "The market follows.", false],
      ["intl_equity", 0, null, false],
      ["bonds", -4, null, false],
      ["cash", 0, null, false],
    ]);
    expect(rows[0].label).toBe("Technology");
    expect(rows[0].min).toBe(-70);
    expect(rows[3].max).toBe(20);
  });
  it("stops marking a clamped shock once the investor moves it", () => {
    expect(sliderRows(result, { ...result.shocks, technology: -60 })[0].clamped).toBe(false);
  });
});
