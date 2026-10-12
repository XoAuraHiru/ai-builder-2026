import { describe, expect, it } from "vitest";
import { describe as describeInstruction, nextTarget, stepStatus, type Instruction } from "./orders";

const base: Instruction = {
  id: "i1", type: "subscribe", fund_code: "ATR-BAL", fund_name: "Atrium Balanced", to_fund_code: null, to_fund_name: null,
  amount: "1000.00", units: null, state: "accepted", acknowledged_risk: false, requested_at: "2026-10-12T09:00:00Z",
  steps: [
    { state: "received", note: "Received.", at: "2026-10-12T09:00:00Z" },
    { state: "checked", note: "All checks passed.", at: "2026-10-12T09:00:00Z" },
    { state: "accepted", note: "Accepted.", at: "2026-10-12T09:00:00Z" },
  ],
};

describe("stepStatus", () => {
  it("marks the steps an accepted instruction has reached", () => {
    expect(stepStatus(base).map((s) => s.done)).toEqual([true, true, true, false, false]);
    expect(stepStatus(base)[1].note).toBe("All checks passed.");
  });
  it("treats an older settled instruction with no recorded steps as complete", () => {
    expect(stepStatus({ ...base, state: "settled", steps: [] }).every((s) => s.done)).toBe(true);
  });
});

describe("describe", () => {
  it("says what the instruction does in words", () => {
    expect(describeInstruction(base)).toBe("Invest $1,000.00 in Atrium Balanced");
    expect(describeInstruction({ ...base, type: "switch", amount: null, units: "10.000000", to_fund_name: "Atrium Cash Reserve" }))
      .toBe("Switch 10.0000 units from Atrium Balanced to Atrium Cash Reserve");
    expect(describeInstruction({ ...base, type: "redeem", amount: null, units: "2.5" })).toBe("Withdraw 2.5000 units of Atrium Balanced");
  });
});

describe("nextTarget", () => {
  it("keeps a valid switch target and replaces one that equals the source fund", () => {
    const codes = ["ATR-CASH", "ATR-INC", "ATR-BAL"];
    expect(nextTarget(codes, "ATR-BAL", "ATR-CASH")).toBe("ATR-CASH");
    expect(nextTarget(codes, "ATR-CASH", "ATR-CASH")).toBe("ATR-INC");
  });
});
