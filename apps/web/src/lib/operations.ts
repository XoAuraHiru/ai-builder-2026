import { formatUsd } from "./format";

export type Check = { code: string; ok: boolean; detail: string };
export type DraftPrice = {
  fund_code: string; name: string; as_of: string; prev_as_of: string | null; prev_nav: string | null; nav: string;
  move_pct: number; status: "draft" | "checked"; checks: Check[];
};
export type RunStep = { step: string; ok: boolean; detail: string; facts: Record<string, unknown> };
export type Brief = { headline: string; points: string[]; watch: string[]; verified: boolean; unsupported_figures: string[]; model: string };
export type OpsRun = {
  id: string; as_of: string | null; triggered_by: string; status: "running" | "ok" | "partial"; steps: RunStep[];
  brief: Brief | null; started_at: string; finished_at: string | null;
};
export type Overview = {
  as_of: string; draft_as_of: string | null; drafts: DraftPrice[]; unpublished: string[]; latest_run: OpsRun | null;
  runs: OpsRun[]; waiting_for_money: number; unmatched_lines: number; proposals: number; pending_approvals: number;
};
export type Evidence = { label: string; detail: string };
export type ApprovalAction = "publish_prices" | "manual_match" | "reverse_posting";
export type Approval = {
  id: string; action: ApprovalAction; summary: string; reason: string; evidence: Evidence[];
  state: "pending" | "approved" | "rejected"; requested_by: string; mine: boolean; requested_at: string;
  decided_by: string | null; decided_at: string | null; decision_note: string | null; result: Record<string, unknown> | null;
};
export type Line = {
  id: string; statement_id: string; line_no: number; value_date: string; amount: string; description: string;
  remitter: string | null; reference: string | null; channel: string | null; state: "unmatched" | "proposed" | "matched" | "ignored";
};
export type Receipt = {
  instruction_id: string; reference: string; account_number: string; holder: string; amount: string; fund_name: string;
  requested_on: string; in_proposal: boolean;
};
export type Subscription = {
  instruction_id: string; reference: string; holder: string; account_number: string; fund_name: string; amount: string;
  state: string; requested_on: string;
};
export type Tier = "exact_reference" | "unique_amount" | "fuzzy" | "combination" | "manual";
export type Match = {
  id: string; tier: Tier; confidence: number; evidence: string[]; proposed_by: string;
  state: "proposed" | "accepted" | "rejected" | "awaiting_approval"; lines: Line[]; subscriptions: Subscription[];
  decided_by: string | null; decided_at: string | null; note: string | null; approval_id: string | null; created_at: string;
};
export type Statement = {
  id: string; filename: string; source: "documentai" | "csv"; bank_name: string | null; account_last4: string | null;
  period_start: string | null; period_end: string | null; uploaded_by: string; uploaded_at: string; notes: string[];
  counts: Record<Line["state"], number>; lines?: Line[];
};
export type Reconciliation = {
  reads_pdf: boolean; sample_format: "csv" | "pdf"; demo: boolean; statements: Statement[]; unmatched: Line[]; receipts: Receipt[]; proposals: Match[]; recent: Match[];
};
export type ReconcileResult = { rules: number; agent: number; scorer: number; summary: string; used_agent: boolean };
export type Step = { state: string; note: string; at: string };
export type BlotterRow = {
  id: string; reference: string | null; type: "subscribe" | "redeem" | "switch"; fund_code: string; fund_name: string;
  holder: string; account_number: string; amount: string | null; units: string | null; state: string;
  requested_at: string; dealing_date: string | null; funded: boolean | null; steps: Step[]; posting_id: string | null;
  not_reversible_because: string | null;
};
export type Authenticator = { code: string; seconds_left: number; period: number; note: string };

export const TIER_COPY: Record<Tier, string> = {
  exact_reference: "Reference and amount match", unique_amount: "The only payment of this amount",
  fuzzy: "A close reference", combination: "A payment split in parts", manual: "Matched by hand",
};
export const ACTION_COPY: Record<ApprovalAction, string> = {
  publish_prices: "Publish prices", manual_match: "Manual match", reverse_posting: "Reversal",
};
export const INSTRUCTION_STATE: Record<string, { label: string; tone: "neutral" | "gain" | "caution" | "loss" }> = {
  received: { label: "Received", tone: "neutral" }, accepted: { label: "Waiting for a price", tone: "neutral" },
  priced: { label: "Priced", tone: "neutral" }, allocated: { label: "Dealt", tone: "neutral" },
  settled: { label: "Settled", tone: "gain" }, rejected: { label: "Rejected", tone: "loss" },
  reversed: { label: "Reversed", tone: "loss" },
};
export const STEP_LABEL: Record<string, string> = {
  received: "Received", checked: "Checked", accepted: "Accepted", funded: "Money received", priced: "Priced",
  allocated: "Dealt", settled: "Settled", rejected: "Rejected", reversed: "Reversed",
};

export function confidenceWords(c: number): string {
  return c >= 0.95 ? "Near certain" : c >= 0.8 ? "Strong" : c >= 0.7 ? "Likely" : "Weak";
}

export function proposerLabel(by: string): string {
  if (by === "rules") return "the rules";
  if (by === "agent") return "the reconciliation agent";
  if (by === "scorer") return "the scorer, as the agent was unavailable";
  return `${by}, by hand`;
}

/** Only digits, at most six: what a one-time code field keeps as it is typed or pasted. */
export function codeDigits(raw: string): string {
  return raw.replace(/\D/g, "").slice(0, 6);
}

/** The totals of a match built by hand, in whole cents so that 0.1 + 0.2 agrees with 0.3. */
export function matchTotals(lines: { amount: string }[], subs: { amount: string }[]): { paid: number; due: number; agrees: boolean } {
  const cents = (xs: { amount: string }[]) => xs.reduce((sum, x) => sum + Math.round(Number(x.amount) * 100), 0);
  const paid = cents(lines);
  const due = cents(subs);
  return { paid: paid / 100, due: due / 100, agrees: paid > 0 && paid === due };
}

export function describeInstruction(r: Pick<BlotterRow, "type" | "amount" | "units" | "fund_name">): string {
  if (r.type === "subscribe") return `Buy ${formatUsd(r.amount ?? 0)} of ${r.fund_name}`;
  const units = Number(r.units ?? 0).toLocaleString("en-US", { maximumFractionDigits: 4 });
  return r.type === "redeem" ? `Sell ${units} units of ${r.fund_name}` : `Switch ${units} units out of ${r.fund_name}`;
}

export function resultWords(a: Pick<Approval, "action" | "state" | "result">): string {
  if (a.state === "rejected") return "Rejected: nothing changed.";
  if (a.state === "pending") return "Waiting for a second person.";
  const r = a.result ?? {};
  if (a.action === "publish_prices") {
    const dealt = ((r.allocation ?? {}) as { allocated?: unknown[] }).allocated?.length ?? 0;
    return `Published ${r.published ?? 0} prices; ${dealt} instruction${dealt === 1 ? "" : "s"} dealt.`;
  }
  if (a.action === "manual_match") {
    const settled = Array.isArray(r.settled) ? r.settled.length > 0 : Boolean(r.settled);
    return settled ? "Matched, and the subscription settled." : "Matched; the subscription settles once it is dealt.";
  }
  return "Reversed: the units and their cash came back out of the account.";
}

/** Each character of `a`, marked where it differs from `b` at the same place: a mistyped reference, highlighted. */
export function diffMarks(a: string, b: string): { ch: string; diff: boolean }[] {
  return [...a].map((ch, i) => ({ ch, diff: b[i] !== undefined && b[i] !== ch }));
}

export function splitProposals(proposals: Match[]): { rules: Match[]; others: Match[] } {
  return {
    rules: proposals.filter((m) => m.proposed_by === "rules" && m.state === "proposed"),
    others: proposals.filter((m) => !(m.proposed_by === "rules" && m.state === "proposed")),
  };
}

export function statementFlow(s: Pick<Statement, "counts">): { read: number; matched: number; waiting: number; left: number; ignored: number } {
  const c = s.counts;
  const n = (k: keyof Statement["counts"]) => c[k] ?? 0;
  return { read: n("unmatched") + n("proposed") + n("matched") + n("ignored"), matched: n("matched"), waiting: n("proposed"),
    left: n("unmatched"), ignored: n("ignored") };
}

export function balanceNote(s: Pick<Statement, "notes">): { ok: boolean; text: string } | null {
  const note = s.notes.find((n) => /add up/i.test(n));
  return note ? { ok: !/do not add up/i.test(note), text: note } : null;
}

export function meterCells(confidence: number): number {
  return Math.max(0, Math.min(5, Math.round(confidence * 5)));
}

export type ChipTone = "gain" | "caution" | "loss" | "neutral";
export type Status = { label: string; tone: ChipTone };

/** Status chips: matched green, waiting for a second person amber, held or rejected coral, a draft neutral. */
export function matchStatus(state: Match["state"]): Status {
  if (state === "accepted") return { label: "Matched", tone: "gain" };
  if (state === "rejected") return { label: "Rejected", tone: "loss" };
  if (state === "awaiting_approval") return { label: "Awaiting second approver", tone: "caution" };
  return { label: "Proposed", tone: "neutral" };
}

export function approvalStatus(state: Approval["state"]): Status {
  if (state === "approved") return { label: "Approved", tone: "gain" };
  if (state === "rejected") return { label: "Rejected", tone: "loss" };
  return { label: "Awaiting second approver", tone: "caution" };
}

export function priceStatus(status: DraftPrice["status"]): Status {
  return status === "checked" ? { label: "Awaiting second approver", tone: "caution" } : { label: "Draft", tone: "neutral" };
}

/** The queue counts the day-end recorded in its Exceptions step, to compare with the counts now. */
export function runCounts(run: Pick<OpsRun, "steps"> | null): { waiting?: number; unmatched?: number; approvals?: number } {
  const facts = run?.steps.find((s) => s.step === "Exceptions")?.facts ?? {};
  const n = (v: unknown) => (typeof v === "number" ? v : undefined);
  return { waiting: n(facts.waiting), unmatched: n(facts.unmatched_lines), approvals: n(facts.approvals) };
}

/** A queue's change since the day-end ran: fewer waiting is good (green), more is a caution (amber). No change, or
 *  nothing to compare with, gives no chip. */
export function sinceRun(now: number, then: number | undefined): { text: string; tone: "gain" | "caution" } | null {
  if (then === undefined || now === then) return null;
  return now > then ? { text: `↑ ${now - then}`, tone: "caution" } : { text: `↓ ${then - now}`, tone: "gain" };
}

/** The first dollar amount in a request's summary, for the request card's right-hand figure. */
export function approvalAmount(summary: string): string | null {
  return summary.match(/\$[\d,]+(?:\.\d{2})?/)?.[0] ?? null;
}

/** A record's id as people read it: the first eight characters, in capitals. */
export function shortId(id: string): string {
  return id.replace(/-/g, "").slice(0, 8).toUpperCase();
}

const WHEN = new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
export function shortWhen(iso: string): string {
  return WHEN.format(new Date(iso));
}

/** A brief or summary from the rules is not Gemini's writing, so it is not shown in the violet block. */
export function writtenByModel(model: string): boolean {
  return model !== "rules";
}

/** Accept each proposal in turn; one failure does not stop the rest, and the result says what happened. */
export async function acceptMany(ids: string[], accept: (id: string) => Promise<unknown>):
  Promise<{ accepted: string[]; failed: { id: string; message: string }[] }> {
  const accepted: string[] = [];
  const failed: { id: string; message: string }[] = [];
  for (const id of ids) {
    try {
      await accept(id);
      accepted.push(id);
    } catch (e) {
      failed.push({ id, message: e instanceof Error ? e.message : String(e) });
    }
  }
  return { accepted, failed };
}
