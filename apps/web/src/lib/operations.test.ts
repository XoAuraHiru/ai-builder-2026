import { describe, expect, it } from "vitest";
import { codeDigits, confidenceWords, describeInstruction, matchTotals, proposerLabel, resultWords } from "./operations";

describe("codeDigits", () => {
  it("keeps six digits from whatever is typed or pasted", () => {
    expect(codeDigits("12 34-56 7")).toBe("123456");
    expect(codeDigits("abc")).toBe("");
  });
});

describe("matchTotals", () => {
  it("agrees to the cent", () => {
    expect(matchTotals([{ amount: "3100.00" }, { amount: "1900.00" }], [{ amount: "5000.00" }])).toEqual({ paid: 5000, due: 5000, agrees: true });
    expect(matchTotals([{ amount: "0.10" }, { amount: "0.20" }], [{ amount: "0.30" }]).agrees).toBe(true);
    expect(matchTotals([{ amount: "777.00" }], [{ amount: "770.00" }]).agrees).toBe(false);
    expect(matchTotals([], []).agrees).toBe(false);
  });
});

describe("words", () => {
  it("names confidence, proposers and instructions plainly", () => {
    expect(confidenceWords(0.99)).toBe("Near certain");
    expect(confidenceWords(0.85)).toBe("Strong");
    expect(confidenceWords(0.72)).toBe("Likely");
    expect(proposerLabel("agent")).toBe("the reconciliation agent");
    expect(proposerLabel("mei@atrium.demo")).toBe("mei@atrium.demo, by hand");
    expect(describeInstruction({ type: "subscribe", amount: "1500.00", units: null, fund_name: "Atrium Balanced" }))
      .toBe("Buy $1,500.00 of Atrium Balanced");
    expect(describeInstruction({ type: "redeem", amount: null, units: "12.500000", fund_name: "Atrium Growth" }))
      .toBe("Sell 12.5 units of Atrium Growth");
  });
  it("says what an approval did", () => {
    expect(resultWords({ action: "publish_prices", state: "approved", result: { published: 7, allocation: { allocated: [{}, {}], rejected: [] } } }))
      .toBe("Published 7 prices; 2 instructions dealt.");
    expect(resultWords({ action: "manual_match", state: "approved", result: { settled: [] } }))
      .toBe("Matched; the subscription settles once it is dealt.");
    expect(resultWords({ action: "manual_match", state: "approved", result: { settled: ["i1"] } }))
      .toBe("Matched, and the subscription settled.");
    expect(resultWords({ action: "reverse_posting", state: "rejected", result: null })).toBe("Rejected: nothing changed.");
  });
});
