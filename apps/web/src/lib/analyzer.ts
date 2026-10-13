import { formatMonth, formatUsd } from "./format";
import type { ScenarioOut, WhatIf } from "./invest";

/** The return analyzer (front door): one fund or one share, a one-time amount, and what it could become. */

export type AnalyzerKind = "unit_trust" | "share";
export type FundOption = { code: string; name: string; risk_band: number; fee_bps: number; min_investment: number };
export type ShareOption = { symbol: string; name: string; kind: "stock" | "etf"; history_start: string };
export type AnalyzerOptions = { funds: FundOption[]; shares: ShareOption[]; min_share_years: number; monthly_minimum: number };
export type Analysis = {
  id: string; kind: AnalyzerKind; code: string; name: string; fee_bps: number; min_investment: number;
  result: WhatIf; comparison: ScenarioOut | null;
};
export type AnalyzerInput = { kind: AnalyzerKind; code: string; initial: number; monthly: number; years: number };
export type UnitPoint = { date: string; price: number; backtest: boolean };
export type UnitHistory = { code: string; name: string; inception_on: string; points: UnitPoint[] };
export type UnitRange = "1y" | "2y" | "all";

export const MAX_YEARS = 40;

/** The API's rules, with the API's words, so the form can answer before a round trip. Null means it can run. */
export function validate(input: AnalyzerInput, options: AnalyzerOptions): string | null {
  if (!(input.initial > 0)) return "Enter a one-time amount to invest.";
  if (!Number.isInteger(input.years) || input.years < 1 || input.years > MAX_YEARS) return `Choose 1 to ${MAX_YEARS} years.`;
  if (input.monthly < 0) return "A monthly amount cannot be negative.";
  if (input.kind === "unit_trust") {
    const fund = options.funds.find((f) => f.code === input.code);
    if (!fund) return "Choose one of Atrium's funds.";
    if (input.initial < fund.min_investment) return `${fund.name} needs at least ${formatUsd(fund.min_investment, 0)} to start.`;
    if (input.monthly > 0 && input.monthly < options.monthly_minimum)
      return `Monthly amounts start at ${formatUsd(options.monthly_minimum, 0)}.`;
    return null;
  }
  if (input.monthly) return "Monthly amounts are for unit trusts only; shares take a one-time amount.";
  if (!options.shares.some((s) => s.symbol === input.code)) return "Choose one of the shares.";
  return null;
}

/** Orders are for whole shares: as many as the amount buys at this price, and what is left over. */
export function wholeShares(amountUsd: number, price: number): { shares: number; cost: number; left: number } {
  if (!(amountUsd > 0) || !(price > 0)) return { shares: 0, cost: 0, left: Math.max(0, amountUsd || 0) };
  const shares = Math.floor((amountUsd + 1e-9) / price);
  const cost = Math.round(shares * price * 100) / 100;
  return { shares, cost, left: Math.round((amountUsd - cost) * 100) / 100 };
}

function initialOf(a: Analysis): number {
  return a.result.initial_usd;
}

export function fundOrderLink(a: Analysis): string {
  const q = new URLSearchParams({ analysis: a.id, fund: a.code, amount: String(initialOf(a)) });
  if (a.result.monthly_usd > 0) q.set("monthly", String(a.result.monthly_usd));
  return `/investor/orders?${q}`;
}

export function shareOrderLink(a: Analysis, price: number): string {
  const q = new URLSearchParams({ analysis: a.id, qty: String(wholeShares(initialOf(a), price).shares) });
  return `/investor/markets/${encodeURIComponent(a.code)}?${q}`;
}

export function applyLink(a: Analysis): string {
  const q = new URLSearchParams({ analysis: a.id, amount: String(initialOf(a)), years: String(a.result.years) });
  if (a.result.monthly_usd > 0) q.set("monthly", String(a.result.monthly_usd));
  return `/apply?${q}`;
}

type Params = { get(name: string): string | null };

function id(p: Params): string | null {
  const v = p.get("analysis");
  return v && /^[A-Za-z0-9-]{1,32}$/.test(v) ? v : null;
}

function positive(p: Params, name: string, integer = false): number | null {
  const raw = p.get(name);
  if (raw === null || raw.trim() === "") return null;
  const n = Number(raw);
  if (!Number.isFinite(n) || n <= 0 || (integer && !Number.isInteger(n))) return null;
  return n;
}

export function readFundOrder(p: Params): { analysis: string; fund: string; amount: number; monthly: number | null } | null {
  const analysis = id(p);
  const fund = p.get("fund");
  const amount = positive(p, "amount");
  if (!analysis || !fund || !/^[A-Z0-9-]{1,16}$/.test(fund) || amount === null) return null;
  return { analysis, fund, amount, monthly: positive(p, "monthly") };
}

export function readShareOrder(p: Params): { analysis: string; qty: number } | null {
  const analysis = id(p);
  const qty = positive(p, "qty", true);
  return analysis && qty !== null ? { analysis, qty } : null;
}

export function readApply(p: Params): { analysis: string; amount: number; monthly: number | null; years: number | null } | null {
  const analysis = id(p);
  const amount = positive(p, "amount");
  if (!analysis || amount === null) return null;
  const years = positive(p, "years", true);
  return { analysis, amount, monthly: positive(p, "monthly"), years: years !== null && years <= 50 ? years : null };
}

/**
 * The disclosure under every result (FINRA Rule 2214 for investment analysis tools): how it works, its limits, that
 * results vary, why the share list flatters itself, and that it is hypothetical. Fixed text, in one place.
 */
export function disclosure(a: Analysis): string[] {
  const r = a.result;
  const window = `${formatMonth(r.window_start)} to ${formatMonth(r.window_end)}`;
  const out = [
    `How this works: ${r.paths.toLocaleString("en-US")} simulated paths, each stitched together from 12-month blocks of ` +
      `real monthly returns from ${window}, so crashes and recoveries keep their real shape. ` +
      (a.kind === "unit_trust"
        ? `The fund's ${(a.fee_bps / 100).toFixed(2)}% annual fee is taken monthly.`
        : "The S&P 500 is simulated on the same months for comparison. No fund fee applies."),
    "Its limits: it uses past prices only. It leaves out taxes, trading costs and inflation, and the future may be " +
      "unlike anything in this window.",
    "Results vary: change the amount, the duration or the investment and the outcomes change; they also change as " +
      "new months are added to the history.",
  ];
  if (a.kind === "share")
    out.push("The shares on offer are large companies and funds chosen today. Their histories include the years that " +
      "made them large, so a simulation of their past flatters them; many companies that looked similar in 2007 did " +
      "far worse. The S&P 500 line shows the broad market on the same months.");
  out.push("These projections are hypothetical. They do not reflect actual investment results and are not guarantees " +
    "of future results. This is not investment advice; Atrium's prototype uses synthetic people and paper money.");
  return out;
}

/** The points a range shows: the last one or two years, or everything. */
export function unitRange(points: UnitPoint[], range: UnitRange): UnitPoint[] {
  if (range === "all" || points.length === 0) return points;
  const last = new Date(`${points[points.length - 1].date}T00:00:00`);
  const from = new Date(last);
  from.setFullYear(last.getFullYear() - (range === "1y" ? 1 : 2));
  const iso = from.toISOString().slice(0, 10);
  return points.filter((p) => p.date >= iso);
}

/** Start-to-end change and the largest fall from a high, over the points shown. */
export function unitStats(points: UnitPoint[]): { changePct: number; fallPct: number; fallFrom: string; fallTo: string } | null {
  if (points.length < 2) return null;
  let peak = points[0];
  let worst = { pct: 0, from: points[0].date, to: points[0].date };
  for (const p of points) {
    if (p.price > peak.price) peak = p;
    const fall = (p.price / peak.price - 1) * 100;
    if (fall < worst.pct) worst = { pct: fall, from: peak.date, to: p.date };
  }
  const changePct = (points[points.length - 1].price / points[0].price - 1) * 100;
  return { changePct: round1(changePct), fallPct: round1(worst.pct), fallFrom: worst.from, fallTo: worst.to };
}

function round1(x: number): number {
  return Math.round(x * 10) / 10;
}
