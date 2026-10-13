"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import { formatDate } from "@/lib/format";
import {
  agreementLine, canPause, caseValue, driftLine, GENERATIVE, MONITORED, passShare, STATUS_LABEL, STATUS_TONE, suiteStatus, suiteTitle,
  type Breaker, type CaseRow, type ModelCard, type Monitoring, type Suite,
} from "@/lib/governance";
import { CountUp } from "@/components/motion";
import { Skeleton, SkeletonText } from "@/components/skeleton";
import { CodeField, DemoAuthenticator } from "@/components/step-up";
import { Badge, Button, Field, inputClass, KeyMoment, Notice, PageHeader, Section } from "@/components/ui";
import { Arrive, Bar, Confirmed, StatusChip, tbl } from "../../../operations/_parts";
import { DetailHeaderSkeleton, LoadingRegion, MomentSkeleton, SectionTitleSkeleton } from "../../../operations/_skeletons";

const msg = (e: unknown, fallback: string) => (e instanceof ApiError ? e.message : fallback);
const OUTCOME = { pass: { label: "Pass", tone: "gain" }, fail: { label: "Fail", tone: "loss" }, error: { label: "No result", tone: "caution" } } as const;
const TIER_LABEL = { high: "High risk tier", medium: "Medium risk tier" } as const;

type Attack = { attack?: string; goal?: string; channel?: string; output?: unknown };
const asRecord = (v: unknown) => (v && typeof v === "object" && !Array.isArray(v) ? (v as Record<string, unknown>) : {});

function Outcome({ outcome }: { outcome: CaseRow["outcome"] }) {
  return <StatusChip tone={OUTCOME[outcome].tone}>{OUTCOME[outcome].label}</StatusChip>;
}

/** The suite's bar: the share of its cases that passed, in green on a sand track (coral when it misses its bar). */
function SuiteMeter({ suite, compare }: { suite: Suite; compare?: Suite }) {
  const share = passShare(suite.counts);
  const status = suiteStatus(suite);
  return (
    <div className="space-y-2.5">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <span className="flex items-baseline gap-2">
          <span className="num text-[30px] font-medium leading-[34px] tracking-[-0.02em]"><CountUp text={`${share}%`} /></span>
          <span className="text-sm text-ink-700">{suite.metric}</span>
        </span>
        <span className="code text-ink-500">{suite.cost_usd > 0 ? `$${suite.cost_usd.toFixed(4)}` : "$0.0000 · no AI cost"}</span>
      </div>
      <Bar pct={share} tone={status.tone} label={`${share}% of cases passed`} />
      {compare && <p className="text-[13px] text-ink-500">Pro on the same alerts: {compare.metric}</p>}
    </div>
  );
}

/** A suite's cases; the first dozen arrive one after another, the rest with the twelfth. */
function CaseTable({ cases }: { cases: CaseRow[] }) {
  return (
    <>
      <ul className="divide-y divide-sand-100 md:hidden">
        {cases.map((c, i) => (
          <Arrive as="li" index={i} key={c.case_id} className="space-y-1.5 py-3 text-sm">
            <p className="flex flex-wrap items-center gap-2"><Outcome outcome={c.outcome} /><span className={tbl.id}>{c.case_id}</span></p>
            <p className="wrap-break-word"><span className="text-ink-500">Expected </span>{caseValue(c.expected)}</p>
            <p className="wrap-break-word"><span className="text-ink-500">Got </span>{caseValue(c.actual)}</p>
            <p className="text-ink-700">{c.detail}</p>
          </Arrive>
        ))}
      </ul>
      <div className={`${tbl.wrap} hidden md:block`}>
        <table className={tbl.table}>
          <thead className={tbl.head}>
            <tr><th className={tbl.th}>Case</th><th className={tbl.th}>Outcome</th><th className={tbl.th}>Expected</th><th className={tbl.th}>Got</th><th className={tbl.th}>Why</th></tr>
          </thead>
          <tbody>
            {cases.map((c, i) => (
              <Arrive as="tr" index={i} key={c.case_id} className={`${tbl.row} align-top`}>
                <td className={`${tbl.td} ${tbl.id}`}>{c.case_id}</td>
                <td className={tbl.td}><Outcome outcome={c.outcome} /></td>
                <td className={`${tbl.td} max-w-[22ch] wrap-break-word text-ink-700`}>{caseValue(c.expected)}</td>
                <td className={`${tbl.td} max-w-[26ch] wrap-break-word`}>{caseValue(c.actual)}</td>
                <td className={`${tbl.td} max-w-[48ch] text-ink-700`}>{c.detail}</td>
              </Arrive>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

function AttackList({ cases }: { cases: CaseRow[] }) {
  return (
    <ul className="space-y-2">
      {cases.map((c, i) => {
        const a = asRecord(c.actual) as Attack;
        return (
          <Arrive as="li" index={i} key={c.case_id} className="rounded-control bg-fill px-4 py-3.5">
            <div className="flex flex-wrap items-center gap-2 text-sm">
              <Outcome outcome={c.outcome} />
              <span className={tbl.id}>{c.case_id}</span>
              {a.channel && <span className="text-xs text-ink-500">in the {a.channel.replace("_", " ")}</span>}
            </div>
            {a.attack && <p className="mt-2 font-mono text-xs leading-5 text-ink-700 wrap-break-word">“{a.attack}”</p>}
            <p className="mt-2 text-sm text-ink-700">{c.detail}</p>
            {a.output !== undefined && <p className="mt-1.5 wrap-break-word text-xs text-ink-500">The target answered: {caseValue(a.output)}</p>}
          </Arrive>
        );
      })}
    </ul>
  );
}

function FairnessList({ cases }: { cases: CaseRow[] }) {
  return (
    <ul className="divide-y divide-sand-100">
      {cases.map((c, i) => {
        const actual = asRecord(c.actual);
        const differing = (actual.differing as Record<string, unknown>[] | undefined) ?? [];
        const scores = (actual.scores as { score: number; variants: string[] }[] | undefined) ?? [];
        const pairs = typeof actual.pairs === "number" ? `${actual.identical} of ${actual.pairs} name pairs read the same` : "";
        const result = scores.length
          ? scores.map((s) => `score ${s.score} for ${s.variants.length} variant${s.variants.length === 1 ? "" : "s"}`).join("; ")
          : pairs;
        return (
          <Arrive as="li" index={i} key={c.case_id} className="py-3 text-sm">
            <p className="flex flex-wrap items-center gap-x-3 gap-y-1">
              <Outcome outcome={c.outcome} /><span className={tbl.id}>{c.case_id}</span>
              {result && <span className="text-ink-700">{result.charAt(0).toUpperCase() + result.slice(1)}</span>}
            </p>
            {c.outcome !== "pass" && <p className="mt-1.5 text-ink-700">{c.detail}</p>}
            {differing.map((pair, i) => (
              <div key={i} className="mt-3 grid gap-3 sm:grid-cols-2">
                {Object.entries(pair).map(([name, reading]) => (
                  <div key={name} className="rounded-control bg-fill px-3 py-2 text-sm">
                    <p className="font-medium">{name}</p>
                    <p className="mt-0.5 wrap-break-word text-ink-700">{caseValue(reading)}</p>
                  </div>
                ))}
              </div>
            ))}
          </Arrive>
        );
      })}
    </ul>
  );
}

/** One suite as an outlined card: its title and chip, the bar it must meet, the pass share as a bar, then its cases. */
function SuiteCard({ suite, all }: { suite: Suite; all: Suite[] }) {
  const compare = suite.kind === "challenger" ? all.find((s) => s.kind === "golden" && s.tier === "live") : undefined;
  const status = suiteStatus(suite);
  return (
    <section className="min-w-0 space-y-5 rounded-panel border border-sand-200 bg-white p-5 sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="text-base font-semibold">{suiteTitle(suite.kind, suite.tier)}</h3>
          <p className="mt-0.5 max-w-[72ch] text-[13px] text-ink-500">The bar: {suite.bar}.</p>
        </div>
        <StatusChip tone={status.tone}>{status.label}</StatusChip>
      </div>
      <SuiteMeter suite={suite} compare={compare} />
      {suite.cases.length === 0 ? <p className="text-sm text-ink-500">No cases were stored for this suite.</p>
        : suite.kind === "red_team" ? <AttackList cases={suite.cases} />
          : suite.kind === "fairness" ? <FairnessList cases={suite.cases} />
            : <CaseTable cases={suite.cases} />}
    </section>
  );
}

function BreakerPanel({ modelKey, breaker, pausable, onChange }:
  { modelKey: string; breaker: Breaker; pausable: boolean; onChange: () => Promise<void> }) {
  const [reason, setReason] = useState("");
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [changed, setChanged] = useState<"reset" | "paused" | null>(null);  // what just went through: it confirms
  const open = breaker.state === "open";

  async function change() {
    setBusy(true);
    setError("");
    setChanged(null);
    try {
      await api(`/governance/breakers/${modelKey}/${open ? "reset" : "open"}`, {
        method: "POST", body: JSON.stringify(open ? { reason, code } : { reason }),
      });
      setReason("");
      setCode("");
      setChanged(open ? "reset" : "paused");
      await onChange();
    } catch (e) {
      setError(msg(e, open ? "The breaker could not be reset. Try again." : "The model could not be paused. Try again."));
    } finally {
      setBusy(false);
    }
  }

  const missing = !reason.trim() ? "Say why it can run again first." : code.length !== 6 ? "Then enter all six digits of the code." : "";
  return (
    <section aria-labelledby="breaker" className="space-y-5 rounded-panel border border-sand-200 bg-white p-5 sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id="breaker" className="text-base font-semibold">Breaker</h2>
        <StatusChip tone={open ? "loss" : "gain"}>{open ? "Open: the model is paused" : "Closed: the model is running"}</StatusChip>
      </div>
      {changed === "reset" && !open && <Confirmed>Breaker reset: the model is running again, and the reset is in its history.</Confirmed>}
      {changed === "paused" && open && <Confirmed tone="neutral">Paused: its fallback stands in until someone resets the breaker.</Confirmed>}
      {breaker.message && <Notice tone="error" title="Paused">{breaker.message}</Notice>}
      {!open && !pausable ? (
        <p className="text-sm text-ink-700">Nothing can stand in for this model, so pausing it would change nothing. When a check fails, it shows Failing instead.</p>
      ) : (
        <div className="grid max-w-[720px] gap-4 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-end">
          <Field label={open ? "Why it can run again" : "Why pause it"} hint="Kept in the model's history and the decision log.">
            <input className={inputClass} value={reason} maxLength={500} onChange={(e) => setReason(e.target.value)} />
          </Field>
          {!open && <Button variant="danger" busy={busy} disabled={!reason.trim()} onClick={change}>Pause this model</Button>}
        </div>
      )}
      {open && (
        <div className="space-y-3">
          <div className="space-y-2">
            <span className="block text-[13px] font-medium">Code from your authenticator</span>
            <span className="block text-xs text-ink-500">A reset needs a one-time code, as two-person approvals do.</span>
            <div className="flex flex-wrap items-center gap-2">
              <CodeField value={code} onChange={setCode} />
              <Button busy={busy} disabled={Boolean(missing)} onClick={change}>Reset the breaker</Button>
            </div>
            {missing && <p className="text-xs text-ink-500">{missing}</p>}
          </div>
          <DemoAuthenticator onUse={setCode} />
        </div>
      )}
      {error && <Notice tone="error">{error}</Notice>}
      {breaker.history.length > 0 && (
        <div>
          <h3 className="text-[13px] font-medium text-ink-500">History</h3>
          <ul className="mt-2 divide-y divide-sand-100 border-t border-sand-100 text-sm">
            {[...breaker.history].reverse().map((h, i) => (
              <li key={i} className="flex flex-wrap items-center gap-x-3 gap-y-1.5 py-2.5">
                <StatusChip tone={h.state === "open" ? "loss" : "gain"}>{h.state === "open" ? "Paused" : "Reset"}</StatusChip>
                <span className="text-xs text-ink-500 sm:order-last">{h.by}, {formatDate(h.at)}</span>
                <span className="w-full text-ink-700 sm:w-auto sm:min-w-0 sm:flex-1">{h.reason}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}

const KIND_ORDER = { golden: 0, fairness: 1, red_team: 2, challenger: 3 } as const;

/** Golden cases first, then fair lending, the red team and the challenger; the free tier before the live. */
function ordered(suites: Suite[]): Suite[] {
  return [...suites].sort((a, b) => KIND_ORDER[a.kind] - KIND_ORDER[b.kind] || (a.tier === b.tier ? 0 : a.tier === "free" ? -1 : 1));
}

function moment(card: ModelCard): { tone: "good" | "alert" | "attention" | "info"; title: string } {
  const failing = card.suites.filter((s) => !s.passed && s.counts.pass + s.counts.fail > 0);
  switch (card.status) {
    case "validated":
      return { tone: "good", title: `Validated${card.last_validated_at ? ` on ${formatDate(card.last_validated_at)}` : ""}: every check met its bar.` };
    case "breaker_open":
      return { tone: "alert", title: card.breaker.message ?? "Paused: its breaker is open." };
    case "failing":
      return { tone: "alert", title: `Failing: ${failing.map((s) => `${suiteTitle(s.kind, s.tier).toLowerCase()} missed its bar`).join("; ") || "a check missed its bar"}.` };
    case "no_result":
      return { tone: "attention", title: "No result: the model could not be reached in the last run." };
    case "not_validated":
      return { tone: "attention", title: "Not validated yet: its checks have not run since they were added." };
    default:
      return { tone: "info", title: "Monitored only: no checks are written for this model yet." };
  }
}

function Fact({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid gap-1 py-3 sm:grid-cols-[11rem_minmax(0,1fr)] sm:gap-4">
      <dt className="text-[13px] text-ink-500">{label}</dt>
      <dd className="min-w-0 text-sm">{children}</dd>
    </div>
  );
}

/** One suite's card while it loads: its title and chip, the pass share and its bar, then a few cases. */
function SuiteSkeleton() {
  return (
    <div className="space-y-5 rounded-panel border border-sand-200 bg-white p-5 sm:p-6">
      <span className="flex items-start justify-between gap-3">
        <span className="flex flex-col gap-2"><Skeleton className="h-4 w-36" /><Skeleton className="h-3 w-72 max-w-[70vw]" /></span>
        <Skeleton className="h-[26px] w-28 rounded-full" />
      </span>
      <span className="flex flex-col gap-2.5">
        <span className="flex items-baseline gap-2"><Skeleton className="h-8 w-20 rounded-[10px]" /><Skeleton className="h-3.5 w-32" /></span>
        <Skeleton className="h-2 w-full rounded-full" />
      </span>
      <div className="divide-y divide-sand-100">
        {[0, 1, 2].map((i) => (
          <span key={i} className="flex items-center gap-4 py-3"><Skeleton className="h-3 w-28" /><Skeleton className="h-[26px] w-14 rounded-full" /><Skeleton className="h-3.5 flex-1" /></span>
        ))}
      </div>
    </div>
  );
}

/** A model card while it loads: header, the validation sentence, its facts and limitations, the suites, the breaker. */
function ModelCardSkeleton() {
  return (
    <LoadingRegion label="Loading the model">
      <DetailHeaderSkeleton badges={3} />
      <div className="space-y-12">
        <MomentSkeleton />
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)] xl:items-start">
          <div className="divide-y divide-sand-100 rounded-panel border border-sand-200 bg-white px-5 py-2 sm:px-6">
            {[0, 1, 2, 3].map((i) => <span key={i} className="grid gap-2 py-3.5 sm:grid-cols-[11rem_minmax(0,1fr)] sm:gap-4"><Skeleton className="h-3 w-24" /><Skeleton className="h-3.5 w-4/5" /></span>)}
          </div>
          <div className="flex flex-col gap-3 rounded-panel border border-sand-200 bg-white p-5 sm:p-6"><Skeleton className="h-3 w-32" /><SkeletonText lines={3} /></div>
        </div>
        <div>
          <SectionTitleSkeleton width="w-28" />
          <div className="space-y-4"><SuiteSkeleton /><SuiteSkeleton /></div>
        </div>
      </div>
    </LoadingRegion>
  );
}

export default function ModelCardPage() {
  const { key } = useParams<{ key: string }>();
  const [card, setCard] = useState<ModelCard | null>(null);
  const [monitoring, setMonitoring] = useState<Monitoring | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    const [found, watched] = await Promise.all([api<ModelCard>(`/governance/models/${key}`), api<Monitoring>("/governance/monitoring")]);
    setCard(found);
    setMonitoring(watched);
  }, [key]);
  useEffect(() => {
    load().catch((e) => setError(msg(e, "Atrium could not load this model. Try again.")));
  }, [load]);

  if (!card) return error ? <Notice tone="error">{error}</Notice> : <ModelCardSkeleton />;
  const top = moment(card);
  const watch = monitoring && MONITORED.has(card.key) ? agreementLine(card.key, monitoring.agreement[card.key], monitoring.window_days)
    : monitoring && card.key === "lead_score" ? driftLine(monitoring.drift.lead_score)
      : monitoring && card.key === "aml_anomaly" ? `${monitoring.drift.aml_anomaly.note}.` : null;
  return (
    <>
      <PageHeader title={card.name} back={{ href: "/compliance/models", label: "Models" }} description={card.purpose}
        actions={<>
          <Badge tone={STATUS_TONE[card.status]}>{STATUS_LABEL[card.status]}</Badge>
          <Badge tone={GENERATIVE.has(card.kind) ? "ai" : "neutral"}>{card.kind_label}</Badge>
          <Badge>{TIER_LABEL[card.tier]}</Badge>
        </>} />
      <div className="space-y-12">
        <KeyMoment tone={top.tone} label="Validation" title={top.title}>
          {card.changed_since_validation && (
            <Notice tone="caution" title="Changed since validation">
              Its prompt, schema, rules or model changed after the last run checked it (version <span className="code">{card.version}</span>, checked <span className="code">{card.validated_version}</span>). The next run will check this version.
            </Notice>
          )}
        </KeyMoment>

        <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)] xl:items-start">
          <section className="min-w-0 rounded-panel border border-sand-200 bg-white px-5 py-2 sm:px-6">
            <h2 className="sr-only">About this model</h2>
            <dl className="divide-y divide-sand-100">
              <Fact label="Owner">{card.owner}</Fact>
              <Fact label="Human gate">{card.human_gate}</Fact>
              <Fact label="While its breaker is open">{card.fallback ?? "Nothing can stand in; it shows Failing instead."}</Fact>
              <Fact label="Version">
                <span className="code text-ink-700">{card.version}</span>
                {card.validated_version && card.validated_version !== card.version && <span className="text-ink-500">, validated version <span className="code">{card.validated_version}</span></span>}
              </Fact>
            </dl>
          </section>
          <section className="min-w-0 rounded-panel border border-sand-200 bg-white p-5 sm:p-6">
            <h2 className="text-[13px] font-medium text-ink-500">Known limitations</h2>
            <ul className="mt-2 list-disc space-y-1.5 pl-5 text-sm marker:text-ink-400">{card.limitations.map((l) => <li key={l}>{l}</li>)}</ul>
          </section>
        </div>

        <Section title="Evidence" description="Each suite the latest runs checked, with the bar it has to meet.">
          {card.suites.length === 0 ? (
            <Notice title="No evidence yet">No run has checked this model yet. The free checks run with every deploy; the live checks start after it.</Notice>
          ) : (
            <div className="space-y-4">{ordered(card.suites).map((s) => <SuiteCard key={`${s.kind}-${s.tier}-${s.bar}`} suite={s} all={card.suites} />)}</div>
          )}
        </Section>

        {watch && (
          <Section title="Watched against people's decisions" description={`Over the last ${monitoring?.window_days ?? 30} days.`}>
            <div className="flex items-start gap-3 rounded-panel border border-sand-200 bg-white px-5 py-4 text-sm text-ink-700 sm:px-6">
              <span aria-hidden="true" className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-green-500" />{watch}
            </div>
          </Section>
        )}

        <BreakerPanel modelKey={card.key} breaker={card.breaker} pausable={canPause(card)} onChange={load} />
      </div>
    </>
  );
}
