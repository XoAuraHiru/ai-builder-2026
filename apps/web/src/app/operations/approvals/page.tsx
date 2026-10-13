"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { api, ApiError } from "@/lib/api";
import { formatDate } from "@/lib/format";
import { useSession } from "@/lib/session-context";
import {
  ACTION_COPY, approvalAmount, approvalStatus, resultWords, shortId, shortWhen, type Approval,
} from "@/lib/operations";
import { CodeField, DemoAuthenticator } from "@/components/step-up";
import { Button, EmptyState, Field, inputClass, Loading, Notice, PageHeader } from "@/components/ui";
import { StatusChip, TableCard, tbl } from "../_parts";

const msg = (e: unknown, fallback: string) => (e instanceof ApiError ? e.message : fallback);

function Check() {
  return (
    <span aria-hidden="true" className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-green-500 text-white">
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><path d="M20 6 9 17l-5-5" /></svg>
    </span>
  );
}

/** The request as the approver reads it: what, which record, how much, why, and the evidence behind it. */
function RequestCard({ approval }: { approval: Approval }) {
  const amount = approvalAmount(approval.summary);
  return (
    <div className="space-y-3 rounded-control bg-fill px-4 py-3.5">
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 flex-col gap-0.5">
          <span className="text-sm font-semibold">{ACTION_COPY[approval.action]}</span>
          <span className="code text-ink-500">{shortId(approval.id)}</span>
        </div>
        {amount && <span className="num shrink-0 text-[20px] font-medium leading-7">{amount}</span>}
      </div>
      <p className="text-sm text-ink-900">{approval.summary}.</p>
      <div className="border-t border-sand-200 pt-3">
        <p className="text-xs font-medium text-ink-500">Why it was asked for</p>
        <p className="mt-1 text-sm text-ink-700">{approval.reason}</p>
      </div>
      {approval.evidence.length > 0 && (
        <dl className="divide-y divide-sand-200 border-t border-sand-200 text-[13px]">
          {approval.evidence.map((e, i) => (
            <div key={i} className="grid gap-x-4 gap-y-0.5 py-2 sm:grid-cols-[7rem_minmax(0,1fr)]">
              <dt className="text-ink-500">{e.label}</dt><dd className="min-w-0 break-words text-ink-700">{e.detail}</dd>
            </div>
          ))}
        </dl>
      )}
    </div>
  );
}

function TwoPersonApproval({ approval, approver, code, setCode, note, setNote, busy, error, onDecide }: {
  approval: Approval; approver: string; code: string; setCode: (c: string) => void; note: string; setNote: (n: string) => void;
  busy: string; error: string; onDecide: (approve: boolean) => void;
}) {
  const status = approvalStatus(approval.state);
  const ready = code.length === 6;
  return (
    <section aria-labelledby="two-person" className="flex min-w-0 flex-col gap-[18px] rounded-panel border border-sand-200 bg-white p-5 sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id="two-person" className="text-[15px] font-semibold">Two-person approval</h2>
        <StatusChip tone={status.tone}>{status.label}</StatusChip>
      </div>
      <RequestCard approval={approval} />
      <ol className="flex flex-col gap-3 text-[13px]">
        <li className="flex items-center gap-2.5">
          <Check />
          <span className="min-w-0 flex-1"><span className="font-semibold">{approval.requested_by}</span> requested · Operations{approval.mine ? " (you)" : ""}</span>
          <span className="shrink-0 text-ink-500">{shortWhen(approval.requested_at)}</span>
        </li>
        <li className="flex items-center gap-2.5">
          <span aria-hidden="true" className="h-6 w-6 shrink-0 rounded-full border-[1.5px] border-dashed border-sand-300" />
          <span className="min-w-0 flex-1">
            {approval.mine
              ? <><span className="font-semibold">Someone else in operations</span> approves with a one-time code</>
              : <><span className="font-semibold">{approver}</span> approves with a one-time code (you)</>}
          </span>
        </li>
      </ol>
      {approval.mine ? (
        <div className="rounded-control bg-fill px-4 py-3.5">
          <p className="text-sm font-medium">You asked for this change, so someone else has to approve it.</p>
          <p className="mt-1 text-[13px] text-ink-500">
            In this demo, <Link href="/#journeys" className="font-semibold text-green-600 underline-offset-4 hover:underline">switch to another operations person</Link> to approve it.
          </p>
        </div>
      ) : (
        <>
          <Field label="Your note" hint="Saved with the decision. Optional.">
            <textarea className={`${inputClass} min-h-16`} value={note} maxLength={500} onChange={(e) => setNote(e.target.value)} />
          </Field>
          <div className="space-y-2">
            <span className="block text-[13px] font-medium">Code from your authenticator</span>
            <div className="flex flex-wrap items-center gap-2">
              <CodeField value={code} onChange={setCode} />
              <Button busy={busy === "approve"} disabled={!ready || Boolean(busy)} onClick={() => onDecide(true)}>Approve</Button>
            </div>
            {!ready && <p className="text-xs text-ink-500">Approve and Reject open once all six digits are in.</p>}
          </div>
          <DemoAuthenticator onUse={setCode} />
          {error && <Notice tone="error">{error}</Notice>}
          <div className="flex flex-wrap items-center gap-3 border-t border-sand-100 pt-4">
            <Button variant="danger" busy={busy === "reject"} disabled={!ready || Boolean(busy)} onClick={() => onDecide(false)}>Reject the request</Button>
            <span className="text-xs text-ink-500">Rejecting changes nothing and is recorded with your note.</span>
          </div>
        </>
      )}
    </section>
  );
}

export default function ApprovalsPage() {
  const { me } = useSession();
  const [rows, setRows] = useState<Approval[] | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [code, setCode] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [done, setDone] = useState<Approval | null>(null);

  const load = useCallback(async () => {
    const all = await api<Approval[]>("/ops/approvals");
    setRows(all);
    const pending = all.filter((a) => a.state === "pending");
    setSelected((s) => (s && pending.some((a) => a.id === s) ? s : pending[0]?.id ?? null));
  }, []);
  useEffect(() => {
    load().catch((e) => setError(msg(e, "Atrium could not load the approvals. Try again.")));
  }, [load]);

  const pending = rows?.filter((a) => a.state === "pending") ?? [];
  const decided = rows?.filter((a) => a.state !== "pending") ?? [];
  const approval = pending.find((a) => a.id === selected) ?? null;

  async function decide(approve: boolean) {
    if (!approval) return;
    setBusy(approve ? "approve" : "reject");
    setError("");
    try {
      setDone(await api<Approval>(`/ops/approvals/${approval.id}/decide`, { method: "POST", body: JSON.stringify({ approve, code, note }) }));
      setCode("");
      setNote("");
      await load();
    } catch (e) {
      setError(msg(e, "Atrium could not record the decision. Try again."));
    } finally {
      setBusy("");
    }
  }

  const header = (
    <PageHeader title="Approvals"
      description="Publishing prices, matching a payment by hand and reversing a posting each need a second person. Read the request, then approve or reject it with the six-digit code from your authenticator." />
  );
  if (!rows) return <>{header}{error ? <Notice tone="error">{error}</Notice> : <Loading label="Loading the approvals" />}</>;
  return (
    <>
      {header}
      {done && <div className="mb-6"><Notice tone="success" title={done.state === "approved" ? "Approved" : "Rejected"}>{done.summary}. {resultWords(done)}</Notice></div>}
      <div className="space-y-12">
        {pending.length === 0 ? <EmptyState title="Nothing is waiting">When someone in operations asks for a fact-changing action, it waits here for a second person.</EmptyState> : (
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-[320px_minmax(0,1fr)] lg:items-start xl:grid-cols-[360px_minmax(0,640px)]">
            <section aria-labelledby="waiting-title" className="min-w-0">
              <h2 id="waiting-title" className="mb-3 px-1 text-[13px] font-medium text-ink-500">{pending.length} waiting for a second person</h2>
              <ul className="space-y-2">
                {pending.map((a) => {
                  const on = a.id === selected;
                  return (
                    <li key={a.id}>
                      <button type="button" aria-current={on} onClick={() => { setSelected(a.id); setDone(null); setError(""); setCode(""); }}
                        className={`block w-full rounded-panel border px-4 py-3.5 text-left transition-colors ${on ? "border-green-300 bg-green-50" : "border-sand-200 bg-white hover:bg-fill"}`}>
                        <span className="flex items-center justify-between gap-2">
                          <span className="text-[13px] font-semibold">{ACTION_COPY[a.action]}</span>
                          <span className="code text-[11px]! text-ink-500">{shortId(a.id)}</span>
                        </span>
                        <span className="mt-1 line-clamp-2 block text-sm text-ink-900">{a.summary}</span>
                        <span className="mt-1 block text-xs text-ink-500">Asked by {a.requested_by}{a.mine ? " (you)" : ""}, {formatDate(a.requested_at)}</span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            </section>
            {approval && (
              <TwoPersonApproval approval={approval} approver={me?.full_name ?? me?.email ?? "You"} code={code} setCode={setCode}
                note={note} setNote={setNote} busy={busy} error={error} onDecide={decide} />
            )}
          </div>
        )}
        {decided.length > 0 && (
          <TableCard title="Decided" description="Every request a second person approved or rejected.">
            <div className={tbl.wrap}>
              <table className={`${tbl.table} min-w-[720px]`}>
                <thead className={tbl.head}><tr><th className={tbl.th}>Request</th><th className={tbl.th}>Kind</th><th className={tbl.th}>Asked by</th><th className={tbl.th}>Decided by</th><th className={tbl.th}>Outcome</th></tr></thead>
                <tbody>
                  {decided.map((a) => {
                    const status = approvalStatus(a.state);
                    return (
                      <tr key={a.id} className={`${tbl.row} align-top`}>
                        <td className={tbl.td}><span className={tbl.id}>{shortId(a.id)}</span><span className="mt-0.5 block font-medium">{a.summary}</span></td>
                        <td className={`${tbl.td} whitespace-nowrap text-ink-700`}>{ACTION_COPY[a.action]}</td>
                        <td className={`${tbl.td} whitespace-nowrap`}>{a.requested_by}<span className="block text-xs text-ink-500">{formatDate(a.requested_at)}</span></td>
                        <td className={`${tbl.td} whitespace-nowrap`}>{a.decided_by}{a.decided_at && <span className="block text-xs text-ink-500">{formatDate(a.decided_at)}</span>}</td>
                        <td className={tbl.td}>
                          <StatusChip tone={status.tone}>{status.label}</StatusChip>
                          <span className="mt-1 block text-xs text-ink-500">{resultWords(a)}{a.decision_note ? ` “${a.decision_note}”` : ""}</span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </TableCard>
        )}
      </div>
    </>
  );
}
