import { formatUsd } from "./format";

export const STEP_FLOW = ["received", "checked", "accepted", "priced", "settled"] as const;
export const STEP_LABEL: Record<string, string> = {
  received: "Received", checked: "Checked", accepted: "Accepted", priced: "Priced", allocated: "Allocated",
  settled: "Settled", rejected: "Rejected",
};

export type Step = { state: string; note: string; at: string };
export type Instruction = {
  id: string; type: "subscribe" | "redeem" | "switch"; fund_code: string; fund_name: string;
  to_fund_code: string | null; to_fund_name: string | null; amount: string | null; units: string | null;
  state: string; acknowledged_risk: boolean; requested_at: string; steps: Step[];
};

/** Each step of the standard flow and whether it is done. Older instructions have no recorded steps: use the state. */
export function stepStatus(i: Instruction): { state: string; label: string; done: boolean; note?: string; at?: string }[] {
  const reached = new Map(i.steps.map((s) => [s.state, s]));
  const at = (STEP_FLOW as readonly string[]).indexOf(i.state);
  return STEP_FLOW.map((state, k) => {
    const s = reached.get(state);
    return { state, label: STEP_LABEL[state], done: Boolean(s) || (at >= 0 && k <= at), note: s?.note, at: s?.at };
  });
}

export function describe(i: Instruction): string {
  if (i.type === "subscribe") return `Invest ${formatUsd(i.amount ?? 0)} in ${i.fund_name}`;
  if (i.type === "redeem") return `Withdraw ${Number(i.units).toFixed(4)} units of ${i.fund_name}`;
  return `Switch ${Number(i.units).toFixed(4)} units from ${i.fund_name} to ${i.to_fund_name}`;
}
