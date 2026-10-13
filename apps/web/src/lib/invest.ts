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
  names?: Record<string, string>;
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
// Design system 0.2: calm bands in the green family, Growth in amber, Adventurous in coral.
export const BAND_COLOR: Record<number, string> = { 1: "#95c0a5", 2: "#649e7d", 3: "#3f8160", 4: "#e2b23e", 5: "#e8705f" };
// Chart series, in order; highlight one series at a time, the rest stay quiet.
export const SERIES = ["#3f8160", "#e2b23e", "#e8705f"];
export const CATEGORY = ["#3f8160", "#f4d27c", "#e8705f", "#95c0a5", "#dcdad1", "#255740", "#e2b23e", "#649e7d"];
// Asset classes keep one colour wherever they appear, all in the calm family: stocks green-500, bonds green-300,
// cash and T-bills sand-300. Coral and amber stay free for risk and caution.
export const ASSET_COLOR: Record<string, string> = {
  equity: "#3f8160", bond: "#95c0a5", cash: "#dcdad1", Stocks: "#3f8160", Bonds: "#95c0a5", "Cash and T-bills": "#dcdad1",
};

/** Correlation cell shading: forest green-500 at a strength that follows |value|. */
export function heat(value: number): string {
  return `rgba(63, 129, 96, ${(Math.min(1, Math.abs(value)) * 0.32).toFixed(3)})`;
}

const BANDS = [1, 2, 3, 4, 5] as const;
const BAND_NAME: Record<number, string> = { 1: "Preserve", 2: "Cautious", 3: "Balanced", 4: "Growth", 5: "Adventurous" };

/** One step of the home risk scale: green fills the profile's band, amber the portfolio's when it sits above it,
 *  pale green when it sits below it (or there is no profile to compare with). Each marked band has a chip above it. */
export type ScaleMark = {
  band: number; label: string; fill: "profile" | "above" | "calm" | "none";
  chip: { text: string; tone: "gain" | "caution" | "neutral" } | null;
};

export function scaleMarks(profile: number | null, portfolio: number): ScaleMark[] {
  return BANDS.map((band) => {
    const label = `${band} ${BAND_NAME[band]}`;
    if (band === profile && band === portfolio) return { band, label, fill: "profile", chip: { text: "Your profile and portfolio", tone: "gain" } };
    if (band === profile) return { band, label, fill: "profile", chip: { text: "Your profile", tone: "gain" } };
    if (band === portfolio) {
      const above = profile !== null && portfolio > profile;
      return { band, label, fill: above ? "above" : "calm", chip: { text: "Your portfolio now", tone: above ? "caution" : "neutral" } };
    }
    return { band, label, fill: "none", chip: null };
  });
}

/** A bar row: a name, its share, and the bar's width as a percentage of the widest row shown. */
export type ExposureRow = { name: string; pct: number; width: number; other: boolean };

function withWidths(rows: { name: string; pct: number; other: boolean }[]): ExposureRow[] {
  const widest = Math.max(0, ...rows.map((r) => r.pct));
  return rows.map((r) => ({ ...r, width: widest > 0 ? Math.round((r.pct / widest) * 1000) / 10 : 0 }));
}

/** "Where your money sits" on Home: the largest exposures from the X-ray. */
export function topExposures(rows: Exposure[], n = 4): ExposureRow[] {
  return withWidths([...rows].sort((a, b) => b.pct - a.pct).slice(0, n).map((r) => ({ name: r.name, pct: r.pct, other: false })));
}

/** The X-ray's sector card: the largest n sectors, then everything else summed as "Other sectors". */
export function sectorRows(rows: Exposure[], n = 4): ExposureRow[] {
  const sorted = [...rows].sort((a, b) => b.value_usd - a.value_usd);
  const total = sorted.reduce((s, r) => s + r.value_usd, 0);
  const top = sorted.slice(0, n).map((r) => ({ name: r.name, pct: r.pct, other: false }));
  const rest = sorted.slice(n);
  if (rest.length === 0 || total <= 0) return withWidths(top);
  const otherPct = Math.round((rest.reduce((s, r) => s + r.value_usd, 0) / total) * 1000) / 10;
  return withWidths([...top, { name: rest.length === 1 ? rest[0].name : "Other sectors", pct: otherPct, other: rest.length > 1 }]);
}

/** The largest overlap between two funds, said in one line, or null when the funds share nothing worth saying. */
export function overlapLine(overlaps: XRay["overlaps"]): string | null {
  const ranked = [...overlaps].sort((a, b) => Math.max(b.shared_etfs_pct, b.shared_companies_pct) - Math.max(a.shared_etfs_pct, a.shared_companies_pct));
  const o = ranked[0];
  if (!o) return null;
  const pct = Math.max(o.shared_etfs_pct, o.shared_companies_pct);
  return `${o.names[0]} and ${o.names[1]} overlap by ${pct.toFixed(1)}%.`;
}

/** "NVIDIA Corp" → "NVIDIA", "Alphabet Inc Class A" → "Alphabet": a company as people say it, for chips. */
export function shortName(name: string): string {
  const short = name.replace(/\s+Class\s+[A-Z]$/i, "")
    .replace(/,?\s+(Corp\.?|Corporation|Inc\.?|Incorporated|Co\.?|Company|Ltd\.?|plc|PLC|Holdings?)$/i, "")
    .trim();
  return short || name;
}

/** An X-ray warning as a finding card: the figure set large, the rest as a sentence, and chips for what it names. */
export type Finding = {
  key: string; title: string; tone: "note" | "look"; figure: string | null; sentence: string;
  chips: { text: string; mono: boolean }[];
};

const PCT = "(\\d+(?:\\.\\d+)?%)";

export function findingCard(w: XRay["warnings"][number], x: Pick<XRay, "overlaps" | "companies">): Finding {
  const base = { key: `${w.code}-${w.message}`, title: w.title, tone: w.severity === "caution" ? "look" as const : "note" as const };
  let m: RegExpMatchArray | null;
  if (w.code === "HOME_BIAS" && (m = w.message.match(new RegExp(`^${PCT}\\s+(.*)$`)))) {
    return { ...base, figure: m[1], sentence: m[2], chips: [] };
  }
  if (w.code === "CONC_COMPANY" && (m = w.message.match(new RegExp(`^(.*) is ${PCT} of your portfolio`)))) {
    const company = x.companies.find((c) => c.name === m![1]);
    return { ...base, figure: m[2], sentence: `of your portfolio is ${m[1]}${company ? ", held through" : "."}`,
      chips: (company?.via ?? []).map((v) => ({ text: v, mono: true })) };
  }
  if ((w.code === "CONC_SECTOR" || w.code === "CONC_FUND") && (m = w.message.match(new RegExp(`^(.*) is ${PCT} of your portfolio\\.?$`)))) {
    return { ...base, figure: m[2], sentence: `of your portfolio is in ${m[1]}.`, chips: [] };
  }
  if (w.code === "ONE_FUND" && (m = w.message.match(/^Everything is in (.*?)\.\s*(.*)$/))) {
    return { ...base, figure: "100%", sentence: `of your money is in ${m[1]}.${m[2] ? ` ${m[2]}` : ""}`, chips: [] };
  }
  if (w.code === "OVERLAP") {
    const o = x.overlaps.find((v) => w.message.startsWith(`${v.names[0]} and ${v.names[1]}`));
    if (o) {
      const both = o.shared_etfs_pct > 0 && o.shared_companies_pct > 0;
      const etfLed = o.shared_etfs_pct >= o.shared_companies_pct;
      const pct = Math.max(o.shared_etfs_pct, o.shared_companies_pct);
      const detail = both ? `: ${o.shared_etfs_pct.toFixed(1)}% in the same ETFs and ${o.shared_companies_pct.toFixed(1)}% in the same companies`
        : etfLed ? ", in the same ETFs" : "";
      return { ...base, figure: `${pct.toFixed(1)}%`, sentence: `overlap between ${o.names[0]} and ${o.names[1]}${detail}`,
        chips: o.top_shared.map((n) => ({ text: shortName(n), mono: false })) };
    }
  }
  return { ...base, figure: null, sentence: w.message, chips: [] };
}

/** The copilot link with a question waiting in the box, and the question read back from the page's address. */
export function copilotHref(question: string): string {
  return `/investor/copilot?q=${encodeURIComponent(question)}`;
}

export function questionFrom(search: string): string {
  const q = new URLSearchParams(search).get("q") ?? "";
  return q.trim().slice(0, 500);
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

/** The risk check as the home page needs it: a report, or the reason there is none. Never neither. */
export function riskState(result: PromiseSettledResult<RiskReport>): { report: RiskReport } | { error: string } {
  if (result.status === "fulfilled") return { report: result.value };
  return { error: result.reason instanceof Error && result.reason.message ? result.reason.message : "Atrium could not check your mix right now." };
}
