"use client";

import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { formatDate } from "@/lib/format";
import { ACTION_COPY, resultWords, type Approval } from "@/lib/operations";
import { CodeField, DemoAuthenticator } from "@/components/step-up";
import { Badge, Button, EmptyState, Field, inputClass, Loading, Notice, PageHeader, Panel, Section, tableStyles as t } from "@/components/ui";

const msg = (e: unknown, fallback: string) => (e instanceof ApiError ? e.message : fallback);

export default function ApprovalsPage() {
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
      <div className="space-y-10">
        {pending.length === 0 ? <EmptyState title="Nothing is waiting">When someone in operations asks for a fact-changing action, it waits here for a second person.</EmptyState> : (
          <div className="grid gap-8 lg:grid-cols-[300px_minmax(0,1fr)]">
            <ul className="h-fit divide-y divide-line border-y border-line">
              {pending.map((a) => (
                <li key={a.id}>
                  <button type="button" aria-current={a.id === selected} onClick={() => { setSelected(a.id); setDone(null); setError(""); }}
                    className={`block w-full px-2 py-3 text-left ${a.id === selected ? "bg-surface" : "hover:bg-surface/60"}`}>
                    <Badge>{ACTION_COPY[a.action]}</Badge>
                    <span className="mt-1 block text-sm font-medium">{a.summary}</span>
                    <span className="block text-xs text-muted">Asked by {a.requested_by}{a.mine ? " (you)" : ""}, {formatDate(a.requested_at)}</span>
                  </button>
                </li>
              ))}
            </ul>
            {approval && (
              <div className="min-w-0 space-y-6">
                <Panel className="space-y-4 p-5">
                  <div>
                    <Badge>{ACTION_COPY[approval.action]}</Badge>
                    <h2 className="mt-2 text-[17px] font-semibold">{approval.summary}</h2>
                    <p className="text-sm text-ink-2">Asked by {approval.requested_by} on {formatDate(approval.requested_at)}.</p>
                  </div>
                  <blockquote className="border-l-2 border-line-strong pl-4 text-[15px]">{approval.reason}</blockquote>
                  <dl className="divide-y divide-line border-y border-line text-sm">
                    {approval.evidence.map((e, i) => (
                      <div key={i} className="grid gap-1 py-2 sm:grid-cols-[9rem_minmax(0,1fr)]"><dt className="text-muted">{e.label}</dt><dd>{e.detail}</dd></div>
                    ))}
                  </dl>
                </Panel>
                {approval.mine ? (
                  <Notice tone="caution" title="You asked for this">A different person approves it. In this demo, choose another operations persona on the sign-in page.</Notice>
                ) : (
                  <section className="space-y-4">
                    <Field label="Your note" hint="Saved with the decision.">
                      <textarea className={`${inputClass} min-h-16`} value={note} maxLength={500} onChange={(e) => setNote(e.target.value)} />
                    </Field>
                    <div className="flex flex-wrap items-end gap-4">
                      <Field label="Code from your authenticator"><CodeField value={code} onChange={setCode} /></Field>
                      <DemoAuthenticator onUse={setCode} />
                    </div>
                    {error && <Notice tone="error">{error}</Notice>}
                    <div className="flex flex-wrap gap-2">
                      <Button busy={busy === "approve"} disabled={code.length !== 6 || Boolean(busy)} onClick={() => decide(true)}>Approve</Button>
                      <Button variant="danger" busy={busy === "reject"} disabled={code.length !== 6 || Boolean(busy)} onClick={() => decide(false)}>Reject</Button>
                    </div>
                  </section>
                )}
              </div>
            )}
          </div>
        )}
        {decided.length > 0 && (
          <Section title="Decided">
            <div className={t.wrap}>
              <table className={t.table}>
                <thead className={t.head}><tr><th className={t.th}>Request</th><th className={t.th}>Asked by</th><th className={t.th}>Decided by</th><th className={t.th}>Outcome</th></tr></thead>
                <tbody>
                  {decided.map((a) => (
                    <tr key={a.id} className={t.row}>
                      <td className={t.td}><span className="font-medium">{a.summary}</span><span className="block text-xs text-muted">{ACTION_COPY[a.action]}</span></td>
                      <td className={t.td}>{a.requested_by}</td>
                      <td className={t.td}>{a.decided_by}{a.decided_at && <span className="block text-xs text-muted">{formatDate(a.decided_at)}</span>}</td>
                      <td className={t.td}>{resultWords(a)}{a.decision_note && <span className="block text-xs text-muted">{a.decision_note}</span>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Section>
        )}
      </div>
    </>
  );
}
