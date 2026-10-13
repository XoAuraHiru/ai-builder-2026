import { describe, expect, it } from "vitest";
import { layoutGraph, type GraphNode } from "./compliance";
import {
  canFlagLeads, canOpenCase, flaggedMessage, PATTERN_LABEL, RING_COLUMNS, ringHeadline, scoreTone, stageLabel, type Ring,
} from "./rings";

const member = (id: string, kind: "lead" | "client", label: string, flags: string[] = []) =>
  ({ id, kind, label, flags, flagged: flags.length > 0, ring_flagged: false });

/** The strongest seeded ring: four leads on the ring device, which also signs in to Sofia Rossi's account. */
const SEEDED: Ring = {
  id: "daab47fe08df", score: 100,
  members: [
    member("lead:c", "lead", "Casey Morgan"), member("lead:j", "lead", "Jordan Lee"), member("lead:t", "lead", "Taylor Kim"),
    member("lead:a", "lead", "Alex Mercer"),
    member("person:s", "client", "Sofia Rossi", ["AML: money in and straight out", "AML: unusual account behaviour"]),
  ],
  stages: ["lead", "client"], strongest: "Device dev-…0001", strongest_kind: "device",
  strongest_members: ["lead:a", "lead:c", "lead:j", "lead:t", "person:s"], identifiers: 2, strong_identifiers: 1, links: 9,
  created_span_hours: 17544, case_alert_id: null, case: null, flagged_leads: 0,
};

describe("ringHeadline", () => {
  it("says how the strongest seeded ring reaches a flagged client", () => {
    expect(ringHeadline(SEEDED)).toBe(
      "4 identities share one device, and that device also signs in to a client account flagged for money in and straight out.");
  });
  it("leaves out the flag when the client has none", () => {
    const quiet = { ...SEEDED, members: SEEDED.members.map((m) => (m.kind === "client" ? { ...m, flags: [], flagged: false } : m)) };
    expect(ringHeadline(quiet)).toBe("4 identities share one device, and that device also signs in to a client account.");
  });
  it("is generic otherwise: N identities share K identifiers, counting only the strong ones", () => {
    const chen: Ring = {
      ...SEEDED, members: [member("lead:m", "lead", "Michael Chen"), member("lead:n", "lead", "M. Chen")], stages: ["lead"],
      strongest: "Phone ending 0142", strongest_kind: "phone", strongest_members: ["lead:m", "lead:n"], identifiers: 2,
      strong_identifiers: 1,
    };
    expect(ringHeadline(chen)).toBe("2 identities share one phone number.");
    expect(ringHeadline({ ...chen, identifiers: 4, strong_identifiers: 3 })).toBe("2 identities share 3 identifiers, among them one phone number.");
    const bank: Ring = { ...chen, members: [member("person:n", "client", "Noah Williams"), member("person:a", "client", "Aisha Khan")],
      stages: ["client"], strongest_kind: "bank", strongest_members: ["person:a", "person:n"] };
    expect(ringHeadline(bank)).toBe("2 identities share one bank account.");
  });
});

describe("labels", () => {
  it("names every pattern Gemini may give", () => {
    expect(PATTERN_LABEL).toEqual({
      synthetic_identity_farm: "Synthetic identity farm", mule_network: "Mule network", account_takeover: "Account takeover",
      duplicate_identity: "Duplicate identity", unclear: "Unclear",
    });
  });
  it("names the stages a ring spans", () => {
    expect(stageLabel(["lead", "client"])).toBe("Leads and clients");
    expect(stageLabel(["lead"])).toBe("Leads only");
    expect(stageLabel(["client"])).toBe("Clients only");
  });
  it("says what flagging did", () => {
    expect(flaggedMessage(3)).toBe("3 leads flagged; their Trust Scores were updated.");
    expect(flaggedMessage(1)).toBe("1 lead flagged; its Trust Score was updated.");
    expect(flaggedMessage(0)).toBe("These leads were already flagged; nothing changed.");
  });
  it("tones the score", () => {
    expect([scoreTone(100), scoreTone(70), scoreTone(52), scoreTone(37)]).toEqual(["loss", "loss", "caution", "neutral"]);
  });
});

describe("actions", () => {
  it("offers a case only when the ring reaches a client, and flagging only when it holds leads", () => {
    expect([canOpenCase(SEEDED), canFlagLeads(SEEDED)]).toEqual([true, true]);
    const leadsOnly = { ...SEEDED, stages: ["lead"] as Ring["stages"], members: SEEDED.members.filter((m) => m.kind === "lead") };
    expect([canOpenCase(leadsOnly), canFlagLeads(leadsOnly)]).toEqual([false, true]);
    const clientsOnly = { ...SEEDED, stages: ["client"] as Ring["stages"], members: SEEDED.members.filter((m) => m.kind === "client") };
    expect([canOpenCase(clientsOnly), canFlagLeads(clientsOnly)]).toEqual([true, false]);
  });
});

describe("the ring layout", () => {
  it("puts leads on the left, what they share in the middle, and clients on the right", () => {
    const nodes: GraphNode[] = [
      { id: "lead:a", kind: "lead", label: "Alex Mercer", flagged: false },
      { id: "device:x", kind: "device", label: "Device dev-…0001", flagged: false },
      { id: "ip:y", kind: "ip", label: "Network …ab12", flagged: false },
      { id: "person:s", kind: "client", label: "Sofia Rossi", flagged: true },
    ];
    const { at } = layoutGraph(nodes, 600, 80, RING_COLUMNS);
    expect([at["lead:a"].x, at["device:x"].x, at["ip:y"].x, at["person:s"].x]).toEqual([100, 300, 300, 500]);
  });
});
