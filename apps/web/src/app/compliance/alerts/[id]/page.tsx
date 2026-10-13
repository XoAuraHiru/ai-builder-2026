"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import { formatDate, formatUsd } from "@/lib/format";
import { motion } from "motion/react";
import {
  alertFindings, CASE_REVIEW_STEPS, citationLabels, EVIDENCE_KIND, SCENARIO_COPY, SEVERITY_LABEL, SEVERITY_TONE, STATE_LABEL, thresholdBars,
  TRIAGE_COPY, type AlertDetail, type BarTone, type CaseReview, type EvidenceRow, type Finding,
} from "@/lib/compliance";
import { AiProse } from "@/components/ai-prose";
import { AiThinking } from "@/components/ai-thinking";
import { EntityGraph } from "@/components/entity-graph";
import { CountUp, EASE } from "@/components/motion";
import { Skeleton, SkeletonText } from "@/components/skeleton";
import { Badge, Button, Field, inputClass, KeyMoment, Notice, PageHeader, Panel, Section, Sparkle } from "@/components/ui";
import { Arrive, Confirmed, StatusChip, TableCard, tbl } from "../../../operations/_parts";
import {
  CardSkeleton, DetailHeaderSkeleton, LoadingRegion, MomentSkeleton, SectionTitleSkeleton, TableCardSkeleton,
} from "../../../operations/_skeletons";

const msg = (e: unknown, fallback: string) => (e instanceof ApiError ? e.message : fallback);
/** An evidence label in the engine's own voice: Geist Mono on sand. */
const REF = "code inline-flex h-5 min-w-7 items-center justify-center rounded-[5px] bg-fill px-1 text-[11px] text-ink-700 no-underline hover:bg-sand-200";
/** A citation Gemini made, inside its violet block. */
const CITE = "code inline-flex h-5 min-w-7 items-center justify-center rounded-[5px] bg-white px-1 align-[2px] text-[11px] font-medium text-ai-700 no-underline hover:bg-ai-100";
const FILL: Record<BarTone, string> = { under: "bg-green-500", near: "bg-amber-400", over: "bg-coral-500" };
const KEY: Record<BarTone, string> = { under: "Clear of the threshold", near: "Within 15% under it", over: "At or over it" };

function ThresholdChart({ evidence }: { evidence: EvidenceRow[] }) {
  const { bars, linePct } = thresholdBars(evidence, 10000);
  if (bars.length === 0) return null;
  const columns = { gridTemplateColumns: `repeat(${bars.length}, minmax(0, 1fr))` };
  const tones = (["under", "near", "over"] as BarTone[]).filter((t) => bars.some((b) => b.tone === t));
  return (
    <figure className="space-y-3">
      <div role="img" className="relative h-52 sm:h-60"
        aria-label={`${bars.length} payments, ${bars.map((b) => `${formatUsd(b.amount)} on ${formatDate(b.date)}`).join(", ")}, against the $10,000 reporting threshold`}>
        {/* The threshold is drawn first; then each payment grows toward it, one after another. */}
        <div aria-hidden="true" className="absolute inset-0 grid gap-4 px-2 sm:gap-10 sm:px-10" style={columns}>
          {bars.map((b, i) => (
            <div key={b.id} className="mx-auto flex h-full w-full max-w-14 flex-col justify-end overflow-hidden rounded-full bg-sand-100">
              <motion.div className={`w-full rounded-full ${FILL[b.tone]}`} initial={{ height: "0%" }} animate={{ height: `${b.pct}%` }}
                transition={{ duration: 0.6, delay: 0.3 + i * 0.12, ease: EASE }} />
            </div>
          ))}
        </div>
        <motion.div aria-hidden="true" className="absolute inset-x-0 origin-left border-t-2 border-dashed border-coral-500" style={{ bottom: `${linePct}%` }}
          initial={{ scaleX: 0 }} animate={{ scaleX: 1 }} transition={{ duration: 0.4, ease: EASE }} />
        <motion.span aria-hidden="true" className="absolute right-0 rounded-full bg-coral-50 px-2.5 py-0.5 text-xs font-semibold text-coral-700" style={{ bottom: `calc(${linePct}% + 8px)` }}
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.3, delay: 0.25 }}>
          $10,000 reporting threshold
        </motion.span>
      </div>
      <div className="grid gap-4 px-2 sm:gap-10 sm:px-10" style={columns}>
        {bars.map((b) => (
          <span key={b.id} className="flex flex-col items-center gap-1 text-center">
            <span className="num text-[15px] font-semibold">{formatUsd(b.amount, 0)}</span>
            <span className="flex flex-wrap items-center justify-center gap-1.5 text-xs text-ink-500">{formatDate(b.date).replace(/, \d{4}$/, "")}<a href={`#ev-${b.id}`} className={REF}>{b.label}</a></span>
          </span>
        ))}
      </div>
      <figcaption className="flex flex-wrap gap-x-5 gap-y-1.5 pt-1 text-xs text-ink-500">
        {tones.map((t) => <span key={t} className="inline-flex items-center gap-1.5"><span aria-hidden="true" className={`h-2 w-3.5 rounded-full ${FILL[t]}`} />{KEY[t]}</span>)}
        <span className="inline-flex items-center gap-1.5"><span aria-hidden="true" className="w-3.5 border-t-2 border-dashed border-coral-500" />The threshold</span>
      </figcaption>
    </figure>
  );
}

function FindingCard({ finding, index }: { finding: Finding; index: number }) {
  return (
    <Arrive index={index} className="flex min-w-0 flex-col gap-3 rounded-panel border border-sand-200 bg-white p-5 sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-[15px] font-semibold">{finding.title}</span>
        <StatusChip tone={finding.chip.tone}>{finding.chip.label}</StatusChip>
      </div>
      <span className="flex items-baseline gap-1.5">
        <span className="num text-[36px] font-medium leading-10 tracking-[-0.03em] sm:text-[44px] sm:leading-[46px]"><CountUp text={finding.figure} /></span>
        {finding.unit && <span className="text-sm text-ink-500">{finding.unit}</span>}
      </span>
      <span className="text-sm text-ink-700">{finding.text}</span>
    </Arrive>
  );
}

/** The threshold chart's shape: payments as pale columns of different heights under a dashed line. */
function ChartSkeleton() {
  return (
    <div className="space-y-3">
      <div className="relative h-52 sm:h-60">
        <div className="absolute inset-0 grid grid-cols-3 gap-4 px-2 sm:gap-10 sm:px-10">
          {["h-[78%]", "h-[84%]", "h-[80%]"].map((h) => (
            <div key={h} className="mx-auto flex h-full w-full max-w-14 flex-col justify-end"><Skeleton className={`w-full rounded-full ${h}`} /></div>
          ))}
        </div>
        <span className="absolute inset-x-0 bottom-[88%] border-t-2 border-dashed border-sand-200" />
      </div>
      <div className="grid grid-cols-3 gap-4 px-2 sm:gap-10 sm:px-10">
        {[0, 1, 2].map((i) => <span key={i} className="flex flex-col items-center gap-1.5"><Skeleton className="h-4 w-16" /><Skeleton className="h-3 w-12" /></span>)}
      </div>
    </div>
  );
}

/** An alert while it loads: its header, the opening card and its findings, the review beside the decision, who is
 *  linked, and the evidence. */
function AlertSkeleton() {
  return (
    <LoadingRegion label="Loading the alert">
      <DetailHeaderSkeleton badges={2} />
      <div className="space-y-12">
        <div className="space-y-4">
          <MomentSkeleton><ChartSkeleton /><Skeleton className="h-3.5 w-[min(560px,90%)]" /></MomentSkeleton>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            {[0, 1, 2].map((i) => (
              <div key={i} className="flex min-w-0 flex-col gap-3 rounded-panel border border-sand-200 bg-white p-5 sm:p-6">
                <span className="flex items-center justify-between gap-2"><Skeleton className="h-4 w-32" /><Skeleton className="h-[26px] w-24 rounded-full" /></span>
                <Skeleton className="h-10 w-28 rounded-[10px] sm:h-[46px]" />
                <SkeletonText lines={1} />
              </div>
            ))}
          </div>
        </div>
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)] xl:items-start">
          <CardSkeleton lines={2} />
          <div className="flex min-w-0 flex-col gap-4 rounded-panel border border-sand-200 bg-white p-5 sm:p-6">
            <Skeleton className="h-4 w-28" />
            <Skeleton className="h-24 w-full rounded-control" />
            <span className="flex gap-2"><Skeleton className="h-11 w-28 rounded-full" /><Skeleton className="h-11 w-36 rounded-full" /></span>
          </div>
        </div>
        <div>
          <SectionTitleSkeleton width="w-36" />
          <div className="rounded-panel border border-sand-200 bg-white p-5 sm:p-6"><Skeleton className="h-64 w-full rounded-control" /></div>
        </div>
        <TableCardSkeleton rows={4} widths={[0.4, 1.2, 0.9, 3, 0.9]} />
      </div>
    </LoadingRegion>
  );
}

function Review({ review, labels }: { review: CaseReview; labels: Record<string, string> }) {
  const problems = [
    review.unsupported_figures.length ? `${review.unsupported_figures.join(", ")} did not come from the evidence` : "",
    review.dropped_citations.length ? `${review.dropped_citations.length} citation${review.dropped_citations.length === 1 ? "" : "s"} to rows that are not in the evidence were removed` : "",
    review.unknown_names?.length ? `${review.unknown_names.join(", ")} ${review.unknown_names.length === 1 ? "is" : "are"} not named in the alert or its linked accounts` : "",
  ].filter(Boolean);
  const steered = review.steering?.length ? review.steering : null;
  return (
    <div className="space-y-4">
      {steered && (
        <Notice tone="caution" title="Payment text tried to steer this review">
          Text written outside Atrium gives the reviewer instructions: {steered.map((t) => `“${t}”`).join("; ")}.
          {review.model_triage === "close" && review.triage !== "close"
            ? " Gemini suggested closing the alert; Atrium's tripwire changed that to escalate, because a steered case is never suggested for closing."
            : " Atrium's tripwire holds: a steered case is never suggested for closing."}
        </Notice>
      )}
      <AiProse model={review.model}
        caption="From the alert, its evidence and the linked accounts. A suggestion only: you decide."
        warning={review.verified ? undefined : `Check before relying on this: ${problems.join("; ")}.`}>
        <p><span className="font-medium">Suggestion: {TRIAGE_COPY[review.triage]}.</span> {review.triage_reason}</p>
        {review.narrative.map((part, i) => (
          <p key={i} className="mt-3">
            {part.text}{" "}
            {part.evidence.map((id) => <a key={id} href={`#ev-${id}`} className={`${CITE} ml-0.5`}>{labels[id]}</a>)}
          </p>
        ))}
        {review.questions.length > 0 && (
          <>
            <p className="mt-4 font-sans text-[13px] font-semibold uppercase tracking-[0.04em] text-ai-700">Questions worth asking</p>
            <ul className="mt-1 list-disc space-y-1 pl-5 marker:text-ai-500">{review.questions.map((q, i) => <li key={i}>{q}</li>)}</ul>
          </>
        )}
      </AiProse>
    </div>
  );
}

export default function AlertPage() {
  const { id } = useParams<{ id: string }>();
  const [alert, setAlert] = useState<AlertDetail | null>(null);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [decided, setDecided] = useState(false);  // the decision went through on this visit: it confirms

  const load = useCallback(async () => setAlert(await api<AlertDetail>(`/compliance/alerts/${id}`)), [id]);
  useEffect(() => {
    load().catch((e) => setError(msg(e, "Atrium could not load this alert. Try again.")));
  }, [load]);

  async function post(key: string, path: string, body: object | undefined, fallback: string) {
    setBusy(key);
    setError("");
    try {
      setAlert(await api<AlertDetail>(path, { method: "POST", body: body ? JSON.stringify(body) : undefined }));
      if (key === "escalate" || key === "close") setDecided(true);
    } catch (e) {
      setError(msg(e, fallback));
    } finally {
      setBusy("");
    }
  }

  if (!alert) return error ? <Notice tone="error">{error}</Notice> : <AlertSkeleton />;
  const labels = citationLabels(alert.evidence);
  const findings = alertFindings(alert);
  return (
    <>
      <PageHeader title={alert.title} back={{ href: "/compliance", label: "Alerts" }}
        description={<>{alert.person.name}{alert.account_number && <>, account <span className="code text-[13px]">{alert.account_number}</span></>}. Raised {formatDate(alert.raised_at)}.</>}
        actions={<><Badge tone={SEVERITY_TONE[alert.severity]}>{SEVERITY_LABEL[alert.severity]} severity</Badge><Badge tone={alert.state === "escalated" ? "caution" : "neutral"}>{STATE_LABEL[alert.state]}</Badge></>} />
      <div className="space-y-12">
        <div className="space-y-4">
          <KeyMoment tone={alert.severity === "low" ? "attention" : "alert"} label="What monitoring found" title={alert.summary}>
            {alert.scenario === "structuring" && <ThresholdChart evidence={alert.evidence} />}
            {SCENARIO_COPY[alert.scenario] && (
              <p className="max-w-[72ch] text-sm text-ink-500"><span className="font-medium text-ink-700">The rule: </span>{SCENARIO_COPY[alert.scenario]}</p>
            )}
          </KeyMoment>
          {findings.length > 0 && (
            <div className={`grid grid-cols-1 gap-4 ${findings.length === 3 ? "md:grid-cols-3" : findings.length === 2 ? "md:grid-cols-2" : ""}`}>
              {findings.map((f, i) => <FindingCard key={f.title} finding={f} index={i} />)}
            </div>
          )}
        </div>

        <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)] xl:items-start">
          <Panel className="min-w-0 space-y-4 p-5 sm:p-6">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 className="text-base font-semibold">Case review</h2>
              {alert.ai_review?.verified && <StatusChip tone="gain">Figures and citations checked</StatusChip>}
            </div>
            {alert.ai_review ? <Review review={alert.ai_review} labels={labels} /> : alert.review_paused ? (
              <Notice tone="caution" title="Decide from the evidence">{alert.review_paused}</Notice>
            ) : busy === "review" ? (
              // Where the review will be: what Gemini Pro is doing with the case meanwhile.
              <AiThinking steps={CASE_REVIEW_STEPS} usually="10 to 20 s" />
            ) : (
              <div className="space-y-4">
                <p className="max-w-[60ch] text-sm text-ink-700">Gemini Pro reads the alert, its evidence and the linked accounts, and suggests what to do. It usually takes 10 to 20 seconds; the decision stays yours.</p>
                <Button variant="ai" busy={busy === "review"} disabled={Boolean(busy)}
                  onClick={() => post("review", `/compliance/alerts/${alert.id}/review`, undefined, "The case review is unavailable right now.")}>
                  <Sparkle />Ask Gemini Pro for a case review
                </Button>
              </div>
            )}
          </Panel>

          <Panel className="min-w-0 space-y-4 p-5 sm:p-6">
            <h2 className="text-base font-semibold">Your decision</h2>
            {alert.state === "open" ? (
              <>
                <Field label="Your note" hint="The record of why. Escalating means filing a suspicious activity report.">
                  <textarea className={`${inputClass} min-h-24`} value={note} maxLength={1000} onChange={(e) => setNote(e.target.value)} />
                </Field>
                {error && <Notice tone="error">{error}</Notice>}
                <div className="flex flex-wrap items-center gap-2">
                  <Button variant="danger" busy={busy === "escalate"} disabled={!note.trim() || Boolean(busy)}
                    onClick={() => post("escalate", `/compliance/alerts/${alert.id}/decide`, { decision: "escalate", note }, "Atrium could not record the decision.")}>Escalate</Button>
                  <Button variant="secondary" busy={busy === "close"} disabled={!note.trim() || Boolean(busy)}
                    onClick={() => post("close", `/compliance/alerts/${alert.id}/decide`, { decision: "close", note }, "Atrium could not record the decision.")}>Close the alert</Button>
                </div>
                {!note.trim() && <p className="text-xs text-ink-500">Write your note first: both decisions are kept with it.</p>}
              </>
            ) : (
              <>
                {decided && (
                  <Confirmed>{alert.state === "escalated" ? "Escalated: a suspicious activity report starts from here." : "Closed, with your note kept."}</Confirmed>
                )}
                <Notice tone={alert.state === "escalated" ? "caution" : "info"} title={`${STATE_LABEL[alert.state]} by ${alert.decided_by} on ${formatDate(alert.decided_at ?? alert.raised_at)}`}>
                  {alert.decision_note}
                </Notice>
              </>
            )}
          </Panel>
        </div>

        <Section title="Who is linked" description="People joined to the subject by a shared bank account, a shared device or an outside payer.">
          <Panel className="p-5 sm:p-6"><EntityGraph nodes={alert.graph.nodes} edges={alert.graph.edges} /></Panel>
        </Section>

        <TableCard id="evidence" title="Evidence" description="The exact rows behind the alert. E1, E2 and so on are what the chart and the case review point at.">
          {/* Grid rows, as the table spec draws them: one element per row, so each E-label anchor exists once. */}
          <div role="table" aria-label="Evidence rows" className="text-sm">
            <div role="row" className="hidden grid-cols-[48px_150px_110px_minmax(0,1fr)_110px] gap-4 border-b border-sand-100 py-2.5 text-xs font-medium text-ink-500 md:grid">
              <span role="columnheader">Row</span><span role="columnheader">Kind</span><span role="columnheader">Date</span>
              <span role="columnheader">Detail</span><span role="columnheader" className="text-right">Amount</span>
            </div>
            {alert.evidence.map((e, i) => (
              <Arrive index={i} key={e.id} id={`ev-${e.id}`} role="row"
                className="-mx-2 grid scroll-mt-24 grid-cols-[48px_minmax(0,1fr)_auto] gap-x-3 gap-y-1 rounded-control border-b border-sand-100 px-2 py-3 last:border-b-0 target:bg-green-50 md:grid-cols-[48px_150px_110px_minmax(0,1fr)_110px] md:gap-4">
                <span role="cell"><span className={REF}>{labels[e.id]}</span></span>
                <span role="cell" className="text-ink-700 md:whitespace-nowrap">{EVIDENCE_KIND[e.kind] ?? e.kind}<span className="text-ink-500 md:hidden">, {formatDate(e.date)}</span></span>
                <span role="cell" className="hidden whitespace-nowrap text-ink-700 md:block">{formatDate(e.date)}</span>
                <span role="cell" className="col-span-3 col-start-1 md:col-span-1 md:col-start-auto">{e.detail}</span>
                <span role="cell" className={`${tbl.amount} row-start-1 col-start-3 md:row-start-auto md:col-start-auto`}>
                  {e.amount ? formatUsd(e.amount) : <span className="text-ink-400">None</span>}
                </span>
              </Arrive>
            ))}
          </div>
        </TableCard>
      </div>
    </>
  );
}
