export const STAGES = ["new", "qualified", "proposal", "onboarding", "client", "disqualified"] as const;
export type Stage = (typeof STAGES)[number];
export const STAGE_LABEL: Record<Stage, string> = {
  new: "New", qualified: "Qualified", proposal: "Proposal", onboarding: "Onboarding", client: "Client",
  disqualified: "Disqualified",
};

export type Factor = { feature: string; label: string; value: string; impact: number };
export type TrustSignal = {
  code: string; label: string; weight: number; evidence: string; source: string; blocking: boolean;
};
export type TrustBand = "clear" | "review" | "high_risk" | "blocked";
/** The front-door analysis a prospect ran before applying (its headline figures, as saved). */
export type LeadAnalysis = {
  id: string; created_at: string; kind: "unit_trust" | "share"; code: string; name: string; initial_usd: string;
  monthly_usd: string; years: number;
  summary: { median_usd: number; p10_usd: number; p90_usd: number; contributed_usd: number; prob_loss_pct: number;
    window_start: string; window_end: string; comparison_median_usd: number | null };
};

export type Lead = {
  id: string; created_at: string; source: string; stage: Stage; full_name: string; email: string;
  phone: string | null; country: string; goals: string; horizon_years: number; investable_usd: string;
  monthly_usd: string; source_of_funds: string; notes: string | null;
  enrichment: {
    goal_category: string; goals_summary: string; suggested_funds: string[]; stated_risk_appetite: string;
    next_best_action: string; confidence: number;
  } | null;
  lead_score: number | null;
  lead_score_factors: { for: Factor[]; against: Factor[]; model: string; source: string; probability: number } | null;
  trust_score: number | null; trust_band: TrustBand | null; trust_signals: TrustSignal[] | null;
  next_best_action: string | null; scored_at: string | null; scoring_error: string | null;
  converted_person_id: string | null;
  analysis?: LeadAnalysis | null;
};

export function groupByStage(leads: Lead[]): Record<Stage, Lead[]> {
  const groups = Object.fromEntries(STAGES.map((s) => [s, [] as Lead[]])) as Record<Stage, Lead[]>;
  for (const l of leads) groups[l.stage]?.push(l);
  for (const s of STAGES)
    groups[s].sort((a, b) => (b.lead_score ?? -1) - (a.lead_score ?? -1) || a.full_name.localeCompare(b.full_name));
  return groups;
}

export function scoreTone(score: number | null): "high" | "medium" | "low" | "pending" {
  if (score === null || score === undefined) return "pending";
  return score >= 70 ? "high" : score >= 40 ? "medium" : "low";
}

export const TRUST_LABEL = {
  clear: "Clear", review: "Review", high_risk: "High risk", blocked: "Blocked", pending: "Not scored",
};

export function trustTone(band: TrustBand | null): keyof typeof TRUST_LABEL {
  return band ?? "pending";
}

type KeyValueStore = { getItem(k: string): string | null; setItem(k: string, v: string): void };

export function deviceId(storage: KeyValueStore): string {
  const existing = storage.getItem("atrium.deviceId");
  if (existing) return existing;
  const id = typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `dev-${Math.random().toString(36).slice(2, 14)}`;
  storage.setItem("atrium.deviceId", id);
  return id;
}

export type Triage = { attention: Lead[]; call: Lead[]; clients: Lead[]; unscored: Lead[]; closed: Lead[] };

/** Leads in the order an advisor should see them: the risky ones first, then the ones worth a call by fit. */
export function triage(leads: Lead[]): Triage {
  const out: Triage = { attention: [], call: [], clients: [], unscored: [], closed: [] };
  for (const l of leads) {
    if (l.stage === "client") out.clients.push(l);
    else if (l.stage === "disqualified") out.closed.push(l);
    else if (!l.scored_at) out.unscored.push(l);
    else if (l.trust_band === "high_risk" || l.trust_band === "blocked") out.attention.push(l);
    else out.call.push(l);
  }
  const byFit = (a: Lead, b: Lead) => (b.lead_score ?? -1) - (a.lead_score ?? -1) || a.full_name.localeCompare(b.full_name);
  out.attention.sort((a, b) => (a.trust_score ?? 101) - (b.trust_score ?? 101) || a.full_name.localeCompare(b.full_name));
  out.call.sort(byFit);
  out.clients.sort(byFit);
  return out;
}

const has = (l: Lead, code: string) => (l.trust_signals ?? []).some((s) => s.code === code);

export function attentionHeadline(attention: Lead[]): string {
  const ring = attention.filter((l) => has(l, "T05"));
  if (ring.length >= 2) {
    const throwaway = ring.every((l) => has(l, "T01"));
    return `${ring.length} leads arrived from one device within 24 hours${throwaway ? ", each with a throwaway email address" : ""}.`;
  }
  if (attention.length === 1) return `${attention[0].full_name} needs a look before anyone calls.`;
  return `${attention.length} leads need a look before anyone calls them.`;
}

export function strongestSignal(lead: Lead): string | null {
  const signals = [...(lead.trust_signals ?? [])].sort((a, b) => b.weight - a.weight);
  return signals[0]?.label ?? null;
}
