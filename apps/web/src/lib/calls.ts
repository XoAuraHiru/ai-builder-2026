import { formatUsd } from "./format";

export type Role = "advisor" | "client" | "third_party" | "unknown";
export type FlagKind = "promissory" | "unsuitable" | "pressure" | "third_party_direction" | "confusion";
export type Severity = "high" | "medium" | "low";
export type UpdateField = "goals" | "horizon_years" | "investable_usd" | "monthly_usd" | "source_of_funds";

export type Segment = { start_s: number; speaker: string; role: Role; text: string };
export type CallFlag = {
  kind: FlagKind; severity: Severity; quote: string; start_s: number; rule: string; why: string; source: "gemini" | "rules";
};
export type CallUpdate = { field: UpdateField; proposed: string; quote: string; start_s: number; current: string | null };
export type CallReading = {
  duration_s: number; transcript: Segment[]; summary: string; action_items: string[];
  facts: { statement: string; start_s: number }[]; updates: CallUpdate[]; flags: CallFlag[];
  unsupported_figures?: string[];  // $ and % figures in the summary that were not said on the call nor are on the form
};
export type Dropped = { flags: number; updates: number; facts: number; invalid_updates?: number };
export type Applied = { field: UpdateField; value: string; previous?: string; by: string; at: string };
export type LeadCall = {
  id: string; filename: string; source: "upload" | "demo"; duration_s: number; reading: CallReading; dropped: Dropped;
  applied: Applied[]; created_at: string; created_by: string;
};

export const DEMO_CALLS = ["pressure", "discovery"] as const;
export type DemoCall = (typeof DEMO_CALLS)[number];

export const FLAG_LABEL: Record<FlagKind, string> = {
  promissory: "Guarantee or promise", unsuitable: "Unsuitable recommendation", pressure: "Pressure",
  third_party_direction: "Third party directing the client", confusion: "Client confusion",
};
export const FIELD_LABEL: Record<UpdateField, string> = {
  goals: "Goals", horizon_years: "Horizon", investable_usd: "To invest now", monthly_usd: "Every month",
  source_of_funds: "Source of funds",
};
export const ROLE_LABEL: Record<Role, string> = {
  advisor: "Advisor", client: "Client", third_party: "Third party", unknown: "Speaker",
};
export const SEVERITY_LABEL: Record<Severity, string> = { high: "High", medium: "Medium", low: "Low" };
const SEVERITY_RANK: Record<Severity, number> = { high: 0, medium: 1, low: 2 };

/** Seconds into a call as m:ss, or h:mm:ss past an hour. */
export function clock(seconds: number): string {
  const whole = Math.max(0, Math.floor(seconds));
  const h = Math.floor(whole / 3600);
  const m = Math.floor((whole % 3600) / 60);
  const s = String(whole % 60).padStart(2, "0");
  return h ? `${h}:${String(m).padStart(2, "0")}:${s}` : `${m}:${s}`;
}

/** High severity first, then in the order they were said. */
export function sortFlags(flags: CallFlag[]): CallFlag[] {
  return [...flags].sort((a, b) => SEVERITY_RANK[a.severity] - SEVERITY_RANK[b.severity] || a.start_s - b.start_s);
}

export function highFlags(flags: CallFlag[]): CallFlag[] {
  return sortFlags(flags).filter((f) => f.severity === "high");
}

const HEADLINE_PART: Record<FlagKind, string> = {
  third_party_direction: "a third party directed the client", promissory: "the advisor promised a return",
  unsuitable: "a recommendation did not fit the client", pressure: "the client was pressed to decide",
  confusion: "the client said they did not understand",
};
const HEADLINE_ORDER: FlagKind[] = ["third_party_direction", "promissory", "unsuitable", "pressure", "confusion"];

/** One sentence for the key moment: what the high-severity flags found. */
export function flagsHeadline(flags: CallFlag[]): string {
  const kinds = new Set(highFlags(flags).map((f) => f.kind));
  const parts = HEADLINE_ORDER.filter((k) => kinds.has(k)).map((k) => HEADLINE_PART[k]);
  if (!parts.length) return "No high-severity conduct flags on this call.";
  const text = parts.length === 1 ? parts[0] : `${parts.slice(0, -1).join(", ")}, and ${parts[parts.length - 1]}`;
  return `${text[0].toUpperCase()}${text.slice(1)}.`;
}

const count = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;

/** Why some of what Gemini said is not shown; null when everything it said held up. */
export function droppedNote(dropped: Dropped): string | null {
  const sentences: string[] = [];
  const quoted = [dropped.flags && count(dropped.flags, "flag", "flags"),
    dropped.updates && count(dropped.updates, "proposed update", "proposed updates")].filter(Boolean) as string[];
  if (quoted.length) {
    const one = dropped.flags + dropped.updates === 1;
    sentences.push(`${quoted.join(" and ")} ${one ? "was" : "were"} dropped because ${one ? "its quote is" : "their quotes are"} not in the transcript.`);
  }
  if (dropped.facts) {
    const one = dropped.facts === 1;
    sentences.push(`${count(dropped.facts, "stated fact", "stated facts")} ${one ? "was" : "were"} dropped because ${one ? "its time is" : "their times are"} outside the call.`);
  }
  const invalid = dropped.invalid_updates ?? 0;
  if (invalid) {
    const one = invalid === 1;
    sentences.push(`${count(invalid, "proposed update", "proposed updates")} ${one ? "was" : "were"} not offered because ${one ? "its value is" : "their values are"} not valid.`);
  }
  return sentences.length ? sentences.join(" ") : null;
}

/** The warning under Gemini's summary when it uses figures the call does not support; undefined when it does not. */
export function figuresWarning(figures: string[] | undefined): string | undefined {
  if (!figures?.length) return undefined;
  const list = figures.length === 1 ? figures[0] : `${figures.slice(0, -1).join(", ")} and ${figures[figures.length - 1]}`;
  const one = figures.length === 1;
  return `Check before relying on this: ${list} ${one ? "was" : "were"} not said on the call and ${one ? "is" : "are"} not on the form.`;
}

/** A field's value as the profile shows it. */
export function fieldValue(field: UpdateField, value: string | null | undefined): string {
  if (value === null || value === undefined || value === "") return "not set";
  if (field === "horizon_years") return `${value} ${value === "1" ? "year" : "years"}`;
  if (field === "investable_usd" || field === "monthly_usd") return formatUsd(value, Number(value) % 1 ? 2 : 0);
  if (field === "source_of_funds") return value.replaceAll("_", " ");
  return value;
}

/** "Horizon: 20 years → 15 years" */
export function updateLine(update: Pick<CallUpdate, "field" | "current" | "proposed"> & Partial<CallUpdate>): string {
  return `${FIELD_LABEL[update.field]}: ${fieldValue(update.field, update.current)} → ${fieldValue(update.field, update.proposed)}`;
}

/** The demo calls and the synthetic leads they were recorded with; the API refuses a demo call on any other lead. */
const DEMO_LEAD: Record<string, DemoCall> = { "ruth.alvarez@example.test": "pressure", "emma.walsh@example.com": "discovery" };

/** The demo call this lead can analyse, if any. */
export function demoFor(email: string): DemoCall | null {
  return DEMO_LEAD[email.trim().toLowerCase()] ?? null;
}

/** The demo call a reading came from, so the page can play it; null for an uploaded recording (never stored). */
export function demoName(call: Pick<LeadCall, "source" | "filename">): DemoCall | null {
  if (call.source !== "demo") return null;
  const stem = call.filename.replace(/\.mp3$/i, "");
  return (DEMO_CALLS as readonly string[]).includes(stem) ? (stem as DemoCall) : null;
}
