import { formatMonth } from "./format";
import type { Narrative } from "@/components/ai-prose";

export type { Narrative };

export type HoldingChange = { symbol: string; name: string; value_usd: number; change_pct: number; change_usd: number };

export type Replay = {
  key: AnalogueKey;
  title: string;
  start: string;
  end: string;
  loss_usd: number; // the window's change in value: negative is a loss
  loss_pct: number;
  trough_month: string | null;
  recovery_months: number | null;
  worst_holding: { symbol: string; name: string; pct: number } | null;
  holdings: HoldingChange[];
  notes: string[];
};

export type History = { replays: Replay[]; empty: boolean; paused: string | null };

export type Impact = {
  total_usd: number;
  total_pct: number;
  holdings: HoldingChange[];
  by_factor: { factor: string; change_usd: number }[];
};

export type AnalogueKey = "crisis_2008" | "pandemic_2020" | "rates_2022";

export type Proposal = {
  in_scope: boolean;
  refusal: string;
  title: string;
  horizon_months: number;
  shocks: { factor: string; pct: number; reason: string }[];
  analogue: AnalogueKey | "none";
  analogue_reason: string;
  assumptions: string[];
};

export type MapResult = {
  proposal: Proposal;
  shocks: Record<string, number>;
  clamped: string[];
  dropped: string[];
  sources: { title: string; uri: string }[];
  sources_note: string | null;
  search_suggestions: string; // Google Search suggestions as Google renders them (HTML); shown as sent
  impact: Impact | null;
};

export const ASSET_FACTORS = ["us_equity", "intl_equity", "bonds", "cash"] as const;

export const FACTOR_LABEL: Record<string, string> = {
  us_equity: "US stocks", intl_equity: "International stocks", bonds: "Bonds", cash: "Cash",
  technology: "Technology", communication_services: "Communication services", consumer_cyclical: "Consumer cyclical",
  consumer_defensive: "Consumer staples", energy: "Energy", financial_services: "Financials", healthcare: "Health care",
  industrials: "Industrials", basic_materials: "Materials", realestate: "Real estate", utilities: "Utilities",
};

export const ANALOGUE_TITLE: Record<AnalogueKey, string> = {
  crisis_2008: "The 2008 financial crisis", pandemic_2020: "The 2020 pandemic crash", rates_2022: "The 2022 rate shock",
};

export const EXAMPLES = ["Oil at $150 and a US recession", "AI stocks fall 40%", "The Fed cuts rates to zero"];

const BOUNDS: Record<string, [number, number]> = { bonds: [-30, 20], cash: [-5, 5] };
const EQUITY: [number, number] = [-70, 50];

/** The server's bounds for a shock, in percent: equities and sectors −70 to +50, bonds −30 to +20, cash −5 to +5. */
export function bounds(factor: string): [number, number] {
  return BOUNDS[factor] ?? EQUITY;
}

export function clampShock(factor: string, pct: number): number {
  const [low, high] = bounds(factor);
  return Math.min(high, Math.max(low, pct));
}

function trimmed(n: number): string {
  return Number.isInteger(n) ? String(n) : n.toFixed(1).replace(/\.0$/, "");
}

/** A shock with its sign: +10%, −12.5%, 0%. */
export function formatShock(pct: number): string {
  if (pct === 0) return "0%";
  return `${pct > 0 ? "+" : "−"}${trimmed(Math.abs(pct))}%`;
}

export function clampedNote(factor: string, pct: number): string {
  return `Held to ${formatShock(clampShock(factor, pct))}, the limit for this kind of shock`;
}

export function recoveryText(months: number | null): string {
  if (months === null) return "Not recovered within the data";
  if (months === 0) return "Never fell below its starting value";
  return `Recovered in ${months} month${months === 1 ? "" : "s"}`;
}

const usd0 = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });

/** Money with its sign, to the dollar: +$1,250 or −$7,420. */
export function signedUsd0(value: number): string {
  const rounded = Math.round(value);
  if (rounded === 0) return "$0";
  return `${rounded > 0 ? "+" : "−"}${usd0.format(Math.abs(rounded))}`;
}

export function signedPct(value: number): string {
  const rounded = Number(value.toFixed(1));
  if (rounded === 0) return "0%";
  return `${rounded > 0 ? "+" : "−"}${Math.abs(rounded).toFixed(1)}%`;
}

/** The key moment's title: "−$7,420, or −15.3% of your portfolio". */
export function impactTitle(totalUsd: number, totalPct: number): string {
  return `${signedUsd0(totalUsd)}, or ${signedPct(totalPct)} of your portfolio`;
}

export function windowText(start: string, end: string): string {
  return `End of ${formatMonth(start)} to end of ${formatMonth(end)}`;
}

export type SliderRow = { factor: string; label: string; pct: number; reason: string | null; clamped: boolean; min: number; max: number };

/** Gemini's shocks first, each with its reason, then the asset classes it left alone; values are the ones in play. */
export function sliderRows(result: MapResult, current: Record<string, number>): SliderRow[] {
  const reasons = new Map(result.proposal.shocks.map((s) => [s.factor, s.reason]));
  const order = [...result.proposal.shocks.map((s) => s.factor), ...ASSET_FACTORS.filter((f) => !reasons.has(f))];
  return order.map((factor) => {
    const pct = current[factor] ?? result.shocks[factor] ?? 0;
    const [min, max] = bounds(factor);
    return {
      factor, label: FACTOR_LABEL[factor] ?? factor, pct, reason: reasons.get(factor) ?? null, min, max,
      clamped: result.clamped.includes(factor) && pct === result.shocks[factor],
    };
  });
}

export function sameShocks(a: Record<string, number>, b: Record<string, number>): boolean {
  const keys = Object.keys(a);
  return keys.length === Object.keys(b).length && keys.every((k) => k in b && a[k] === b[k]);
}

/** The studio's state. Answers carry the ticket or the shocks they were asked for, and an answer that a newer request
 * overtook is dropped: the page never shows figures or prose for shocks no longer in play. */
export type Studio = {
  mapping: boolean;
  mapTicket: number;
  mapError: string;
  result: MapResult | null;
  shocks: Record<string, number>;
  impact: Impact | null;
  edits: number;            // slider moves since the last mapping; the debounced apply runs when this changes
  applyTicket: number;      // the apply whose answer counts; -1 when none does
  updating: boolean;
  applyError: string;
  narrative: Narrative | null;
  explaining: boolean;
  explainFor: Record<string, number> | null;  // the shocks the explanation in flight was asked for
  explainError: string;
};

export const INITIAL_STUDIO: Studio = {
  mapping: false, mapTicket: 0, mapError: "", result: null, shocks: {}, impact: null, edits: 0, applyTicket: -1,
  updating: false, applyError: "", narrative: null, explaining: false, explainFor: null, explainError: "",
};

export type StudioAction =
  | { type: "map"; ticket: number }
  | { type: "mapped"; ticket: number; result: MapResult }
  | { type: "mapFailed"; ticket: number; error: string }
  | { type: "move"; factor: string; pct: number }
  | { type: "applying"; ticket: number }
  | { type: "applied"; ticket: number; impact: Impact }
  | { type: "applyFailed"; ticket: number; error: string }
  | { type: "explain" }
  | { type: "explained"; forShocks: Record<string, number>; narrative: Narrative }
  | { type: "explainFailed"; forShocks: Record<string, number>; error: string };

/** Whether a mapping can start: one at a time, and only for a scenario of at least three characters. */
export function canMap(s: Studio, text: string): boolean {
  return !s.mapping && text.trim().length >= 3;
}

export function studio(s: Studio, a: StudioAction): Studio {
  switch (a.type) {
    case "map":
      return { ...s, mapping: true, mapTicket: a.ticket, mapError: "" };
    case "mapped":
      if (a.ticket !== s.mapTicket) return s;
      return { ...s, mapping: false, result: a.result, shocks: a.result.shocks, impact: a.result.impact, edits: 0,
        applyTicket: -1, updating: false, applyError: "", narrative: null, explaining: false, explainFor: null,
        explainError: "" };
    case "mapFailed":
      return a.ticket === s.mapTicket ? { ...s, mapping: false, mapError: a.error } : s;
    case "move":
      return { ...s, shocks: { ...s.shocks, [a.factor]: a.pct }, edits: s.edits + 1, narrative: null, explainError: "" };
    case "applying":
      return { ...s, applyTicket: a.ticket, updating: true };
    case "applied":
      return a.ticket === s.applyTicket ? { ...s, impact: a.impact, updating: false, applyError: "" } : s;
    case "applyFailed":
      return a.ticket === s.applyTicket ? { ...s, updating: false, applyError: a.error } : s;
    case "explain":
      return { ...s, explaining: true, explainError: "", explainFor: s.shocks };
    case "explained":
    case "explainFailed": {
      if (!s.explainFor || !sameShocks(a.forShocks, s.explainFor)) return s;  // a newer request, or a new mapping
      const current = sameShocks(a.forShocks, s.shocks);
      const done = { ...s, explaining: false, explainFor: null };
      if (!current) return done;
      return a.type === "explained" ? { ...done, narrative: a.narrative } : { ...done, explainError: a.error };
    }
  }
}
