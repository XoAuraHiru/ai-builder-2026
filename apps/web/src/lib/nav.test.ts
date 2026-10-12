import { describe, expect, it } from "vitest";
import { isActive, isPublic, WORKSPACES, workspacesFor } from "./nav";

describe("workspacesFor", () => {
  it("gives investors only the investor workspace", () => {
    expect(workspacesFor(["investor"]).map((w) => w.key)).toEqual(["investor"]);
  });
  it("puts a staff member's own workspace first", () => {
    expect(workspacesFor(["ops", "staff"]).map((w) => w.key)).toEqual(["operations", "advisor", "compliance"]);
    expect(workspacesFor(["advisor", "staff"])[0].key).toBe("advisor");
    expect(workspacesFor(["compliance", "staff"])[0].key).toBe("compliance");
  });
  it("gives unknown roles nothing", () => {
    expect(workspacesFor([])).toEqual([]);
  });
});

describe("isActive", () => {
  it("matches workspace roots exactly", () => {
    expect(isActive("/investor", "/investor")).toBe(true);
    expect(isActive("/investor/funds", "/investor")).toBe(false);
  });
  it("keeps a section active on its detail pages", () => {
    expect(isActive("/investor/funds/ATR-BAL", "/investor/funds")).toBe(true);
    expect(isActive("/advisor/leads/abc", "/advisor")).toBe(true);
  });
  it("knows the trading pages", () => {
    expect(WORKSPACES.investor.links.map((l) => l.href)).toEqual(expect.arrayContaining(["/investor/markets", "/investor/trades"]));
    expect(WORKSPACES.advisor.links.map((l) => l.label)).toContain("Held orders");
    expect(isActive("/investor/markets/NVDA", "/investor/markets")).toBe(true);
    expect(isActive("/advisor/held", "/advisor")).toBe(false);
  });
});

describe("isPublic", () => {
  it("knows the pages that need no sign-in", () => {
    expect(isPublic("/apply")).toBe(true);
    expect(isPublic("/login")).toBe(true);
    expect(isPublic("/investor")).toBe(false);
  });
});
