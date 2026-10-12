import { describe, expect, it } from "vitest";
import { WORKSPACES, workspaceFor, sectionFor } from "./nav";
import { PERSONAS } from "./personas";
import { addVisit, JOURNEYS, journeyFor, loadVisits, progress, saveVisits, stepMatches } from "./journeys";

describe("journeys", () => {
  it("gives every persona a story of two to four steps", () => {
    for (const p of PERSONAS) {
      const j = journeyFor(p.email);
      expect(j, p.email).not.toBeNull();
      expect(j!.steps.length).toBeGreaterThanOrEqual(2);
      expect(j!.steps.length).toBeLessThanOrEqual(4);
    }
    expect(journeyFor("nobody@example.test")).toBeNull();
  });
  it("points every step at a page inside the person's own workspace or the Copilot", () => {
    const roles: Record<string, string[]> = {
      Investor: ["investor"], Advisor: ["advisor", "staff"], Operations: ["ops", "staff"], Compliance: ["compliance", "staff"],
    };
    for (const p of PERSONAS) {
      const space = workspaceFor(roles[p.role])!;
      for (const s of journeyFor(p.email)!.steps) {
        const reachable = sectionFor(space, s.href) !== null || s.href === "/investor/copilot";
        expect(reachable, `${p.email} ${s.href}`).toBe(true);
      }
    }
    expect(Object.keys(WORKSPACES)).toHaveLength(4);
  });
  it("matches a step by its exact page, or by its pattern", () => {
    const priya = journeyFor("priya@atrium.demo")!;
    expect(stepMatches(priya.steps[0], "/investor")).toBe(true);
    expect(stepMatches(priya.steps[0], "/investor/xray")).toBe(false);
    const omar = journeyFor("omar@atrium.demo")!;
    expect(stepMatches(omar.steps[1], "/compliance/alerts/abc")).toBe(true);
    expect(stepMatches(omar.steps[1], "/compliance")).toBe(false);
  });
  it("ticks the visited steps and points at the first one left", () => {
    const priya = journeyFor("priya@atrium.demo")!;
    expect(progress(priya, [])).toEqual({ done: [false, false, false, false], current: 0, count: 0 });
    expect(progress(priya, ["/investor", "/investor/markets/NVDA"])).toEqual({ done: [true, false, true, false], current: 1, count: 2 });
    const all = priya.steps.map((s) => s.href);
    expect(progress(priya, all).current).toBeNull();
  });
  it("remembers each page once, and only the latest sixty", () => {
    expect(addVisit(["/a"], "/a")).toEqual(["/a"]);
    const many = Array.from({ length: 70 }, (_, i) => `/p${i}`).reduce(addVisit, [] as string[]);
    expect(many).toHaveLength(60);
    expect(many[59]).toBe("/p69");
  });
  it("survives storage that is blocked or holds junk", () => {
    expect(loadVisits("priya@atrium.demo")).toEqual([]);   // no localStorage in the test environment
    expect(() => saveVisits("priya@atrium.demo", ["/investor"])).not.toThrow();
    const store: Record<string, string> = { "atrium.journey.priya@atrium.demo": "{not json" };
    globalThis.localStorage = { getItem: (k: string) => store[k] ?? null, setItem: (k: string, v: string) => { store[k] = v; } } as Storage;
    expect(loadVisits("priya@atrium.demo")).toEqual([]);
    saveVisits("PRIYA@atrium.demo", ["/investor", "/investor/what-if"]);
    expect(loadVisits("priya@atrium.demo")).toEqual(["/investor", "/investor/what-if"]);
    store["atrium.journey.priya@atrium.demo"] = JSON.stringify(["/investor", 7, null]);
    expect(loadVisits("priya@atrium.demo")).toEqual(["/investor"]);
    // @ts-expect-error tidy up the stand-in
    delete globalThis.localStorage;
    expect(JOURNEYS).toHaveLength(8);
  });
});
