/** The Model Risk Office: types mirroring /governance/*, and the copy the Models pages read. */

export type ModelStatus = "validated" | "failing" | "breaker_open" | "monitored_only" | "not_validated" | "no_result";
export type ModelKind = "gemini_prompt" | "adk_agent" | "bigquery_ml" | "document_ai" | "rules";
export type SuiteKind = "golden" | "red_team" | "fairness" | "challenger";
export type Tier = "free" | "live";

export type ModelRow = {
  key: string; name: string; kind: ModelKind; kind_label: string; tier: "high" | "medium"; owner: string;
  status: ModelStatus; version: string; validated_version: string | null; changed_since_validation: boolean;
  last_validated_at: string | null; last_run_id: string | null; fallback: string | null;
};

export type RunStatus = "running" | "finished" | "failed" | "did_not_finish";
export type RunRow = {
  id: string; tier: Tier; trigger: "deploy" | "button" | "local"; status: RunStatus; started_at: string;
  finished_at: string | null; requested_by: string | null; cost_usd: string; git_sha: string;
  summary: { passed?: boolean; counts?: { suites: number; passed: number }; error?: string; suites?: SuiteSummary[] };
};

export type Counts = { pass: number; fail: number; error: number };
export type SuiteSummary = {
  model_key: string; kind: SuiteKind; tier: Tier; bar: string; metric: string; passed: boolean; counts: Counts;
  cost_usd: number; case_ids?: string[];
};
export type CaseRow = {
  case_id: string; outcome: "pass" | "fail" | "error"; expected: unknown; actual: unknown; detail: string;
  cost_usd: string; latency_ms: number;
};
export type Suite = SuiteSummary & { cases: CaseRow[] };
export type BreakerChange = { state: "open" | "closed"; reason: string; by: string; at: string; run_id: string | null };
export type Breaker = {
  state: "open" | "closed"; reason: string; changed_by: string | null; changed_at: string | null;
  history: BreakerChange[]; message: string | null;
};
export type ModelCard = ModelRow & {
  purpose: string; human_gate: string; limitations: string[]; sources_missing: string[]; suites: Suite[]; breaker: Breaker;
};
export type ModelsOut = { models: ModelRow[]; counts: Record<string, number>; last_run: RunRow | null };

export type Agreement = { agreed: number; decided: number; rate: number | null; note: string; by?: Record<string, Agreement> };
export type LeadDrift = { psi: number | null; recent: number; warn: boolean; note: string };
export type AnomalyDrift = { share: number | null; flagged: number; accounts: number; training_share: number; note: string };
export type Monitoring = {
  agreement: Record<string, Agreement>; drift: { lead_score: LeadDrift; aml_anomaly: AnomalyDrift }; window_days: number;
};

export const STATUS_LABEL: Record<ModelStatus, string> = {
  validated: "Validated", failing: "Failing", breaker_open: "Breaker open", monitored_only: "Monitored only",
  not_validated: "Not validated yet", no_result: "No result",
};
export const STATUS_TONE: Record<ModelStatus, "gain" | "loss" | "neutral" | "caution"> = {
  validated: "gain", failing: "loss", breaker_open: "loss", monitored_only: "neutral", not_validated: "caution",
  no_result: "caution",
};
/** Gemini and the ADK agent write text, so their kind wears the daylight colour; rules and statistical models do not. */
export const GENERATIVE: ReadonlySet<ModelKind> = new Set(["gemini_prompt", "adk_agent"]);

const SUITE_LABEL: Record<SuiteKind, string> = {
  golden: "Golden cases", red_team: "Red team", fairness: "Fair lending", challenger: "Challenger",
};

export function suiteTitle(kind: SuiteKind, tier: Tier): string {
  return tier === "live" ? `${SUITE_LABEL[kind]} (live)` : SUITE_LABEL[kind];
}

const count = (n: number, one: string, many: string) => (n === 1 ? one : `${n} ${many}`);

export function headline(models: ModelRow[], lastRun?: RunRow | null): { title: string; detail: string } {
  const validated = models.filter((m) => m.status === "validated").length;
  const open = models.filter((m) => m.status === "breaker_open").length;
  const failing = models.filter((m) => m.status === "failing").length;
  const detail = lastRun ? `Last live run: ${runLine(lastRun)}.` : "No live run yet: the live checks start after each deploy.";
  if (models.length > 0 && validated === models.length) return { title: "Every model is validated.", detail };
  const parts = [`${validated} of ${models.length} models validated.`];
  if (open) parts.push(`${count(open, "One breaker is", "breakers are")} open.`);
  if (failing) parts.push(failing === 1 ? "One is failing its checks." : `${failing} are failing their checks.`);
  return { title: parts.join(" "), detail };
}

function fixed(n: number): string {
  return Number.isInteger(n) ? String(n) : n.toFixed(2);
}

/** An expected or actual value from a case, in one short line. */
export function caseValue(v: unknown): string {
  if (v === null || v === undefined) return "None";
  if (typeof v === "number") return fixed(v);
  if (typeof v === "string") return v;
  if (typeof v === "boolean") return String(v);
  if (Array.isArray(v)) return v.length ? v.map(caseValue).join(", ") : "none";
  if (typeof v === "object") {
    return Object.entries(v as Record<string, unknown>).map(([k, x]) => `${k.replaceAll("_", " ")}: ${caseValue(x)}`).join("; ");
  }
  return String(v);
}

const UTC_DAY = new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", timeZone: "UTC" });
const UTC_TIME = new Intl.DateTimeFormat("en-GB", { hour: "2-digit", minute: "2-digit", hour12: false, timeZone: "UTC" });

export function clockUtc(iso: string): string {
  return `${UTC_TIME.format(new Date(iso))} UTC`;
}

const TRIGGER: Record<RunRow["trigger"], string> = {
  deploy: "after a deploy", button: "started from this page", local: "run on this server",
};

/** One run as a line: what started it, how it ended, and what it cost. */
export function runLine(run: RunRow): string {
  const what = `${run.tier === "free" ? "Free checks" : "Live checks"} ${TRIGGER[run.trigger] ?? "run"}`;
  const cost = `$${Number(run.cost_usd || 0).toFixed(2)}`;
  if (run.status === "running") return `${what}, running since ${clockUtc(run.started_at)}`;
  if (run.status === "failed") return `${what}, could not start or stopped early at ${clockUtc(run.started_at)}`;
  if (run.status === "did_not_finish") return `${what}, did not finish (started ${clockUtc(run.started_at)})`;
  const at = run.finished_at ?? run.started_at;
  return `${what}, finished ${UTC_DAY.format(new Date(at))} at ${clockUtc(at)}, ${cost}`;
}

const AGREEMENT_COPY: Record<string, { name: string; line: (pct: number) => string }> = {
  reconciler_agent: { name: "Reconciliation agent", line: (p) => `Operations accepted ${p}% of the agent's proposals` },
  case_reviewer: { name: "Case review", line: (p) => `The MLRO's decision matched ${p}% of case-review triages` },
  held_order_reviewer: { name: "Held-order review note", line: (p) => `Advisors followed ${p}% of review-note suggestions` },
};

const sentence = (text: string) => text.charAt(0).toLowerCase() + text.slice(1);

export function agreementLine(key: string, a: Agreement, windowDays = 30): string {
  const copy = AGREEMENT_COPY[key] ?? { name: key, line: (p: number) => `People agreed with ${p}% of its suggestions` };
  if (a.rate === null) return `${copy.name}: ${sentence(a.note)}.`;
  return `${copy.line(Math.round(a.rate * 100))} (${a.decided} decisions in ${windowDays} days).`;
}

export function driftLine(d: LeadDrift): string {
  if (d.psi === null) return `Lead scores: ${sentence(d.note)}.`;
  return `Lead scores this month compared with training: ${d.note}.`;
}

/** A breaker switches a model to its fallback; with none, pausing would change nothing, so it is not offered. */
export function canPause(model: Pick<ModelRow, "fallback">): boolean {
  return Boolean(model.fallback);
}

/** The monitored models a card can show, by key. */
export const MONITORED: ReadonlySet<string> = new Set(Object.keys(AGREEMENT_COPY));
