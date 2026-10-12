"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { formatUsd } from "@/lib/format";
import { attentionHeadline, STAGE_LABEL, strongestSignal, triage, type Lead } from "@/lib/leads";
import { useMe } from "@/lib/session-context";
import { TrustBadge } from "@/components/score-badge";
import { Button, KeyMoment, Loading, Notice, PageHeader, Section } from "@/components/ui";

function FitBar({ score }: { score: number | null }) {
  return (
    <span className="flex items-center gap-2.5">
      <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-line" aria-hidden="true">
        <span className="block h-full rounded-full bg-ink" style={{ width: `${score ?? 0}%` }} />
      </span>
      <span className="num w-7 text-right text-[13px] font-semibold">{score ?? "?"}</span>
    </span>
  );
}

function LeadRow({ lead }: { lead: Lead }) {
  return (
    <li>
      <Link href={`/advisor/leads/${lead.id}`}
        className="grid gap-x-5 gap-y-1 border-t border-line py-4 hover:bg-ground/60 sm:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)_auto_110px] sm:items-center">
        <span className="min-w-0">
          <span className="block font-semibold">{lead.full_name}</span>
          <span className="block truncate text-[13px] text-muted">{STAGE_LABEL[lead.stage]}. {lead.goals}</span>
        </span>
        <span className="flex items-center gap-2 text-[13px] text-muted sm:block"><span className="sm:sr-only">Fit</span><FitBar score={lead.lead_score} /></span>
        <span><TrustBadge band={lead.trust_band} score={lead.trust_score} /></span>
        <span className="num font-semibold sm:text-right">{formatUsd(lead.investable_usd, 0)}</span>
      </Link>
    </li>
  );
}

export default function Leads() {
  const me = useMe();
  const [leads, setLeads] = useState<Lead[] | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState("");
  const staff = me.roles.includes("staff");

  const load = useCallback(async () => {
    try {
      setLeads(await api<Lead[]>("/leads"));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    if (staff) load();
  }, [staff, load]);

  async function scorePending() {
    setBusy(true);
    setError("");
    setProgress("");
    try {
      // The API scores a small batch per request; keep going until nothing is left, showing progress as we go.
      for (let round = 0; round < 20; round++) {
        const r = await api<{ scored: number; remaining: number }>("/leads/score-pending", { method: "POST" });
        await load();
        if (r.remaining === 0 || r.scored === 0) break;
        setProgress(`${r.remaining} still to score`);
      }
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(false);
      setProgress("");
      await load();
    }
  }

  if (!staff) return <Notice tone="caution" title="Leads are for Atrium staff">Choose Daniel on the front page.</Notice>;
  if (error && !leads) return <Notice tone="error" title="Could not load the leads">{error}</Notice>;
  if (!leads) return <Loading label="Loading the leads" />;
  const t = triage(leads);
  const scoreButton = t.unscored.length > 0 && (
    <Button busy={busy} onClick={scorePending}>
      {busy ? `Scoring with Gemini${progress ? `, ${progress}` : ""}` : `Score ${t.unscored.length} new lead${t.unscored.length > 1 ? "s" : ""}`}
    </Button>
  );

  return (
    <>
      <PageHeader title="Leads"
        description="Every lead is scored twice before you call: for fit, how likely they are to become a client, and for trust, how likely they are to be real."
        actions={scoreButton || undefined} />
      {error && <div className="mb-6"><Notice tone="error">{error}</Notice></div>}
      <div className="space-y-10">
        {t.attention.length > 0 && (
          <KeyMoment tone="alert" label="Look at these first" title={attentionHeadline(t.attention)}>
            <ul className="grid gap-3 sm:grid-cols-2 2xl:grid-cols-4">
              {t.attention.map((l) => (
                <li key={l.id}>
                  <Link href={`/advisor/leads/${l.id}`}
                    className="flex h-full flex-col gap-1 rounded-[14px] border border-loss/25 bg-danger-wash p-4 hover:border-loss">
                    <span className="font-semibold">{l.full_name}</span>
                    <span className="num text-[13px] text-ink-2">{formatUsd(l.investable_usd, 0)} to invest</span>
                    <span className="num text-[13px] font-semibold text-loss">
                      {l.trust_band === "blocked" ? "Blocked" : `Trust ${l.trust_score}, high risk`}
                    </span>
                    {strongestSignal(l) && <span className="text-[13px] text-ink-2">{strongestSignal(l)}</span>}
                  </Link>
                </li>
              ))}
            </ul>
          </KeyMoment>
        )}

        {(t.call.length > 0 || t.unscored.length === 0) && (
          <Section title="Worth a call" description="Sorted by fit. The bar is the Lead Score; the badge is the Trust Score.">
            {t.call.length === 0 ? <p className="text-sm text-muted">No leads are waiting for a call.</p> : (
              <ul className="rounded-panel border border-line bg-surface px-5 [&>li:first-child>a]:border-t-0">
                {t.call.map((l) => <LeadRow key={l.id} lead={l} />)}
              </ul>
            )}
          </Section>
        )}

        {t.unscored.length > 0 && (
          <Section title="Not scored yet" description="Gemini reads each new lead's answers; the Lead Score and Trust Score follow.">
            <ul className="rounded-panel border border-line bg-surface px-5 [&>li:first-child>a]:border-t-0">
              {t.unscored.map((l) => <LeadRow key={l.id} lead={l} />)}
            </ul>
          </Section>
        )}

        {t.clients.length > 0 && (
          <Section title="Clients" description="Leads that opened an account.">
            <ul className="rounded-panel border border-line bg-surface px-5 [&>li:first-child>a]:border-t-0">
              {t.clients.map((l) => <LeadRow key={l.id} lead={l} />)}
            </ul>
          </Section>
        )}
        {t.closed.length > 0 && <p className="text-sm text-muted">{t.closed.length} disqualified lead{t.closed.length > 1 ? "s are" : " is"} not shown.</p>}
      </div>
    </>
  );
}
