"use client";

import { motion } from "motion/react";
import type { ReactNode } from "react";
import { formatUsd } from "@/lib/format";
import { Badge } from "@/components/ui";
import { VERDICT_COPY, VERDICTS, type GuardCheck, type GuardianReport, type Outcome, type Verdict } from "@/lib/trading";

const OUTCOME: Record<Outcome, { said: string; color: string }> = {
  pass: { said: "Passed", color: "text-green-600" }, info: { said: "Note", color: "text-ink-500" },
  warn: { said: "Warning", color: "text-amber-800" }, hold: { said: "Needs an advisor", color: "text-coral-700" },
  block: { said: "Blocked", color: "text-coral-700" },
};
// Green to proceed, amber for care, coral for a hold and a deeper coral for a block: holds are a risk signal.
const FILL: Record<Verdict, string> = { proceed: "bg-green-500", warn: "bg-amber-400", hold: "bg-coral-500", block: "bg-coral-700" };
const CHIP: Record<Verdict, "gain" | "caution" | "loss"> = { proceed: "gain", warn: "caution", hold: "loss", block: "loss" };

function Mark({ outcome }: { outcome: Outcome }) {
  const shape: Record<Outcome, ReactNode> = {
    pass: <path d="M3.5 8.5 6.5 11.5 12.5 4.5" fill="none" stroke="currentColor" strokeWidth="1.75" />,
    info: <><circle cx="8" cy="8" r="5.5" fill="none" stroke="currentColor" strokeWidth="1.25" /><path d="M8 7.2v3.6M8 5.1h.01" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" /></>,
    warn: <><path d="M8 2.5 14 13H2z" fill="none" stroke="currentColor" strokeWidth="1.25" strokeLinejoin="round" /><path d="M8 6.5v3M8 11.2h.01" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" /></>,
    hold: <path d="M5.5 3.5v9M10.5 3.5v9" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />,
    block: <path d="M4.5 4.5l7 7m0-7-7 7" fill="none" stroke="currentColor" strokeWidth="1.75" />,
  };
  return <svg viewBox="0 0 16 16" className={`mt-0.5 h-4 w-4 shrink-0 ${OUTCOME[outcome].color}`} aria-hidden="true">{shape[outcome]}</svg>;
}

/** The verdict as a position on a four-step scale, so its severity reads before its words do. */
export function VerdictScale({ verdict }: { verdict: Verdict }) {
  return (
    <div role="img" aria-label={`Verdict: ${VERDICT_COPY[verdict].label}`}>
      <div className="grid grid-cols-4 gap-1" aria-hidden="true">
        {VERDICTS.map((v) => (
          <span key={v} className="relative h-1.5 overflow-hidden rounded-full bg-sand-100">
            {v === verdict && <motion.span layoutId="guardian-verdict" className={`absolute inset-0 rounded-full ${FILL[v]}`} />}
          </span>
        ))}
      </div>
      <div className="mt-1.5 grid grid-cols-4 gap-1 text-[11px] text-ink-500" aria-hidden="true">
        {VERDICTS.map((v) => <span key={v} className={v === verdict ? "font-medium text-ink-900" : ""}>{VERDICT_COPY[v].label}</span>)}
      </div>
    </div>
  );
}

/** Each check with its outcome and its reason. Rows arrive one after another: the Guardian answering the request. */
export function CheckList({ checks }: { checks: GuardCheck[] }) {
  return (
    <ul className="divide-y divide-sand-100">
      {checks.map((c, i) => (
        <motion.li key={c.code} initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }}
          transition={{ delay: i * 0.035, duration: 0.2 }} className="flex gap-2.5 py-2.5 text-sm">
          <Mark outcome={c.outcome} />
          <span className="min-w-0">
            <span className="sr-only">{OUTCOME[c.outcome].said}: </span>
            <span className="font-medium text-ink-900">{c.title}</span>
            <span className="block text-ink-700">{c.detail}</span>
          </span>
        </motion.li>
      ))}
    </ul>
  );
}

export function GuardianPanel({ report, children }: { report: GuardianReport; children?: ReactNode }) {
  const e = report.estimate;
  const rows: [string, string][] = [
    ["Expected price", `${formatUsd(e.price)} a share`],
    ["Estimated total", formatUsd(e.value)],
    ...(report.order.order_type === "market" ? [["Estimated spread cost", formatUsd(e.spread_cost)] as [string, string]] : []),
    ["Paper cash after", formatUsd(e.cash_after)],
  ];
  return (
    <section aria-labelledby="guardian-title" className="space-y-5 rounded-panel border border-sand-200 bg-white p-5 sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-x-3 gap-y-2">
        <div className="min-w-0">
          <h2 id="guardian-title" className="text-base font-semibold">Pre-trade Guardian</h2>
          <p className="mt-0.5 text-sm text-ink-700">{report.order.words}.</p>
        </div>
        <Badge tone={CHIP[report.verdict]}>{VERDICT_COPY[report.verdict].label}</Badge>
      </div>
      <div>
        <VerdictScale verdict={report.verdict} />
        <p className="mt-3 text-sm"><span className="font-medium">{VERDICT_COPY[report.verdict].label}.</span> {VERDICT_COPY[report.verdict].line}</p>
      </div>
      <CheckList checks={report.checks} />
      <dl className="grid grid-cols-2 gap-x-6 gap-y-3 border-t border-sand-100 pt-4 text-sm">
        {rows.map(([k, v]) => (
          <div key={k}><dt className="text-ink-500">{k}</dt><dd className="num font-medium">{v}</dd></div>
        ))}
      </dl>
      {children}
    </section>
  );
}
