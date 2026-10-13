import { describe, expect, it } from "vitest";
import {
  applicationErrors, attentionHeadline, deviceId, groupByStage, meterSegments, scoreTone, signedWeight, sourceLabel, STAGES, strongestSignal, timeAgo, topSignals, triage,
  TRUST_SEGMENTS, trustMeter, trustTone, type Lead,
} from "./leads";

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
  it("finds the strongest signal by the size of its deduction, as the API sends them (negative)", () => {
    const l = scored("x", { trust_signals: [signal("T02", "Phone not in international format", -10), signal("T01", "Disposable email domain", -25)] });
    expect(strongestSignal(l)).toBe("Disposable email domain");
    expect(topSignals(l, 1).map((s) => s.code)).toEqual(["T01"]);
    expect(topSignals(l).map((s) => s.code)).toEqual(["T01", "T02"]);
  });
});

describe("trust meter", () => {
  it("fills one of 20 segments per 5 points, in the band's colour", () => {
    expect(TRUST_SEGMENTS).toBe(20);
    expect(trustMeter(23, "high_risk")).toEqual({ filled: 5, tone: "coral" });
    expect(trustMeter(50, "review")).toEqual({ filled: 10, tone: "amber" });
    expect(trustMeter(100, "clear")).toEqual({ filled: 20, tone: "green" });
    expect(trustMeter(60, "blocked")).toEqual({ filled: 12, tone: "coral" });
  });
  it("keeps a non-zero score visible, empties a zero, and shows nothing before scoring", () => {
    expect(trustMeter(2, "high_risk")).toEqual({ filled: 1, tone: "coral" });
    expect(trustMeter(0, "blocked")).toEqual({ filled: 0, tone: "coral" });
    expect(trustMeter(null, null)).toEqual({ filled: 0, tone: "none" });
    expect(trustMeter(140, "clear").filled).toBe(20);
  });
});

describe("meterSegments", () => {
  it("lists the 20 segments in the order they fill, the filled ones in the band's tone", () => {
    const segments = meterSegments(23, "high_risk");
    expect(segments).toHaveLength(20);
    expect(segments.slice(0, 5)).toEqual(["coral", "coral", "coral", "coral", "coral"]);
    expect(segments.slice(5).every((s) => s === null)).toBe(true);
    expect(meterSegments(100, "clear").every((s) => s === "green")).toBe(true);
  });
  it("is empty before scoring and for a zero", () => {
    expect(meterSegments(null, null).every((s) => s === null)).toBe(true);
    expect(meterSegments(0, "blocked").every((s) => s === null)).toBe(true);
  });
});

describe("applicationErrors", () => {
  const ok = { full_name: "Avery Quinn", email: "avery@example.com", goals: "Retire early", horizon_years: "10", investable_usd: "25000" };
  it("passes a complete application", () => {
    expect(applicationErrors(ok)).toEqual({});
  });
  it("says what to fix, one sentence per field", () => {
    expect(applicationErrors({ full_name: " A ", email: "avery@", goals: "", horizon_years: "51", investable_usd: "" })).toEqual({
      full_name: "Enter your full name.",
      email: "Enter an email address, like name@example.com.",
      goals: "Tell us what you are investing for, in a few words.",
      horizon_years: "Choose between 0 and 50 years.",
      investable_usd: "Enter how much you would invest now.",
    });
    expect(applicationErrors({ ...ok, horizon_years: "2.5", investable_usd: "0" })).toEqual({
      horizon_years: "Choose between 0 and 50 years.", investable_usd: "Enter how much you would invest now." });
  });
});

describe("signal and lead wording", () => {
  it("signs weights with a true minus", () => {
    expect([signedWeight(-25), signedWeight(6), signedWeight(0)]).toEqual(["−25", "+6", "0"]);
  });
  it("names where a lead came from", () => {
    expect([sourceLabel("web"), sourceLabel("referral"), sourceLabel("event"), sourceLabel("fax")]).toEqual(
      ["Web enquiry", "Referral", "Event", "Fax"]);
  });
  it("says how long ago, reading the API's zone-less times as UTC", () => {
    const now = new Date("2026-10-13T12:00:00Z");
    expect(timeAgo("2026-10-13T11:59:40", now)).toBe("just now");
    expect(timeAgo("2026-10-13T11:59:00", now)).toBe("1 minute ago");
    expect(timeAgo("2026-10-13T11:35:00Z", now)).toBe("25 minutes ago");
    expect(timeAgo("2026-10-13T10:00:00", now)).toBe("2 hours ago");
    expect(timeAgo("2026-10-12T09:00:00", now)).toBe("yesterday");
    expect(timeAgo("2026-10-09T12:00:00", now)).toBe("4 days ago");
    expect(timeAgo("2026-09-01T12:00:00", now)).toBe("Sep 1, 2026");
  });
});
