import type { GraphColumns, GraphEdge, GraphNode } from "./compliance";

export type RingPattern = "synthetic_identity_farm" | "mule_network" | "account_takeover" | "duplicate_identity" | "unclear";
export type IdentifierKind = "bank" | "device" | "document" | "phone" | "email" | "ip";
export type Stage = "lead" | "client";
export type RingMember = { id: string; kind: Stage; label: string; flags: string[]; flagged: boolean; ring_flagged: boolean };
export type Ring = {
  id: string; score: number; members: RingMember[]; stages: Stage[];
  strongest: string; strongest_kind: IdentifierKind; strongest_members: string[];
  identifiers: number; strong_identifiers: number; links: number; created_span_hours: number;
  case_alert_id: string | null; case: { id: string; title: string; state: "open" | "escalated" | "closed" } | null;
  flagged_leads: number;
};
export type RingLinkRow = {
  id: string; member: string; member_kind: Stage; identifier: string; kind: IdentifierKind;
  strength: "strong" | "weak"; detail: string; seen_at: string | null;
};
export type RingDetail = Ring & { graph: { nodes: GraphNode[]; edges: GraphEdge[] }; link_rows: RingLinkRow[] };
export type RingList = { rings: Ring[]; strongest: Ring | null };
export type RingNarrative = {
  pattern: RingPattern; summary: string; parts: { text: string; links: string[] }[]; next_checks: string[];
};
export type NarrateResult = { narrative: RingNarrative; dropped_citations: number; model: string; unsupported_figures: string[] };

export const PATTERN_LABEL: Record<RingPattern, string> = {
  synthetic_identity_farm: "Synthetic identity farm", mule_network: "Mule network", account_takeover: "Account takeover",
  duplicate_identity: "Duplicate identity", unclear: "Unclear",
};
export const KIND_LABEL: Record<IdentifierKind, string> = {
  bank: "Bank account", device: "Device", document: "Identity document", phone: "Phone", email: "Email", ip: "Network",
};
const NOUN: Record<IdentifierKind, string> = {
  bank: "bank account", device: "device", document: "identity document", phone: "phone number", email: "email address",
  ip: "network",
};
/** How a shared identifier reaches a client's account, in the headline. */
const REACH: Record<IdentifierKind, string> = {
  bank: "pays into", device: "signs in to", document: "belongs to", phone: "belongs to", email: "belongs to", ip: "connects to",
};

/** Leads on the left, what they share in the middle, clients on the right: a ring that crosses stages reads left to right. */
export const RING_COLUMNS: GraphColumns = {
  lead: 0, person: 0, device: 1, phone: 1, email: 1, ip: 1, document: 1, bank: 1, account: 1, client: 2, payer: 2,
};

export function stageLabel(stages: Stage[]): string {
  if (stages.includes("lead") && stages.includes("client")) return "Leads and clients";
  return stages.includes("client") ? "Clients only" : "Leads only";
}

const amlFlag = (m: RingMember) => m.flags.find((f) => f.startsWith("AML: "));

/** The ring in one sentence. A ring whose strongest link joins several leads to a client says so, with the client's
 *  most serious AML flag; any other ring says how many identities share how many strong identifiers (a shared
 *  network is shown in the graph but joins no one, so the sentence does not count it). */
export function ringHeadline(ring: Ring): string {
  const on = (kind: Stage) => ring.members.filter((m) => m.kind === kind && ring.strongest_members.includes(m.id));
  const leads = on("lead");
  const clients = on("client");
  const noun = NOUN[ring.strongest_kind];
  if (leads.length >= 2 && clients.length >= 1) {
    const flagged = clients.find(amlFlag);
    const reached = clients.length === 1 ? "a client account" : `${clients.length} client accounts`;
    const flag = clients.length === 1 && flagged ? ` flagged for ${amlFlag(flagged)!.slice(5)}` : "";
    return `${leads.length} identities share one ${noun}, and that ${noun} also ${REACH[ring.strongest_kind]} ${reached}${flag}.`;
  }
  const n = ring.members.length;
  return ring.strong_identifiers <= 1
    ? `${n} identities share one ${noun}.`
    : `${n} identities share ${ring.strong_identifiers} identifiers, among them one ${noun}.`;
}

/** What Gemini Flash does while it explains a ring, in order (app/services/rings.py narrate_ring). */
export const RING_STEPS = [
  "Reading the ring's members and links",
  "Gemini Flash is matching the ring to known fraud patterns",
  "Checking every cited link belongs to this ring",
];

/** Every link a reading cites, once each, in the order it first cites them: what the graph lights when it arrives. */
export function citedLinks(narrative: Pick<RingNarrative, "parts">): string[] {
  return [...new Set(narrative.parts.flatMap((p) => p.links))];
}

export function flaggedMessage(count: number): string {
  if (count === 0) return "These leads were already flagged; nothing changed.";
  return count === 1 ? "1 lead flagged; its Trust Score was updated." : `${count} leads flagged; their Trust Scores were updated.`;
}

export function scoreTone(score: number): "loss" | "caution" | "neutral" {
  return score >= 70 ? "loss" : score >= 40 ? "caution" : "neutral";
}

/** A case needs a client (an AML alert is always on a person with an account); flagging needs leads. */
export const canOpenCase = (ring: Ring) => ring.members.some((m) => m.kind === "client");
export const canFlagLeads = (ring: Ring) => ring.members.some((m) => m.kind === "lead");
