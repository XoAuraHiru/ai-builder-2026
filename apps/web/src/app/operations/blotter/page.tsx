"use client";

import { Fragment, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { api, ApiError } from "@/lib/api";
import { formatDate } from "@/lib/format";
import { describeInstruction, INSTRUCTION_STATE, STEP_LABEL, type Approval, type BlotterRow } from "@/lib/operations";
import { Badge, Button, EmptyState, Field, inputClass, Loading, Notice, PageHeader, Segmented, tableStyles as t } from "@/components/ui";

const msg = (e: unknown, fallback: string) => (e instanceof ApiError ? e.message : fallback);
const FILTERS = [
  { value: "all", label: "All" }, { value: "accepted", label: "Waiting for a price" }, { value: "allocated", label: "Dealt" },
  { value: "settled", label: "Settled" }, { value: "reversed", label: "Reversed" },
] as const;
type Filter = (typeof FILTERS)[number]["value"];

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

  return (
    <>
      <PageHeader title="Blotter"
        description="Every fund instruction as it moves from received to settled, with what was checked at each step. A reversal is asked for here and approved by a second person." />
      <div className="mb-6"><Segmented label="Show" value={filter} options={[...FILTERS]} onChange={(f) => { setFilter(f); setRows(null); setOpen(null); }} /></div>
      {asked && <div className="mb-6"><Notice tone="success" title="Sent for approval">{asked.summary}. A second person approves it in <Link href="/operations/approvals" className="underline underline-offset-4">Approvals</Link>.</Notice></div>}
      {error && <div className="mb-6"><Notice tone="error">{error}</Notice></div>}
      {!rows ? <Loading label="Loading the blotter" /> : rows.length === 0 ? <EmptyState title="No instructions here">Instructions appear as clients place them.</EmptyState> : (
        <div className={t.wrap}>
          <table className={t.table}>
            <thead className={t.head}>
              <tr><th className={t.th}>Requested</th><th className={t.th}>Client</th><th className={t.th}>Instruction</th><th className={t.th}>Reference</th><th className={t.th}>State</th></tr>
            </thead>
            <tbody>
              {rows.map((r) => {
                const state = INSTRUCTION_STATE[r.state] ?? { label: r.state, tone: "neutral" as const };
                const waiting = r.funded === false && !["rejected", "reversed"].includes(r.state);
                return (
                  <Fragment key={r.id}>
                    <tr className={t.row}>
                      <td className={`${t.td} whitespace-nowrap`}>{formatDate(r.requested_at)}</td>
                      <td className={t.td}><span className="font-medium">{r.holder}</span><span className="block text-xs text-muted">{r.account_number}</span></td>
                      <td className={t.td}>
                        <button type="button" aria-expanded={open === r.id} className="text-left underline decoration-line-strong underline-offset-4 hover:decoration-ink"
                          onClick={() => { setOpen(open === r.id ? null : r.id); setReason(""); setAsked(null); }}>
                          {describeInstruction(r)}
                        </button>
                      </td>
                      <td className={`${t.td} num`}>{r.reference ?? "None"}</td>
                      <td className={t.td}>
                        <Badge tone={state.tone}>{state.label}</Badge>
                        {waiting && <span className="mt-0.5 block text-xs text-caution">Waiting for money</span>}
                      </td>
                    </tr>
                    {open === r.id && (
                      <tr className={t.row}>
                        <td colSpan={5} className="bg-surface px-4 py-4">
                          <div className="grid gap-6 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
                            <div>
                              <p className="text-sm font-medium">Timeline</p>
                              {r.steps.length === 0 ? <p className="mt-1 text-sm text-muted">No steps recorded yet.</p> : (
                                <ol className="mt-2 space-y-2 border-l border-line pl-4 text-sm">
                                  {r.steps.map((s, i) => (
                                    <li key={i}>
                                      <span className="font-medium">{STEP_LABEL[s.state] ?? s.state}</span> <span className="text-xs text-muted">{formatDate(s.at)}</span>
                                      <span className="block text-ink-2">{s.note}</span>
                                    </li>
                                  ))}
                                </ol>
                              )}
                            </div>
                            <div>
                              {r.posting_id && (r.not_reversible_because ? (
                                <p className="text-sm text-ink-2">{r.not_reversible_because}</p>
                              ) : (
                                <div className="space-y-3">
                                  <Field label="Why this allocation should be reversed" hint="A second person approves the reversal with a one-time code.">
                                    <textarea className={`${inputClass} min-h-16`} value={reason} maxLength={500} onChange={(e) => setReason(e.target.value)}
                                      placeholder="For example: The client's payment was returned unpaid by their bank." />
                                  </Field>
                                  <Button variant="secondary" busy={busy} disabled={!reason.trim()} onClick={() => askReversal(r)}>Ask for a reversal</Button>
                                </div>
                              ))}
                            </div>
                          </div>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
