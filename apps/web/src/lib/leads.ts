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

/** What scoring a lead does, in order, for the panel that waits on it: Gemini reads the form, the Lead Score model
 *  scores fit, and the fixed trust rules weigh the contact details, the device and any documents. */
export const SCORING_STEPS = [
  "Gemini is reading the lead's answers",
  "Scoring fit with the Lead Score model",
  "Weighing contacts, devices and documents for the Trust Score",
];

export type Triage ={ attention: Lead[]; call: Lead[]; clients: Lead[]; unscored: Lead[]; closed: Lead[] };

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

/** A lead's trust signals, the largest deduction first (the API sends deductions as negative weights). */
export function topSignals(lead: Pick<Lead, "trust_signals">, limit?: number): TrustSignal[] {
  const sorted = [...(lead.trust_signals ?? [])].sort((a, b) => Math.abs(b.weight) - Math.abs(a.weight));
  return limit === undefined ? sorted : sorted.slice(0, limit);
}

export function strongestSignal(lead: Lead): string | null {
  return topSignals(lead, 1)[0]?.label ?? null;
}

export const TRUST_SEGMENTS = 20;
export type MeterTone = "coral" | "amber" | "green" | "none";

/** The Trust Score as a 20-segment meter: one segment per 5 points (a non-zero score always shows one), coral for high
 *  risk or blocked, amber for review, green for clear. Before scoring, nothing is filled. */
export function trustMeter(score: number | null, band: TrustBand | null): { filled: number; tone: MeterTone } {
  if (score === null || score === undefined || band === null) return { filled: 0, tone: "none" };
  const capped = Math.max(0, Math.min(100, score));
  const filled = capped > 0 ? Math.max(1, Math.round(capped / (100 / TRUST_SEGMENTS))) : 0;
  return { filled, tone: band === "clear" ? "green" : band === "review" ? "amber" : "coral" };
}

/** The meter segment by segment, in the order they fill: the band's tone for a filled one, null for an empty one. */
export function meterSegments(score: number | null, band: TrustBand | null): (Exclude<MeterTone, "none"> | null)[] {
  const { filled, tone } = trustMeter(score, band);
  return Array.from({ length: TRUST_SEGMENTS }, (_, i) => (i < filled && tone !== "none" ? tone : null));
}

/** A signal's weight as signed text with a true minus: "−25", "+6". */
export function signedWeight(weight: number): string {
  return weight > 0 ? `+${weight}` : weight < 0 ? `−${Math.abs(weight)}` : "0";
}

const SOURCE_LABEL: Record<string, string> = {
  web: "Web enquiry", referral: "Referral", email: "Email reply", event: "Event", chat: "Chat",
};

export function sourceLabel(source: string): string {
  return SOURCE_LABEL[source] ?? (source ? source[0].toUpperCase() + source.slice(1).replaceAll("_", " ") : "Unknown source");
}

export type ApplicationField = "full_name" | "email" | "goals" | "horizon_years" | "investable_usd";

/** The prospect form's checks, one sentence per field to fix; empty when it can be sent. Phone stays optional and
 *  unchecked here: its format is a trust signal for the advisor, not a reason to turn a prospect away. */
export function applicationErrors(form: Record<ApplicationField, string>): Partial<Record<ApplicationField, string>> {
  const out: Partial<Record<ApplicationField, string>> = {};
  if (form.full_name.trim().length < 2) out.full_name = "Enter your full name.";
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email.trim())) out.email = "Enter an email address, like name@example.com.";
  if (form.goals.trim().length < 3) out.goals = "Tell us what you are investing for, in a few words.";
  const years = Number(form.horizon_years);
  if (form.horizon_years.trim() === "" || !Number.isInteger(years) || years < 0 || years > 50) out.horizon_years = "Choose between 0 and 50 years.";
  if (!(Number(form.investable_usd) > 0)) out.investable_usd = "Enter how much you would invest now.";
  return out;
}

/** How long ago, in words; past a week, the date. The API's times carry no zone and are UTC. */
export function timeAgo(iso: string, now: Date = new Date()): string {
  const utc = /(?:[zZ]|[+-]\d\d:?\d\d)$/.test(iso) ? iso : `${iso}Z`;
  const then = new Date(utc);
  const minutes = Math.floor((now.getTime() - then.getTime()) / 60_000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return minutes === 1 ? "1 minute ago" : `${minutes} minutes ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return hours === 1 ? "1 hour ago" : `${hours} hours ago`;
  if (hours < 48) return "yesterday";
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days} days ago`;
  return then.toLocaleDateString("en-US", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
}
