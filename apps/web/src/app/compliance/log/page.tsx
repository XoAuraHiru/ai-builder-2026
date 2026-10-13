"use client";

import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { formatDate } from "@/lib/format";
import { purposeLabel, type DecisionLog } from "@/lib/compliance";
import { ACTION_COPY, approvalStatus, resultWords, shortId, shortWhen, type Approval } from "@/lib/operations";
import { Loading, Notice, PageHeader } from "@/components/ui";
import { StatCard, StatusChip, TableCard, tbl } from "../../operations/_parts";

const msg = (e: unknown, fallback: string) => (e instanceof ApiError ? e.message : fallback);
const subjectLabel = (s: string) => {
  const words = s.replace(/_/g, " ").replace(/^aml\b/, "AML");
  return words.charAt(0).toUpperCase() + words.slice(1);
};
const cost = (usd: string | number) => `$${Number(usd).toFixed(4)}`;
const tokens = (n: number) => n.toLocaleString("en-US");

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
      description="Every AI output Atrium has used, with its model, tokens and cost, and every two-person approval with who asked and who decided." />
  );
  if (!log || !approvals) return <>{header}{error ? <Notice tone="error">{error}</Notice> : <Loading label="Loading the logs" />}</>;
  const models = new Set(log.decisions.map((d) => d.model)).size;
  const waiting = approvals.filter((a) => a.state === "pending").length;
  return (
    <>
      {header}
      <div className="mb-12 grid grid-cols-2 gap-3 sm:gap-4 xl:grid-cols-4">
        <StatCard icon="list" title="AI decisions shown" value={log.count} tone="neutral"
          caption={`From ${models} model${models === 1 ? "" : "s"}`} />
        <StatCard icon="hash" title="Tokens in" value={tokens(log.tokens_in)} tone="neutral" caption={`${tokens(log.tokens_out)} out`} />
        <StatCard icon="money" title="Their cost" value={<span className="font-mono text-[26px] tracking-normal">{cost(log.cost_usd)}</span>} tone="neutral"
          caption={Number(log.cost_usd) > 0 && Number(log.cost_usd) < 0.01 ? "Under a cent" : "Every call, at list price"} />
        <StatCard icon="check" title="Two-person approvals" value={approvals.length} tone={waiting > 0 ? "caution" : "gain"}
          caption={waiting > 0 ? `${waiting} waiting for a second person` : "None waiting"} />
      </div>
      <div className="space-y-12">
        <TableCard title="AI decisions" description="The latest hundred, newest first.">
          {log.decisions.length === 0 ? <p className="py-6 text-sm text-ink-500">No AI output has been used yet.</p> : (
            <>
            <ul className="divide-y divide-sand-100 md:hidden">
              {log.decisions.map((d) => (
                <li key={d.id} className="py-3">
                  <span className="flex items-baseline justify-between gap-3">
                    <span className="font-medium">{purposeLabel(d.purpose)}</span>
                    <span className="code shrink-0 text-ink-700">{cost(d.cost_usd)}</span>
                  </span>
                  <span className="mt-0.5 block text-xs text-ink-500">{shortWhen(d.created_at)} · {subjectLabel(d.subject_type)}</span>
                  <span className="code mt-1 block text-[11px] text-ink-700">{d.model} · {tokens(d.tokens_in)} / {tokens(d.tokens_out)} tokens</span>
                </li>
              ))}
            </ul>
            <div className={`${tbl.wrap} hidden md:block`}>
              <table className={`${tbl.table} min-w-[760px]`}>
                <thead className={tbl.head}>
                  <tr>
                    <th className={tbl.th}>When</th><th className={tbl.th}>What</th><th className={tbl.th}>Model</th><th className={tbl.th}>About</th>
                    <th className={`${tbl.th} text-right`}>Tokens in / out</th><th className={`${tbl.th} text-right`}>Cost</th>
                  </tr>
                </thead>
                <tbody>
                  {log.decisions.map((d) => (
                    <tr key={d.id} className={tbl.row}>
                      <td className={`${tbl.td} whitespace-nowrap text-ink-700`}>{shortWhen(d.created_at)}</td>
                      <td className={`${tbl.td} font-medium`}>{purposeLabel(d.purpose)}</td>
                      <td className={`${tbl.td} ${tbl.id}`}>{d.model}</td>
                      <td className={`${tbl.td} text-ink-700`}>{subjectLabel(d.subject_type)}</td>
                      <td className={`${tbl.td} ${tbl.amount}`}>{tokens(d.tokens_in)} / {tokens(d.tokens_out)}</td>
                      <td className={`${tbl.td} code whitespace-nowrap text-right text-ink-700`}>{cost(d.cost_usd)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            </>
          )}
        </TableCard>
        <TableCard title="Two-person approvals" description="Who asked, who decided, and what changed.">
          {approvals.length === 0 ? <p className="py-6 text-sm text-ink-500">No approval has been asked for yet.</p> : (
            <>
            <ul className="divide-y divide-sand-100 md:hidden">
              {approvals.map((a) => {
                const status = approvalStatus(a.state);
                return (
                  <li key={a.id} className="space-y-1.5 py-3">
                    <span className="flex items-center justify-between gap-3">
                      <StatusChip tone={status.tone}>{status.label}</StatusChip>
                      <span className={tbl.id}>{shortId(a.id)}</span>
                    </span>
                    <span className="block text-sm font-medium">{a.summary}</span>
                    <span className="block text-xs text-ink-500">
                      {ACTION_COPY[a.action]}, asked by {a.requested_by}{a.decided_by ? `, decided by ${a.decided_by}` : ""}. {resultWords(a)}
                    </span>
                  </li>
                );
              })}
            </ul>
            <div className={`${tbl.wrap} hidden md:block`}>
              <table className={`${tbl.table} min-w-[720px]`}>
                <thead className={tbl.head}><tr><th className={tbl.th}>Request</th><th className={tbl.th}>Asked by</th><th className={tbl.th}>Decided by</th><th className={tbl.th}>Outcome</th></tr></thead>
                <tbody>
                  {approvals.map((a) => {
                    const status = approvalStatus(a.state);
                    return (
                      <tr key={a.id} className={`${tbl.row} align-top`}>
                        <td className={tbl.td}>
                          <span className={tbl.id}>{shortId(a.id)}</span>
                          <span className="mt-0.5 block font-medium">{a.summary}</span>
                          <span className="block text-xs text-ink-500">{ACTION_COPY[a.action]}, {formatDate(a.requested_at)}</span>
                        </td>
                        <td className={`${tbl.td} whitespace-nowrap`}>{a.requested_by}</td>
                        <td className={`${tbl.td} whitespace-nowrap`}>{a.decided_by ?? <span className="text-ink-500">Waiting</span>}</td>
                        <td className={tbl.td}>
                          <StatusChip tone={status.tone}>{status.label}</StatusChip>
                          <span className="mt-1 block text-xs text-ink-500">{resultWords(a)}</span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            </>
          )}
        </TableCard>
      </div>
    </>
  );
}
