export type EvidenceKind = "instruction" | "posting" | "statement_line" | "order" | "bank_link" | "feature";
export type EvidenceRow = { kind: EvidenceKind; id: string; date: string; amount: string | null; detail: string };
export type GraphNode = { id: string; kind: "person" | "account" | "bank" | "payer"; label: string; flagged: boolean };
export type GraphEdge = { source: string; target: string; label: string };
export type CaseReview = {
  triage: "escalate" | "close" | "request_information"; triage_reason: string;
  narrative: { text: string; evidence: string[] }[]; questions: string[]; unsupported_figures: string[];
  dropped_citations: string[]; unknown_names?: string[]; verified: boolean; model: string; written_at: string;
};
export type Alert = {
  id: string; scenario: string; title: string; severity: "high" | "medium" | "low"; score: number;
  person: { id: string; name: string; country: string; risk_band: number | null }; account_number: string | null;
  summary: string; evidence_count: number; state: "open" | "escalated" | "closed"; raised_at: string;
  decided_by: string | null; decided_at: string | null; decision_note: string | null;
};
export type AlertDetail = Alert & {
  evidence: EvidenceRow[]; ai_review: CaseReview | null; graph: { nodes: GraphNode[]; edges: GraphEdge[] };
  review_paused?: string | null;  // the case reviewer's breaker message while it is switched off
};
export type AiDecisionRow = {
  id: string; agent: string; purpose: string; model: string; subject_type: string; subject_id: string;
  confidence: number | null; tokens_in: number; tokens_out: number; latency_ms: number; cost_usd: string; created_at: string;
};
export type DecisionLog = { count: number; cost_usd: string; tokens_in: number; tokens_out: number; decisions: AiDecisionRow[] };

export const SEVERITY_TONE = { high: "loss", medium: "caution", low: "neutral" } as const;
export const SEVERITY_LABEL: Record<Alert["severity"], string> = { high: "High", medium: "Medium", low: "Low" };
export const STATE_LABEL: Record<Alert["state"], string> = { open: "Open", escalated: "Escalated", closed: "Closed" };
export const EVIDENCE_KIND: Record<EvidenceKind, string> = {
  instruction: "Fund instruction", posting: "Ledger posting", statement_line: "Bank statement line",
  order: "Share order", bank_link: "Shared bank account", feature: "Behaviour measure",
};
export const TRIAGE_COPY: Record<CaseReview["triage"], string> = {
  escalate: "escalate it", close: "close it", request_information: "ask the client for more information",
};
/** What each monitoring rule looks for, in the words of its thresholds (app/services/aml.py). */
export const SCENARIO_COPY: Record<string, string> = {
  structuring: "Three or more subscriptions between $8,500 and $10,000 within seven days: amounts kept just under the $10,000 reporting threshold.",
  rapid_in_out: "At least $10,000 paid in, and 75% or more of it taken out again within ten days.",
  third_party_funding: "A subscription paid from a bank account in someone else's name.",
  linked_round_trip: "Money leaving one account and arriving in another within 14 days, where both accounts are paid from the same bank account.",
  velocity: "Five or more instructions and orders within 24 hours.",
  dormant_reactivation: "$25,000 or more arriving after 180 days without any activity.",
  high_risk_jurisdiction: "Activity by a person recorded in a FATF call-for-action jurisdiction.",
  anomaly: "An account whose last 90 days sit far from every cluster of ordinary behaviour in the k-means model.",
};
const PURPOSE_COPY: Record<string, string> = {
  aml_case_review: "AML case review", ops_brief: "Morning brief", reconciliation: "Reconciliation agent",
  statement_normalise: "Statement reading", order_explainer: "Order explanation", held_order_review: "Held-order review",
};

export function purposeLabel(purpose: string): string {
  const words = PURPOSE_COPY[purpose] ?? purpose.replace(/_/g, " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}

/** Evidence ids become E1, E2 and so on, in the order the evidence is listed, so the case review can point at rows. */
export function citationLabels(evidence: { id: string }[]): Record<string, string> {
  return Object.fromEntries(evidence.map((e, i) => [e.id, `E${i + 1}`]));
}

const COLUMN = { person: 0, account: 1, bank: 2, payer: 2 } as const;

/** People on the left, accounts in the middle, and the bank accounts and outside payers they share on the right. The
 *  flagged person comes first in their column; each column spreads its nodes evenly over the height. */
export function layoutGraph(nodes: GraphNode[], width: number, rowHeight: number): { at: Record<string, { x: number; y: number }>; height: number } {
  const columns: GraphNode[][] = [[], [], []];
  for (const n of nodes) columns[COLUMN[n.kind]].push(n);
  const height = (Math.max(1, ...columns.map((c) => c.length)) + 1) * rowHeight;
  const at: Record<string, { x: number; y: number }> = {};
  columns.forEach((column, c) => {
    column.sort((a, b) => Number(b.flagged) - Number(a.flagged) || a.label.localeCompare(b.label));
    column.forEach((n, i) => {
      at[n.id] = { x: Math.round(((c + 0.5) / 3) * width), y: Math.round(((i + 1) / (column.length + 1)) * height) };
    });
  });
  return { at, height };
}

export type ThresholdBar = { id: string; label: string; date: string; amount: number; pct: number };

/** Payment rows drawn against a reporting threshold: each bar's height and the line's, as a share of the chart. */
export function thresholdBars(evidence: EvidenceRow[], threshold: number): { bars: ThresholdBar[]; linePct: number } {
  const labels = citationLabels(evidence);
  const rows = evidence.filter((e) => e.amount !== null && (e.kind === "instruction" || e.kind === "posting"));
  const top = Math.max(threshold * 1.08, ...rows.map((r) => Number(r.amount)));
  return {
    bars: rows.map((r) => ({ id: r.id, label: labels[r.id], date: r.date, amount: Number(r.amount), pct: (Number(r.amount) / top) * 100 })),
    linePct: (threshold / top) * 100,
  };
}
