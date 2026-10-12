"use client";

import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { formatDate, formatUsd } from "@/lib/format";
import { purposeLabel, type DecisionLog } from "@/lib/compliance";
import { ACTION_COPY, resultWords, type Approval } from "@/lib/operations";
import { Figure, Loading, Notice, PageHeader, Section, tableStyles as t } from "@/components/ui";

const msg = (e: unknown, fallback: string) => (e instanceof ApiError ? e.message : fallback);
const subjectLabel = (s: string) => {
  const words = s.replace(/_/g, " ").replace(/^aml/, "AML");
  return words.charAt(0).toUpperCase() + words.slice(1);
};

export default function DecisionLogPage() {
  const [log, setLog] = useState<DecisionLog | null>(null);
  const [approvals, setApprovals] = useState<Approval[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([api<DecisionLog>("/compliance/ai-decisions"), api<Approval[]>("/compliance/approvals")])
      .then(([l, a]) => { setLog(l); setApprovals(a); })
      .catch((e) => setError(msg(e, "Atrium could not load the logs. Try again.")));
  }, []);

  const header = (
    <PageHeader title="Decision log"
      description="Every AI output Atrium has used, with its model, tokens and cost, and every four-eyes approval with who asked and who decided." />
  );
  if (!log || !approvals) return <>{header}{error ? <Notice tone="error">{error}</Notice> : <Loading label="Loading the logs" />}</>;
  return (
    <>
      {header}
      <div className="mb-10 grid grid-cols-2 gap-6 sm:grid-cols-3">
        <Figure label="AI decisions shown" value={String(log.count)} />
        <Figure label="Tokens in and out" value={`${log.tokens_in.toLocaleString("en-US")} / ${log.tokens_out.toLocaleString("en-US")}`} />
        <Figure label="Their cost" value={formatUsd(Number(log.cost_usd) < 0.01 && Number(log.cost_usd) > 0 ? 0.01 : log.cost_usd)} detail={Number(log.cost_usd) < 0.01 && Number(log.cost_usd) > 0 ? "Under a cent" : undefined} />
      </div>
      <div className="space-y-10">
        <Section title="AI decisions" description="The latest hundred.">
          <div className={t.wrap}>
            <table className={t.table}>
              <thead className={t.head}><tr><th className={t.th}>When</th><th className={t.th}>What</th><th className={t.th}>Model</th><th className={t.th}>About</th><th className={`${t.th} text-right`}>Tokens</th><th className={`${t.th} text-right`}>Cost</th></tr></thead>
              <tbody>
                {log.decisions.map((d) => (
                  <tr key={d.id} className={t.row}>
                    <td className={`${t.td} whitespace-nowrap`}>{formatDate(d.created_at)}</td>
                    <td className={t.td}>{purposeLabel(d.purpose)}</td>
                    <td className={t.td}>{d.model}</td>
                    <td className={t.td}>{subjectLabel(d.subject_type)}</td>
                    <td className={`${t.td} num text-right`}>{d.tokens_in.toLocaleString("en-US")} / {d.tokens_out.toLocaleString("en-US")}</td>
                    <td className={`${t.td} num text-right`}>${Number(d.cost_usd).toFixed(4)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Section>
        <Section title="Four-eyes approvals">
          <div className={t.wrap}>
            <table className={t.table}>
              <thead className={t.head}><tr><th className={t.th}>Request</th><th className={t.th}>Asked by</th><th className={t.th}>Decided by</th><th className={t.th}>Outcome</th></tr></thead>
              <tbody>
                {approvals.map((a) => (
                  <tr key={a.id} className={t.row}>
                    <td className={t.td}><span className="font-medium">{a.summary}</span><span className="block text-xs text-muted">{ACTION_COPY[a.action]}, {formatDate(a.requested_at)}</span></td>
                    <td className={t.td}>{a.requested_by}</td>
                    <td className={t.td}>{a.decided_by ?? "Waiting"}</td>
                    <td className={t.td}>{resultWords(a)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Section>
      </div>
    </>
  );
}
