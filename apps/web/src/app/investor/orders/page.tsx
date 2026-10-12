"use client";

import { useCallback, useEffect, useState } from "react";
import { api, ApiError, type Portfolio } from "@/lib/api";
import { formatDate, formatSignedUsd, formatUsd } from "@/lib/format";
import type { Fund } from "@/lib/invest";
import { describe, stepStatus, type Instruction } from "@/lib/orders";
import { useMe } from "@/lib/session-context";
import { Badge, Button, EmptyState, Field, inputClass, Loading, MoneyInput, Notice, PageHeader, Panel, RiskBand, Section, Segmented } from "@/components/ui";

type Kind = "subscribe" | "redeem" | "switch";
type Check = { code: string; ok: boolean; message: string };
type PlanOut = {
  ok: boolean; checks: Check[]; needs_acknowledgement: boolean; suitability: string | null;
  estimate: { units?: string; nav?: string; nav_as_of?: string };
  redemption: { units: string; value: string; cost: string; realised_gain: string; nav: string; nav_as_of: string } | null;
};
type Recurring = { id: string; fund_code: string; fund_name: string; amount: string; day_of_month: number; status: string; acknowledged_risk: boolean };

const message = (e: unknown) => (e instanceof ApiError ? e.message : "Atrium could not reach its server. Try again.");

function Stepper({ instruction }: { instruction: Instruction }) {
  const steps = stepStatus(instruction);
  return (
    <ol className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs">
      {steps.map((s, i) => (
        <li key={s.state} className="flex items-center gap-2" title={s.note}>
          <span className={`flex items-center gap-1.5 ${s.done ? "text-ink" : "text-muted"}`}>
            <span aria-hidden="true" className={`h-2 w-2 rounded-full ${s.done ? "bg-ink" : "border border-line-strong"}`} />{s.label}
          </span>
          {i < steps.length - 1 && <span aria-hidden="true" className={`h-px w-5 ${steps[i + 1].done ? "bg-ink" : "bg-line-strong"}`} />}
        </li>
      ))}
    </ol>
  );
}

function CheckList({ checks }: { checks: Check[] }) {
  return (
    <ul className="space-y-1.5 text-sm">
      {checks.map((c) => (
        <li key={c.code + c.message} className="flex items-start gap-2">
          <svg viewBox="0 0 16 16" className={`mt-0.5 h-4 w-4 shrink-0 ${c.ok ? "text-gain" : "text-loss"}`} aria-hidden="true">
            {c.ok ? <path d="M3.5 8.5 6.5 11.5 12.5 4.5" fill="none" stroke="currentColor" strokeWidth="1.75" />
              : <path d="M4.5 4.5l7 7m0-7-7 7" fill="none" stroke="currentColor" strokeWidth="1.75" />}
          </svg>
          <span><span className="sr-only">{c.ok ? "Passed: " : "Failed: "}</span>{c.message}</span>
        </li>
      ))}
    </ul>
  );
}

export default function OrdersPage() {
  const me = useMe();
  const account = me.accounts[0];
  const [funds, setFunds] = useState<Fund[]>([]);
  const [held, setHeld] = useState<Record<string, string>>({});
  const [band, setBand] = useState<number | null>(null);
  const [history, setHistory] = useState<Instruction[] | null>(null);
  const [plans, setPlans] = useState<Recurring[]>([]);
  const [kind, setKind] = useState<Kind>("subscribe");
  const [fund, setFund] = useState("ATR-BAL");
  const [toFund, setToFund] = useState("ATR-CASH");
  const [amount, setAmount] = useState("1000");
  const [plan, setPlan] = useState<PlanOut | null>(null);
  const [ack, setAck] = useState(false);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [placed, setPlaced] = useState<Instruction | null>(null);
  const [monthly, setMonthly] = useState({ fund: "ATR-BAL", amount: "250", day: "5", ack: false });
  const [monthlyError, setMonthlyError] = useState("");

  const load = useCallback(async () => {
    if (!account) return;
    const [f, p, profile, list, recurring] = await Promise.all([
      api<Fund[]>("/funds"), api<Portfolio>(`/accounts/${account.id}/portfolio`),
      api<{ current_band: number | null }>("/me/risk-profile"),
      api<Instruction[]>(`/accounts/${account.id}/instructions`), api<Recurring[]>(`/accounts/${account.id}/recurring`)]);
    setFunds(f);
    setHeld(p.by_fund);
    setBand(profile.current_band);
    setHistory(list);
    setPlans(recurring);
  }, [account]);

  useEffect(() => {
    load().catch((e) => setError(message(e)));
    const preset = new URLSearchParams(window.location.search).get("fund");
    if (preset) setFund(preset);
  }, [load]);

  useEffect(() => {
    setPlan(null);
    setAck(false);
    setPlaced(null);
  }, [kind, fund, toFund, amount]);

  useEffect(() => {
    if (kind !== "subscribe" && !(fund in held) && Object.keys(held).length) setFund(Object.keys(held)[0]);
  }, [kind, fund, held]);

  if (!account) return <EmptyState title="No investment account yet">Choose an investor persona to place instructions.</EmptyState>;
  if (!history) return error ? <Notice tone="error">{error}</Notice> : <Loading label="Loading your instructions" />;

  const byCode = Object.fromEntries(funds.map((f) => [f.code, f]));
  const sourceFunds = kind === "subscribe" ? funds : funds.filter((f) => f.code in held);
  const body = () => ({ type: kind, fund_code: fund, ...(kind === "switch" ? { to_fund_code: toFund } : {}), amount_usd: amount || "0", acknowledge_risk: ack });

  async function review() {
    setBusy("review");
    setError("");
    try {
      setPlan(await api<PlanOut>(`/accounts/${account!.id}/instructions/preview`, { method: "POST", body: JSON.stringify(body()) }));
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy("");
    }
  }

  async function place() {
    setBusy("place");
    setError("");
    try {
      setPlaced(await api<Instruction>(`/accounts/${account!.id}/instructions`, { method: "POST", body: JSON.stringify(body()) }));
      setPlan(null);
      await load();
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy("");
    }
  }

  async function addMonthly(e: React.FormEvent) {
    e.preventDefault();
    setMonthlyError("");
    try {
      await api(`/accounts/${account!.id}/recurring`, { method: "POST", body: JSON.stringify({
        fund_code: monthly.fund, amount_usd: monthly.amount || "0", day_of_month: Number(monthly.day), acknowledge_risk: monthly.ack }) });
      await load();
    } catch (err) {
      setMonthlyError(message(err));
    }
  }

  async function cancelMonthly(id: string) {
    try {
      await api(`/accounts/${account!.id}/recurring/${id}`, { method: "DELETE" });
      await load();
    } catch (err) {
      setMonthlyError(message(err));
    }
  }

  const monthlyAbove = band !== null && (byCode[monthly.fund]?.risk_band ?? 0) > band;
  return (
    <>
      <PageHeader title="Orders" description="Invest, withdraw or switch between funds. Atrium checks every instruction against your holdings and your risk profile before it is accepted, and shows you the checks first." />
      <div className="space-y-12">
        <div className="grid gap-8 lg:grid-cols-[340px_minmax(0,1fr)]">
          <Panel className="h-fit space-y-5 p-5">
            <Segmented label="Instruction type" value={kind} onChange={setKind}
              options={[{ value: "subscribe", label: "Invest" }, { value: "redeem", label: "Withdraw" }, { value: "switch", label: "Switch" }]} />
            {sourceFunds.length === 0 ? <p className="text-sm text-ink-2">You have no holdings to withdraw or switch yet.</p> : (
              <>
                <Field label={kind === "subscribe" ? "Fund" : "From fund"}>
                  <select className={inputClass} value={fund} onChange={(e) => setFund(e.target.value)}>
                    {sourceFunds.map((f) => <option key={f.code} value={f.code}>{f.name} (band {f.risk_band})</option>)}
                  </select>
                </Field>
                {kind === "switch" && (
                  <Field label="To fund">
                    <select className={inputClass} value={toFund} onChange={(e) => setToFund(e.target.value)}>
                      {funds.filter((f) => f.code !== fund).map((f) => <option key={f.code} value={f.code}>{f.name} (band {f.risk_band})</option>)}
                    </select>
                  </Field>
                )}
                <Field label="Amount" hint={kind === "subscribe" ? `Minimum ${formatUsd(byCode[fund]?.min_investment ?? 0, 0)}` : `You hold ${formatUsd(held[fund] ?? 0)} of this fund`}>
                  <MoneyInput value={amount} onChange={setAmount} />
                </Field>
                <Button variant="secondary" busy={busy === "review"} onClick={review} disabled={!amount}>Review instruction</Button>
              </>
            )}
            <p className="text-xs text-muted">Your band: {band ? <RiskBand band={band} /> : "not set"}</p>
          </Panel>
          <div className="min-w-0 space-y-5">
            {error && <Notice tone="error">{error}</Notice>}
            {placed && (
              <Notice tone="success" title="Instruction accepted">
                <p>{describe(placed)}. It will be dealt at the next published price.</p>
                <div className="mt-2"><Stepper instruction={placed} /></div>
              </Notice>
            )}
            {plan ? (
              <Panel className="space-y-5 p-5">
                <div>
                  <p className="text-sm font-medium">Checks</p>
                  <div className="mt-2"><CheckList checks={plan.checks} /></div>
                </div>
                {plan.estimate.units && (
                  <p className="text-sm text-ink-2">About {Number(plan.estimate.units).toFixed(4)} units at the latest price of {formatUsd(plan.estimate.nav ?? 0)} ({formatDate(plan.estimate.nav_as_of ?? "")}). The final price is the next one published.</p>
                )}
                {plan.redemption && (
                  <p className="text-sm text-ink-2">
                    Sells about {Number(plan.redemption.units).toFixed(4)} units worth {formatUsd(plan.redemption.value)}, first in, first out.
                    Estimated realised gain {formatSignedUsd(plan.redemption.realised_gain)}. Not tax advice.
                  </p>
                )}
                {plan.needs_acknowledgement && plan.suitability && (
                  <Notice tone="caution" title="Above your risk profile">
                    <p>{plan.suitability}</p>
                    <label className="mt-2 flex items-start gap-2 text-ink">
                      <input type="checkbox" className="mt-1 accent-[var(--color-ink)]" checked={ack} onChange={(e) => setAck(e.target.checked)} />
                      I understand this carries more risk than my profile suggests.
                    </label>
                  </Notice>
                )}
                <Button busy={busy === "place"} disabled={!plan.ok || (plan.needs_acknowledgement && !ack)} onClick={place}>Place instruction</Button>
              </Panel>
            ) : !placed && (
              <EmptyState title="Review before you place">Choose a fund and an amount, then review. You will see every check before anything is placed.</EmptyState>
            )}
          </div>
        </div>
        <Section title="Monthly contributions" description="A fixed amount into one fund each month. Plans start at $50; the day-end process turns each due plan into an investment.">
          <form onSubmit={addMonthly} className="flex flex-wrap items-end gap-3">
            <Field label="Fund" className="min-w-56">
              <select className={inputClass} value={monthly.fund} onChange={(e) => setMonthly({ ...monthly, fund: e.target.value, ack: false })}>
                {funds.map((f) => <option key={f.code} value={f.code}>{f.name}</option>)}
              </select>
            </Field>
            <Field label="Amount" className="w-36"><MoneyInput value={monthly.amount} onChange={(v) => setMonthly({ ...monthly, amount: v })} /></Field>
            <Field label="Day of month" className="w-28">
              <input type="number" min={1} max={28} className={`${inputClass} num`} value={monthly.day} onChange={(e) => setMonthly({ ...monthly, day: e.target.value })} />
            </Field>
            {monthlyAbove && (
              <label className="flex items-center gap-2 pb-2 text-sm">
                <input type="checkbox" className="accent-[var(--color-ink)]" checked={monthly.ack} onChange={(e) => setMonthly({ ...monthly, ack: e.target.checked })} />
                I understand this fund is above my risk profile
              </label>
            )}
            <Button type="submit" variant="secondary">Add monthly plan</Button>
          </form>
          {monthlyError && <div className="mt-3"><Notice tone="caution">{monthlyError}</Notice></div>}
          {plans.length > 0 && (
            <ul className="mt-5 divide-y divide-line border-y border-line text-sm">
              {plans.map((p) => (
                <li key={p.id} className="flex flex-wrap items-center justify-between gap-3 py-2.5">
                  <span>{formatUsd(p.amount)} into {p.fund_name} on day {p.day_of_month} {p.acknowledged_risk && <Badge tone="caution">risk acknowledged</Badge>}</span>
                  {p.status === "active" ? <Button variant="quiet" onClick={() => cancelMonthly(p.id)}>Cancel plan</Button> : <Badge>Cancelled</Badge>}
                </li>
              ))}
            </ul>
          )}
        </Section>
        <Section title="Your instructions">
          {history.length === 0 ? <p className="text-sm text-muted">No instructions yet.</p> : (
            <ul className="divide-y divide-line border-y border-line">
              {history.map((i) => (
                <li key={i.id} className="grid gap-2 py-3 md:grid-cols-[minmax(0,1fr)_auto] md:items-center">
                  <span className="min-w-0">
                    <span className="text-sm font-medium">{describe(i)}</span>
                    <span className="block text-xs text-muted">{formatDate(i.requested_at)}{i.acknowledged_risk ? ". Risk acknowledged by you." : ""}</span>
                  </span>
                  <Stepper instruction={i} />
                </li>
              ))}
            </ul>
          )}
        </Section>
      </div>
    </>
  );
}
