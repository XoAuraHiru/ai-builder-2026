"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { api, ApiError, apiDownload, apiUpload } from "@/lib/api";
import { formatDate, formatUsd } from "@/lib/format";
import {
  confidenceWords, matchTotals, proposerLabel, TIER_COPY,
  type Approval, type Match, type ReconcileResult, type Reconciliation, type Statement,
} from "@/lib/operations";
import { AiProse } from "@/components/ai-prose";
import { Badge, Button, EmptyState, Field, inputClass, Loading, Notice, PageHeader, Section, tableStyles as t } from "@/components/ui";

const msg = (e: unknown, fallback: string) => (e instanceof ApiError ? e.message : fallback);
const UPLOAD = "inline-flex cursor-pointer items-center justify-center gap-2 rounded-control border border-line-strong bg-surface px-3.5 py-2 text-sm font-medium text-ink transition-colors hover:border-ink focus-within:ring-2 focus-within:ring-ink";

function saveBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function Proposal({ match, busy, onDecide }: { match: Match; busy: string; onDecide: (id: string, action: "accept" | "reject") => void }) {
  return (
    <li className="py-5">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-medium">{TIER_COPY[match.tier]}</span>
        <Badge tone={match.confidence >= 0.8 ? "gain" : "caution"}>
          <span className="num">{confidenceWords(match.confidence)}, {Math.round(match.confidence * 100)}%</span>
        </Badge>
        <span className="text-xs text-muted">Proposed by {proposerLabel(match.proposed_by)}</span>
      </div>
      <div className="mt-3 grid gap-4 md:grid-cols-2">
        <div>
          <p className="text-xs text-muted">On the statement</p>
          <ul className="mt-1 space-y-1 text-sm">
            {match.lines.map((l) => (
              <li key={l.id}><span className="num font-medium">{formatUsd(l.amount)}</span> <span className="text-ink-2">{formatDate(l.value_date)}, {l.description}</span></li>
            ))}
          </ul>
        </div>
        <div>
          <p className="text-xs text-muted">Waiting for money</p>
          <ul className="mt-1 space-y-1 text-sm">
            {match.subscriptions.map((s) => (
              <li key={s.instruction_id}><span className="num font-medium">{formatUsd(s.amount)}</span> <span className="text-ink-2">{s.reference}, {s.holder}, into {s.fund_name}</span></li>
            ))}
          </ul>
        </div>
      </div>
      <ul className="mt-3 list-disc space-y-0.5 pl-5 text-sm text-ink-2">{match.evidence.map((e, i) => <li key={i}>{e}</li>)}</ul>
      <div className="mt-4 flex flex-wrap items-center gap-2">
        {match.state === "awaiting_approval" ? (
          <p className="text-sm text-ink-2">Matched by hand; waiting for a second person in <Link href="/operations/approvals" className="underline underline-offset-4">Approvals</Link>.</p>
        ) : (
          <>
            <Button busy={busy === `accept:${match.id}`} disabled={Boolean(busy)} onClick={() => onDecide(match.id, "accept")}>Accept the match</Button>
            <Button variant="secondary" busy={busy === `reject:${match.id}`} disabled={Boolean(busy)} onClick={() => onDecide(match.id, "reject")}>Reject</Button>
          </>
        )}
      </div>
    </li>
  );
}

export default function ReconciliationPage() {
  const [data, setData] = useState<Reconciliation | null>(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [read, setRead] = useState<Statement | null>(null);
  const [found, setFound] = useState<ReconcileResult | null>(null);
  const [lineIds, setLineIds] = useState<string[]>([]);
  const [subIds, setSubIds] = useState<string[]>([]);
  const [reason, setReason] = useState("");
  const [asked, setAsked] = useState<Approval | null>(null);
  const file = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => setData(await api<Reconciliation>("/ops/reconciliation")), []);
  useEffect(() => {
    load().catch((e) => setError(msg(e, "Atrium could not load reconciliation. Try again.")));
  }, [load]);

  async function act(key: string, fallback: string, work: () => Promise<void>) {
    setBusy(key);
    setError("");
    try {
      await work();
      await load();
    } catch (e) {
      setError(msg(e, fallback));
    } finally {
      setBusy("");
    }
  }

  const fmt = data?.reads_pdf ? "pdf" : "csv";
  const readSample = () => act("sample", "Atrium could not read the sample statement. Try again.", async () => {
    setRead(await api<Statement>("/ops/statements/sample", { method: "POST", body: JSON.stringify({ fmt }) }));
    setFound(null);
  });
  const upload = (f: File) => act("upload", "Atrium could not read that statement.", async () => {
    const form = new FormData();
    form.append("file", f);
    try {
      setRead(await apiUpload<Statement>("/ops/statements", form));
      setFound(null);
    } finally {
      if (file.current) file.current.value = "";
    }
  });
  const findMatches = () => act("find", "Atrium could not look for matches. Try again.", async () => {
    setFound(await api<ReconcileResult>("/ops/reconcile", { method: "POST" }));
  });
  const decide = (id: string, action: "accept" | "reject") => act(`${action}:${id}`, "Atrium could not record the decision. Try again.", async () => {
    await api<Match>(`/ops/matches/${id}/${action}`, { method: "POST", body: JSON.stringify({}) });
  });
  const download = (kind: "pdf" | "csv") => act(`download:${kind}`, "Atrium could not write the sample statement.", async () => {
    saveBlob(await apiDownload(`/ops/statements/sample?fmt=${kind}`), `atrium-sample-statement.${kind}`);
  });
  const askManual = () => act("manual", "Atrium could not ask for the match.", async () => {
    setAsked(await api<Approval>("/ops/matches/manual", { method: "POST", body: JSON.stringify({ line_ids: lineIds, instruction_ids: subIds, reason }) }));
    setLineIds([]);
    setSubIds([]);
    setReason("");
  });
  const addDemoPayments = () => act("demo", "Atrium could not add the demo payments. Try again.", async () => {
    await api<{ added: number }>("/ops/demo/payments", { method: "POST" });
  });
  const toggle = (list: string[], set: (v: string[]) => void, id: string) => set(list.includes(id) ? list.filter((x) => x !== id) : [...list, id]);

  const header = (
    <PageHeader title="Reconciliation"
      description="Match the money that reached the client money account with the subscriptions waiting for it. Rules take the clear cases, an agent proposes the rest, and a person decides each one."
      actions={
        <>
          <Button busy={busy === "sample"} disabled={Boolean(busy) || !data} onClick={readSample}>Read the sample statement</Button>
          <label className={UPLOAD}>
            Upload a statement
            <input ref={file} type="file" accept=".pdf,.csv,application/pdf,text/csv" className="sr-only" disabled={Boolean(busy)}
              onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])} />
          </label>
        </>
      } />
  );
  if (!data) return <>{header}{error ? <Notice tone="error">{error}</Notice> : <Loading label="Loading reconciliation" />}</>;
  const chosenLines = data.unmatched.filter((l) => lineIds.includes(l.id));
  const chosenSubs = data.receipts.filter((r) => subIds.includes(r.instruction_id));
  const totals = matchTotals(chosenLines, chosenSubs);
  const counted = read ? Object.values(read.counts).reduce((a, b) => a + b, 0) : 0;
  return (
    <>
      {header}
      <p className="-mt-4 mb-6 text-sm text-muted">
        The sample statement is written for the payments Atrium is waiting for, with the imperfections real statements have
        {data.reads_pdf ? "; as a PDF it is read by Document AI" : "; Document AI is not configured here, so it is read as a CSV"}.
        Download it as a <button type="button" className="underline underline-offset-4" onClick={() => download("pdf")}>PDF</button> or
        a <button type="button" className="underline underline-offset-4" onClick={() => download("csv")}>CSV</button>.
      </p>
      <div className="space-y-10">
        {(error || read) && (
          <div className="space-y-3">
            {error && <Notice tone="error">{error}</Notice>}
            {read && (
              <Notice tone="success" title={`Read ${counted} lines from ${read.filename}`}>
                {read.counts.unmatched} deposit{read.counts.unmatched === 1 ? "" : "s"} to match; {read.counts.ignored} ignored (interest and fees).
                {read.source === "documentai" ? " Read by Document AI's bank statement parser." : ""} {read.notes.join(" ")}
              </Notice>
            )}
          </div>
        )}
        <Section title="Find matches"
          description={`${data.unmatched.length} deposit${data.unmatched.length === 1 ? " waits" : "s wait"} to be matched with ${data.receipts.length} subscription${data.receipts.length === 1 ? "" : "s"} waiting for money.`}
          actions={<Button busy={busy === "find"} disabled={Boolean(busy) || data.unmatched.length === 0 || data.receipts.length === 0} onClick={findMatches}>Find matches</Button>}>
          {found ? (
            <div className="space-y-3">
              <p className="text-sm text-ink-2">
                The rules proposed {found.rules}; {found.used_agent ? `the agent proposed ${found.agent}` : `the scorer proposed ${found.scorer}`}. Each proposal below needs your decision.
              </p>
              {found.used_agent
                ? <AiProse caption="Written by the reconciliation agent (Gemini Flash) after it scored and checked each candidate."><p>{found.summary}</p></AiProse>
                : <p className="text-sm text-ink-2">{found.summary}</p>}
            </div>
          ) : <p className="text-sm text-muted">Rules match a reference and an amount exactly; the agent then works the typos, missing references and split payments.</p>}
          {data.demo && data.receipts.length === 0 && (
            <div className="mt-4">
              <Notice title="No subscription is waiting for money"
                action={<Button variant="secondary" busy={busy === "demo"} disabled={Boolean(busy)} onClick={addDemoPayments}>Add demo payments</Button>}>
                Earlier visitors matched them all. Add a new set of client subscriptions; the sample statement is then written for them.
              </Notice>
            </div>
          )}
        </Section>
        <Section title="Proposals to decide">
          {data.proposals.length === 0
            ? <EmptyState title="Nothing to decide">Read a statement, then find matches.</EmptyState>
            : <ul className="divide-y divide-line border-y border-line">{data.proposals.map((m) => <Proposal key={m.id} match={m} busy={busy} onDecide={decide} />)}</ul>}
        </Section>
        <Section title="Match by hand" description="When neither the rules nor the agent can pair a payment, choose the lines and the subscriptions yourself. A second person approves the match.">
          <div className="grid gap-6 lg:grid-cols-2">
            <fieldset>
              <legend className="text-sm font-medium">Deposits on the statement</legend>
              {data.unmatched.length === 0 ? <p className="mt-2 text-sm text-muted">Every deposit is matched or proposed.</p> : (
                <ul className="mt-2 divide-y divide-line border-y border-line">
                  {data.unmatched.map((l) => (
                    <li key={l.id}>
                      <label className="flex cursor-pointer items-start gap-3 py-2.5 text-sm">
                        <input type="checkbox" className="mt-1" checked={lineIds.includes(l.id)} onChange={() => toggle(lineIds, setLineIds, l.id)} />
                        <span className="min-w-0">
                          <span className="num font-medium">{formatUsd(l.amount)}</span> <span className="text-muted">{formatDate(l.value_date)}</span>
                          <span className="block text-ink-2">{l.description}</span>
                        </span>
                      </label>
                    </li>
                  ))}
                </ul>
              )}
            </fieldset>
            <fieldset>
              <legend className="text-sm font-medium">Subscriptions waiting for money</legend>
              {data.receipts.length === 0 ? <p className="mt-2 text-sm text-muted">No subscription is waiting for money.</p> : (
                <ul className="mt-2 divide-y divide-line border-y border-line">
                  {data.receipts.map((r) => (
                    <li key={r.instruction_id}>
                      <label className={`flex items-start gap-3 py-2.5 text-sm ${r.in_proposal ? "opacity-60" : "cursor-pointer"}`}>
                        <input type="checkbox" className="mt-1" disabled={r.in_proposal} checked={subIds.includes(r.instruction_id)} onChange={() => toggle(subIds, setSubIds, r.instruction_id)} />
                        <span className="min-w-0">
                          <span className="num font-medium">{formatUsd(r.amount)}</span> <span className="num text-muted">{r.reference}</span>
                          <span className="block text-ink-2">{r.holder}, into {r.fund_name}, asked {formatDate(r.requested_on)}{r.in_proposal ? "; in a proposal" : ""}</span>
                        </span>
                      </label>
                    </li>
                  ))}
                </ul>
              )}
            </fieldset>
          </div>
          {(lineIds.length > 0 || subIds.length > 0) && (
            <div className="mt-5 max-w-xl space-y-3">
              <p className="text-sm">
                The lines total <span className="num font-medium">{formatUsd(totals.paid)}</span> and the subscriptions <span className="num font-medium">{formatUsd(totals.due)}</span>.{" "}
                <span className={totals.agrees ? "text-gain" : "text-caution"}>{totals.agrees ? "They agree." : "They do not agree yet."}</span>
              </p>
              <Field label="Why these belong together" hint="The approver reads this before deciding.">
                <textarea className={`${inputClass} min-h-20`} value={reason} maxLength={500} onChange={(e) => setReason(e.target.value)}
                  placeholder="For example: The client confirmed by phone that this check pays for their October subscription." />
              </Field>
              <Button busy={busy === "manual"} disabled={!lineIds.length || !subIds.length || !reason.trim()} onClick={askManual}>Ask for approval</Button>
            </div>
          )}
          {asked && <div className="mt-5"><Notice tone="success" title="Sent for approval">{asked.summary}.</Notice></div>}
        </Section>
        {data.recent.length > 0 && (
          <Section title="Recently decided">
            <ul className="divide-y divide-line border-y border-line text-sm">
              {data.recent.map((m) => (
                <li key={m.id} className="flex flex-wrap items-baseline justify-between gap-2 py-2.5">
                  <span className="min-w-0">
                    {m.subscriptions.map((s) => `${s.reference} for ${s.holder}`).join(", ")}
                    <span className="block text-xs text-muted">{TIER_COPY[m.tier]}; {m.state} by {m.decided_by ?? "operations"}{m.decided_at ? ` on ${formatDate(m.decided_at)}` : ""}</span>
                  </span>
                  <Badge tone={m.state === "accepted" ? "gain" : "neutral"}>{m.state === "accepted" ? "Accepted" : "Rejected"}</Badge>
                </li>
              ))}
            </ul>
          </Section>
        )}
        {data.statements.length > 0 && (
          <Section title="Statements">
            <div className={t.wrap}>
              <table className={t.table}>
                <thead className={t.head}><tr><th className={t.th}>File</th><th className={t.th}>Read by</th><th className={t.th}>Uploaded</th><th className={`${t.th} text-right`}>To match</th><th className={`${t.th} text-right`}>Matched</th></tr></thead>
                <tbody>
                  {data.statements.map((s) => (
                    <tr key={s.id} className={t.row}>
                      <td className={t.td}>{s.filename}{s.bank_name && <span className="block text-xs text-muted">{s.bank_name}{s.account_last4 ? `, account ending ${s.account_last4}` : ""}</span>}</td>
                      <td className={t.td}>{s.source === "documentai" ? "Document AI" : "CSV"}</td>
                      <td className={t.td}>{formatDate(s.uploaded_at)}<span className="block text-xs text-muted">{s.uploaded_by}</span></td>
                      <td className={`${t.td} num text-right`}>{s.counts.unmatched + s.counts.proposed}</td>
                      <td className={`${t.td} num text-right`}>{s.counts.matched}</td>
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
