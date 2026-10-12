import type { Narrative } from "@/components/ai-prose";

export type { Narrative };

export type Fund = {
  code: string; name: string; category: string; risk_band: number; fee_bps: number; min_investment: string;
  objective: string; who_for: string; inception_on: string;
  constituents: { ticker: string; weight: string; asset_class: string; region: string; sector: string }[];
};

export type YearPoint = { year: number; p10: number; p25: number; p50: number; p75: number; p90: number; contributed: number };

export type ScenarioOut = {
  label: string; allocation: Record<string, number>; fee_bps: number; yearly: YearPoint[];
  final: Record<"p10" | "p25" | "p50" | "p75" | "p90", number>; prob_goal: number | null; prob_loss: number;
  median_without_fees: number; fee_cost: number;
  history: { annual_return_pct: number; annual_volatility_pct: number; worst_12m_pct: number; best_12m_pct: number;
    max_drawdown_pct: number; window_start: string; window_end: string };
};

export type WhatIf = {
  initial_usd: number; monthly_usd: number; years: number; goal_usd: number | null; contributed: number;
  window_start: string; window_end: string; months: number; paths: number; method: string; scenarios: ScenarioOut[];
};

export type ScenarioIn = { label?: string; allocation: Record<string, number> };

export type RiskReport = {
  window_start: string; window_end: string; months: number; weights: Record<string, number>; value_usd: number;
  annual_volatility_pct: number; beta: number; max_drawdown_pct: number; drawdown_peak: string; drawdown_trough: string;
  var95_1m_pct: number; var95_1m_usd: number; sharpe: number; worst_month: { month: string; pct: number };
  best_month: { month: string; pct: number }; correlations: Record<string, Record<string, number>>;
  risk_contributions_pct: Record<string, number>; portfolio_band: number; profile_band: number | null;
  verdict: "above" | "within" | "below" | "no_profile";
};

export type Exposure = { name: string; value_usd: number; pct: number };
export type XRay = {
  total_value_usd: number;
  etfs: { ticker: string; asset_class: string; value_usd: number; pct: number; expense_ratio_pct: number | null }[];
  sectors: Exposure[]; regions: Exposure[]; asset_classes: Exposure[];
  companies: { symbol: string; name: string; value_usd: number; pct: number; via: string[] }[];
  coverage_pct: number;
  overlaps: { funds: string[]; names: string[]; shared_etfs_pct: number; shared_companies_pct: number; top_shared: string[] }[];
  fees: { atrium_annual_usd: number; etf_annual_usd: number; total_annual_usd: number; total_pct: number; ten_year_usd: number };
  warnings: { code: string; severity: "caution" | "info"; title: string; message: string }[];
  profiles_as_of: string;
};

/** The one place raw colours live: chart series need concrete values for SVG and inline styles. */
export const BAND_COLOR: Record<number, string> = { 1: "#4d7f95", 2: "#4f8f7a", 3: "#8f9a45", 4: "#c58a2c", 5: "#b5502f" };
export const SERIES = ["#17202a", "#4d7f95", "#c58a2c"];
export const CATEGORY = ["#17202a", "#4d7f95", "#8f9a45", "#c58a2c", "#b5502f", "#6d6390", "#9aa3aa", "#5f8f86"];

/** Correlation cell shading: graphite at a strength that follows |value|. */
export function heat(value: number): string {
  return `rgba(23, 32, 42, ${(Math.min(1, Math.abs(value)) * 0.28).toFixed(3)})`;
}

export function currentMix(byFund: Record<string, string | number>): Record<string, number> | null {
  const entries = Object.entries(byFund).map(([k, v]) => [k, Number(v)] as const).filter(([, v]) => v > 0);
  const total = entries.reduce((s, [, v]) => s + v, 0);
  if (!total) return null;
  return Object.fromEntries(entries.map(([k, v]) => [k, Math.round((v / total) * 10_000) / 10_000]));
}

export function scenarioKey(s: ScenarioIn): string {
  return Object.keys(s.allocation).sort().map((k) => `${k}:${s.allocation[k]}`).join("|");
}

/** Add a scenario (at most `max`, replacing the last) or remove it (keeping at least one). */
export function toggleScenario(list: ScenarioIn[], s: ScenarioIn, max = 3): ScenarioIn[] {
  const key = scenarioKey(s);
  if (list.some((x) => scenarioKey(x) === key)) return list.length > 1 ? list.filter((x) => scenarioKey(x) !== key) : list;
  return list.length < max ? [...list, s] : [...list.slice(0, max - 1), s];
}

export function verdictText(verdict: RiskReport["verdict"], portfolio: number, profile: number | null): string {
  if (verdict === "no_profile") return `Your portfolio behaves like risk band ${portfolio}. Set your risk profile to compare.`;
  if (verdict === "above") return `Your portfolio behaves like band ${portfolio}, above your profile's band ${profile}.`;
  if (verdict === "below") return `Your portfolio behaves like band ${portfolio}, below your profile's band ${profile}.`;
  return `Your portfolio behaves like band ${portfolio}, in line with your profile.`;
}

export function parseMoney(text: string): number {
  const n = Number(text.replace(/[^\d.]/g, ""));
  return Number.isFinite(n) ? n : 0;
}
