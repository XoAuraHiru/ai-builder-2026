"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { api, ApiError } from "@/lib/api";
import { formatDate } from "@/lib/format";
import { alertsMoment, SEVERITY_LABEL, SEVERITY_TONE, type Alert } from "@/lib/compliance";
import { Button, ButtonLink, EmptyState, KeyMoment, Notice, PageHeader, Segmented } from "@/components/ui";
import { Arrive, StatusChip, TableCard, tbl } from "../operations/_parts";
import { ChipsSkeleton, LoadingRegion, MomentSkeleton, TableCardSkeleton } from "../operations/_skeletons";

type State = "open" | "escalated" | "closed";
const STATES: { value: State; label: string }[] = [
  { value: "open", label: "Open" }, { value: "escalated", label: "Escalated" }, { value: "closed", label: "Closed" },
];
const msg = (e: unknown, fallback: string) => (e instanceof ApiError ? e.message : fallback);
const href = (a: Alert) => `/compliance/alerts/${a.id}`;

function Severity({ alert }: { alert: Alert }) {
  return <StatusChip tone={SEVERITY_TONE[alert.severity]}>{SEVERITY_LABEL[alert.severity]}</StatusChip>;
}

export default function AlertsPage() {
  const [state, setState] = useState<State>("open");
  const [alerts, setAlerts] = useState<Alert[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [raised, setRaised] = useState<number | null>(null);

  const load = useCallback(async (s: State) => setAlerts(await api<Alert[]>(`/compliance/alerts?state=${s}`)), []);
  useEffect(() => {
    load(state).catch((e) => setError(msg(e, "Atrium could not load the alerts. Try again.")));
  }, [state, load]);

  async function runMonitoring() {
    setBusy(true);
    setError("");
    try {
      setRaised((await api<{ raised: number }>("/compliance/monitoring", { method: "POST" })).raised);
      await load(state);
    } catch (e) {
      setError(msg(e, "Monitoring could not run. Try again."));
    } finally {
      setBusy(false);
    }
  }

  const moment = state === "open" && alerts ? alertsMoment(alerts) : null;
  const count = (s: Alert["severity"]) => alerts?.filter((a) => a.severity === s).length ?? 0;
  return (
    <>
      <PageHeader title="Alerts"
        description="Transaction monitoring runs every evening over fund instructions, the ledger, bank statements and share orders. Each alert carries the exact rows behind it; you escalate or close it."
        actions={<Button variant="secondary" busy={busy} onClick={runMonitoring}>Run monitoring now</Button>} />
      <div className="space-y-8">
        {raised !== null && <Notice tone="success" title="Monitoring finished">{raised === 0 ? "No new alerts: anything it found was already raised." : `${raised} new alert${raised === 1 ? "" : "s"}.`}</Notice>}
        {error && <Notice tone="error">{error}</Notice>}
        {moment && (
          <KeyMoment tone={moment.tone} label={moment.top ? "Needs a decision" : "All clear"} title={moment.title}
            actions={moment.top && <ButtonLink href={`/compliance/alerts/${moment.top}`}>Open the most serious</ButtonLink>}>
            {moment.top && (
              <div className="flex flex-wrap gap-2">
                {count("high") > 0 && <StatusChip tone="loss">{count("high")} high</StatusChip>}
                {count("medium") > 0 && <StatusChip tone="caution">{count("medium")} medium</StatusChip>}
                {count("low") > 0 && <StatusChip tone="neutral">{count("low")} low</StatusChip>}
              </div>
            )}
          </KeyMoment>
        )}
        {/* While the open alerts load, the opening card's shape holds its place above the filter. */}
        {!alerts && state === "open" && !error && <div aria-hidden="true"><MomentSkeleton actions={1}><ChipsSkeleton count={3} /></MomentSkeleton></div>}
        <Segmented label="Show" value={state} options={STATES} onChange={(s) => { setState(s); setAlerts(null); }} />
        {!alerts ? (
          <LoadingRegion label="Loading the alerts"><TableCardSkeleton rows={6} widths={[0.8, 3, 1.3, 1, 0.8]} /></LoadingRegion>
        ) : alerts.length === 0 ? (
          <EmptyState title={state === "open" ? "No open alerts" : `No ${state} alerts`}>Monitoring raises an alert when a rule fires or an account behaves unlike ordinary accounts.</EmptyState>
        ) : (
          <TableCard title={`${alerts.length} ${state} alert${alerts.length === 1 ? "" : "s"}`} description="Newest first. Open one to read its evidence and decide.">
            <div className={`${tbl.wrap} hidden md:block`}>
              <table className={`${tbl.table} min-w-[760px]`}>
                <thead className={tbl.head}>
                  <tr><th className={tbl.th}>Severity</th><th className={tbl.th}>Alert</th><th className={tbl.th}>Client</th><th className={tbl.th}>Raised</th><th className={`${tbl.th} text-right`}>Evidence</th></tr>
                </thead>
                <tbody>
                  {/* The alerts arrive in order, newest first. */}
                  {alerts.map((a, i) => (
                    <Arrive as="tr" index={i} key={a.id} className={`${tbl.row} align-top transition-colors hover:bg-fill`}>
                      <td className={tbl.td}><Severity alert={a} /></td>
                      <td className={`${tbl.td} max-w-[56ch]`}>
                        <Link href={href(a)} className="font-medium hover:text-green-700 hover:underline">{a.title}</Link>
                        <span className="mt-0.5 line-clamp-2 block text-[13px] text-ink-700">{a.summary}</span>
                      </td>
                      <td className={`${tbl.td} whitespace-nowrap`}>{a.person.name}{a.account_number && <span className={`block ${tbl.id} text-[11px]! text-ink-500`}>{a.account_number}</span>}</td>
                      <td className={`${tbl.td} whitespace-nowrap text-ink-700`}>{formatDate(a.raised_at)}</td>
                      <td className={`${tbl.td} ${tbl.amount}`}>{a.evidence_count} row{a.evidence_count === 1 ? "" : "s"}</td>
                    </Arrive>
                  ))}
                </tbody>
              </table>
            </div>
            <ul className="divide-y divide-sand-100 md:hidden">
              {alerts.map((a, i) => (
                <Arrive as="li" index={i} key={a.id}>
                  <Link href={href(a)} className="block py-3.5">
                    <span className="flex items-center justify-between gap-3">
                      <Severity alert={a} />
                      <span className="text-xs text-ink-500">{formatDate(a.raised_at)}</span>
                    </span>
                    <span className="mt-2 block font-medium">{a.title}</span>
                    <span className="mt-0.5 line-clamp-2 block text-[13px] text-ink-700">{a.summary}</span>
                    <span className="mt-1.5 flex items-center justify-between gap-3 text-xs text-ink-500">
                      <span>{a.person.name}{a.account_number && <span className="code text-[11px]"> · {a.account_number}</span>}</span>
                      <span>{a.evidence_count} row{a.evidence_count === 1 ? "" : "s"} of evidence</span>
                    </span>
                  </Link>
                </Arrive>
              ))}
            </ul>
          </TableCard>
        )}
      </div>
    </>
  );
}
