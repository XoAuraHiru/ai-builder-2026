import { describe, expect, it } from "vitest";
import {
  acceptMany, approvalAmount, arriveDelay, codeArrival, confirmPause, statementSteps, statementUsually, approvalStatus, balanceNote, codeDigits, confidenceWords, describeInstruction, diffMarks, matchStatus,
  matchTotals, meterCells, priceStatus, proposerLabel, resultWords, runCounts, shortId, shortWhen, sinceRun, splitProposals,
  statementFlow, writtenByModel,
} from "./operations";

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

describe("reconciliation views", () => {
  it("marks the characters where two references differ", () => {
    expect(diffMarks("ATR-97B3905C", "ATR-97B39D5C").filter((m) => m.diff).map((m) => m.ch)).toEqual(["0"]);
    expect(diffMarks("ATR-1", "ATR-12").map((m) => m.diff)).toEqual([false, false, false, false, false]);
  });
  it("keeps the rules' exact matches apart from the agent's proposals", () => {
    const m = (id: string, by: string, state = "proposed") => ({ id, proposed_by: by, state }) as never;
    const split = splitProposals([m("a", "rules"), m("b", "agent"), m("c", "scorer"), m("d", "mei@atrium.demo", "awaiting_approval")]);
    expect(split.rules.map((x: { id: string }) => x.id)).toEqual(["a"]);
    expect(split.others.map((x: { id: string }) => x.id)).toEqual(["b", "c", "d"]);
  });
  it("counts a statement's lines and reads its balance check", () => {
    const s = { counts: { unmatched: 1, proposed: 2, matched: 5, ignored: 2 },
      notes: ["Read 10.", "The transactions add up to the change in balance, $16,778.42."] } as never;
    expect(statementFlow(s)).toEqual({ read: 10, matched: 5, waiting: 2, left: 1, ignored: 2 });
    expect(balanceNote(s)).toEqual({ ok: true, text: "The transactions add up to the change in balance, $16,778.42." });
    expect(balanceNote({ counts: {}, notes: ["They do not add up, so check the statement."] } as never)?.ok).toBe(false);
    expect(balanceNote({ counts: {}, notes: ["Read from CSV."] } as never)).toBeNull();
  });
  it("fills a five-cell meter from a confidence", () => {
    expect([meterCells(0.99), meterCells(0.85), meterCells(0.5), meterCells(0)]).toEqual([5, 4, 3, 0]);
  });
});

describe("status chips", () => {
  it("colours matches, approvals and prices by what they mean", () => {
    expect(matchStatus("accepted")).toEqual({ label: "Matched", tone: "gain" });
    expect(matchStatus("awaiting_approval")).toEqual({ label: "Awaiting second approver", tone: "caution" });
    expect(matchStatus("rejected").tone).toBe("loss");
    expect(matchStatus("proposed").tone).toBe("neutral");
    expect(approvalStatus("pending").label).toBe("Awaiting second approver");
    expect(approvalStatus("approved").tone).toBe("gain");
    expect(approvalStatus("rejected").tone).toBe("loss");
    expect(priceStatus("draft")).toEqual({ label: "Draft", tone: "neutral" });
    expect(priceStatus("checked").tone).toBe("caution");
  });
});

describe("since the day-end", () => {
  it("reads the counts the run recorded and says how the queues moved", () => {
    const run = { steps: [{ step: "Exceptions", ok: true, detail: "", facts: { waiting: 6, unmatched_lines: 2, approvals: 0 } }] };
    expect(runCounts(run)).toEqual({ waiting: 6, unmatched: 2, approvals: 0 });
    expect(runCounts(null)).toEqual({ waiting: undefined, unmatched: undefined, approvals: undefined });
    expect(sinceRun(8, 6)).toEqual({ text: "↑ 2", tone: "caution" });
    expect(sinceRun(1, 4)).toEqual({ text: "↓ 3", tone: "gain" });
    expect(sinceRun(6, 6)).toBeNull();
    expect(sinceRun(6, undefined)).toBeNull();
  });
});

describe("request card", () => {
  it("finds the amount, shortens the id and knows the rules' writing from a model's", () => {
    expect(approvalAmount("Reverse the allocation of 8.3 units to ACC-0001 ($900.00 on October 5)")).toBe("$900.00");
    expect(approvalAmount("Match $12,500.00 from two lines")).toBe("$12,500.00");
    expect(approvalAmount("Publish 7 prices for October 12")).toBeNull();
    expect(shortId("5466df7774414770847783d0d939f53b")).toBe("5466DF77");
    expect(shortWhen("2026-10-13T10:58:31Z")).toMatch(/^Oct 1[34], \d{1,2}:\d{2}\s?[AP]M$/);
    expect(writtenByModel("rules")).toBe(false);
    expect(writtenByModel("gemini-3.8-flash")).toBe(true);
  });
});

describe("acceptMany", () => {
  it("accepts what it can and names what it could not", async () => {
    const seen: string[] = [];
    const accept = async (id: string) => {
      seen.push(id);
      if (id === "b") throw new Error("This proposal has already been decided.");
    };
    expect(await acceptMany(["a", "b", "c"], accept)).toEqual({
      accepted: ["a", "c"], failed: [{ id: "b", message: "This proposal has already been decided." }],
    });
    expect(seen).toEqual(["a", "b", "c"]);
    expect(await acceptMany([], accept)).toEqual({ accepted: [], failed: [] });
  });
});

describe("arriveDelay", () => {
  it("brings rows in 45 ms apart, the first dozen only", () => {
    expect(arriveDelay(0)).toBeCloseTo(0.04);
    expect(arriveDelay(1)).toBeCloseTo(0.085);
    expect(arriveDelay(11)).toBeCloseTo(0.535);
    expect(arriveDelay(40)).toBeCloseTo(arriveDelay(11));
    expect(arriveDelay(-3)).toBeCloseTo(0.04);
    expect(arriveDelay(5, { cap: 3, step: 0.1, start: 0 })).toBeCloseTo(0.2);
  });
});

describe("codeArrival", () => {
  it("finds where the new digits of a code begin", () => {
    expect(codeArrival("12", "123")).toBe(2);
    expect(codeArrival("", "482913")).toBe(0);
    expect(codeArrival("123", "12")).toBe(2);
    expect(codeArrival("111111", "482913")).toBe(0);
    expect(codeArrival("4829", "4829")).toBe(4);
  });
});

describe("confirmPause", () => {
  it("waits for the check to draw, unless motion is reduced", () => {
    expect(confirmPause(false)).toBeGreaterThan(400);
    expect(confirmPause(null)).toBeGreaterThan(400);
    expect(confirmPause(true)).toBe(0);
    expect(confirmPause(false, true)).toBeLessThan(confirmPause(false));
    expect(confirmPause(true, true)).toBe(0);
  });
});

describe("statementSteps", () => {
  it("says who reads the file before Gemini reads the narrations", () => {
    expect(statementSteps("pdf")[0]).toMatch(/Document AI/);
    expect(statementSteps("csv")[0]).toMatch(/CSV/);
    expect(statementSteps("csv")[1]).toMatch(/^Gemini/);
    expect(statementUsually("csv")).toBe("a few seconds");
    expect(statementUsually("pdf")).toMatch(/s$/);
  });
});
