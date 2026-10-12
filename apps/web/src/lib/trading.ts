import { formatUsd } from "./format";
import type { Quote, Session } from "./markets";

export type Outcome = "pass" | "info" | "warn" | "hold" | "block";
export type Verdict = "proceed" | "warn" | "hold" | "block";
export type GuardCheck = { code: string; title: string; outcome: Outcome; detail: string };
export type TrustSignal = { code: string; label: string; weight: number; evidence: string; source: string };
export type GuardianReport = {
  verdict: Verdict;
  order: { symbol: string; side: "buy" | "sell"; order_type: "market" | "limit"; quantity: number; limit_price: string | null; words: string };
  instrument: { symbol: string; name: string; kind: string; risk_band: number; sector_label: string | null; volatility_pct: number };
  quote: Quote;
  session: Session;
  estimate: { quote: string; price: string; value: string; spread_cost: string; cash_after: string; units_after: string };
  checks: GuardCheck[];
  trust: { score: number; band: "clear" | "review" | "high_risk"; signals: TrustSignal[] };
  takeover: boolean;
};
export type Step = { state: string; note: string; at: string };
export type ReviewNote = {
  summary: string; considerations: string[]; questions_for_client: string[]; suggestion: "release" | "reject" | "call_client";
  suggestion_reason: string; verified: boolean; unsupported_figures: string[]; model: string;
};
export type TradeOrder = {
  id: string; account_id: string; account_number: string; client_name: string; symbol: string; name: string;
  side: "buy" | "sell"; order_type: "market" | "limit"; quantity: number; limit_price: string | null; state: string;
  verdict: Verdict; acknowledged_warnings: boolean; estimated_value: string; fill_price: string | null; filled_at: string | null;
  broker: string; trust_score: number; trust_band: "clear" | "review" | "high_risk"; created_at: string; timeline: Step[];
  guardian: Partial<GuardianReport>; review_note: string | null; reviewed_by_name: string | null; ai_review: ReviewNote | null;
};
export type Orders = { cash: string; cash_free: string; orders: TradeOrder[] };
export type Draft = { symbol: string; side: "buy" | "sell"; order_type: "market" | "limit"; quantity: string; limit_price: string };

export const VERDICTS: Verdict[] = ["proceed", "warn", "hold", "block"];
export const VERDICT_COPY: Record<Verdict, { label: string; line: string }> = {
  proceed: { label: "Proceed", line: "Nothing in the checks stops this order." },
  warn: { label: "Proceed with care", line: "Read the warnings, then confirm them to place the order." },
  hold: { label: "Advisor review", line: "An advisor reviews this order before anything is bought or sold." },
  block: { label: "Blocked", line: "This order can't be placed as it stands." },
};
export const STATE_COPY: Record<string, { label: string; tone: "neutral" | "gain" | "caution" | "loss" }> = {
  held: { label: "With an advisor", tone: "caution" }, open: { label: "Waiting to fill", tone: "neutral" },
  filled: { label: "Filled", tone: "gain" }, cancelled: { label: "Cancelled", tone: "neutral" },
  rejected: { label: "Rejected", tone: "loss" },
};

export function actionLabel(v: Verdict): string {
  return v === "hold" ? "Send to an advisor" : v === "block" ? "Can't place this order" : "Place order";
}

export function canPlace(v: Verdict, acknowledged: boolean): boolean {
  return v === "proceed" || v === "hold" || (v === "warn" && acknowledged);
}

export function estimateCost(price: string | number, quantity: string): number | null {
  const q = quantity.trim();
  const p = Number(price);
  if (!/^\d+$/.test(q) || Number(q) < 1 || !Number.isFinite(p) || p <= 0) return null;
  return p * Number(q);
}

/** The request body for a draft order, or one sentence saying what to fix. */
export function orderBody(d: Draft, acknowledge = false): { body: Record<string, unknown> } | { error: string } {
  const q = d.quantity.trim();
  if (!/^\d+$/.test(q) || Number(q) < 1) return { error: "Enter a whole number of shares, 1 or more." };
  if (Number(q) > 100_000) return { error: "Orders are limited to 100,000 shares." };
  const body: Record<string, unknown> = {
    symbol: d.symbol, side: d.side, order_type: d.order_type, quantity: Number(q), acknowledge_warnings: acknowledge };
  if (d.order_type === "limit") {
    const raw = d.limit_price.replace(/[$,\s]/g, "");
    const limit = Number(raw);
    if (!raw || !Number.isFinite(limit) || limit <= 0) {
      return { error: d.side === "buy" ? "Enter the most you'll pay for a share." : "Enter the least you'll accept for a share." };
    }
    body.limit_price = limit.toFixed(2);
  }
  return { body };
}

export function describeOrder(o: Pick<TradeOrder, "side" | "quantity" | "symbol" | "order_type" | "limit_price">): string {
  const how = o.order_type === "market" ? "at market" : `with a limit of ${formatUsd(o.limit_price ?? 0)}`;
  return `${o.side === "buy" ? "Buy" : "Sell"} ${o.quantity} ${o.symbol} ${how}`;
}

export function concerns(checks: GuardCheck[] | undefined): GuardCheck[] {
  return (checks ?? []).filter((c) => c.outcome !== "pass");
}
