export type EvidenceKind = "instruction" | "posting" | "statement_line" | "order" | "bank_link" | "feature" | "ring_link";
export type EvidenceRow = { kind: EvidenceKind; id: string; date: string; amount: string | null; detail: string };
/** Alert graphs use people, accounts, banks and payers; ring graphs use leads and clients and what they share. */
export type GraphNodeKind =
  | "person" | "account" | "bank" | "payer"
  | "lead" | "client" | "device" | "phone" | "email" | "ip" | "document";
export type GraphNode = { id: string; kind: GraphNodeKind; label: string; flagged: boolean };
/** `strong` and `id` come with ring links only: a weak link is drawn dashed, and the id is what Gemini cites. */
export type GraphEdge = { source: string; target: string; label: string; strong?: boolean; id?: string };
export type CaseReviewTriage = "escalate" | "close" | "request_information";
export type CaseReview = {
  triage: CaseReviewTriage; triage_reason: string;
  narrative: { text: string; evidence: string[] }[]; questions: string[]; unsupported_figures: string[];
  dropped_citations: string[]; unknown_names?: string[]; verified: boolean; model: string; written_at: string;
  steering?: string[]; model_triage?: CaseReviewTriage;  // outsiders' text that tried to steer, and what the model said
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
  order: "Share order", bank_link: "Shared bank account", feature: "Behaviour measure", ring_link: "Ring link",
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
  ring: "Several identities share devices, bank accounts or documents across the lifecycle.",
};
const PURPOSE_COPY: Record<string, string> = {
  aml_case_review: "AML case review", ops_brief: "Morning brief", reconciliation: "Reconciliation agent",
  statement_normalise: "Statement reading", order_explainer: "Order explanation", held_order_review: "Held-order review",
  ring_narrative: "Ring narrative",
};

export function purposeLabel(purpose: string): string {
  const words = PURPOSE_COPY[purpose] ?? purpose.replace(/_/g, " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}

/** Evidence ids become E1, E2 and so on, in the order the evidence is listed, so the case review can point at rows. */
export function citationLabels(evidence: { id: string }[]): Record<string, string> {
  return Object.fromEntries(evidence.map((e, i) => [e.id, `E${i + 1}`]));
}

export type GraphColumns = Record<GraphNodeKind, 0 | 1 | 2>;
/** The alert graph's columns. Ring kinds have a place too, but ring graphs pass their own (RING_COLUMNS in rings.ts). */
const COLUMN: GraphColumns = {
  person: 0, account: 1, bank: 2, payer: 2, lead: 0, client: 0, device: 2, phone: 2, email: 2, ip: 2, document: 2,
};

/** People on the left, accounts in the middle, and the bank accounts and outside payers they share on the right. The
 *  flagged person comes first in their column; each column spreads its nodes evenly over the height. */
export function layoutGraph(nodes: GraphNode[], width: number, rowHeight: number, place: GraphColumns = COLUMN):
  { at: Record<string, { x: number; y: number }>; height: number } {
  const columns: GraphNode[][] = [[], [], []];
  for (const n of nodes) columns[place[n.kind]].push(n);
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

/** The order a graph's links draw in: strong links first, then weak ones, each group as listed (an alert's links carry
 *  no strength and draw as listed). Gives each edge, by key, its place in that order. */
export function drawOrder(edges: Pick<GraphEdge, "source" | "target" | "strong">[]): Record<string, number> {
  const rank = (e: Pick<GraphEdge, "strong">) => (e.strong === false ? 1 : 0);
  const order = edges.map((e, i) => ({ key: `${e.source}-${e.target}`, rank: rank(e), i }))
    .sort((a, b) => a.rank - b.rank || a.i - b.i);
  return Object.fromEntries(order.map((o, n) => [o.key, n]));
}

/** What Gemini Pro's case review does while the MLRO waits, in order (app/services/compliance_ai.py review_alert). */
export const CASE_REVIEW_STEPS = [
  "Gathering the alert, its evidence and the linked accounts",
  "Gemini Pro is weighing the evidence against known typologies",
  "Drafting the case narrative, each part citing its evidence",
  "Checking every citation, figure and name against the evidence",
];

/** Where a payment sits against the threshold: over it (coral), just under it (amber, within 15%), or clear (green). */
export type BarTone = "over" | "near" | "under";
export type ThresholdBar = { id: string; label: string; date: string; amount: number; pct: number; tone: BarTone };

/** Payment rows drawn against a reporting threshold: each bar's height and the line's, as a share of the chart. */
export function thresholdBars(evidence: EvidenceRow[], threshold: number): { bars: ThresholdBar[]; linePct: number } {
  const labels = citationLabels(evidence);
  const rows = evidence.filter((e) => e.amount !== null && (e.kind === "instruction" || e.kind === "posting"));
  const top = Math.max(threshold * 1.08, ...rows.map((r) => Number(r.amount)));
  const tone = (n: number): BarTone => (n >= threshold ? "over" : n >= threshold * 0.85 ? "near" : "under");
  return {
    bars: rows.map((r) => ({
      id: r.id, label: labels[r.id], date: r.date, amount: Number(r.amount), pct: (Number(r.amount) / top) * 100, tone: tone(Number(r.amount)),
    })),
    linePct: (threshold / top) * 100,
  };
}

export type FindingTone = "gain" | "caution" | "loss" | "neutral";
/** One finding on the alert's opening card: a short title, the figure large, a sentence, and a status chip. */
export type Finding = { title: string; figure: string; unit?: string; text: string; chip: { label: string; tone: FindingTone } };

const MONEY_KINDS: ReadonlySet<EvidenceKind> = new Set(["instruction", "posting", "statement_line", "order"]);
/** The time window each rule looks over (app/services/aml.py), so a span inside it can say so. */
const WINDOW_DAYS: Record<string, number> = { structuring: 7, rapid_in_out: 10, linked_round_trip: 14 };
const DAY_MS = 86_400_000;
const shortDay = (iso: string) => new Date(`${iso.slice(0, 10)}T00:00:00`).toLocaleDateString("en-US", { month: "short", day: "numeric" });
const dollars = (n: number) => `$${Math.round(n).toLocaleString("en-US")}`;

/** The figures behind an alert, one card each. A behaviour alert shows its measures against ordinary accounts; a
 *  payment alert shows the money, the days it took and who else is linked. */
export function alertFindings(alert: Pick<AlertDetail, "scenario" | "severity" | "evidence" | "graph">): Finding[] {
  const features = alert.evidence.filter((e) => e.kind === "feature");
  if (features.length > 0) {
    return features.slice(0, 3).map((f) => {
      const [head, ...rest] = f.detail.split(": ");
      const tail = rest.join(": ");
      const where = tail.split(", where ")[1];
      return {
        title: rest.length ? head : EVIDENCE_KIND.feature,
        figure: f.amount !== null ? dollars(Number(f.amount)) : tail || f.detail,
        text: where ? `${where.charAt(0).toUpperCase()}${where.slice(1)}.` : f.detail,
        chip: { label: "Far from ordinary", tone: "loss" },
      };
    });
  }
  const out: Finding[] = [];
  const money = alert.evidence.filter((e) => e.amount !== null && MONEY_KINDS.has(e.kind));
  if (money.length > 0) {
    const total = money.reduce((sum, e) => sum + Number(e.amount), 0);
    out.push({
      title: "Money in the evidence", figure: dollars(total),
      text: `Across ${money.length} payment${money.length === 1 ? "" : "s"} and ledger rows.`,
      chip: alert.severity === "low" ? { label: "Note", tone: "neutral" } : { label: "Worth a look", tone: "caution" },
    });
    const days = money.map((e) => new Date(`${e.date.slice(0, 10)}T00:00:00`).getTime());
    const first = Math.min(...days);
    const last = Math.max(...days);
    const span = Math.round((last - first) / DAY_MS);
    const window = WINDOW_DAYS[alert.scenario];
    const firstIso = money.find((e) => new Date(`${e.date.slice(0, 10)}T00:00:00`).getTime() === first)!.date;
    const lastIso = money.find((e) => new Date(`${e.date.slice(0, 10)}T00:00:00`).getTime() === last)!.date;
    out.push({
      title: "From first to last", figure: span === 0 ? "Same day" : String(span), unit: span === 0 ? undefined : span === 1 ? "day" : "days",
      text: span === 0 ? `All on ${shortDay(firstIso)}.` : `From ${shortDay(firstIso)} to ${shortDay(lastIso)}.`,
      chip: window !== undefined && span <= window ? { label: `Inside the rule's ${window} days`, tone: "caution" } : { label: "Note", tone: "neutral" },
    });
  }
  const subject = alert.graph.nodes.find((n) => n.flagged && n.kind === "person");
  const others = alert.graph.nodes.filter((n) => (n.kind === "person" || n.kind === "payer") && n.id !== subject?.id);
  const sharedBank = alert.graph.nodes.some((n) => n.kind === "bank"
    && alert.graph.edges.filter((e) => e.target === n.id || e.source === n.id).length > 1);
  const payer = others.some((n) => n.kind === "payer");
  out.push({
    title: "Linked people", figure: String(others.length),
    text: others.length ? others.map((n) => n.label).join(", ") : "No one else shares an account, a device or a payer.",
    chip: others.length === 0 ? { label: "None linked", tone: "neutral" }
      : sharedBank ? { label: "Share a bank account", tone: "loss" }
        : payer ? { label: "Outside payer", tone: "caution" } : { label: "Linked", tone: "caution" },
  });
  return out.slice(0, 3);
}

/** The alerts page's opening sentence: how many open alerts wait, how many are high severity, and which to open. */
export function alertsMoment(alerts: Pick<Alert, "id" | "severity" | "score" | "title">[]):
  { tone: "alert" | "attention" | "good"; title: string; top: string | null } {
  if (alerts.length === 0) return { tone: "good", title: "No open alerts. Monitoring runs again this evening.", top: null };
  const rank = { high: 3, medium: 2, low: 1 } as const;
  const top = [...alerts].sort((a, b) => rank[b.severity] - rank[a.severity] || b.score - a.score)[0];
  const high = alerts.filter((a) => a.severity === "high").length;
  const n = alerts.length;
  const lead = `${n} open alert${n === 1 ? " waits" : "s wait"} for a decision`;
  const tail = high === 0 ? "." : high === n ? (n === 1 ? ", and it is high severity." : `, all ${n} high severity.`)
    : `; ${high} ${high === 1 ? "is" : "are"} high severity.`;
  return { tone: high > 0 ? "alert" : "attention", title: `${lead}${tail}`, top: top.id };
}
