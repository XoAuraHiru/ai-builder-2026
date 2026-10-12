import { describe, expect, it } from "vitest";
import { attentionHeadline, deviceId, groupByStage, scoreTone, STAGES, strongestSignal, triage, trustTone, type Lead } from "./leads";

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

const scored = (id: string, over: Partial<Lead>) =>
  ({ id, full_name: id, stage: "new", lead_score: 50, trust_score: 100, trust_band: "clear", trust_signals: [],
     scored_at: "2026-10-12T10:00:00Z", ...over }) as Lead;
const signal = (code: string, label: string, weight: number) => ({ code, label, weight, evidence: "", source: "rules", blocking: false });

describe("triage", () => {
  it("puts risky leads first, then the ones worth a call by fit, and keeps clients and unscored apart", () => {
    const leads = [
      scored("ring", { trust_band: "high_risk", trust_score: 27 }), scored("blocked", { trust_band: "blocked", trust_score: 0 }),
      scored("good", { lead_score: 66 }), scored("ok", { lead_score: 39, trust_band: "review" }),
      scored("client", { stage: "client", lead_score: 91 }), scored("fresh", { scored_at: null }),
      scored("lost", { stage: "disqualified" }),
    ];
    const t = triage(leads);
    expect(t.attention.map((l) => l.id)).toEqual(["blocked", "ring"]);
    expect(t.call.map((l) => l.id)).toEqual(["good", "ok"]);
    expect([t.clients.map((l) => l.id), t.unscored.map((l) => l.id), t.closed.map((l) => l.id)]).toEqual([["client"], ["fresh"], ["lost"]]);
  });
  it("says what the risky leads have in common, in one sentence", () => {
    const ring = ["a", "b", "c", "d"].map((id) => scored(id, {
      trust_band: "high_risk", trust_signals: [signal("T01", "Disposable email domain", 30), signal("T05", "Many leads from one device", 40)] }));
    expect(attentionHeadline(ring)).toBe("4 leads arrived from one device within 24 hours, each with a throwaway email address.");
    expect(attentionHeadline([scored("x", { full_name: "Linda Morales", trust_band: "blocked" })])).toBe("Linda Morales needs a look before anyone calls.");
    expect(attentionHeadline([scored("x", { trust_band: "blocked" }), scored("y", { trust_band: "blocked" })])).toBe("2 leads need a look before anyone calls them.");
    expect(strongestSignal(ring[0])).toBe("Many leads from one device");
    expect(strongestSignal(scored("z", {}))).toBeNull();
  });
});
