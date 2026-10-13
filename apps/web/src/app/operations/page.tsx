"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { api, ApiError } from "@/lib/api";
import { formatDate, formatPct } from "@/lib/format";
import {
  priceStatus, runCounts, sinceRun, writtenByModel, type Approval, type OpsRun, type Overview,
} from "@/lib/operations";
import { AiProse } from "@/components/ai-prose";
import { Button, ChangeChip, EmptyState, Field, inputClass, Loading, Notice, PageHeader, Section } from "@/components/ui";
import { StatCard, StatusChip, TableCard, tbl, type GlyphName } from "./_parts";

const msg = (e: unknown, fallback: string) => (e instanceof ApiError ? e.message : fallback);
const runStatus = (r: OpsRun) => (r.status === "ok"
  ? { label: "Every step finished", tone: "gain" as const }
  : r.status === "running" ? { label: "Running", tone: "neutral" as const } : { label: "Some steps need a look", tone: "caution" as const });

function StepLog({ run }: { run: OpsRun }) {
  return (
    <TableCard title="Step log" description="What each step of the run did, in order.">
      <div className={tbl.wrap}>
        <table className={tbl.table}>
          <thead className={tbl.head}><tr><th className={tbl.th}>Step</th><th className={tbl.th}>What happened</th><th className={`${tbl.th} hidden text-right sm:table-cell`}>Outcome</th></tr></thead>
          <tbody>
            {run.steps.map((s) => {
              const chip = <StatusChip tone={s.ok ? "gain" : "caution"}>{s.ok ? "Done" : "Needs a look"}</StatusChip>;
              return (
                <tr key={s.step} className={`${tbl.row} align-top sm:align-middle`}>
                  <td className={`${tbl.td} font-medium sm:whitespace-nowrap`}>{s.step}<span className="mt-1.5 block sm:hidden">{chip}</span></td>
                  <td className={`${tbl.td} text-ink-700`}>{s.detail}</td>
                  <td className={`${tbl.td} hidden text-right sm:table-cell`}>{chip}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </TableCard>
  );
}

function MorningBrief({ run }: { run: OpsRun }) {
  const b = run.brief;
  if (!b) return null;
  const body = (
    <>
      <p className="text-[20px] font-medium leading-snug sm:text-[22px]">{b.headline}</p>
      <ul className="mt-3 list-disc space-y-1 pl-5 marker:text-ai-500">{b.points.map((p, i) => <li key={i}>{p}</li>)}</ul>
      {b.watch.length > 0 && (
        <>
          <p className="mt-4 font-sans text-[13px] font-semibold uppercase tracking-[0.04em] text-ai-700">Worth watching</p>
          <ul className="mt-1 list-disc space-y-1 pl-5 marker:text-ai-500">{b.watch.map((w, i) => <li key={i}>{w}</li>)}</ul>
        </>
      )}
    </>
  );
  if (!writtenByModel(b.model)) {
    return (
      <div className="rounded-[16px] bg-fill px-6 py-[22px] text-[15px] leading-[22px]">
        <p className="text-[13px] font-semibold text-ink-700">The rules&apos; summary</p>
        <p className="mt-2 text-[17px] font-semibold">{b.headline}</p>
        <ul className="mt-2 list-disc space-y-1 pl-5 text-ink-700">{b.points.map((p, i) => <li key={i}>{p}</li>)}</ul>
        <p className="mt-3 text-xs text-ink-500">Gemini was unavailable, so the brief lists the steps.</p>
      </div>
    );
  }
  return (
    <AiProse model={b.model}
      caption="From the run's step log. Every dollar and percentage figure is checked against it."
      warning={b.verified ? undefined : `Check before relying on this: ${b.unsupported_figures.join(", ")} did not come from the run.`}>
      {body}
    </AiProse>
  );
}

export default function DayEndPage() {
  const [data, setData] = useState<Overview | null>(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [reason, setReason] = useState("");
  const [asked, setAsked] = useState<Approval | null>(null);

  const load = useCallback(async () => setData(await api<Overview>("/ops/overview")), []);
  useEffect(() => {
    load().catch((e) => setError(msg(e, "Atrium could not load the day-end. Try again.")));
  }, [load]);

  async function runNow() {
    setBusy("run");
    setError("");
    try {
      await api<OpsRun>("/ops/day-end", { method: "POST" });
      await load();
    } catch (e) {
      setError(msg(e, "The day-end could not run. Try again."));
    } finally {
      setBusy("");
    }
  }

  async function askToPublish() {
    if (!data?.draft_as_of) return;
    setBusy("publish");
    setError("");
    try {
      setAsked(await api<Approval>("/ops/prices/publish", { method: "POST", body: JSON.stringify({ as_of: data.draft_as_of, reason }) }));
      setReason("");
      await load();
    } catch (e) {
      setError(msg(e, "Atrium could not ask for publication. Try again."));
    } finally {
      setBusy("");
    }
  }

  const drafts = data?.drafts.filter((d) => d.status === "draft") ?? [];
  // One green action per view: asking for publication when draft prices wait, otherwise running the day-end.
  const header = (
    <PageHeader title="Today"
      description="Each weekday evening the day-end drafts fund prices from the market's closes, turns due monthly plans into orders, deals what it can, runs transaction monitoring and writes a brief. Prices wait for a second person before anything is dealt."
      actions={<Button variant={drafts.length > 0 ? "secondary" : "primary"} busy={busy === "run"} onClick={runNow}>Run the day-end now</Button>} />
  );
  if (!data) return <>{header}{error ? <Notice tone="error">{error}</Notice> : <Loading label="Loading the day-end" />}</>;
  const run = data.latest_run;
  const then = runCounts(run);
  const cards: { title: string; value: number; then?: number; icon: GlyphName; href: string; idle: string; busy: string }[] = [
    { title: "Waiting for money", value: data.waiting_for_money, then: then.waiting, icon: "money", href: "/operations/reconciliation",
      idle: "No subscription is waiting", busy: "Subscriptions not yet paid for" },
    { title: "Deposits to match", value: data.unmatched_lines, then: then.unmatched, icon: "inbox", href: "/operations/reconciliation",
      idle: "Every deposit is matched", busy: "Statement lines with no match" },
    { title: "Proposals to decide", value: data.proposals, icon: "match", href: "/operations/reconciliation",
      idle: "Nothing to decide", busy: "Matches waiting for you" },
    { title: "Approvals waiting", value: data.pending_approvals, then: then.approvals, icon: "check", href: "/operations/approvals",
      idle: "Nothing to approve", busy: "Need a second person" },
  ];
  return (
    <>
      {header}
      {error && <div className="mb-6"><Notice tone="error">{error}</Notice></div>}
      <div className="mb-12 grid grid-cols-2 gap-3 sm:gap-4 xl:grid-cols-4">
        {cards.map((c) => {
          const moved = sinceRun(c.value, c.then);
          return (
            <StatCard key={c.title} icon={c.icon} title={c.title} value={c.value} href={c.href}
              tone={c.value > 0 ? "caution" : "gain"}
              caption={moved ? "Since the day-end" : c.value > 0 ? c.busy : c.idle}
              chip={moved && <ChangeChip tone={moved.tone}>{moved.text}</ChangeChip>} />
          );
        })}
      </div>
      <div className="space-y-12">
        <Section title={run ? `The run for ${formatDate(run.as_of ?? run.started_at)}` : "No run yet"}
          description={run ? `Started by ${run.triggered_by} on ${formatDate(run.started_at)}.` : "Cloud Scheduler starts the day-end at 5:15 pm New York time on weekdays; you can also run it now."}
          actions={run && <StatusChip tone={runStatus(run).tone}>{runStatus(run).label}</StatusChip>}>
          {run ? (
            <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)] xl:items-start [&>*]:min-w-0">
              <MorningBrief run={run} />
              <StepLog run={run} />
            </div>
          ) : <EmptyState title="The day-end has not run yet" action={<Button busy={busy === "run"} onClick={runNow}>Run the day-end now</Button>} />}
        </Section>

        <Section title={data.draft_as_of ? `Prices for ${formatDate(data.draft_as_of)}` : "Prices"}
          description="Each house fund's price moves with its constituents' closes since the last published price. A checker reads the checks and asks for publication; a second person approves it.">
          {data.drafts.length === 0 ? (
            <div className="rounded-panel border border-sand-200 bg-white px-6 py-5 text-sm text-ink-700">
              {data.unpublished.length === 0 ? `Prices for ${formatDate(data.as_of)} are published.` : "No draft prices are waiting. Run the day-end to draft them."}
            </div>
          ) : (
            <div className="space-y-4">
              <TableCard title="Draft prices" description={`${data.drafts.length} fund${data.drafts.length === 1 ? "" : "s"}, priced from the market's closes.`}>
                <div className={tbl.wrap}>
                  <table className={`${tbl.table} min-w-[760px]`}>
                    <thead className={tbl.head}>
                      <tr>
                        <th className={tbl.th}>Fund</th><th className={`${tbl.th} text-right`}>Last published</th>
                        <th className={`${tbl.th} text-right`}>Draft</th><th className={`${tbl.th} text-right`}>Move</th>
                        <th className={tbl.th}>Checks</th><th className={tbl.th}>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.drafts.map((d) => {
                        const status = priceStatus(d.status);
                        return (
                          <tr key={d.fund_code} className={`${tbl.row} align-top`}>
                            <td className={tbl.td}>
                              <span className="flex items-center gap-2.5">
                                <span className="flex h-7 min-w-11 items-center justify-center rounded-tile bg-green-50 px-1.5 font-mono text-[10px] font-medium text-green-700">{d.fund_code.replace(/^ATR-/, "")}</span>
                                <span className="flex flex-col"><span className="font-medium">{d.name}</span><span className={tbl.id}>{d.fund_code}</span></span>
                              </span>
                            </td>
                            <td className={`${tbl.td} ${tbl.amount}`}>
                              {d.prev_nav ? Number(d.prev_nav).toFixed(4) : "None"}
                              {d.prev_as_of && <span className="block text-xs text-ink-500">{formatDate(d.prev_as_of)}</span>}
                            </td>
                            <td className={`${tbl.td} ${tbl.amount} font-medium`}>{Number(d.nav).toFixed(4)}</td>
                            <td className={`${tbl.td} text-right`}>
                              {d.move_pct === 0 ? <span className="tabular-nums text-ink-700">{formatPct(0, 2)}</span>
                                : <ChangeChip value={d.move_pct}>{d.move_pct > 0 ? "↑" : "↓"} {formatPct(Math.abs(d.move_pct), 2)}</ChangeChip>}
                            </td>
                            <td className={tbl.td}>
                              <ul className="space-y-0.5">
                                {d.checks.map((c) => (
                                  <li key={c.code} className={`flex gap-1.5 ${c.ok ? "text-ink-700" : "font-medium text-amber-800"}`}>
                                    <span aria-hidden="true" className={c.ok ? "text-green-600" : "text-amber-800"}>{c.ok ? "✓" : "!"}</span>{c.detail}
                                  </li>
                                ))}
                              </ul>
                            </td>
                            <td className={tbl.td}><StatusChip tone={status.tone}>{status.label}</StatusChip></td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </TableCard>
              {asked && <Notice tone="success" title="Sent for approval">{asked.summary}. A second person approves it in <Link href="/operations/approvals" className="font-semibold text-green-600 underline underline-offset-4">Approvals</Link>.</Notice>}
              {drafts.length > 0 ? (
                <div className="max-w-xl space-y-3 rounded-panel border border-sand-200 bg-white p-5 sm:p-6">
                  <Field label="Why these prices are right" hint="The approver reads this before deciding.">
                    <textarea className={`${inputClass} min-h-20`} value={reason} maxLength={500} onChange={(e) => setReason(e.target.value)}
                      placeholder="For example: Every move matches its constituents' closes; no fund moved more than 5%." />
                  </Field>
                  <div className="flex flex-wrap items-center gap-3">
                    <Button busy={busy === "publish"} disabled={!reason.trim()} onClick={askToPublish}>Ask for publication</Button>
                    {!reason.trim() && <span className="text-xs text-ink-500">Say why the prices are right first.</span>}
                  </div>
                </div>
              ) : !asked && (
                <Notice tone="caution" title="Waiting for a second person">Publication has been asked for. Once a second person approves it in Approvals, the waiting instructions are dealt at these prices.</Notice>
              )}
            </div>
          )}
        </Section>

        {data.runs.length > 1 && (
          <TableCard title="Earlier runs">
            <div className={tbl.wrap}>
              <table className={`${tbl.table} min-w-[480px]`}>
                <thead className={tbl.head}><tr><th className={tbl.th}>Run for</th><th className={tbl.th}>Started by</th><th className={tbl.th}>Started</th><th className={`${tbl.th} text-right`}>Outcome</th></tr></thead>
                <tbody>
                  {data.runs.slice(1).map((r) => (
                    <tr key={r.id} className={tbl.row}>
                      <td className={`${tbl.td} whitespace-nowrap font-medium`}>{formatDate(r.as_of ?? r.started_at)}</td>
                      <td className={tbl.td}>{r.triggered_by}</td>
                      <td className={`${tbl.td} whitespace-nowrap text-ink-700`}>{formatDate(r.started_at)}</td>
                      <td className={`${tbl.td} text-right`}><StatusChip tone={runStatus(r).tone}>{runStatus(r).label}</StatusChip></td>
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
