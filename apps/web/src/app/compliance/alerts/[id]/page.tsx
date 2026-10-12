"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import { formatDate, formatUsd } from "@/lib/format";
import {
  citationLabels, EVIDENCE_KIND, SCENARIO_COPY, SEVERITY_LABEL, SEVERITY_TONE, STATE_LABEL, TRIAGE_COPY,
  type AlertDetail, type CaseReview,
} from "@/lib/compliance";
import { AiProse } from "@/components/ai-prose";
import { EntityGraph } from "@/components/entity-graph";
import { Badge, Button, Field, inputClass, Loading, Notice, PageHeader, Section } from "@/components/ui";

const msg = (e: unknown, fallback: string) => (e instanceof ApiError ? e.message : fallback);

function Review({ review, labels }: { review: CaseReview; labels: Record<string, string> }) {
  const problems = [
    review.unsupported_figures.length ? `${review.unsupported_figures.join(", ")} did not come from the evidence` : "",
    review.dropped_citations.length ? `${review.dropped_citations.length} citation${review.dropped_citations.length === 1 ? "" : "s"} to rows that are not in the evidence were removed` : "",
  ].filter(Boolean);
  return (
    <AiProse caption={`Written by ${review.model} from the alert, its evidence and the linked entities. A suggestion only: you decide.`}
      warning={review.verified ? undefined : `Check before relying on this: ${problems.join("; ")}.`}>
      <p><span className="font-semibold">Suggestion: {TRIAGE_COPY[review.triage]}.</span> {review.triage_reason}</p>
      {review.narrative.map((part, i) => (
        <p key={i} className="mt-3">
          {part.text}{" "}
          {part.evidence.map((id) => (
            <a key={id} href={`#ev-${id}`} className="num ml-0.5 align-super font-sans text-[11px] text-daylight-ink underline underline-offset-2">{labels[id]}</a>
          ))}
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
        <Section title="What monitoring found">
          <p className="max-w-[72ch] text-[15px]">{alert.summary}</p>
          {SCENARIO_COPY[alert.scenario] && <p className="mt-2 max-w-[72ch] text-sm text-muted">The rule: {SCENARIO_COPY[alert.scenario]}</p>}
        </Section>
        <Section title="Evidence" description="The exact rows behind the alert.">
          <ol className="divide-y divide-line border-y border-line text-sm">
            {alert.evidence.map((e) => (
              <li key={e.id} id={`ev-${e.id}`} className="grid scroll-mt-24 grid-cols-[2.25rem_minmax(0,1fr)] gap-x-3 py-3 target:bg-daylight-wash">
                <span className="num font-medium">{labels[e.id]}</span>
                <div className="min-w-0">
                  <div className="flex flex-wrap items-baseline justify-between gap-x-4">
                    <span className="text-muted">{EVIDENCE_KIND[e.kind] ?? e.kind}, {formatDate(e.date)}</span>
                    {e.amount && <span className="num font-medium">{formatUsd(e.amount)}</span>}
                  </div>
                  <p className="mt-0.5 text-[15px]">{e.detail}</p>
                </div>
              </li>
            ))}
          </ol>
        </Section>
        <Section title="Linked entities" description="People joined to the subject by a shared bank account, a shared device or an outside payer.">
          <EntityGraph nodes={alert.graph.nodes} edges={alert.graph.edges} />
        </Section>
        <Section title="Case review">
          {alert.ai_review ? <Review review={alert.ai_review} labels={labels} /> : (
            <div className="flex flex-wrap items-center gap-3">
              <Button variant="secondary" busy={busy === "review"} onClick={() => post("review", `/compliance/alerts/${alert.id}/review`, undefined, "The case review is unavailable right now.")}>
                Ask Gemini Pro for a case review
              </Button>
              <span className="text-xs text-muted">It reads the alert, its evidence and the linked entities, then suggests. It takes about half a minute.</span>
            </div>
          )}
        </Section>
        <Section title="Decision">
          {alert.state === "open" ? (
            <div className="max-w-xl space-y-3">
              <Field label="Your note" hint="The record of why. Escalating means filing a suspicious activity report.">
                <textarea className={`${inputClass} min-h-24`} value={note} maxLength={1000} onChange={(e) => setNote(e.target.value)} />
              </Field>
              {error && <Notice tone="error">{error}</Notice>}
              <div className="flex flex-wrap gap-2">
                <Button variant="danger" busy={busy === "escalate"} disabled={!note.trim() || Boolean(busy)}
                  onClick={() => post("escalate", `/compliance/alerts/${alert.id}/decide`, { decision: "escalate", note }, "Atrium could not record the decision.")}>Escalate</Button>
                <Button variant="secondary" busy={busy === "close"} disabled={!note.trim() || Boolean(busy)}
                  onClick={() => post("close", `/compliance/alerts/${alert.id}/decide`, { decision: "close", note }, "Atrium could not record the decision.")}>Close the alert</Button>
              </div>
            </div>
          ) : (
            <Notice tone={alert.state === "escalated" ? "caution" : "info"} title={`${STATE_LABEL[alert.state]} by ${alert.decided_by} on ${formatDate(alert.decided_at ?? alert.raised_at)}`}>
              {alert.decision_note}
            </Notice>
          )}
        </Section>
      </div>
    </>
  );
}
