import { describe, expect, it } from "vitest";
import { routeKind, sectionFor, tabFor, WORKSPACES, workspaceFor } from "./nav";

const investor = WORKSPACES.investor;

describe("workspaceFor", () => {
  it("gives each person only their own workspace", () => {
    expect(workspaceFor(["investor"])?.key).toBe("investor");
    expect(workspaceFor(["advisor", "staff"])?.key).toBe("advisor");
    expect(workspaceFor(["ops", "staff"])?.key).toBe("operations");
    expect(workspaceFor(["compliance", "staff"])?.key).toBe("compliance");
    expect(workspaceFor(["admin", "staff"])?.key).toBe("advisor");
    expect(workspaceFor([])).toBeNull();
  });
  it("keeps every rail to five items at most", () => {
    for (const w of Object.values(WORKSPACES)) expect(w.sections.length).toBeLessThanOrEqual(5);
  });
});

describe("sectionFor", () => {
  it("maps deep pages to their rail item", () => {
    expect(sectionFor(investor, "/investor")?.key).toBe("home");
    expect(sectionFor(investor, "/investor/xray")?.key).toBe("portfolio");
    expect(sectionFor(investor, "/investor/profile")?.key).toBe("portfolio");
    expect(sectionFor(investor, "/investor/markets/NVDA")?.key).toBe("markets");
    expect(sectionFor(investor, "/investor/trades")?.key).toBe("markets");
    expect(sectionFor(investor, "/investor/funds/ATR-BAL")?.key).toBe("funds");
    expect(sectionFor(investor, "/investor/orders")?.key).toBe("funds");
    expect(sectionFor(investor, "/investor/what-if")?.key).toBe("plan");
    expect(sectionFor(investor, "/investor/copilot")).toBeNull();
    expect(sectionFor(WORKSPACES.advisor, "/advisor/leads/abc/proposal")?.key).toBe("leads");
    expect(sectionFor(WORKSPACES.advisor, "/advisor/held")?.key).toBe("held");
    expect(sectionFor(WORKSPACES.operations, "/operations")?.key).toBe("today");
    expect(sectionFor(WORKSPACES.operations, "/operations/approvals")?.key).toBe("approvals");
    expect(sectionFor(WORKSPACES.compliance, "/compliance/alerts/x")?.key).toBe("alerts");
    expect(sectionFor(WORKSPACES.compliance, "/compliance/log")?.key).toBe("log");
  });
  it("finds the tab inside a section", () => {
    const portfolio = sectionFor(investor, "/investor/risk")!;
    expect(tabFor(portfolio, "/investor/risk")?.label).toBe("Risk");
    const markets = sectionFor(investor, "/investor/markets/NVDA")!;
    expect(tabFor(markets, "/investor/markets/NVDA")?.label).toBe("Markets");
    expect(tabFor(markets, "/investor/trades")?.label).toBe("Your trades");
  });
});

describe("routeKind", () => {
  it("tells the front door, public pages and the app apart", () => {
    expect(routeKind("/")).toBe("front");
    expect(routeKind("/login")).toBe("public");
    expect(routeKind("/apply")).toBe("public");
    expect(routeKind("/investor")).toBe("app");
  });
});
