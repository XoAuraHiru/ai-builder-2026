"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { api, ApiError } from "@/lib/api";
import { formatDate } from "@/lib/format";
import { useSession } from "@/lib/session-context";
import {
  ACTION_COPY, approvalAmount, approvalStatus, confirmPause, resultWords, shortId, shortWhen, type Approval,
} from "@/lib/operations";
import { EASE } from "@/components/motion";
import { Skeleton, SkeletonText } from "@/components/skeleton";
import { CodeField, DemoAuthenticator } from "@/components/step-up";
import { Button, EmptyState, Field, inputClass, Notice, PageHeader } from "@/components/ui";
import { CheckDot, Confirmed, ConfirmedNotice, CrossDot, QueueItem, StatusChip, TableCard, tbl } from "../_parts";
import { LoadingRegion, TableCardSkeleton } from "../_skeletons";

const msg = (e: unknown, fallback: string) => (e instanceof ApiError ? e.message : fallback);
const wait = (ms: number) => new Promise<void>((done) => { window.setTimeout(done, ms); });

/** Approvals while they load: the waiting requests beside the two-person panel, then the decided table. */
function ApprovalsSkeleton() {
  return (
    <LoadingRegion label="Loading the approvals">
      <div className="space-y-12">
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-[320px_minmax(0,1fr)] lg:items-start xl:grid-cols-[360px_minmax(0,640px)]">
          <div className="min-w-0">
            <Skeleton className="mx-1 mb-3 h-3.5 w-48" />
            <div className="space-y-2">
              {[0, 1, 2].map((i) => (
                <div key={i} className="flex flex-col gap-2 rounded-panel border border-sand-200 bg-white px-4 py-3.5">
                  <span className="flex justify-between gap-2"><Skeleton className="h-3.5 w-28" /><Skeleton className="h-3 w-16" /></span>
                  <SkeletonText lines={2} />
                  <Skeleton className="h-3 w-2/5" />
                </div>
              ))}
            </div>
          </div>
          <div className="flex min-w-0 flex-col gap-[18px] rounded-panel border border-sand-200 bg-white p-5 sm:p-6">
            <span className="flex items-center justify-between gap-3"><Skeleton className="h-4 w-40" /><Skeleton className="h-[26px] w-44 rounded-full" /></span>
            <div className="flex flex-col gap-3 rounded-control bg-fill px-4 py-3.5">
              <span className="flex justify-between gap-3"><Skeleton className="h-3.5 w-32" /><Skeleton className="h-6 w-24 rounded-[8px]" /></span>
              <SkeletonText lines={2} />
              <Skeleton className="h-3 w-1/3" />
              <Skeleton className="h-3.5 w-4/5" />
            </div>
            {[0, 1].map((i) => (
              <span key={i} className="flex items-center gap-2.5"><Skeleton className="h-6 w-6 shrink-0 rounded-full" /><Skeleton className="h-3.5 w-3/5" /></span>
            ))}
            <span className="flex flex-col gap-1.5"><Skeleton className="h-3.5 w-24" /><Skeleton className="h-16 w-full rounded-control" /></span>
            <span className="flex flex-wrap items-center gap-1.5">
              {Array.from({ length: 6 }, (_, i) => <Skeleton key={i} className="h-11 w-10 rounded-[10px]" />)}
              <Skeleton className="ml-0.5 h-11 w-28 rounded-full" />
            </span>
          </div>
        </div>
        <TableCardSkeleton rows={4} widths={[3, 1, 1, 1, 2]} chip />
      </div>
    </LoadingRegion>
  );
}

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

/** The approver's step: dashed while it waits, then a check (or a cross) drawing itself as the decision goes through. */
function ApproverStep({ approval, approver }: { approval: Approval; approver: string }) {
  const decided = approval.state !== "pending";
  return (
    <li className="flex items-center gap-2.5">
      <AnimatePresence mode="wait" initial={false}>
        {decided ? (
          <motion.span key="decided" className="flex" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.12 }}>
            {approval.state === "approved" ? <CheckDot /> : <CrossDot />}
          </motion.span>
        ) : (
          <motion.span key="waiting" aria-hidden="true" exit={{ opacity: 0, scale: 0.8 }} transition={{ duration: 0.14, ease: EASE }}
            className="h-6 w-6 shrink-0 rounded-full border-[1.5px] border-dashed border-sand-300" />
        )}
      </AnimatePresence>
      <span className="min-w-0 flex-1">
        {decided
          ? <><span className="font-semibold">{approval.decided_by ?? approver}</span> {approval.state === "approved" ? "approved" : "rejected"} with a one-time code (you)</>
          : approval.mine
            ? <><span className="font-semibold">Someone else in operations</span> approves with a one-time code</>
            : <><span className="font-semibold">{approver}</span> approves with a one-time code (you)</>}
      </span>
      {decided && approval.decided_at && <span className="shrink-0 text-ink-500">{shortWhen(approval.decided_at)}</span>}
    </li>
  );
}

function TwoPersonApproval({ approval, approver, code, setCode, note, setNote, busy, error, onDecide }: {
  approval: Approval; approver: string; code: string; setCode: (c: string) => void; note: string; setNote: (n: string) => void;
  busy: string; error: string; onDecide: (approve: boolean) => void;
}) {
  const status = approvalStatus(approval.state);
  const ready = code.length === 6;
  const decided = approval.state !== "pending";
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
        <ApproverStep approval={approval} approver={approver} />
      </ol>
      {decided ? (
        // The decision went through: it confirms here, then the request leaves the waiting list.
        <div className="flex min-h-11 items-center border-t border-sand-100 pt-4">
          <Confirmed tone={approval.state === "approved" ? "gain" : "neutral"}>
            {approval.state === "approved" ? `Approved. ${resultWords(approval)}` : "Rejected: nothing changed, and your note is kept."}
          </Confirmed>
        </div>
      ) : approval.mine ? (
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
  const [justDecided, setJustDecided] = useState<Approval | null>(null);  // shown in the panel while its check draws
  const reduce = useReducedMotion();

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
  const approval = justDecided ?? pending.find((a) => a.id === selected) ?? null;

  async function decide(approve: boolean) {
    if (!approval) return;
    setBusy(approve ? "approve" : "reject");
    setError("");
    try {
      const out = await api<Approval>(`/ops/approvals/${approval.id}/decide`, { method: "POST", body: JSON.stringify({ approve, code, note }) });
      setCode("");
      setNote("");
      setJustDecided(out);  // the approver's step checks and the panel confirms, then the request leaves the list
      await wait(confirmPause(reduce) + (reduce ? 0 : 280));
      setDone(out);
      await load();
    } catch (e) {
      setError(msg(e, "Atrium could not record the decision. Try again."));
    } finally {
      setBusy("");
      setJustDecided(null);
    }
  }

  const header = (
    <PageHeader title="Approvals"
      description="Publishing prices, matching a payment by hand and reversing a posting each need a second person. Read the request, then approve or reject it with the six-digit code from your authenticator." />
  );
  if (!rows) return <>{header}{error ? <Notice tone="error">{error}</Notice> : <ApprovalsSkeleton />}</>;
  return (
    <>
      {header}
      {done && (
        <div className="mb-6">
          <ConfirmedNotice tone={done.state === "approved" ? "gain" : "neutral"} title={done.state === "approved" ? "Approved" : "Rejected"}>
            {done.summary}. {resultWords(done)}
          </ConfirmedNotice>
        </div>
      )}
      <div className="space-y-12">
        {pending.length === 0 && !justDecided ? <EmptyState title="Nothing is waiting">When someone in operations asks for a fact-changing action, it waits here for a second person.</EmptyState> : (
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-[320px_minmax(0,1fr)] lg:items-start xl:grid-cols-[360px_minmax(0,640px)]">
            <section aria-labelledby="waiting-title" className="min-w-0">
              <h2 id="waiting-title" className="mb-3 px-1 text-[13px] font-medium text-ink-500">{pending.length} waiting for a second person</h2>
              {/* The requests arrive in order; a decided one fades and closes out of the list. */}
              <ul className="-mb-2">
                <AnimatePresence>
                  {pending.map((a, i) => {
                    const on = a.id === selected;
                    return (
                      <QueueItem key={a.id} index={i} gap="pb-2" as="li">
                          <button type="button" aria-current={on} disabled={Boolean(justDecided)}
                            onClick={() => { setSelected(a.id); setDone(null); setError(""); setCode(""); }}
                            className={`block w-full rounded-panel border px-4 py-3.5 text-left transition-colors ${on ? "border-green-300 bg-green-50" : "border-sand-200 bg-white hover:bg-fill"}`}>
                            <span className="flex items-center justify-between gap-2">
                              <span className="text-[13px] font-semibold">{ACTION_COPY[a.action]}</span>
                              <span className="code text-[11px] text-ink-500">{shortId(a.id)}</span>
                            </span>
                            <span className="mt-1 line-clamp-2 block text-sm text-ink-900">{a.summary}</span>
                            <span className="mt-1 block text-xs text-ink-500">Asked by {a.requested_by}{a.mine ? " (you)" : ""}, {formatDate(a.requested_at)}</span>
                          </button>
                      </QueueItem>
                    );
                  })}
                </AnimatePresence>
              </ul>
            </section>
            {approval && (
              // A newly chosen request eases into the panel.
              <motion.div key={approval.id} className="min-w-0" initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.26, ease: EASE }}>
                <TwoPersonApproval approval={approval} approver={me?.full_name ?? me?.email ?? "You"} code={code} setCode={setCode}
                  note={note} setNote={setNote} busy={busy} error={error} onDecide={decide} />
              </motion.div>
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
