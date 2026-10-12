"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { api, ApiError, apiDownload, apiUpload } from "@/lib/api";
import { formatDate, formatUsd } from "@/lib/format";
import {
  acceptMany, balanceNote, confidenceWords, diffMarks, matchTotals, meterCells, proposerLabel, splitProposals, statementFlow, TIER_COPY,
  type Approval, type Match, type ReconcileResult, type Reconciliation, type Statement,
} from "@/lib/operations";
import { AiProse } from "@/components/ai-prose";
import { Badge, Button, EmptyState, Field, inputClass, Loading, Notice, PageHeader, Panel, Section, tableStyles as t } from "@/components/ui";

const msg = (e: unknown, fallback: string) => (e instanceof ApiError ? e.message : fallback);
const UPLOAD = "inline-flex min-h-11 cursor-pointer items-center justify-center gap-2 rounded-full border border-line-strong bg-surface px-5 text-sm font-semibold text-ink transition-colors hover:border-ink focus-within:ring-2 focus-within:ring-ink";

function saveBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function Chevron() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true" className="shrink-0 text-muted transition-transform group-open:rotate-180">
      <path d="M3 5.5 7 9l4-3.5" fill="none" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  );
}

function Meter({ confidence }: { confidence: number }) {
  const filled = meterCells(confidence);
  return (
    <span className="flex items-center gap-2.5 text-[13px] text-ink-2">
      <span className="flex gap-[3px]" aria-hidden="true">
        {[0, 1, 2, 3, 4].map((i) => <span key={i} className={`h-1.5 w-4 rounded-[2px] ${i < filled ? "bg-gain" : "bg-line"}`} />)}
      </span>
      <span className="num">{confidenceWords(confidence)}, {Math.round(confidence * 100)}%</span>
    </span>
  );
}

function Reference({ text, against }: { text: string; against: string }) {
  return (
    <span className="num">
      {diffMarks(text, against).map((m, i) => m.diff
        ? <mark key={i} className="rounded-[3px] bg-daylight-wash px-0.5 text-daylight-ink">{m.ch}</mark>
        : <span key={i}>{m.ch}</span>)}
    </span>
  );
}

function Pair({ match, busy, onDecide }: { match: Match; busy: string; onDecide: (id: string, action: "accept" | "reject") => void }) {
  const sub = match.subscriptions[0];
  const typed = match.lines.length === 1 && match.lines[0].reference && sub && match.lines[0].reference !== sub.reference
    ? match.lines[0].reference : null;
  return (
    <Panel className="space-y-4 p-5 sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <span className="font-semibold">{TIER_COPY[match.tier]}</span>
        <Meter confidence={match.confidence} />
      </div>
      <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_40px_minmax(0,1fr)] md:items-stretch">
        <div className="space-y-1 rounded-[14px] border border-line bg-ground/60 p-4">
          <p className="text-xs text-muted">On the statement{match.lines.length > 1 ? `, ${match.lines.length} lines` : ""}</p>
          {match.lines.map((l) => (
            <p key={l.id} className="text-sm"><span className="num font-semibold">{formatUsd(l.amount)}</span> <span className="text-ink-2">{l.description}</span></p>
          ))}
          {typed && sub && <p className="text-[13px] text-ink-2">Reference written as <Reference text={typed} against={sub.reference} /></p>}
        </div>
        <div className="hidden items-center justify-center md:flex" aria-hidden="true">
          <svg width="36" height="12" viewBox="0 0 36 12"><path d="M2 6h30M27 1l6 5-6 5" fill="none" stroke="#8c979f" strokeWidth="1.4" /></svg>
        </div>
        <div className="space-y-1 rounded-[14px] border border-line bg-ground/60 p-4">
          <p className="text-xs text-muted">Waiting for money</p>
          {match.subscriptions.map((s) => (
            <p key={s.instruction_id} className="text-sm"><span className="num font-semibold">{formatUsd(s.amount)}</span> <span className="text-ink-2">{s.reference}, {s.holder}, {s.fund_name}</span></p>
          ))}
        </div>
      </div>
      <ul className="flex flex-wrap gap-2">
        {match.evidence.map((e, i) => <li key={i} className="rounded-full bg-ground px-3 py-1 text-[13px] text-ink-2">{e}</li>)}
      </ul>
      <div className="flex flex-wrap items-center gap-2.5">
        {match.state === "awaiting_approval" ? (
          <p className="text-sm text-ink-2">Matched by hand; waiting for a second person in <Link href="/operations/approvals" className="font-semibold underline underline-offset-4">Approvals</Link>.</p>
        ) : (
          <>
            <Button busy={busy === `accept:${match.id}`} disabled={Boolean(busy)} onClick={() => onDecide(match.id, "accept")}>Accept the match</Button>
            <Button variant="secondary" busy={busy === `reject:${match.id}`} disabled={Boolean(busy)} onClick={() => onDecide(match.id, "reject")}>Reject</Button>
          </>
        )}
        <span className="flex items-center gap-2 text-[13px] text-muted">
          {match.proposed_by === "agent" && <span aria-hidden="true" className="h-2 w-2 rounded-[1px] bg-daylight" />}
          Proposed by {proposerLabel(match.proposed_by)}
        </span>
      </div>
    </Panel>
  );
}

function Flow({ statement }: { statement: Statement }) {
  const f = statementFlow(statement);
  const balance = balanceNote(statement);
  const tiles = [
    { n: f.read, label: "transactions read", cls: "bg-ground" },
    { n: f.matched, label: "matched", cls: "bg-gain-wash text-gain" },
    { n: f.waiting, label: "waiting for your decision", cls: "bg-daylight-wash text-daylight-ink" },
    { n: f.left, label: "left for you", cls: "border border-dashed border-line-strong bg-surface" },
  ];
  return (
    <Panel className="space-y-5 p-6 sm:p-7">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h2 className="text-[18px] font-semibold">Latest statement, read by {statement.source === "documentai" ? "Document AI" : "the CSV reader"}</h2>
        <span className="text-[13px] text-muted">{statement.filename}{statement.account_last4 ? `, account ending ${statement.account_last4}` : ""}</span>
      </div>
      <ul className="grid grid-cols-2 gap-2.5 md:grid-cols-4">
        {tiles.map((x) => (
          <li key={x.label} className={`rounded-[14px] p-4 ${x.cls}`}>
            <span className="num wide block text-[30px] font-semibold leading-none">{x.n}</span>
            <span className="mt-1.5 block text-sm text-ink-2">{x.label}</span>
          </li>
        ))}
      </ul>
      {balance && (
        <p className={`flex items-center gap-2.5 text-sm font-semibold ${balance.ok ? "text-gain" : "text-caution"}`}>
          <span aria-hidden="true">{balance.ok ? "✓" : "!"}</span>{balance.text}
        </p>
      )}
      {f.ignored > 0 && <p className="text-[13px] text-muted">{f.ignored} line{f.ignored > 1 ? "s" : ""} (interest and fees) need no match.</p>}
    </Panel>
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
  const [showExact, setShowExact] = useState(false);
  const file = useRef<HTMLInputElement>(null);
  const byHand = useRef<HTMLDetailsElement>(null);

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
  async function acceptAll(ids: string[]) {
    setBusy("accept-all");
    setError("");
    const { accepted, failed } = await acceptMany(ids, (id) =>
      api<Match>(`/ops/matches/${id}/accept`, { method: "POST", body: JSON.stringify({}) }));
    if (failed.length > 0) {
      setError(`Accepted ${accepted.length} of ${ids.length}. Could not accept ${failed.length}: ${failed[0].message}`);
    }
    try {
      await load();  // whatever happened, show the server's state
    } catch (e) {
      setError(msg(e, "Atrium could not reload reconciliation. Try again."));
    } finally {
      setBusy("");
    }
  }
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
  function openByHand(lineId: string) {
    setLineIds([lineId]);
    if (byHand.current) {
      byHand.current.open = true;
      byHand.current.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }

  const header = (
    <PageHeader title="Reconciliation"
      description="Match the money that reached the client money account with the subscriptions waiting for it. Rules take the clear cases, an agent proposes the rest, and you decide each one."
      actions={
        <>
          <label className={UPLOAD}>
            Upload a statement
            <input ref={file} type="file" accept=".pdf,.csv,application/pdf,text/csv" className="sr-only" disabled={Boolean(busy)}
              onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])} />
          </label>
          <Button busy={busy === "sample"} disabled={Boolean(busy) || !data} onClick={readSample}>Read the sample statement</Button>
        </>
      } />
  );
  if (!data) return <>{header}{error ? <Notice tone="error">{error}</Notice> : <Loading label="Loading reconciliation" />}</>;

  // The list holds live counts; the upload reply's counts are only as of the moment it was read.
  const latest = (read && data.statements.find((s) => s.id === read.id)) ?? read ?? data.statements[0] ?? null;
  const { rules, others } = splitProposals(data.proposals);
  const proposedLines = new Set(data.proposals.flatMap((m) => m.lines.map((l) => l.id)));
  const left = data.unmatched.filter((l) => !proposedLines.has(l.id));
  const waiting = data.receipts.filter((r) => !r.in_proposal);
  const chosenLines = data.unmatched.filter((l) => lineIds.includes(l.id));
  const chosenSubs = data.receipts.filter((r) => subIds.includes(r.instruction_id));
  const totals = matchTotals(chosenLines, chosenSubs);

  return (
    <>
      {header}
      <p className="-mt-4 mb-8 max-w-[70ch] text-sm text-muted">
        The sample statement is written for the payments Atrium is waiting for, with the imperfections real statements have
        {data.reads_pdf ? ", and as a PDF it is read by Document AI" : "; Document AI is not configured here, so it is read as a CSV"}.
        Download it as a <button type="button" className="underline underline-offset-4" onClick={() => download("pdf")}>PDF</button> or
        a <button type="button" className="underline underline-offset-4" onClick={() => download("csv")}>CSV</button>.
      </p>
      <div className="space-y-10">
        {error && <Notice tone="error">{error}</Notice>}
        {latest ? <Flow statement={latest} /> : (
          <EmptyState title="No statement yet" action={<Button busy={busy === "sample"} onClick={readSample}>Read the sample statement</Button>}>
            Read the sample statement, or upload the client money account&apos;s statement as a PDF or CSV.
          </EmptyState>
        )}

        {data.unmatched.length > 0 && waiting.length > 0 && (
          <Panel className="flex flex-wrap items-center justify-between gap-4 p-5 sm:p-6">
            <p className="text-[15px]">
              <span className="font-semibold">{data.unmatched.length} deposit{data.unmatched.length === 1 ? " waits" : "s wait"}</span>
              <span className="text-ink-2"> to be matched with {waiting.length} subscription{waiting.length === 1 ? "" : "s"} waiting for money.</span>
            </p>
            <Button busy={busy === "find"} disabled={Boolean(busy)} onClick={findMatches}>Find matches</Button>
          </Panel>
        )}
        {found && (
          <div className="space-y-3">
            <p className="text-sm text-ink-2">The rules proposed {found.rules}; {found.used_agent ? `the agent proposed ${found.agent}` : `the scorer proposed ${found.scorer}`}.</p>
            {found.used_agent
              ? <AiProse caption="Written by the reconciliation agent (Gemini Flash) after it scored and checked each candidate."><p>{found.summary}</p></AiProse>
              : <p className="text-sm text-ink-2">{found.summary}</p>}
          </div>
        )}
        {data.demo && data.receipts.length === 0 && (
          <Notice title="No subscription is waiting for money"
            action={<Button variant="secondary" size="sm" busy={busy === "demo"} disabled={Boolean(busy)} onClick={addDemoPayments}>Add demo payments</Button>}>
            Earlier visitors matched them all. Add a new set of client subscriptions; the sample statement is then written for them.
          </Notice>
        )}

        {others.length > 0 && (
          <Section title="The agent's proposals" description="You decide each one.">
            <div className="space-y-4">{others.map((m) => <Pair key={m.id} match={m} busy={busy} onDecide={decide} />)}</div>
          </Section>
        )}

        {rules.length > 0 && (
          <Panel className="space-y-4 p-5 sm:p-6">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <h2 className="font-semibold">{rules.length} exact match{rules.length === 1 ? "" : "es"} by the rules</h2>
                <p className="text-sm text-ink-2">Reference and amount agree, or the only payment of its amount came from the holder: {rules.slice(0, 3).map((m) => m.subscriptions[0]?.holder).filter(Boolean).join(", ")}{rules.length > 3 ? ` and ${rules.length - 3} more` : ""}.</p>
              </div>
              <div className="flex flex-wrap gap-2.5">
                <Button variant="secondary" aria-expanded={showExact} onClick={() => setShowExact((v) => !v)}>{showExact ? "Hide them" : "Review them"}</Button>
                <Button busy={busy === "accept-all"} disabled={Boolean(busy)} onClick={() => acceptAll(rules.map((m) => m.id))}>
                  Accept all {rules.length}
                </Button>
              </div>
            </div>
            {showExact && <div className="space-y-4">{rules.map((m) => <Pair key={m.id} match={m} busy={busy} onDecide={decide} />)}</div>}
          </Panel>
        )}

        {left.length > 0 && (
          <Section title="Left for you" description="No rule or agent found a subscription for these deposits.">
            <ul className="space-y-3">
              {left.map((l) => (
                <li key={l.id} className="flex flex-wrap items-center justify-between gap-4 rounded-panel border border-dashed border-line-strong bg-surface p-5">
                  <p className="text-sm"><span className="num font-semibold">{formatUsd(l.amount)}</span> <span className="text-ink-2">{formatDate(l.value_date)}, {l.description}</span></p>
                  <Button variant="secondary" size="sm" onClick={() => openByHand(l.id)}>Match by hand</Button>
                </li>
              ))}
            </ul>
          </Section>
        )}

        <details ref={byHand} className="group rounded-panel border border-line bg-surface">
          <summary className="flex min-h-14 cursor-pointer items-center justify-between gap-4 px-5 font-semibold sm:px-6">
            Match by hand
            <span className="ml-auto text-sm font-normal text-muted">A second person approves the match</span>
            <Chevron />
          </summary>
          <div className="space-y-5 border-t border-line p-5 sm:p-6">
            <div className="grid gap-6 lg:grid-cols-2">
              <fieldset>
                <legend className="text-sm font-semibold">Deposits on the statement</legend>
                {data.unmatched.length === 0 ? <p className="mt-2 text-sm text-muted">Every deposit is matched or proposed.</p> : (
                  <ul className="mt-2 divide-y divide-line border-y border-line">
                    {data.unmatched.map((l) => (
                      <li key={l.id}>
                        <label className="flex min-h-11 cursor-pointer items-start gap-3 py-2.5 text-sm">
                          <input type="checkbox" className="mt-1" checked={lineIds.includes(l.id)} onChange={() => toggle(lineIds, setLineIds, l.id)} />
                          <span className="min-w-0"><span className="num font-semibold">{formatUsd(l.amount)}</span> <span className="text-muted">{formatDate(l.value_date)}</span><span className="block text-ink-2">{l.description}</span></span>
                        </label>
                      </li>
                    ))}
                  </ul>
                )}
              </fieldset>
              <fieldset>
                <legend className="text-sm font-semibold">Subscriptions waiting for money</legend>
                {data.receipts.length === 0 ? <p className="mt-2 text-sm text-muted">No subscription is waiting for money.</p> : (
                  <ul className="mt-2 divide-y divide-line border-y border-line">
                    {data.receipts.map((r) => (
                      <li key={r.instruction_id}>
                        <label className={`flex min-h-11 items-start gap-3 py-2.5 text-sm ${r.in_proposal ? "opacity-60" : "cursor-pointer"}`}>
                          <input type="checkbox" className="mt-1" disabled={r.in_proposal} checked={subIds.includes(r.instruction_id)} onChange={() => toggle(subIds, setSubIds, r.instruction_id)} />
                          <span className="min-w-0"><span className="num font-semibold">{formatUsd(r.amount)}</span> <span className="num text-muted">{r.reference}</span><span className="block text-ink-2">{r.holder}, {r.fund_name}{r.in_proposal ? "; in a proposal" : ""}</span></span>
                        </label>
                      </li>
                    ))}
                  </ul>
                )}
              </fieldset>
            </div>
            {(lineIds.length > 0 || subIds.length > 0) && (
              <div className="max-w-xl space-y-3">
                <p className="text-sm">
                  The lines total <span className="num font-semibold">{formatUsd(totals.paid)}</span> and the subscriptions <span className="num font-semibold">{formatUsd(totals.due)}</span>.{" "}
                  <span className={totals.agrees ? "text-gain" : "text-caution"}>{totals.agrees ? "They agree." : "They do not agree yet."}</span>
                </p>
                <Field label="Why these belong together" hint="The approver reads this before deciding.">
                  <textarea className={`${inputClass} min-h-20`} value={reason} maxLength={500} onChange={(e) => setReason(e.target.value)}
                    placeholder="For example: The client confirmed by phone that this check pays for their October subscription." />
                </Field>
                <Button busy={busy === "manual"} disabled={!lineIds.length || !subIds.length || !reason.trim()} onClick={askManual}>Ask for approval</Button>
              </div>
            )}
            {asked && <Notice tone="success" title="Sent for approval">{asked.summary}.</Notice>}
          </div>
        </details>

        {data.recent.length > 0 && (
          <details className="group rounded-panel border border-line bg-surface">
            <summary className="flex min-h-14 cursor-pointer items-center justify-between gap-4 px-5 font-semibold sm:px-6">Recently decided<Chevron /></summary>
            <ul className="divide-y divide-line border-t border-line px-5 text-sm sm:px-6">
              {data.recent.map((m) => (
                <li key={m.id} className="flex flex-wrap items-baseline justify-between gap-2 py-3">
                  <span className="min-w-0">
                    {m.subscriptions.map((s) => `${s.reference} for ${s.holder}`).join(", ")}
                    <span className="block text-xs text-muted">{TIER_COPY[m.tier]}; {m.state} by {m.decided_by ?? "operations"}{m.decided_at ? ` on ${formatDate(m.decided_at)}` : ""}</span>
                  </span>
                  <Badge tone={m.state === "accepted" ? "gain" : "neutral"}>{m.state === "accepted" ? "Accepted" : "Rejected"}</Badge>
                </li>
              ))}
            </ul>
          </details>
        )}

        {data.statements.length > 0 && (
          <details className="group rounded-panel border border-line bg-surface">
            <summary className="flex min-h-14 cursor-pointer items-center justify-between gap-4 px-5 font-semibold sm:px-6">Statements<Chevron /></summary>
            <div className={`${t.wrap} border-t border-line px-5 sm:px-6`}>
              <table className={t.table}>
                <thead className={t.head}><tr><th className={t.th}>File</th><th className={t.th}>Read by</th><th className={t.th}>Uploaded</th><th className={`${t.th} text-right`}>To match</th><th className={`${t.th} text-right`}>Matched</th></tr></thead>
                <tbody>
                  {data.statements.map((s) => (
                    <tr key={s.id} className={t.row}>
                      <td className={t.td}>{s.filename}{s.bank_name && <span className="block text-xs text-muted">{s.bank_name}{s.account_last4 ? `, account ending ${s.account_last4}` : ""}</span>}</td>
                      <td className={t.td}>{s.source === "documentai" ? "Document AI" : "CSV"}</td>
                      <td className={t.td}>{formatDate(s.uploaded_at)}<span className="block text-xs text-muted">{s.uploaded_by}</span></td>
                      <td className={`${t.td} num text-right`}>{(s.counts.unmatched ?? 0) + (s.counts.proposed ?? 0)}</td>
                      <td className={`${t.td} num text-right`}>{s.counts.matched ?? 0}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
        )}
      </div>
    </>
  );
}
