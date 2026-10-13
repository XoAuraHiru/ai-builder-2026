"use client";

import { Fragment, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { api, ApiError } from "@/lib/api";
import { formatDate, formatUsd } from "@/lib/format";
import { INSTRUCTION_STATE, shortWhen, STEP_LABEL, type Approval, type BlotterRow } from "@/lib/operations";
import { Button, EmptyState, Field, inputClass, Loading, Notice, PageHeader, Segmented } from "@/components/ui";
import { StatusChip, TableCard, tbl } from "../_parts";

const msg = (e: unknown, fallback: string) => (e instanceof ApiError ? e.message : fallback);
const FILTERS = [
  { value: "all", label: "All" }, { value: "accepted", label: "Waiting for a price" }, { value: "allocated", label: "Dealt" },
  { value: "settled", label: "Settled" }, { value: "reversed", label: "Reversed" },
] as const;
type Filter = (typeof FILTERS)[number]["value"];
const SIDE: Record<BlotterRow["type"], string> = { subscribe: "Buy", redeem: "Sell", switch: "Switch out" };

const state = (r: BlotterRow) => INSTRUCTION_STATE[r.state] ?? { label: r.state, tone: "neutral" as const };
const waitingForMoney = (r: BlotterRow) => r.funded === false && !["rejected", "reversed"].includes(r.state);
const units = (r: BlotterRow) => `${Number(r.units ?? 0).toLocaleString("en-US", { maximumFractionDigits: 4 })} units`;
const amount = (r: BlotterRow) => (r.type === "subscribe" ? formatUsd(r.amount ?? 0) : units(r));

function FundTile({ code }: { code: string }) {
  return (
    <span aria-hidden="true" className="flex h-7 w-11 shrink-0 items-center justify-center rounded-tile bg-green-50 font-mono text-[10px] font-medium text-green-700">
      {code.replace(/^ATR-/, "")}
    </span>
  );
}

function Chevron({ open }: { open: boolean }) {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" aria-hidden="true" className={`shrink-0 text-ink-500 transition-transform ${open ? "rotate-180" : ""}`}>
      <path d="m6 9 6 6 6-6" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

/** What happened to one instruction, step by step, and the reversal request where a reversal is possible. */
function Detail({ row, reason, setReason, busy, onAsk }:
  { row: BlotterRow; reason: string; setReason: (v: string) => void; busy: boolean; onAsk: () => void }) {
  return (
    <div className="grid gap-6 md:grid-cols-2">
      <div className="min-w-0">
        <p className="text-[13px] font-medium">Timeline</p>
        {row.steps.length === 0 ? <p className="mt-1 text-sm text-ink-500">No timeline was recorded for this instruction.</p> : (
          <ol className="mt-3 space-y-3">
            {row.steps.map((s, i) => {
              const bad = s.state === "rejected" || s.state === "reversed";
              return (
                <li key={i} className="flex gap-3 text-sm">
                  <span aria-hidden="true" className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[10px] text-white ${bad ? "bg-coral-500" : "bg-green-500"}`}>
                    {bad ? "!" : "✓"}
                  </span>
                  <span className="min-w-0">
                    <span className="font-medium">{STEP_LABEL[s.state] ?? s.state}</span> <span className="text-xs text-ink-500">{shortWhen(s.at)}</span>
                    <span className="block text-ink-700">{s.note}</span>
                  </span>
                </li>
              );
            })}
          </ol>
        )}
      </div>
      <div className="min-w-0">
        {row.posting_id && (row.not_reversible_because ? (
          <Notice title="This allocation cannot be reversed">{row.not_reversible_because}</Notice>
        ) : (
          <div className="space-y-3">
            <Field label="Why this allocation should be reversed" hint="A second person approves the reversal with a one-time code.">
              <textarea className={`${inputClass} min-h-20 bg-white!`} value={reason} maxLength={500} onChange={(e) => setReason(e.target.value)}
                placeholder="For example: The client's payment was returned unpaid by their bank." />
            </Field>
            <div className="flex flex-wrap items-center gap-3">
              <Button variant="danger" busy={busy} disabled={!reason.trim()} onClick={onAsk}>Ask for a reversal</Button>
              {!reason.trim() && <span className="text-xs text-ink-500">Say why first.</span>}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function BlotterPage() {
  const [filter, setFilter] = useState<Filter>("all");
  const [rows, setRows] = useState<BlotterRow[] | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [asked, setAsked] = useState<Approval | null>(null);

  const load = useCallback(async (f: Filter) => {
    setRows(await api<BlotterRow[]>(`/ops/blotter${f === "all" ? "" : `?state=${f}`}`));
  }, []);
  useEffect(() => {
    load(filter).catch((e) => setError(msg(e, "Atrium could not load the blotter. Try again.")));
  }, [filter, load]);

  async function askReversal(row: BlotterRow) {
    if (!row.posting_id) return;
    setBusy(true);
    setError("");
    try {
      setAsked(await api<Approval>("/ops/reversals", { method: "POST", body: JSON.stringify({ posting_id: row.posting_id, reason }) }));
      setReason("");
    } catch (e) {
      setError(msg(e, "Atrium could not ask for the reversal. Try again."));
    } finally {
      setBusy(false);
    }
  }
  const toggle = (id: string) => { setOpen(open === id ? null : id); setReason(""); setAsked(null); };
  const detail = (r: BlotterRow) => <Detail row={r} reason={reason} setReason={setReason} busy={busy} onAsk={() => askReversal(r)} />;

  return (
    <>
      <PageHeader title="Blotter"
        description="Every fund instruction as it moves from received to settled, with what was checked at each step. A reversal is asked for here and approved by a second person." />
      <div className="mb-6"><Segmented label="Show" value={filter} options={[...FILTERS]} onChange={(f) => { setFilter(f); setRows(null); setOpen(null); }} /></div>
      {asked && <div className="mb-6"><Notice tone="success" title="Sent for approval">{asked.summary}. A second person approves it in <Link href="/operations/approvals" className="font-semibold text-green-600 underline-offset-4 hover:underline">Approvals</Link>.</Notice></div>}
      {error && <div className="mb-6"><Notice tone="error">{error}</Notice></div>}
      {!rows ? <Loading label="Loading the blotter" /> : rows.length === 0 ? <EmptyState title="No instructions here">Instructions appear as clients place them.</EmptyState> : (
        <TableCard title={`${rows.length} instruction${rows.length === 1 ? "" : "s"}`} description="Newest first. Open one to see its timeline.">
          <div className={`${tbl.wrap} hidden md:block`}>
            <table className={`${tbl.table} min-w-[820px]`}>
              <thead className={tbl.head}>
                <tr>
                  <th className={tbl.th}>Reference</th><th className={tbl.th}>Requested</th><th className={tbl.th}>Client</th>
                  <th className={tbl.th}>Instruction</th><th className={`${tbl.th} text-right`}>Amount</th><th className={tbl.th}>Status</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => {
                  const s = state(r);
                  const isOpen = open === r.id;
                  return (
                    <Fragment key={r.id}>
                      <tr className={`${tbl.row} ${isOpen ? "border-b-0 bg-fill" : ""}`}>
                        <td className={`${tbl.td} ${tbl.id}`}>{r.reference ?? <span className="text-ink-400">None</span>}</td>
                        <td className={`${tbl.td} whitespace-nowrap text-ink-700`}>{formatDate(r.requested_at)}</td>
                        <td className={tbl.td}><span className="font-medium">{r.holder}</span><span className={`block ${tbl.id} text-[11px]! text-ink-500`}>{r.account_number}</span></td>
                        <td className={tbl.td}>
                          <button type="button" aria-expanded={isOpen} onClick={() => toggle(r.id)} className="group flex items-center gap-2.5 text-left">
                            <FundTile code={r.fund_code} />
                            <span className="flex min-w-0 flex-col">
                              <span className="font-medium group-hover:text-green-700">{r.fund_name}</span>
                              <span className="text-xs text-ink-500">{SIDE[r.type]}</span>
                            </span>
                            <Chevron open={isOpen} />
                          </button>
                        </td>
                        <td className={`${tbl.td} ${tbl.amount}`}>{amount(r)}</td>
                        <td className={tbl.td}>
                          <StatusChip tone={s.tone}>{s.label}</StatusChip>
                          {waitingForMoney(r) && <span className="mt-1 block text-xs font-medium text-amber-800">Waiting for money</span>}
                        </td>
                      </tr>
                      {isOpen && (
                        <tr className={tbl.row}>
                          <td colSpan={6} className="bg-fill px-4 pb-5 pt-2">{detail(r)}</td>
                        </tr>
                      )}
                    </Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
          <ul className="divide-y divide-sand-100 md:hidden">
            {rows.map((r) => {
              const s = state(r);
              const isOpen = open === r.id;
              return (
                <li key={r.id} className="py-3.5">
                  <button type="button" aria-expanded={isOpen} onClick={() => toggle(r.id)} className="flex w-full items-start gap-3 text-left">
                    <FundTile code={r.fund_code} />
                    <span className="min-w-0 flex-1">
                      <span className="flex items-baseline justify-between gap-3">
                        <span className="truncate font-medium">{r.holder}</span>
                        <span className="num shrink-0 font-medium">{amount(r)}</span>
                      </span>
                      <span className="mt-0.5 block text-[13px] text-ink-700">{SIDE[r.type]} · {r.fund_name}</span>
                      <span className="mt-2 flex flex-wrap items-center gap-2">
                        <StatusChip tone={s.tone}>{s.label}</StatusChip>
                        {waitingForMoney(r) && <span className="text-xs font-medium text-amber-800">Waiting for money</span>}
                        {r.reference
                          ? <span className="code ml-auto text-[11px]! text-ink-500">{r.reference}</span>
                          : <span className="ml-auto text-xs text-ink-500">{formatDate(r.requested_at)}</span>}
                      </span>
                    </span>
                  </button>
                  {isOpen && <div className="mt-3 rounded-control bg-fill p-4">{detail(r)}</div>}
                </li>
              );
            })}
          </ul>
        </TableCard>
      )}
    </>
  );
}
