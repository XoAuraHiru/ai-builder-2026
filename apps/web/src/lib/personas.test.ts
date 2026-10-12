import { describe, expect, it } from "vitest";
import { actFor, initials, personaFor, PERSONAS, personasByAct } from "./personas";

describe("personas", () => {
  it("finds a persona by email, whatever the case", () => {
    expect(personaFor("PRIYA@atrium.demo")?.name).toBe("Priya Raman");
    expect(personaFor("nobody@example.test")).toBeNull();
    expect(personaFor(null)).toBeNull();
  });
  it("makes initials from a name", () => {
    expect(initials("Priya Raman")).toBe("PR");
    expect(initials("Kenji")).toBe("KE");
    expect(initials("  ")).toBe("?");
  });
  it("places each person in a stage, falling back on their role", () => {
    expect(actFor("tom@atrium.demo", ["investor"])).toBe("trade");
    expect(actFor("new@example.test", ["investor"])).toBe("invest");
    expect(actFor("boss@example.test", ["admin", "staff"])).toBe("acquire");
    expect(actFor("checker@example.test", ["ops", "staff"])).toBe("operate");
  });
  it("groups the eight people by stage, in story order, with Priya as the start", () => {
    expect(personasByAct().map((g) => [g.act.key, g.people.length])).toEqual([["acquire", 1], ["invest", 2], ["trade", 2], ["operate", 3]]);
    expect(PERSONAS.filter((p) => p.start).map((p) => p.name)).toEqual(["Priya Raman"]);
  });
});
