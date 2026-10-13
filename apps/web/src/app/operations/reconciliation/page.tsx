"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { api, ApiError, apiDownload, apiUpload } from "@/lib/api";
import { formatDate, formatUsd } from "@/lib/format";
import {
  acceptMany, balanceNote, confidenceWords, diffMarks, matchStatus, matchTotals, meterCells, proposerLabel, shortId, splitProposals,
  statementFlow, TIER_COPY,
  type Approval, type Match, type ReconcileResult, type Reconciliation, type Statement,
} from "@/lib/operations";
import { AiProse } from "@/components/ai-prose";
import { Badge, Button, EmptyState, Field, inputClass, Loading, Notice, PageHeader, Section, Sparkle } from "@/components/ui";
import { StatCard, StatusChip, TableCard, tbl } from "../_parts";

const msg = (e: unknown, fallback: string) => (e instanceof ApiError ? e.message : fallback);
const UPLOAD = "inline-flex min-h-11 cursor-pointer items-center justify-center gap-2 whitespace-nowrap rounded-full border border-sand-200 bg-white px-5 text-sm font-medium text-ink-900 transition-colors hover:bg-fill focus-within:shadow-[0_0_0_3px_var(--color-green-200)]";
const LINK = "font-semibold text-green-600 underline-offset-4 hover:text-green-800 hover:underline";

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
    <svg width="14" height="14" viewBox="0 0 24 24" aria-hidden="true" className="shrink-0 text-ink-500 transition-transform group-open:rotate-180">
      <path d="m6 9 6 6 6-6" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

/** How sure the proposer is, as a five-step green meter with the words and the percentage beside it. */
function Meter({ confidence }: { confidence: number }) {
  const filled = meterCells(confidence);
  return (
    <span className="flex items-center gap-2.5" role="img" aria-label={`Confidence ${Math.round(confidence * 100)}%, ${confidenceWords(confidence).toLowerCase()}`}>
      <span className="flex gap-[3px]" aria-hidden="true">
        {[0, 1, 2, 3, 4].map((i) => <span key={i} className={`h-2 w-4 rounded-[3px] ${i < filled ? "bg-green-500" : "bg-sand-200"}`} />)}
      </span>
      <span aria-hidden="true" className="whitespace-nowrap text-[13px] font-medium text-green-700">
        {confidenceWords(confidence)} <span className="num">{Math.round(confidence * 100)}%</span>
      </span>
    </span>
  );
}

/** A reference with the characters that differ from the expected one marked in amber: a typing slip, shown. */
function Reference({ text, against }: { text: string; against: string }) {
  return (
    <span className="font-mono text-[13px] text-ink-900">
      {diffMarks(text, against).map((m, i) => m.diff
        ? <mark key={i} className="rounded-[3px] border-b-[1.5px] border-amber-400 bg-amber-50 px-[1px] text-amber-800">{m.ch}</mark>
        : <span key={i}>{m.ch}</span>)}
    </span>
  );
}

function Side({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="min-w-0 space-y-2 rounded-control bg-fill p-4">
      <p className="text-xs font-medium text-ink-500">{label}</p>
      {children}
    </div>
  );
}

function Pair({ match, busy, onDecide }: { match: Match; busy: string; onDecide: (id: string, action: "accept" | "reject") => void }) {
  const sub = match.subscriptions[0];
  const typed = match.lines.length === 1 && match.lines[0].reference && sub && match.lines[0].reference !== sub.reference
    ? match.lines[0].reference : null;
  const agent = match.proposed_by === "agent";
  return (
    <article className="space-y-4 rounded-panel border border-sand-200 bg-white p-5 sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2.5">
          <h3 className="text-base font-semibold">{TIER_COPY[match.tier]}</h3>
          {agent ? <Badge tone="ai">Gemini proposal</Badge> : match.state === "awaiting_approval"
            ? <StatusChip tone={matchStatus(match.state).tone}>{matchStatus(match.state).label}</StatusChip> : null}
        </div>
        <Meter confidence={match.confidence} />
      </div>
      <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_32px_minmax(0,1fr)] md:items-stretch">
        <Side label={`On the statement${match.lines.length > 1 ? `, ${match.lines.length} lines` : ""}`}>
          {match.lines.map((l) => (
            <p key={l.id} className="text-sm">
              <span className="block text-[20px] font-medium leading-7 tracking-[-0.01em] num">{formatUsd(l.amount)}</span>
              <span className="block text-ink-700">{l.description}</span>
            </p>
          ))}
          {typed && sub && (
            <p className="flex flex-wrap items-baseline gap-x-2 border-t border-sand-200 pt-2 text-[13px] text-ink-700">
              Written as <Reference text={typed} against={sub.reference} />
            </p>
          )}
        </Side>
        <div className="hidden items-center justify-center text-ink-400 md:flex" aria-hidden="true">
          <svg width="28" height="12" viewBox="0 0 28 12"><path d="M1 6h24M20 1l5 5-5 5" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /></svg>
        </div>
        <Side label="Waiting for money">
          {match.subscriptions.map((s) => (
            <p key={s.instruction_id} className="text-sm">
              <span className="block text-[20px] font-medium leading-7 tracking-[-0.01em] num">{formatUsd(s.amount)}</span>
              <span className="block text-ink-700">{s.holder}, {s.fund_name}</span>
              <span className="block pt-0.5">
                {typed ? <span className="text-[13px] text-ink-700">Expected <Reference text={s.reference} against={typed} /></span>
                  : <span className="font-mono text-[13px] text-ink-700">{s.reference}</span>}
              </span>
            </p>
          ))}
        </Side>
      </div>
      <ul className="flex flex-wrap gap-2" aria-label="Why it matches">
        {match.evidence.map((e, i) => (
          <li key={i} className="inline-flex items-center gap-1.5 rounded-full bg-fill px-3 py-1 text-[13px] text-ink-700">
            <span aria-hidden="true" className="text-green-600">✓</span>{e}
          </li>
        ))}
      </ul>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2.5 border-t border-sand-100 pt-4">
        {match.state === "awaiting_approval" ? (
          <p className="text-sm text-ink-700">Matched by hand; waiting for a second person in <Link href="/operations/approvals" className={LINK}>Approvals</Link>.</p>
        ) : (
          <>
            <Button busy={busy === `accept:${match.id}`} disabled={Boolean(busy)} onClick={() => onDecide(match.id, "accept")}>Accept the match</Button>
            <Button variant="danger" busy={busy === `reject:${match.id}`} disabled={Boolean(busy)} onClick={() => onDecide(match.id, "reject")}>Reject</Button>
          </>
        )}
        <span className={`inline-flex items-center gap-1.5 text-[13px] sm:ml-auto ${agent ? "text-ai-700" : "text-ink-500"}`}>
          {agent && <Sparkle size={12} />}Proposed by {proposerLabel(match.proposed_by)}
        </span>
      </div>
    </article>
  );
}

function Flow({ statement }: { statement: Statement }) {
  const f = statementFlow(statement);
  const balance = balanceNote(statement);
  const toMatch = f.read - f.ignored;
  return (
    <section aria-labelledby="flow-title" className="space-y-4">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 px-1">
        <h2 id="flow-title" className="text-[20px] font-semibold leading-7 tracking-[-0.01em]">
          Latest statement, read by {statement.source === "documentai" ? "Document AI" : "the CSV reader"}
        </h2>
        <span className="text-[13px] text-ink-500">
          <span className="font-mono text-xs text-ink-700">{statement.filename}</span>{statement.account_last4 ? `, account ending ${statement.account_last4}` : ""}
        </span>
      </div>
      <div className="grid grid-cols-2 gap-3 sm:gap-4 xl:grid-cols-4">
        <StatCard icon="list" title="Transactions read" value={f.read} tone="neutral"
          caption={f.ignored > 0 ? `${f.ignored} (interest and fees) need no match` : "Every line is a deposit"}
          chip={balance && <StatusChip tone={balance.ok ? "gain" : "caution"}>{balance.ok ? "Balances" : "Does not balance"}</StatusChip>} />
        <StatCard icon="check" title="Matched" value={f.matched} unit={`of ${toMatch}`} tone="gain"
          caption={f.matched === toMatch && toMatch > 0 ? "Every deposit is matched" : "Accepted by a person"} />
        <StatCard icon="match" title="Waiting for you" value={f.waiting} tone={f.waiting > 0 ? "caution" : "gain"}
          caption={f.waiting > 0 ? "Proposals to accept or reject" : "No proposal waits"} />
        <StatCard icon="hand" title="Left for you" value={f.left} tone={f.left > 0 ? "caution" : "gain"}
          caption={f.left > 0 ? "No rule or agent found a match" : "Nothing left over"} />
      </div>
      {balance && (
        <p className={`flex items-center gap-2 px-1 text-[13px] font-medium ${balance.ok ? "text-green-700" : "text-amber-800"}`}>
          <span aria-hidden="true">{balance.ok ? "✓" : "!"}</span>{balance.text}
        </p>
      )}
    </section>
  );
}

function Pick({ checked, disabled, onChange, children }:
  { checked: boolean; disabled?: boolean; onChange: () => void; children: React.ReactNode }) {
  return (
    <label className={`flex min-h-11 items-start gap-3 rounded-control px-3 py-2.5 text-sm transition-colors ${disabled ? "opacity-60" : "cursor-pointer hover:bg-fill"} ${checked ? "bg-green-50 hover:bg-green-50" : ""}`}>
      <input type="checkbox" className="mt-0.5 h-4 w-4 shrink-0 accent-green-500" disabled={disabled} checked={checked} onChange={onChange} />
      <span className="min-w-0">{children}</span>
    </label>
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

  const fmt = data?.sample_format ?? "csv";
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

  // Each proposal card carries its own green Accept; the page's own actions stay tonal or outlined beside them.
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
          <Button variant="tonal" busy={busy === "sample"} disabled={Boolean(busy) || !data} onClick={readSample}>Read the sample statement</Button>
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
  const missing = !lineIds.length ? "Choose at least one deposit." : !subIds.length ? "Choose the subscription it pays for."
    : !reason.trim() ? "Say why they belong together." : "";

  return (
    <>
      {header}
      <p className="-mt-4 mb-8 max-w-[72ch] px-1 text-[13px] leading-5 text-ink-500">
        The sample statement is written for the payments Atrium is waiting for, with the imperfections real statements have
        {data.sample_format === "pdf" ? ", and as a PDF it is read by Document AI"
          : data.reads_pdf ? ". It is read as a CSV; upload the PDF to have Document AI read it"
          : "; Document AI is not configured here, so it is read as a CSV"}.
        Download it as a <button type="button" className={LINK} onClick={() => download("pdf")}>PDF</button> or
        a <button type="button" className={LINK} onClick={() => download("csv")}>CSV</button>.
      </p>
      <div className="space-y-12">
        {error && <Notice tone="error">{error}</Notice>}
        {latest ? <Flow statement={latest} /> : (
          <EmptyState title="No statement yet" action={<Button busy={busy === "sample"} onClick={readSample}>Read the sample statement</Button>}>
            Read the sample statement, or upload the client money account&apos;s statement as a PDF or CSV.
          </EmptyState>
        )}

        {data.unmatched.length > 0 && waiting.length > 0 && (
          <div className="flex flex-wrap items-center justify-between gap-4 rounded-panel border border-sand-200 bg-white p-5 sm:p-6">
            <p className="text-[15px]">
              <span className="font-semibold">{data.unmatched.length} deposit{data.unmatched.length === 1 ? " waits" : "s wait"}</span>
              <span className="text-ink-700"> to be matched with {waiting.length} subscription{waiting.length === 1 ? "" : "s"} waiting for money.</span>
            </p>
            <Button busy={busy === "find"} disabled={Boolean(busy)} onClick={findMatches}>Find matches</Button>
          </div>
        )}
        {found && (
          <div className="space-y-3">
            <p className="px-1 text-sm text-ink-700">The rules proposed {found.rules}; {found.used_agent ? `the agent proposed ${found.agent}` : `the scorer proposed ${found.scorer}`}.</p>
            {found.used_agent
              ? <AiProse caption="Written by the reconciliation agent after it scored and checked each candidate."><p>{found.summary}</p></AiProse>
              : <Notice title="The scorer stood in">{found.summary}</Notice>}
          </div>
        )}
        {data.demo && data.receipts.length === 0 && (
          <Notice title="No subscription is waiting for money"
            action={<Button variant="secondary" size="sm" busy={busy === "demo"} disabled={Boolean(busy)} onClick={addDemoPayments}>Add demo payments</Button>}>
            Earlier visitors matched them all. Add a new set of client subscriptions; the sample statement is then written for them.
          </Notice>
        )}

        {others.length > 0 && (
          <Section title="Proposals to decide" description="The agent's and the scorer's proposals. You decide each one.">
            <div className="space-y-4">{others.map((m) => <Pair key={m.id} match={m} busy={busy} onDecide={decide} />)}</div>
          </Section>
        )}

        {rules.length > 0 && (
          <section className="space-y-4 rounded-panel border border-sand-200 bg-white p-5 sm:p-6">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div className="min-w-0 max-w-[72ch]">
                <div className="flex flex-wrap items-center gap-2.5">
                  <h2 className="text-base font-semibold">{rules.length} exact match{rules.length === 1 ? "" : "es"} by the rules</h2>
                  <StatusChip tone="neutral">Rules</StatusChip>
                </div>
                <p className="mt-1 text-sm text-ink-700">Reference and amount agree, or the only payment of its amount came from the holder: {rules.slice(0, 3).map((m) => m.subscriptions[0]?.holder).filter(Boolean).join(", ")}{rules.length > 3 ? ` and ${rules.length - 3} more` : ""}.</p>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button variant="secondary" aria-expanded={showExact} onClick={() => setShowExact((v) => !v)}>{showExact ? "Hide them" : "Review them"}</Button>
                <Button variant="tonal" busy={busy === "accept-all"} disabled={Boolean(busy)} onClick={() => acceptAll(rules.map((m) => m.id))}>
                  Accept all {rules.length}
                </Button>
              </div>
            </div>
            {showExact && <div className="space-y-4">{rules.map((m) => <Pair key={m.id} match={m} busy={busy} onDecide={decide} />)}</div>}
          </section>
        )}

        {left.length > 0 && (
          <Section title="Left for you" description="No rule or agent found a subscription for these deposits.">
            <ul className="space-y-3">
              {left.map((l) => (
                <li key={l.id} className="flex flex-wrap items-center justify-between gap-4 rounded-panel border border-dashed border-sand-300 bg-white p-5">
                  <p className="min-w-0 text-sm">
                    <span className="block text-[20px] font-medium leading-7 tracking-[-0.01em] num">{formatUsd(l.amount)}</span>
                    <span className="text-ink-700">{formatDate(l.value_date)}, {l.description}</span>
                  </p>
                  <Button variant="secondary" size="sm" onClick={() => openByHand(l.id)}>Match by hand</Button>
                </li>
              ))}
            </ul>
          </Section>
        )}

        <details ref={byHand} className="group scroll-mt-24 rounded-panel border border-sand-200 bg-white">
          <summary className="flex min-h-16 cursor-pointer list-none items-center gap-4 px-5 sm:px-6 [&::-webkit-details-marker]:hidden">
            <span className="text-base font-semibold">Match by hand</span>
            <span className="ml-auto flex items-center gap-4">
              <span className="hidden text-[13px] text-ink-500 sm:inline">A second person approves the match</span>
              <Chevron />
            </span>
          </summary>
          <div className="space-y-6 border-t border-sand-100 p-5 sm:p-6">
            <div className="grid gap-6 lg:grid-cols-2">
              <fieldset className="min-w-0">
                <legend className="mb-2 text-[13px] font-medium">Deposits on the statement</legend>
                {data.unmatched.length === 0 ? <p className="text-sm text-ink-500">Every deposit is matched or proposed.</p> : (
                  <div className="space-y-1">
                    {data.unmatched.map((l) => (
                      <Pick key={l.id} checked={lineIds.includes(l.id)} onChange={() => toggle(lineIds, setLineIds, l.id)}>
                        <span className="num font-semibold">{formatUsd(l.amount)}</span> <span className="text-ink-500">{formatDate(l.value_date)}</span>
                        <span className="block text-ink-700">{l.description}</span>
                      </Pick>
                    ))}
                  </div>
                )}
              </fieldset>
              <fieldset className="min-w-0">
                <legend className="mb-2 text-[13px] font-medium">Subscriptions waiting for money</legend>
                {data.receipts.length === 0 ? <p className="text-sm text-ink-500">No subscription is waiting for money.</p> : (
                  <div className="space-y-1">
                    {data.receipts.map((r) => (
                      <Pick key={r.instruction_id} disabled={r.in_proposal} checked={subIds.includes(r.instruction_id)} onChange={() => toggle(subIds, setSubIds, r.instruction_id)}>
                        <span className="num font-semibold">{formatUsd(r.amount)}</span> <span className="font-mono text-xs text-ink-700">{r.reference}</span>
                        <span className="block text-ink-700">{r.holder}, {r.fund_name}{r.in_proposal ? "; in a proposal" : ""}</span>
                      </Pick>
                    ))}
                  </div>
                )}
              </fieldset>
            </div>
            {(lineIds.length > 0 || subIds.length > 0) && (
              <div className="max-w-xl space-y-4">
                <div className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-control bg-fill px-4 py-3 text-sm">
                  <span>Deposits <span className="num font-semibold">{formatUsd(totals.paid)}</span></span>
                  <span>Subscriptions <span className="num font-semibold">{formatUsd(totals.due)}</span></span>
                  <StatusChip tone={totals.agrees ? "gain" : "caution"}>{totals.agrees ? "They agree" : "They do not agree yet"}</StatusChip>
                </div>
                <Field label="Why these belong together" hint="The approver reads this before deciding.">
                  <textarea className={`${inputClass} min-h-20`} value={reason} maxLength={500} onChange={(e) => setReason(e.target.value)}
                    placeholder="For example: The client confirmed by phone that this check pays for their October subscription." />
                </Field>
                <div className="flex flex-wrap items-center gap-3">
                  <Button busy={busy === "manual"} disabled={Boolean(missing)} onClick={askManual}>Ask for approval</Button>
                  {missing && <span className="text-xs text-ink-500">{missing}</span>}
                </div>
              </div>
            )}
            {asked && <Notice tone="success" title="Sent for approval">{asked.summary}.</Notice>}
          </div>
        </details>

        {data.recent.length > 0 && (
          <TableCard title="Recently decided" description="Matches people accepted or rejected, newest first.">
            <div className={tbl.wrap}>
              <table className={`${tbl.table} min-w-[680px]`}>
                <thead className={tbl.head}>
                  <tr><th className={tbl.th}>Reference</th><th className={tbl.th}>Client</th><th className={tbl.th}>How it matched</th><th className={tbl.th}>Decided</th><th className={`${tbl.th} text-right`}>Amount</th><th className={tbl.th}>Status</th></tr>
                </thead>
                <tbody>
                  {data.recent.map((m) => {
                    const status = matchStatus(m.state);
                    const amount = m.subscriptions.reduce((sum, s) => sum + Number(s.amount), 0);
                    return (
                      <tr key={m.id} className={tbl.row}>
                        <td className={`${tbl.td} ${tbl.id}`}>{m.subscriptions.map((s) => s.reference).join(", ") || shortId(m.id)}</td>
                        <td className={tbl.td}>{m.subscriptions.map((s) => s.holder).join(", ")}</td>
                        <td className={`${tbl.td} text-ink-700`}>{TIER_COPY[m.tier]}</td>
                        <td className={`${tbl.td} whitespace-nowrap text-ink-700`}>{m.decided_at ? formatDate(m.decided_at) : "None"}<span className="block text-xs text-ink-500">{m.decided_by ?? "operations"}</span></td>
                        <td className={`${tbl.td} ${tbl.amount}`}>{formatUsd(amount)}</td>
                        <td className={tbl.td}><StatusChip tone={status.tone}>{status.label}</StatusChip></td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </TableCard>
        )}

        {data.statements.length > 0 && (
          <TableCard title="Statements" description="Every statement read, with what is still to match.">
            <div className={tbl.wrap}>
              <table className={`${tbl.table} min-w-[680px]`}>
                <thead className={tbl.head}><tr><th className={tbl.th}>File</th><th className={tbl.th}>Read by</th><th className={tbl.th}>Uploaded</th><th className={`${tbl.th} text-right`}>To match</th><th className={`${tbl.th} text-right`}>Matched</th></tr></thead>
                <tbody>
                  {data.statements.map((s) => (
                    <tr key={s.id} className={tbl.row}>
                      <td className={tbl.td}><span className={tbl.id}>{s.filename}</span>{s.bank_name && <span className="block text-xs text-ink-500">{s.bank_name}{s.account_last4 ? `, account ending ${s.account_last4}` : ""}</span>}</td>
                      <td className={tbl.td}>{s.source === "documentai" ? "Document AI" : "CSV reader"}</td>
                      <td className={`${tbl.td} whitespace-nowrap text-ink-700`}>{formatDate(s.uploaded_at)}<span className="block text-xs text-ink-500">{s.uploaded_by}</span></td>
                      <td className={`${tbl.td} ${tbl.amount}`}>{(s.counts.unmatched ?? 0) + (s.counts.proposed ?? 0)}</td>
                      <td className={`${tbl.td} ${tbl.amount}`}>{s.counts.matched ?? 0}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </TableCard>
        )}
      </div>
    </>
  );
}
