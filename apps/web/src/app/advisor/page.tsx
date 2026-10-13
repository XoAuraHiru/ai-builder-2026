"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { formatUsd } from "@/lib/format";
import { attentionHeadline, SCORING_STEPS, sourceLabel, STAGE_LABEL, timeAgo, topSignals, triage, type Lead } from "@/lib/leads";
import { initials } from "@/lib/personas";
import { useMe } from "@/lib/session-context";
import { LEAD_ROW, LeadsSkeleton } from "@/components/advisor-skeletons";
import { AiThinking } from "@/components/ai-thinking";
import { Stagger, StaggerItem } from "@/components/motion";
import { TrustBadge, TrustMeter, TrustScoreCard } from "@/components/score-badge";
import { Button, KeyMoment, Notice, PageHeader, Section } from "@/components/ui";

// Rows past the first dozen are below the fold: they show at once rather than queue behind the ones in view.
const STAGGERED = 12;

function LeadRow({ lead, staggered }: { lead: Lead; staggered: boolean }) {
  const scored = lead.lead_score !== null;
  const Row = staggered ? StaggerItem : PlainItem;
  return (
    <Row as="li" className="border-t border-sand-100 first:border-t-0">
      <Link href={`/advisor/leads/${lead.id}`} className={`${LEAD_ROW} flex flex-col gap-3 px-5 py-4 hover:bg-fill sm:px-6`}>
        <span className="flex min-w-0 items-center gap-3">
          <span aria-hidden="true" className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-sand-100 text-xs font-semibold">
            {initials(lead.full_name)}
          </span>
          <span className="min-w-0">
            <span className="block truncate text-sm font-medium">{lead.full_name}</span>
            <span className="block truncate text-xs text-ink-500">
              {STAGE_LABEL[lead.stage]} · {sourceLabel(lead.source)} · {timeAgo(lead.created_at)}
            </span>
            <span className="mt-0.5 block truncate text-xs text-ink-500">{lead.goals}</span>
          </span>
        </span>
        <span className="flex flex-wrap items-center gap-x-5 gap-y-3 md:contents">
          {/* On phones: the Lead Score and the amount share a line, the Trust Score takes the next; from md, grid columns. */}
          <span className="order-1 flex items-baseline gap-1 md:order-none">
            <span className="sr-only">Lead Score</span>
            {scored ? (
              <>
                <span className="num text-[22px] font-medium leading-7 tracking-[-0.01em]">{lead.lead_score}</span>
                <span className="num text-xs text-ink-500">/ 100<span className="md:hidden"> fit</span></span>
              </>
            ) : <span className="text-[13px] text-ink-400">Not scored</span>}
          </span>
          <span className="order-3 flex basis-full flex-col gap-2 md:order-none md:basis-auto">
            <span className="flex items-center gap-2">
              <TrustBadge band={lead.trust_band} score={lead.trust_score} />
              {lead.trust_score !== null && <span className="num text-[13px] text-ink-700">{lead.trust_score} <span className="text-ink-500">/ 100</span></span>}
            </span>
            <span className="block w-full md:max-w-[240px]"><TrustMeter score={lead.trust_score} band={lead.trust_band} size="sm" /></span>
          </span>
          <span className="order-2 ml-auto flex flex-col items-end md:order-none md:ml-0">
            <span className="sr-only">Amount</span>
            <span className="num text-sm font-medium">{formatUsd(lead.investable_usd, 0)}</span>
            <span className="text-xs text-ink-500">to invest</span>
          </span>
        </span>
      </Link>
    </Row>
  );
}

function PlainItem({ className, children }: { as: "li"; className: string; children: React.ReactNode }) {
  return <li className={className}>{children}</li>;
}

/** The rows arrive one after another when the list first appears; a lead that moves into it later simply arrives. */
function LeadList({ leads }: { leads: Lead[] }) {
  return (
    <div className="overflow-hidden rounded-panel border border-sand-200 bg-white">
      <div aria-hidden="true" className={`${LEAD_ROW} hidden border-b border-sand-100 px-6 py-2.5 text-xs font-medium text-ink-500`}>
        <span>Lead</span><span>Lead Score</span><span>Trust Score</span><span className="text-right">Amount</span>
      </div>
      <Stagger as="ul">{leads.map((l, i) => <LeadRow key={l.id} lead={l} staggered={i < STAGGERED} />)}</Stagger>
    </div>
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
  if (!leads) return <LeadsSkeleton />;
  const t = triage(leads);
  // While scoring, the button only holds its place (with how many are left); the violet panel below says what is happening.
  const scoreButton = (t.unscored.length > 0 || busy) && (
    <Button disabled={busy} onClick={scorePending}>
      {busy ? `Scoring${progress ? `, ${progress}` : ""}` : `Score ${t.unscored.length} new lead${t.unscored.length > 1 ? "s" : ""}`}
    </Button>
  );
  const best = t.call[0];

  return (
    <>
      <PageHeader title="Leads"
        description="Every lead is scored twice before you call: for fit, how likely they are to become a client, and for trust, how likely they are to be real."
        actions={scoreButton || undefined} />
      {error && <div className="mb-6"><Notice tone="error">{error}</Notice></div>}
      <div className="space-y-12">
        {busy && <AiThinking compact steps={SCORING_STEPS} usually="a few seconds a lead" />}
        {t.attention.length > 0 ? (
          <KeyMoment tone="alert" label="Look at these first" title={attentionHeadline(t.attention)}>
            <Stagger as="ul" className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
              {t.attention.map((l) => (
                <StaggerItem as="li" key={l.id} className="min-w-0">
                  <Link href={`/advisor/leads/${l.id}`} aria-label={`${l.full_name}, Trust Score ${l.trust_score ?? "not scored"}. Open the lead`}
                    className="group block h-full rounded-panel">
                    <TrustScoreCard score={l.trust_score} band={l.trust_band} signals={topSignals(l)} fit={l.lead_score} limit={3}
                      person={{ name: l.full_name, meta: `${sourceLabel(l.source)} · ${timeAgo(l.created_at)}` }}
                      className="h-full transition-colors group-hover:border-sand-300 group-hover:bg-fill"
                      footer={<p className="num mt-auto text-[13px] text-ink-700">{formatUsd(l.investable_usd, 0)} to invest</p>} />
                  </Link>
                </StaggerItem>
              ))}
            </Stagger>
          </KeyMoment>
        ) : t.unscored.length > 0 ? (
          <KeyMoment tone="attention" label="New leads"
            title={`${t.unscored.length} new lead${t.unscored.length > 1 ? "s have" : " has"} not been scored yet.`}>
            <p className="max-w-[60ch] text-[15px] leading-[22px] text-ink-700">
              Score them to see who is worth a call first and who needs a look before anyone calls.
            </p>
          </KeyMoment>
        ) : best ? (
          <KeyMoment tone="good" label="Clear to call" title={`No lead needs a trust review. ${best.full_name} fits best.`}>
            <p className="max-w-[60ch] text-[15px] leading-[22px] text-ink-700">
              {t.call.length} lead{t.call.length > 1 ? "s are" : " is"} worth a call, sorted by fit below.
            </p>
          </KeyMoment>
        ) : null}

        {(t.call.length > 0 || t.unscored.length === 0) && (
          <Section title="Worth a call" description="Sorted by fit. The figure is the Lead Score; the meter is the Trust Score.">
            {t.call.length === 0 ? <p className="text-sm text-ink-500">No leads are waiting for a call.</p> : <LeadList leads={t.call} />}
          </Section>
        )}

        {t.unscored.length > 0 && (
          <Section title="Not scored yet" description="Gemini reads each new lead's answers; the Lead Score and Trust Score follow.">
            <LeadList leads={t.unscored} />
          </Section>
        )}

        {t.clients.length > 0 && (
          <Section title="Clients" description="Leads that opened an account.">
            <LeadList leads={t.clients} />
          </Section>
        )}
        {t.closed.length > 0 && <p className="text-sm text-ink-500">{t.closed.length} disqualified lead{t.closed.length > 1 ? "s are" : " is"} not shown.</p>}
      </div>
    </>
  );
}
