"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { api, ApiError } from "@/lib/api";
import { formatDate } from "@/lib/format";
import {
  agreementLine, clockUtc, driftLine, elapsedClock, GENERATIVE, headline, MONITORED, runLine, runMeta, runNotice, STATUS_LABEL, STATUS_TONE,
  type ModelRow, type ModelStatus, type ModelsOut, type Monitoring, type RunRow,
} from "@/lib/governance";
import { CountUp } from "@/components/motion";
import { Skeleton, SkeletonText } from "@/components/skeleton";
import { Button, KeyMoment, Notice, PageHeader, Section, Spinner } from "@/components/ui";
import { ArriveChip, StatusChip, TableCard, tbl } from "../../operations/_parts";
import { ChipsSkeleton, LoadingRegion, MomentSkeleton, SectionTitleSkeleton, TableCardSkeleton } from "../../operations/_skeletons";

const msg = (e: unknown, fallback: string) => (e instanceof ApiError ? e.message : fallback);
const POLL_MS = 10_000;
const TIER_LABEL = { high: "High", medium: "Medium" } as const;
const ORDER: ModelStatus[] = ["breaker_open", "failing", "no_result", "not_validated", "monitored_only", "validated"];

function KindChip({ model }: { model: Pick<ModelRow, "kind" | "kind_label"> }) {
  return <StatusChip tone={GENERATIVE.has(model.kind) ? "ai" : "neutral"}>{model.kind_label}</StatusChip>;
}

/** A model's status, arriving in order down the inventory: the evidence read row by row. */
function StatusCell({ model, index }: { model: ModelRow; index: number }) {
  return (
    <ArriveChip index={index}>
      <span className="flex flex-wrap items-center gap-1.5">
        <StatusChip tone={STATUS_TONE[model.status]}>{STATUS_LABEL[model.status]}</StatusChip>
        {model.changed_since_validation && <StatusChip tone="caution">Changed since validation</StatusChip>}
      </span>
    </ArriveChip>
  );
}

/** While the live checks run: a calm panel with the time so far, not Gemini's violet (this is the evaluation harness
 *  at work, a Cloud Run job, not Gemini writing). The page looks every ten seconds and updates when the run ends. */
function RunningPanel({ startedAt }: { startedAt: string | null }) {
  const [now, setNow] = useState(() => Date.now());
  const [since] = useState(() => new Date().toISOString());
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);
  const start = startedAt ?? since;
  return (
    <div role="status" aria-live="polite" className="flex flex-wrap items-center gap-x-5 gap-y-3 rounded-panel border border-sand-200 bg-white px-5 py-4 sm:px-6">
      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-fill text-green-600"><Spinner /></span>
      <div className="min-w-0 flex-1">
        <p className="text-sm font-semibold">The live checks are running</p>
        <p className="mt-0.5 text-[13px] text-ink-700">
          Gemini, the reconciliation agent and the red team meet the golden cases as a Cloud Run job. This page looks every ten
          seconds and updates when the run ends.
        </p>
      </div>
      <p className="code shrink-0 text-[12px] text-ink-700">
        <span aria-hidden="true">{elapsedClock(start, now)}</span>
        <span className="text-ink-500"> since {clockUtc(start)} · usually about 10 min</span>
      </p>
    </div>
  );
}

/** Models while they load: the opening card with its counts, the inventory, and what is watched. */
function ModelsSkeleton() {
  return (
    <LoadingRegion label="Loading the models" className="space-y-12">
      <MomentSkeleton>
        <ChipsSkeleton count={3} />
        <SkeletonText lines={2} className="max-w-[72ch]" />
        <span className="flex gap-2 border-t border-sand-100 pt-4"><Skeleton className="h-3 w-20" /><Skeleton className="h-3 w-72 max-w-[70%]" /></span>
      </MomentSkeleton>
      <TableCardSkeleton rows={8} widths={[2.2, 1.2, 0.8, 1.2, 1.6, 1]} chip={4} />
      <div>
        <SectionTitleSkeleton width="w-72" />
        <div className="divide-y divide-sand-100 rounded-panel border border-sand-200 bg-white">
          {[0, 1, 2, 3].map((i) => <div key={i} className="flex items-center gap-3 px-5 py-4 sm:px-6"><Skeleton className="h-1.5 w-1.5 rounded-full" /><Skeleton className="h-3.5 w-3/5" /></div>)}
        </div>
      </div>
    </LoadingRegion>
  );
}

function validatedOn(model: ModelRow) {
  return model.last_validated_at ? formatDate(model.last_validated_at) : "Never";
}

function Inventory({ models }: { models: ModelRow[] }) {
  return (
    <TableCard title="Inventory" description="Each model once, with its risk tier, its owner and what its latest evidence says. A model without checks is monitored only, never shown as validated.">
      <div className={`${tbl.wrap} hidden md:block`}>
        <table className={`${tbl.table} min-w-[760px]`}>
          <thead className={tbl.head}>
            <tr>
              <th className={tbl.th}>Model</th><th className={tbl.th}>Kind</th><th className={tbl.th}>Risk tier</th>
              <th className={tbl.th}>Owner</th><th className={tbl.th}>Status</th><th className={`${tbl.th} text-right`}>Last validated</th>
            </tr>
          </thead>
          <tbody>
            {models.map((m, i) => (
              <tr key={m.key} className={`${tbl.row} transition-colors hover:bg-fill`}>
                <td className={tbl.td}>
                  <Link href={`/compliance/models/${m.key}`} className="font-medium hover:text-green-700 hover:underline">{m.name}</Link>
                  <span className={`block ${tbl.id} text-[11px]! text-ink-500`}>{m.key}</span>
                </td>
                <td className={tbl.td}><KindChip model={m} /></td>
                <td className={`${tbl.td} text-ink-700`}>{TIER_LABEL[m.tier]}</td>
                <td className={`${tbl.td} whitespace-nowrap text-ink-700`}>{m.owner}</td>
                <td className={tbl.td}><StatusCell model={m} index={i} /></td>
                <td className={`${tbl.td} whitespace-nowrap text-right text-ink-700`}>{validatedOn(m)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <ul className="divide-y divide-sand-100 md:hidden">
        {models.map((m, i) => (
          <li key={m.key}>
            <Link href={`/compliance/models/${m.key}`} className="block py-3.5">
              <span className="flex items-baseline justify-between gap-3">
                <span className="font-medium">{m.name}</span>
                <span className="shrink-0 text-xs text-ink-500">{TIER_LABEL[m.tier]} tier</span>
              </span>
              <span className="mt-2 flex flex-wrap items-center gap-1.5"><KindChip model={m} /><StatusCell model={m} index={i} /></span>
              <span className="mt-1.5 block text-[13px] text-ink-700">
                {m.owner} · {m.last_validated_at ? `validated ${formatDate(m.last_validated_at)}` : "not validated yet"}
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </TableCard>
  );
}

function Watching({ monitoring }: { monitoring: Monitoring }) {
  const lines = [
    ...Object.entries(monitoring.agreement).filter(([key]) => MONITORED.has(key))
      .map(([key, a]) => ({ key, text: agreementLine(key, a, monitoring.window_days), href: `/compliance/models/${key}` })),
    { key: "lead_score", text: driftLine(monitoring.drift.lead_score), href: "/compliance/models/lead_score" },
    { key: "aml_anomaly", text: `AML anomaly model: ${monitoring.drift.aml_anomaly.note}.`, href: "/compliance/models/aml_anomaly" },
  ];
  return (
    <div className="rounded-panel border border-sand-200 bg-white">
      {monitoring.trips === false && (
        <p className="border-b border-sand-100 px-5 py-3.5 text-[13px] text-ink-500 sm:px-6">
          Report-only for the judging window: visitors&apos; exploratory decisions are shown here, but a low rate does not
          pause a model. The live checks still pause a model that misses its bar.
        </p>
      )}
      <ul className="divide-y divide-sand-100">
        {lines.map((l) => (
          <li key={l.key}>
            <Link href={l.href} className="flex items-start gap-3 px-5 py-3.5 text-sm text-ink-700 transition-colors hover:bg-fill hover:text-ink-900 sm:px-6">
              <span aria-hidden="true" className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-green-500" />{l.text}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function ModelsPage() {
  const [data, setData] = useState<ModelsOut | null>(null);
  const [latest, setLatest] = useState<RunRow | null>(null);
  const [monitoring, setMonitoring] = useState<Monitoring | null>(null);
  const [running, setRunning] = useState<RunRow | null>(null);
  const [refused, setRefused] = useState("");
  const [done, setDone] = useState<RunRow | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    const [models, watched, runs] = await Promise.all([
      api<ModelsOut>("/governance/models"), api<Monitoring>("/governance/monitoring"), api<RunRow[]>("/governance/runs?limit=1"),
    ]);
    setData(models);
    setMonitoring(watched);
    setLatest(runs[0] ?? null);
    setRunning(models.last_run?.status === "running" ? models.last_run : null);
  }, []);
  useEffect(() => {
    load().catch((e) => setError(msg(e, "Atrium could not load the models. Try again.")));
  }, [load]);

  // While a live run is going, look every ten seconds; when it ends, reload the inventory and its evidence.
  useEffect(() => {
    if (!running) return;
    const timer = setInterval(async () => {
      try {
        const [last] = await api<RunRow[]>("/governance/runs?limit=1");
        if (!last || last.status !== "running") {
          clearInterval(timer);
          await load();
          if (last) setDone(last);
        }
      } catch {
        // a missed poll is retried on the next tick
      }
    }, POLL_MS);
    return () => clearInterval(timer);
  }, [running, load]);

  async function start() {
    setBusy(true);
    setError("");
    setRefused("");
    setDone(null);
    try {
      const run = await api<RunRow>("/governance/evals/run", { method: "POST" });
      if (run.status === "running") {
        setRunning(run);
      } else {
        await load();
        setDone(run);
      }
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) setRefused(e.message);
      else setError(msg(e, "The live checks could not be started. Try again."));
    } finally {
      setBusy(false);
    }
  }

  const action = (
    <Button variant="tonal" busy={busy} disabled={Boolean(running) || Boolean(refused)} onClick={start}>
      {running ? `Live checks running since ${clockUtc(running.started_at)}` : "Run the live checks"}
    </Button>
  );
  const head = (
    <PageHeader title="Models" actions={action}
      description="Every model in Atrium, validated before and after each deploy, attacked by a red team, checked for fair lending, and watched against people's decisions." />
  );
  if (!data) return <>{head}{error ? <Notice tone="error">{error}</Notice> : <ModelsSkeleton />}</>;

  const top = headline(data.models, data.last_run);
  const open = data.models.some((m) => m.status === "breaker_open");
  const tone = top.title === "Every model is validated." ? "good" : open ? "alert" : "attention";
  const counts = ORDER.map((s) => ({ s, n: data.models.filter((m) => m.status === s).length })).filter((c) => c.n > 0);
  const run = running ?? latest;
  return (
    <>
      {head}
      <div className="space-y-12">
        {(running || busy) && <RunningPanel startedAt={running?.started_at ?? null} />}
        {(refused || error || done) && (
          <div className="space-y-3">
            {refused && <Notice tone="caution" title="The live checks cannot start yet">{refused}</Notice>}
            {error && <Notice tone="error">{error}</Notice>}
            {done && <Notice tone={runNotice(done).tone} title={runNotice(done).title}>{runLine(done)}.</Notice>}
          </div>
        )}
        <KeyMoment tone={tone} label="Model risk" title={top.title}>
          <div className="flex flex-wrap gap-2">
            {counts.map(({ s, n }) => <StatusChip key={s} tone={STATUS_TONE[s]}><CountUp text={String(n)} duration={0.6} /> {STATUS_LABEL[s].toLowerCase()}</StatusChip>)}
          </div>
          <p className="max-w-[72ch] text-sm text-ink-700">{top.detail} The free checks run before every deploy and stop it on any failure; the live checks then measure Gemini, the reconciliation agent and the red team against the same golden cases.</p>
          {run && (
            <p className="flex flex-wrap items-center gap-x-2 gap-y-1 border-t border-sand-100 pt-4">
              <span className="text-xs font-medium text-ink-500">Latest run</span>
              <span className="code text-ink-700">{runMeta(run)}</span>
            </p>
          )}
        </KeyMoment>

        <Inventory models={data.models} />

        <Section title="Watched against people's decisions" description={`Over the last ${monitoring?.window_days ?? 30} days. A rate needs at least ten decisions; a High-tier model people agree with less than 60% of the time is paused.`}>
          {monitoring ? <Watching monitoring={monitoring} /> : (
            <LoadingRegion label="Loading monitoring" className="space-y-3 rounded-panel border border-sand-200 bg-white p-5 sm:p-6">
              <SkeletonText lines={3} />
            </LoadingRegion>
          )}
        </Section>
      </div>
    </>
  );
}
