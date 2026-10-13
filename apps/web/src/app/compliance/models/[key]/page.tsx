"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import { formatDate } from "@/lib/format";
import {
  agreementLine, canPause, caseValue, driftLine, GENERATIVE, MONITORED, STATUS_LABEL, STATUS_TONE, suiteTitle,
  type Breaker, type CaseRow, type ModelCard, type Monitoring, type Suite,
} from "@/lib/governance";
import { CodeField, DemoAuthenticator } from "@/components/step-up";
import { Badge, Button, Field, inputClass, KeyMoment, Loading, Notice, PageHeader, Panel, Section, tableStyles as t } from "@/components/ui";

const msg = (e: unknown, fallback: string) => (e instanceof ApiError ? e.message : fallback);
const OUTCOME = { pass: { label: "Pass", tone: "gain" }, fail: { label: "Fail", tone: "loss" }, error: { label: "No result", tone: "caution" } } as const;
const TIER_LABEL = { high: "High risk tier", medium: "Medium risk tier" } as const;

type Attack = { attack?: string; goal?: string; channel?: string; output?: unknown };
const asRecord = (v: unknown) => (v && typeof v === "object" && !Array.isArray(v) ? (v as Record<string, unknown>) : {});

function Outcome({ outcome }: { outcome: CaseRow["outcome"] }) {
  return <Badge tone={OUTCOME[outcome].tone}>{OUTCOME[outcome].label}</Badge>;
}

function SuiteHead({ suite, compare }: { suite: Suite; compare?: Suite }) {
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-2 text-sm">
      <Badge tone={suite.passed ? "gain" : suite.counts.pass + suite.counts.fail === 0 ? "caution" : "loss"}>
        {suite.passed ? "Meets its bar" : suite.counts.pass + suite.counts.fail === 0 ? "No result" : "Misses its bar"}
      </Badge>
      <span className="font-medium text-ink">{suite.metric}</span>
      {compare && <span className="text-ink-2">Pro, same alerts: {compare.metric}</span>}
      <span className="num text-muted">{suite.cost_usd > 0 ? `$${suite.cost_usd.toFixed(4)} of AI` : "No AI cost"}</span>
    </div>
  );
}

function CaseTable({ cases }: { cases: CaseRow[] }) {
  return (
    <>
      <ul className="divide-y divide-line border-y border-line md:hidden">
        {cases.map((c) => (
          <li key={c.case_id} className="space-y-1.5 py-3.5 text-sm">
            <p className="flex flex-wrap items-center gap-2"><Outcome outcome={c.outcome} /><span className="font-medium">{c.case_id}</span></p>
            <p className="wrap-break-word"><span className="text-muted">Expected </span>{caseValue(c.expected)}</p>
            <p className="wrap-break-word"><span className="text-muted">Got </span>{caseValue(c.actual)}</p>
            <p className="text-ink-2">{c.detail}</p>
          </li>
        ))}
      </ul>
      <CaseGrid cases={cases} />
    </>
  );
}

function CaseGrid({ cases }: { cases: CaseRow[] }) {
  return (
    <div className={`${t.wrap} hidden md:block`}>
      <table className={t.table}>
        <thead className={t.head}>
          <tr><th className={t.th}>Case</th><th className={t.th}>Outcome</th><th className={t.th}>Expected</th><th className={t.th}>Got</th><th className={t.th}>Why</th></tr>
        </thead>
        <tbody>
          {cases.map((c) => (
            <tr key={c.case_id} className={`${t.row} align-top`}>
              <td className={`${t.td} font-medium`}>{c.case_id}</td>
              <td className={t.td}><Outcome outcome={c.outcome} /></td>
              <td className={`${t.td} max-w-[22ch] wrap-break-word text-ink-2`}>{caseValue(c.expected)}</td>
              <td className={`${t.td} max-w-[26ch] wrap-break-word`}>{caseValue(c.actual)}</td>
              <td className={`${t.td} max-w-[48ch] text-ink-2`}>{c.detail}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function AttackList({ cases }: { cases: CaseRow[] }) {
  return (
    <ul className="space-y-3">
      {cases.map((c) => {
        const a = asRecord(c.actual) as Attack;
        return (
          <li key={c.case_id} className="rounded-panel border border-line px-5 py-4">
            {a.attack && (
              <blockquote className="border-l-2 border-line-strong pl-3 text-sm italic text-ink-2">
                “{a.attack}”{a.channel && <span className="not-italic text-muted"> in the {a.channel.replace("_", " ")}</span>}
              </blockquote>
            )}
            <div className="mt-3 flex flex-wrap items-center gap-2 text-sm">
              <Outcome outcome={c.outcome} />
              <span className="font-medium">{c.case_id}</span>
            </div>
            <p className="mt-1.5 text-sm text-ink-2">{c.detail}</p>
            {a.output !== undefined && <p className="mt-1.5 wrap-break-word text-xs text-muted">The target answered: {caseValue(a.output)}</p>}
          </li>
        );
      })}
    </ul>
  );
}

function FairnessList({ cases }: { cases: CaseRow[] }) {
  return (
    <ul className="divide-y divide-line border-y border-line">
      {cases.map((c) => {
        const actual = asRecord(c.actual);
        const differing = (actual.differing as Record<string, unknown>[] | undefined) ?? [];
        const scores = (actual.scores as { score: number; variants: string[] }[] | undefined) ?? [];
        const pairs = typeof actual.pairs === "number" ? `${actual.identical} of ${actual.pairs} name pairs read the same` : "";
        const result = scores.length
          ? scores.map((s) => `score ${s.score} for ${s.variants.length} variant${s.variants.length === 1 ? "" : "s"}`).join("; ")
          : pairs;
        return (
          <li key={c.case_id} className="py-3 text-sm">
            <p className="flex flex-wrap items-center gap-x-3 gap-y-1">
              <Outcome outcome={c.outcome} /><span className="font-medium">{c.case_id}</span>
              {result && <span className="text-ink-2">{result.charAt(0).toUpperCase() + result.slice(1)}</span>}
            </p>
            {c.outcome !== "pass" && <p className="mt-1.5 text-ink-2">{c.detail}</p>}
            {differing.map((pair, i) => (
              <div key={i} className="mt-3 grid gap-3 sm:grid-cols-2">
                {Object.entries(pair).map(([name, reading]) => (
                  <div key={name} className="rounded-control border border-line bg-ground px-3 py-2 text-sm">
                    <p className="font-medium">{name}</p>
                    <p className="mt-0.5 wrap-break-word text-ink-2">{caseValue(reading)}</p>
                  </div>
                ))}
              </div>
            ))}
          </li>
        );
      })}
    </ul>
  );
}

function SuiteSection({ suite, all }: { suite: Suite; all: Suite[] }) {
  const compare = suite.kind === "challenger"
    ? all.find((s) => s.kind === "golden" && s.tier === "live") : undefined;
  return (
    <Section title={suiteTitle(suite.kind, suite.tier)} description={`The bar: ${suite.bar}.`}>
      <div className="space-y-4">
        <SuiteHead suite={suite} compare={compare} />
        {suite.cases.length === 0 ? <p className="text-sm text-muted">No cases were stored for this suite.</p>
          : suite.kind === "red_team" ? <AttackList cases={suite.cases} />
            : suite.kind === "fairness" ? <FairnessList cases={suite.cases} />
              : <CaseTable cases={suite.cases} />}
      </div>
    </Section>
  );
}

function BreakerPanel({ modelKey, breaker, pausable, onChange }:
  { modelKey: string; breaker: Breaker; pausable: boolean; onChange: () => Promise<void> }) {
  const [reason, setReason] = useState("");
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const open = breaker.state === "open";

  async function change() {
    setBusy(true);
    setError("");
    try {
      await api(`/governance/breakers/${modelKey}/${open ? "reset" : "open"}`, {
        method: "POST", body: JSON.stringify(open ? { reason, code } : { reason }),
      });
      setReason("");
      setCode("");
      await onChange();
    } catch (e) {
      setError(msg(e, open ? "The breaker could not be reset. Try again." : "The model could not be paused. Try again."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Panel className="space-y-5 p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-[17px] font-semibold">Breaker</h2>
        <Badge tone={open ? "loss" : "gain"}>{open ? "Open: the model is paused" : "Closed: the model is running"}</Badge>
      </div>
      {breaker.message && <Notice tone="caution">{breaker.message}</Notice>}
      {!open && !pausable ? (
        <p className="text-sm text-ink-2">Nothing can stand in for this model, so pausing it would change nothing. When a check fails, it shows Failing instead.</p>
      ) : (
        <div className="grid gap-4 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-end">
          <Field label={open ? "Why it can run again" : "Why pause it"} hint="Kept in the model's history and the decision log.">
            <input className={inputClass} value={reason} maxLength={500} onChange={(e) => setReason(e.target.value)} />
          </Field>
          {!open && <Button variant="danger" busy={busy} disabled={!reason.trim()} onClick={change}>Pause this model</Button>}
        </div>
      )}
      {open && (
        <div className="space-y-3">
          <Field label="Code from your authenticator" hint="A reset needs a one-time code, as four-eyes approvals do.">
            <CodeField value={code} onChange={setCode} />
          </Field>
          <DemoAuthenticator onUse={setCode} />
          <Button busy={busy} disabled={!reason.trim() || code.length !== 6} onClick={change}>Reset the breaker</Button>
        </div>
      )}
      {error && <Notice tone="error">{error}</Notice>}
      {breaker.history.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold">History</h3>
          <ul className="mt-2 divide-y divide-line border-y border-line text-sm">
            {[...breaker.history].reverse().map((h, i) => (
              <li key={i} className="flex flex-wrap gap-x-3 gap-y-1 py-2.5">
                <Badge tone={h.state === "open" ? "loss" : "gain"}>{h.state === "open" ? "Paused" : "Reset"}</Badge>
                <span className="text-ink-2">{h.reason}</span>
                <span className="text-muted">{h.by}, {formatDate(h.at)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </Panel>
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

  if (!card) return error ? <Notice tone="error">{error}</Notice> : <Loading label="Loading the model" />;
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
      <div className="space-y-10">
        <KeyMoment tone={top.tone} label="Validation" title={top.title}>
          {card.changed_since_validation && (
            <Notice tone="caution" title="Changed since validation">
              Its prompt, schema, rules or model changed after the last run checked it (version {card.version}, checked {card.validated_version}). The next run will check this version.
            </Notice>
          )}
        </KeyMoment>

        <Panel className="grid gap-6 p-6 md:grid-cols-2">
          <div className="space-y-4 text-sm">
            <div><p className="text-muted">Owner</p><p className="mt-0.5 font-medium">{card.owner}</p></div>
            <div><p className="text-muted">Human gate</p><p className="mt-0.5">{card.human_gate}</p></div>
            <div><p className="text-muted">While its breaker is open</p><p className="mt-0.5">{card.fallback ?? "Nothing can stand in; it shows Failing instead."}</p></div>
            <div>
              <p className="text-muted">Version</p>
              <p className="num mt-0.5">{card.version}{card.validated_version && card.validated_version !== card.version ? `, validated version ${card.validated_version}` : ""}</p>
            </div>
          </div>
          <div className="text-sm">
            <p className="text-muted">Known limitations</p>
            <ul className="mt-1.5 list-disc space-y-1.5 pl-5">{card.limitations.map((l) => <li key={l}>{l}</li>)}</ul>
          </div>
        </Panel>

        {card.suites.length === 0 ? (
          <Notice title="No evidence yet">No run has checked this model yet. The free checks run with every deploy; the live checks start after it.</Notice>
        ) : ordered(card.suites).map((s) => <SuiteSection key={`${s.kind}-${s.tier}-${s.bar}`} suite={s} all={card.suites} />)}

        {watch && (
          <Section title="Watched against people's decisions" description={`Over the last ${monitoring?.window_days ?? 30} days.`}>
            <Panel className="px-5 py-4 text-sm text-ink-2">{watch}</Panel>
          </Section>
        )}

        <BreakerPanel modelKey={card.key} breaker={card.breaker} pausable={canPause(card)} onChange={load} />
      </div>
    </>
  );
}
