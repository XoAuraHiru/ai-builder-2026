"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { api, ApiError } from "@/lib/api";
import { formatDate } from "@/lib/format";
import { SEVERITY_LABEL, SEVERITY_TONE, type Alert } from "@/lib/compliance";
import { Badge, Button, EmptyState, Loading, Notice, PageHeader, Segmented } from "@/components/ui";

type State = "open" | "escalated" | "closed";
const STATES: { value: State; label: string }[] = [
  { value: "open", label: "Open" }, { value: "escalated", label: "Escalated" }, { value: "closed", label: "Closed" },
];
const msg = (e: unknown, fallback: string) => (e instanceof ApiError ? e.message : fallback);

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

  return (
    <>
      <PageHeader title="Alerts"
        description="Transaction monitoring runs every evening over fund instructions, the ledger, bank statements and share orders. Each alert carries the exact rows behind it; you escalate or close it."
        actions={<Button variant="secondary" busy={busy} onClick={runMonitoring}>Run monitoring now</Button>} />
      <div className="mb-6"><Segmented label="Show" value={state} options={STATES} onChange={(s) => { setState(s); setAlerts(null); }} /></div>
      {raised !== null && <div className="mb-6"><Notice tone="success" title="Monitoring finished">{raised === 0 ? "No new alerts: anything it found was already raised." : `${raised} new alert${raised === 1 ? "" : "s"}.`}</Notice></div>}
      {error && <div className="mb-6"><Notice tone="error">{error}</Notice></div>}
      {!alerts ? <Loading label="Loading the alerts" /> : alerts.length === 0 ? (
        <EmptyState title={state === "open" ? "No open alerts" : `No ${state} alerts`}>Monitoring raises an alert when a rule fires or an account behaves unlike ordinary accounts.</EmptyState>
      ) : (
        <ul className="divide-y divide-line border-y border-line">
          {alerts.map((a) => (
            <li key={a.id}>
              <Link href={`/compliance/alerts/${a.id}`} className="group grid gap-2 py-4 sm:grid-cols-[minmax(0,1fr)_auto] sm:gap-6">
                <span className="min-w-0">
                  <span className="flex flex-wrap items-center gap-2">
                    <Badge tone={SEVERITY_TONE[a.severity]}>{SEVERITY_LABEL[a.severity]}</Badge>
                    <span className="font-medium group-hover:underline">{a.title}</span>
                    <span className="text-sm text-ink-2">{a.person.name}{a.account_number ? `, ${a.account_number}` : ""}</span>
                  </span>
                  <span className="mt-1 line-clamp-2 block max-w-[80ch] text-sm text-ink-2">{a.summary}</span>
                </span>
                <span className="text-sm text-muted sm:text-right">
                  Raised {formatDate(a.raised_at)}
                  <span className="block">{a.evidence_count} row{a.evidence_count === 1 ? "" : "s"} of evidence</span>
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
