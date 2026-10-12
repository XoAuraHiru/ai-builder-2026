import { describe, expect, it } from "vitest";
import { citationLabels, layoutGraph, purposeLabel, type GraphNode } from "./compliance";

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
