"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import { formatDate, formatUsd } from "@/lib/format";
import {
  citationLabels, EVIDENCE_KIND, SCENARIO_COPY, SEVERITY_LABEL, SEVERITY_TONE, STATE_LABEL, thresholdBars, TRIAGE_COPY,
  type AlertDetail, type CaseReview, type EvidenceRow,
} from "@/lib/compliance";
import { AiProse } from "@/components/ai-prose";
import { EntityGraph } from "@/components/entity-graph";
import { Badge, Button, Field, inputClass, KeyMoment, Loading, Notice, PageHeader, Panel, Section } from "@/components/ui";

const msg = (e: unknown, fallback: string) => (e instanceof ApiError ? e.message : fallback);
const CHIP = "num inline-flex h-5 min-w-6 items-center justify-center rounded-[5px] bg-daylight-wash px-1 align-[2px] font-sans text-[11px] font-semibold text-daylight-ink no-underline hover:bg-daylight hover:text-ink";

function ThresholdChart({ evidence }: { evidence: EvidenceRow[] }) {
  const { bars, linePct } = thresholdBars(evidence, 10000);
  if (bars.length === 0) return null;
  const columns = { gridTemplateColumns: `repeat(${bars.length}, minmax(0, 1fr))` };
  return (
    <figure className="m-0">
      <div role="img" className="relative h-56 border-b border-line-strong"
        aria-label={`${bars.length} payments, ${bars.map((b) => `${formatUsd(b.amount)} on ${formatDate(b.date)}`).join(", ")}, each below the $10,000 reporting threshold`}>
        <div aria-hidden="true" className="absolute inset-x-0 border-t-2 border-dashed border-loss" style={{ bottom: `${linePct}%` }} />
        <span aria-hidden="true" className="num absolute right-0 bg-surface pl-2 text-xs font-semibold text-loss" style={{ bottom: `calc(${linePct}% + 6px)` }}>
          $10,000 reporting threshold
        </span>
        <div aria-hidden="true" className="absolute inset-0 grid items-end gap-6 px-4 sm:gap-12 sm:px-12" style={columns}>
          {bars.map((b) => <div key={b.id} className="rounded-t-[8px] bg-ink" style={{ height: `${b.pct}%` }} />)}
        </div>
      </div>
      <div className="mt-3 grid gap-6 px-4 sm:gap-12 sm:px-12" style={columns}>
        {bars.map((b) => (
          <span key={b.id} className="flex flex-col items-center text-center">
            <span className="num font-semibold">{formatUsd(b.amount)}</span>
            <span className="text-[13px] text-muted">{formatDate(b.date)} <a href={`#ev-${b.id}`} className={CHIP}>{b.label}</a></span>
          </span>
        ))}
      </div>
    </figure>
  );
}

function Review({ review, labels }: { review: CaseReview; labels: Record<string, string> }) {
  const problems = [
    review.unsupported_figures.length ? `${review.unsupported_figures.join(", ")} did not come from the evidence` : "",
    review.dropped_citations.length ? `${review.dropped_citations.length} citation${review.dropped_citations.length === 1 ? "" : "s"} to rows that are not in the evidence were removed` : "",
  ].filter(Boolean);
  return (
    <AiProse caption={`Written by ${review.model} from the alert, its evidence and the linked accounts. A suggestion only: you decide.`}
      warning={review.verified ? undefined : `Check before relying on this: ${problems.join("; ")}.`}>
      <p><span className="font-semibold">Suggestion: {TRIAGE_COPY[review.triage]}.</span> {review.triage_reason}</p>
      {review.narrative.map((part, i) => (
        <p key={i} className="mt-3">
          {part.text}{" "}
          {part.evidence.map((id) => <a key={id} href={`#ev-${id}`} className={`${CHIP} ml-0.5`}>{labels[id]}</a>)}
        </p>
      ))}
      {review.questions.length > 0 && (
        <>
          <p className="mt-4 font-semibold">Questions worth asking</p>
          <ul className="mt-1 list-disc space-y-1 pl-5">{review.questions.map((q, i) => <li key={i}>{q}</li>)}</ul>
        </>
      )}
    </AiProse>
  );
}

export default function AlertPage() {
  const { id } = useParams<{ id: string }>();
  const [alert, setAlert] = useState<AlertDetail | null>(null);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(async () => setAlert(await api<AlertDetail>(`/compliance/alerts/${id}`)), [id]);
  useEffect(() => {
    load().catch((e) => setError(msg(e, "Atrium could not load this alert. Try again.")));
  }, [load]);

  async function post(key: string, path: string, body: object | undefined, fallback: string) {
    setBusy(key);
    setError("");
    try {
      setAlert(await api<AlertDetail>(path, { method: "POST", body: body ? JSON.stringify(body) : undefined }));
    } catch (e) {
      setError(msg(e, fallback));
    } finally {
      setBusy("");
    }
  }

  if (!alert) return error ? <Notice tone="error">{error}</Notice> : <Loading label="Loading the alert" />;
  const labels = citationLabels(alert.evidence);
  return (
    <>
      <PageHeader title={alert.title} back={{ href: "/compliance", label: "Alerts" }}
        description={`${alert.person.name}${alert.account_number ? `, account ${alert.account_number}` : ""}. Raised ${formatDate(alert.raised_at)}.`}
        actions={<><Badge tone={SEVERITY_TONE[alert.severity]}>{SEVERITY_LABEL[alert.severity]} severity</Badge><Badge>{STATE_LABEL[alert.state]}</Badge></>} />
      <div className="space-y-10">
        <KeyMoment tone="alert" label="What monitoring found" title={alert.summary}>
          {alert.scenario === "structuring" && <ThresholdChart evidence={alert.evidence} />}
          {SCENARIO_COPY[alert.scenario] && <p className="max-w-[72ch] pt-2 text-sm text-muted">The rule: {SCENARIO_COPY[alert.scenario]}</p>}
        </KeyMoment>

        <div className="grid gap-6 lg:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)] lg:items-start">
          <Panel className="space-y-4 p-6">
            <div className="flex flex-wrap items-baseline justify-between gap-3">
              <h2 className="text-[17px] font-semibold">Case review</h2>
              {alert.ai_review?.verified && <Badge tone="gain">Figures and citations checked</Badge>}
            </div>
            {alert.ai_review ? <Review review={alert.ai_review} labels={labels} /> : (
              <div className="space-y-3">
                <p className="text-sm text-ink-2">Gemini Pro reads the alert, its evidence and the linked accounts, and suggests what to do. It takes about half a minute.</p>
                <Button variant="secondary" busy={busy === "review"} disabled={Boolean(busy)}
                  onClick={() => post("review", `/compliance/alerts/${alert.id}/review`, undefined, "The case review is unavailable right now.")}>
                  Ask Gemini Pro for a case review
                </Button>
              </div>
            )}
          </Panel>

          <Panel className="space-y-4 p-6">
            <h2 className="text-[17px] font-semibold">Your decision</h2>
            {alert.state === "open" ? (
              <>
                <Field label="Your note" hint="The record of why. Escalating means filing a suspicious activity report.">
                  <textarea className={`${inputClass} min-h-24`} value={note} maxLength={1000} onChange={(e) => setNote(e.target.value)} />
                </Field>
                {error && <Notice tone="error">{error}</Notice>}
                <div className="flex flex-wrap gap-2.5">
                  <Button variant="danger" busy={busy === "escalate"} disabled={!note.trim() || Boolean(busy)}
                    onClick={() => post("escalate", `/compliance/alerts/${alert.id}/decide`, { decision: "escalate", note }, "Atrium could not record the decision.")}>Escalate</Button>
                  <Button variant="secondary" busy={busy === "close"} disabled={!note.trim() || Boolean(busy)}
                    onClick={() => post("close", `/compliance/alerts/${alert.id}/decide`, { decision: "close", note }, "Atrium could not record the decision.")}>Close the alert</Button>
                </div>
              </>
            ) : (
              <Notice tone={alert.state === "escalated" ? "caution" : "info"} title={`${STATE_LABEL[alert.state]} by ${alert.decided_by} on ${formatDate(alert.decided_at ?? alert.raised_at)}`}>
                {alert.decision_note}
              </Notice>
            )}
          </Panel>
        </div>

        <Section title="Who is linked" description="People joined to the subject by a shared bank account, a shared device or an outside payer.">
          <Panel className="p-5 sm:p-6"><EntityGraph nodes={alert.graph.nodes} edges={alert.graph.edges} /></Panel>
        </Section>

        <Section title="Evidence" description="The exact rows behind the alert.">
          <ol className="rounded-panel border border-line bg-surface px-5 text-sm">
            {alert.evidence.map((e) => (
              <li key={e.id} id={`ev-${e.id}`} className="grid scroll-mt-24 grid-cols-[2.5rem_minmax(0,1fr)] gap-x-3 border-t border-line py-3.5 first:border-t-0 target:bg-daylight-wash">
                <span className="num font-semibold">{labels[e.id]}</span>
                <div className="min-w-0">
                  <div className="flex flex-wrap items-baseline justify-between gap-x-4">
                    <span className="text-muted">{EVIDENCE_KIND[e.kind] ?? e.kind}, {formatDate(e.date)}</span>
                    {e.amount && <span className="num font-semibold">{formatUsd(e.amount)}</span>}
                  </div>
                  <p className="mt-0.5 text-[15px]">{e.detail}</p>
                </div>
              </li>
            ))}
          </ol>
        </Section>
      </div>
    </>
  );
}
