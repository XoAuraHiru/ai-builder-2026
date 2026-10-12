import { describe, expect, it } from "vitest";
import { deviceId, groupByStage, scoreTone, STAGES, trustTone, type Lead } from "./leads";

const lead = (id: string, stage: Lead["stage"], score: number | null, name = id) =>
  ({ id, stage, lead_score: score, full_name: name }) as Lead;

describe("groupByStage", () => {
  it("returns every stage and sorts by score, unscored last", () => {
    const groups = groupByStage([lead("a", "new", 40), lead("b", "new", null), lead("c", "new", 90), lead("d", "client", 10)]);
    expect(Object.keys(groups)).toEqual([...STAGES]);
    expect(groups.new.map((l) => l.id)).toEqual(["c", "a", "b"]);
    expect(groups.client.map((l) => l.id)).toEqual(["d"]);
    expect(groups.proposal).toEqual([]);
  });
});

describe("tones", () => {
  it("maps scores and bands", () => {
    expect([scoreTone(85), scoreTone(70), scoreTone(55), scoreTone(10), scoreTone(null)]).toEqual(
      ["high", "high", "medium", "low", "pending"]);
    expect([trustTone("clear"), trustTone("blocked"), trustTone(null)]).toEqual(["clear", "blocked", "pending"]);
  });
});

describe("deviceId", () => {
  it("creates one id and then reuses it", () => {
    const store = new Map<string, string>();
    const storage = { getItem: (k: string) => store.get(k) ?? null, setItem: (k: string, v: string) => void store.set(k, v) };
    const first = deviceId(storage);
    expect(first).toMatch(/^[A-Za-z0-9-]{8,64}$/);
    expect(deviceId(storage)).toBe(first);
  });
});
