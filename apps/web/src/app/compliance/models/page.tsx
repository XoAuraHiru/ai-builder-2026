"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { api, ApiError } from "@/lib/api";
import { formatDate } from "@/lib/format";
import {
  agreementLine, clockUtc, driftLine, GENERATIVE, headline, MONITORED, runLine, STATUS_LABEL, STATUS_TONE,
  type ModelRow, type ModelsOut, type Monitoring, type RunRow,
} from "@/lib/governance";
import { Badge, Button, KeyMoment, Loading, Notice, PageHeader, Panel, Section, tableStyles as t } from "@/components/ui";

const msg = (e: unknown, fallback: string) => (e instanceof ApiError ? e.message : fallback);
const POLL_MS = 10_000;
const TIER_LABEL = { high: "High", medium: "Medium" } as const;

function KindBadge({ model }: { model: ModelRow }) {
  return <Badge tone={GENERATIVE.has(model.kind) ? "ai" : "neutral"}>{model.kind_label}</Badge>;
}

function StatusCell({ model }: { model: ModelRow }) {
  return (
    <span className="flex flex-wrap items-center gap-1.5">
      <Badge tone={STATUS_TONE[model.status]}>{STATUS_LABEL[model.status]}</Badge>
      {model.changed_since_validation && <Badge tone="caution">Changed since validation</Badge>}
    </span>
  );
}

function validatedOn(model: ModelRow) {
  return model.last_validated_at ? formatDate(model.last_validated_at) : "Never";
}

function Inventory({ models }: { models: ModelRow[] }) {
  return (
    <>
      <div className={`${t.wrap} hidden md:block`}>
        <table className={t.table}>
          <thead className={t.head}>
            <tr>
              <th className={t.th}>Model</th><th className={t.th}>Kind</th><th className={t.th}>Risk tier</th>
              <th className={t.th}>Owner</th><th className={t.th}>Status</th><th className={`${t.th} text-right`}>Last validated</th>
            </tr>
          </thead>
          <tbody>
            {models.map((m) => (
              <tr key={m.key} className={t.row}>
                <td className={t.td}><Link href={`/compliance/models/${m.key}`} className="font-medium hover:underline">{m.name}</Link></td>
                <td className={t.td}><KindBadge model={m} /></td>
                <td className={t.td}>{TIER_LABEL[m.tier]}</td>
                <td className={`${t.td} text-ink-2`}>{m.owner}</td>
                <td className={t.td}><StatusCell model={m} /></td>
                <td className={`${t.td} num whitespace-nowrap text-right text-ink-2`}>{validatedOn(m)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <ul className="divide-y divide-line border-y border-line md:hidden">
        {models.map((m) => (
          <li key={m.key}>
            <Link href={`/compliance/models/${m.key}`} className="group block py-4">
              <span className="flex items-baseline justify-between gap-3">
                <span className="font-medium group-hover:underline">{m.name}</span>
                <span className="text-xs text-muted">{TIER_LABEL[m.tier]} tier</span>
              </span>
              <span className="mt-2 flex flex-wrap items-center gap-1.5"><KindBadge model={m} /><StatusCell model={m} /></span>
              <span className="mt-1.5 block text-sm text-ink-2">
                {m.owner} · {m.last_validated_at ? `checked ${formatDate(m.last_validated_at)}` : "not checked yet"}
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </>
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
    <Panel className="divide-y divide-line">
      {lines.map((l) => (
        <Link key={l.key} href={l.href} className="flex items-start gap-3 px-5 py-3.5 text-sm text-ink-2 hover:text-ink">
          <span aria-hidden="true" className="mt-1.75 h-1.5 w-1.5 shrink-0 rounded-xs bg-ink-2" />{l.text}
        </Link>
      ))}
    </Panel>
  );
}

export default function ModelsPage() {
  const [data, setData] = useState<ModelsOut | null>(null);
  const [monitoring, setMonitoring] = useState<Monitoring | null>(null);
  const [running, setRunning] = useState<RunRow | null>(null);
  const [refused, setRefused] = useState("");
  const [done, setDone] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    const [models, watched] = await Promise.all([api<ModelsOut>("/governance/models"), api<Monitoring>("/governance/monitoring")]);
    setData(models);
    setMonitoring(watched);
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
        const [latest] = await api<RunRow[]>("/governance/runs?limit=1");
        if (!latest || latest.status !== "running") {
          clearInterval(timer);
          await load();
          if (latest) setDone(runLine(latest));
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
    setDone("");
    try {
      const run = await api<RunRow>("/governance/evals/run", { method: "POST" });
      if (run.status === "running") {
        setRunning(run);
      } else {
        await load();
        setDone(runLine(run));
      }
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) setRefused(e.message);
      else setError(msg(e, "The live checks could not be started. Try again."));
    } finally {
      setBusy(false);
    }
  }

  const action = (
    <Button variant="secondary" busy={busy} disabled={Boolean(running) || Boolean(refused)} onClick={start}>
      {running ? `Live checks running since ${clockUtc(running.started_at)}` : "Run the live checks"}
    </Button>
  );
  const head = (
    <PageHeader title="Models" actions={action}
      description="Every model in Atrium, validated before and after each deploy, attacked by a red team, checked for fair lending, and watched against people's decisions." />
  );
  if (!data) return <>{head}{error ? <Notice tone="error">{error}</Notice> : <Loading label="Loading the models" />}</>;

  const top = headline(data.models, data.last_run);
  const open = data.models.some((m) => m.status === "breaker_open");
  const tone = top.title === "Every model is validated." ? "good" : open ? "alert" : "attention";
  return (
    <>
      {head}
      <div className="space-y-10">
        {(refused || error || done) && (
          <div className="space-y-3">
            {refused && <Notice tone="caution" title="The live checks cannot start yet">{refused}</Notice>}
            {error && <Notice tone="error">{error}</Notice>}
            {done && <Notice tone="success" title="The checks finished">{done}.</Notice>}
          </div>
        )}
        <KeyMoment tone={tone} label="Model risk" title={top.title}>
          <p className="max-w-[72ch] text-sm text-ink-2">{top.detail} The free checks run before every deploy and stop it on any failure; the live checks then measure Gemini, the reconciliation agent and the red team against the same golden cases.</p>
        </KeyMoment>

        <Section title="Inventory" description="Each model once, with its risk tier, its owner and what its latest evidence says. A model without checks is monitored only, never shown as validated.">
          <Inventory models={data.models} />
        </Section>

        <Section title="Watched against people's decisions" description={`Over the last ${monitoring?.window_days ?? 30} days. A rate needs at least ten decisions; a High-tier model people agree with less than 60% of the time is paused.`}>
          {monitoring ? <Watching monitoring={monitoring} /> : <Loading label="Loading monitoring" />}
        </Section>
      </div>
    </>
  );
}
