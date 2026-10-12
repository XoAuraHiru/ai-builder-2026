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
