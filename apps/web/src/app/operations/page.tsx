"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { api, ApiError } from "@/lib/api";
import { formatDate, formatPct } from "@/lib/format";
import type { Approval, OpsRun, Overview } from "@/lib/operations";
import { AiProse } from "@/components/ai-prose";
import { Badge, Button, EmptyState, Field, inputClass, Loading, Notice, PageHeader, Section, tableStyles as t } from "@/components/ui";

const msg = (e: unknown, fallback: string) => (e instanceof ApiError ? e.message : fallback);

function Steps({ run }: { run: OpsRun }) {
  return (
    <ol className="divide-y divide-line border-y border-line">
      {run.steps.map((s) => (
        <li key={s.step} className="grid grid-cols-[1rem_8.5rem_minmax(0,1fr)] items-baseline gap-3 py-2.5 text-sm">
          <span aria-hidden="true" className={s.ok ? "text-gain" : "font-semibold text-caution"}>{s.ok ? "✓" : "!"}</span>
          <span className="font-medium">{s.step}<span className="sr-only">{s.ok ? ", done" : ", needs a look"}</span></span>
          <span className="text-ink-2">{s.detail}</span>
        </li>
      ))}
    </ol>
  );
}

function MorningBrief({ run }: { run: OpsRun }) {
  const b = run.brief;
  if (!b) return null;
  const body = (
    <>
      <p className="text-[19px] font-semibold leading-snug">{b.headline}</p>
      <ul className="mt-3 list-disc space-y-1 pl-5">{b.points.map((p, i) => <li key={i}>{p}</li>)}</ul>
      {b.watch.length > 0 && (
        <>
          <p className="mt-4 font-semibold">Worth watching</p>
          <ul className="mt-1 list-disc space-y-1 pl-5">{b.watch.map((w, i) => <li key={i}>{w}</li>)}</ul>
        </>
      )}
    </>
  );
  if (b.model === "rules") return <div className="text-[15px]">{body}<p className="mt-3 text-xs text-muted">Gemini was unavailable, so the brief lists the steps.</p></div>;
  return (
    <AiProse caption={`Written by ${b.model} from the run's step log. Every dollar and percentage figure is checked against it.`}
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

  const header = (
    <PageHeader title="Day-end"
      description="Each weekday evening the day-end drafts fund prices from the market's closes, turns due monthly plans into orders, deals what it can, runs transaction monitoring and writes a brief. Prices wait for a second person before anything is dealt."
      actions={<Button busy={busy === "run"} onClick={runNow}>Run the day-end now</Button>} />
  );
  if (!data) return <>{header}{error ? <Notice tone="error">{error}</Notice> : <Loading label="Loading the day-end" />}</>;
  const run = data.latest_run;
  const waiting = [
    { label: "Waiting for money", value: data.waiting_for_money, href: "/operations/reconciliation" },
    { label: "Deposits to match", value: data.unmatched_lines, href: "/operations/reconciliation" },
    { label: "Proposals to decide", value: data.proposals, href: "/operations/reconciliation" },
    { label: "Approvals waiting", value: data.pending_approvals, href: "/operations/approvals" },
  ];
  const drafts = data.drafts.filter((d) => d.status === "draft");
  return (
    <>
      {header}
      {error && <div className="mb-6"><Notice tone="error">{error}</Notice></div>}
      <div className="mb-10 grid grid-cols-2 gap-px overflow-hidden rounded-panel border border-line bg-line sm:grid-cols-4">
        {waiting.map((w) => (
          <Link key={w.label} href={w.href} className="group bg-surface px-4 py-3 hover:bg-ground">
            <span className="block text-sm text-muted group-hover:text-ink">{w.label}</span>
            <span className="num wider mt-1 block text-[26px] font-semibold">{w.value}</span>
          </Link>
        ))}
      </div>
      <div className="space-y-10">
        <Section title={run ? `The run for ${formatDate(run.as_of ?? run.started_at)}` : "No run yet"}
          description={run ? `Started by ${run.triggered_by} on ${formatDate(run.started_at)}.` : "Cloud Scheduler starts the day-end at 5:15 pm New York time on weekdays; you can also run it now."}
          actions={run && <Badge tone={run.status === "ok" ? "gain" : "caution"}>{run.status === "ok" ? "Every step finished" : "Some steps need a look"}</Badge>}>
          {run ? (
            <div className="grid gap-8 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
              <MorningBrief run={run} />
              <Steps run={run} />
            </div>
          ) : <EmptyState title="The day-end has not run yet" action={<Button busy={busy === "run"} onClick={runNow}>Run the day-end now</Button>} />}
        </Section>
        <Section title={data.draft_as_of ? `Prices for ${formatDate(data.draft_as_of)}` : "Prices"}
          description="Each house fund's price moves with its constituents' closes since the last published price. A checker reads the checks and asks for publication; a second person approves it.">
          {data.drafts.length === 0 ? (
            <p className="text-sm text-ink-2">
              {data.unpublished.length === 0 ? `Prices for ${formatDate(data.as_of)} are published.` : "No draft prices are waiting. Run the day-end to draft them."}
            </p>
          ) : (
            <>
              <div className={t.wrap}>
                <table className={t.table}>
                  <thead className={t.head}>
                    <tr>
                      <th className={t.th}>Fund</th><th className={`${t.th} text-right`}>Last published</th>
                      <th className={`${t.th} text-right`}>Draft</th><th className={`${t.th} text-right`}>Move</th><th className={t.th}>Checks</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.drafts.map((d) => (
                      <tr key={d.fund_code} className={t.row}>
                        <td className={t.td}><span className="font-medium">{d.name}</span><span className="block text-xs text-muted">{d.fund_code}</span></td>
                        <td className={`${t.td} num text-right`}>
                          {d.prev_nav ? Number(d.prev_nav).toFixed(4) : "None"}
                          {d.prev_as_of && <span className="block text-xs text-muted">{formatDate(d.prev_as_of)}</span>}
                        </td>
                        <td className={`${t.td} num text-right font-medium`}>{Number(d.nav).toFixed(4)}</td>
                        <td className={`${t.td} num text-right`}>{formatPct(d.move_pct, 2, true)}</td>
                        <td className={t.td}>
                          <ul className="space-y-0.5">
                            {d.checks.map((c) => <li key={c.code} className={c.ok ? "text-ink-2" : "font-medium text-caution"}>{c.detail}</li>)}
                          </ul>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {asked && <div className="mt-5"><Notice tone="success" title="Sent for approval">{asked.summary}. A second person approves it in <Link href="/operations/approvals" className="underline underline-offset-4">Approvals</Link>.</Notice></div>}
              {drafts.length > 0 ? (
                <div className="mt-5 max-w-xl space-y-3 border-t border-line pt-5">
                  <Field label="Why these prices are right" hint="The approver reads this before deciding.">
                    <textarea className={`${inputClass} min-h-20`} value={reason} maxLength={500} onChange={(e) => setReason(e.target.value)}
                      placeholder="For example: Every move matches its constituents' closes; no fund moved more than 5%." />
                  </Field>
                  <Button busy={busy === "publish"} disabled={!reason.trim()} onClick={askToPublish}>Ask for publication</Button>
                </div>
              ) : !asked && (
                <div className="mt-5"><Notice title="Waiting for a second person">Publication has been asked for. Once a second person approves it in Approvals, the waiting instructions are dealt at these prices.</Notice></div>
              )}
            </>
          )}
        </Section>
        {data.runs.length > 1 && (
          <Section title="Earlier runs">
            <ul className="divide-y divide-line border-y border-line text-sm">
              {data.runs.slice(1).map((r) => (
                <li key={r.id} className="flex flex-wrap items-baseline justify-between gap-2 py-2.5">
                  <span>The run for {formatDate(r.as_of ?? r.started_at)}, started by {r.triggered_by}</span>
                  <Badge tone={r.status === "ok" ? "gain" : "caution"}>{r.status === "ok" ? "Every step finished" : "Some steps need a look"}</Badge>
                </li>
              ))}
            </ul>
          </Section>
        )}
      </div>
    </>
  );
}
