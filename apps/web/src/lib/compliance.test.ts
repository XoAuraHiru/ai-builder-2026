import { describe, expect, it } from "vitest";
import { alertFindings, alertsMoment, citationLabels, layoutGraph, purposeLabel, thresholdBars, type EvidenceRow, type GraphNode } from "./compliance";

const NODES: GraphNode[] = [
  { id: "person:b", kind: "person", label: "Noah Williams", flagged: false },
  { id: "person:a", kind: "person", label: "Aisha Khan", flagged: true },
  { id: "account:1", kind: "account", label: "Account ACC-0001", flagged: false },
  { id: "bank:x", kind: "bank", label: "Bank account ending 4471", flagged: false },
  { id: "payer:m", kind: "payer", label: "Marcus Okonkwo", flagged: false },
];

describe("layoutGraph", () => {
  it("puts people, accounts and what they share in three columns", () => {
    const { at, height } = layoutGraph(NODES, 600, 80);
    expect([at["person:a"].x, at["account:1"].x, at["bank:x"].x, at["payer:m"].x]).toEqual([100, 300, 500, 500]);
    expect(height).toBe(240);
    expect(at["person:a"].y).toBeLessThan(at["person:b"].y);
    expect(at["account:1"].y).toBe(120);
  });
});

describe("labels", () => {
  it("numbers evidence rows in order", () => {
    expect(citationLabels([{ id: "x" }, { id: "y" }])).toEqual({ x: "E1", y: "E2" });
  });
  it("names AI purposes plainly", () => {
    expect(purposeLabel("aml_case_review")).toBe("AML case review");
    expect(purposeLabel("ops_brief")).toBe("Morning brief");
    expect(purposeLabel("something_new")).toBe("Something new");
  });
});

describe("alertFindings", () => {
  const row = (id: string, kind: EvidenceRow["kind"], date: string, amount: string | null, detail = "") => ({ kind, id, date, amount, detail });
  it("shows a payment alert's money, its days and who else is linked", () => {
    const found = alertFindings({
      scenario: "structuring", severity: "high",
      evidence: [row("a", "instruction", "2026-10-07", "9400.00"), row("b", "instruction", "2026-10-09", "9750.00"),
        row("c", "instruction", "2026-10-11", "9900.00"), row("k", "bank_link", "2026-10-13", null)],
      graph: { nodes: NODES.slice(1, 4), edges: [{ source: "person:a", target: "account:1", label: "holds" }, { source: "account:1", target: "bank:x", label: "pays from" }] },
    });
    expect(found.map((f) => [f.title, f.figure, f.unit, f.chip.tone])).toEqual([
      ["Money in the evidence", "$29,050", undefined, "caution"],
      ["From first to last", "4", "days", "caution"],
      ["Linked people", "0", undefined, "neutral"],
    ]);
    expect(found[1].text).toBe("From Oct 7 to Oct 11.");
    expect(found[1].chip.label).toBe("Inside the rule's 7 days");
  });
  it("names linked people and a shared bank account in coral", () => {
    const found = alertFindings({
      scenario: "linked_round_trip", severity: "high",
      evidence: [row("x", "posting", "2026-10-05", "4900.00"), row("y", "instruction", "2026-10-09", "4900.00")],
      graph: {
        nodes: [...NODES.slice(0, 4)],
        edges: [{ source: "account:1", target: "bank:x", label: "pays from" }, { source: "account:2", target: "bank:x", label: "pays from" }],
      },
    });
    expect(found[2]).toEqual({ title: "Linked people", figure: "1", text: "Noah Williams", chip: { label: "Share a bank account", tone: "loss" } });
  });
  it("reads a behaviour alert's measures against ordinary accounts", () => {
    const found = alertFindings({
      scenario: "anomaly", severity: "low", graph: { nodes: [], edges: [] },
      evidence: [row("f1", "feature", "2026-10-13", "42000.00", "Taken out over 90 days: $42,000, where ordinary accounts sit near $1,000")],
    });
    expect(found).toEqual([{ title: "Taken out over 90 days", figure: "$42,000", text: "Ordinary accounts sit near $1,000.", chip: { label: "Far from ordinary", tone: "loss" } }]);
  });
});

describe("alertsMoment", () => {
  it("says how many alerts wait and points at the most serious", () => {
    const a = (id: string, severity: "high" | "medium" | "low", score: number) => ({ id, severity, score, title: id });
    expect(alertsMoment([])).toEqual({ tone: "good", title: "No open alerts. Monitoring runs again this evening.", top: null });
    expect(alertsMoment([a("m", "medium", 0.9), a("h1", "high", 0.8), a("h2", "high", 0.9)]))
      .toEqual({ tone: "alert", title: "3 open alerts wait for a decision; 2 are high severity.", top: "h2" });
    expect(alertsMoment([a("l", "low", 1)]).title).toBe("1 open alert waits for a decision.");
    expect(alertsMoment([a("h", "high", 1)]).title).toBe("1 open alert waits for a decision, and it is high severity.");
  });
});

describe("thresholdBars", () => {
  it("scales each payment against the reporting line, labelled by its evidence row", () => {
    const ev = (id: string, amount: string | null, kind = "instruction") => ({ kind, id, date: "2026-10-06", amount, detail: "" }) as EvidenceRow;
    const { bars, linePct } = thresholdBars([ev("a", "9400.00"), ev("b", "9750.00"), ev("c", "9900.00"), ev("bank", null, "bank_link")], 10000);
    expect(bars.map((b) => [b.label, Math.round(b.pct)])).toEqual([["E1", 87], ["E2", 90], ["E3", 92]]);
    expect(bars.map((b) => b.tone)).toEqual(["near", "near", "near"]);
    expect(thresholdBars([ev("p", "4000.00"), ev("q", "12000.00")], 10000).bars.map((b) => b.tone)).toEqual(["under", "over"]);
    expect(Math.round(linePct)).toBe(93);
    expect(thresholdBars([ev("x", null, "feature")], 10000).bars).toEqual([]);
  });
});
