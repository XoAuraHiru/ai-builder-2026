"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import { formatDate, formatMonth, formatPct, formatUsd } from "@/lib/format";
import { SERIES, type ScenarioOut } from "@/lib/invest";
import type { Lead } from "@/lib/leads";
import { FanChart } from "@/components/fan-chart";
import { ProposalBadges, ProposalSections, type Proposal } from "@/components/proposal-view";
import { AtriumMark } from "@/components/shell";
import { Button, ButtonLink, EmptyState, Loading, Notice } from "@/components/ui";

type ProjectionScenario = NonNullable<Proposal["content"]["projection"]>["scenarios"][number];

export default function PrintableProposal() {
  const { id } = useParams<{ id: string }>();
  const [lead, setLead] = useState<Lead | null>(null);
  const [proposal, setProposal] = useState<Proposal | null | undefined>(undefined);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([api<Lead>(`/leads/${id}`), api<Proposal[]>(`/leads/${id}/proposals`)])
      .then(([l, p]) => { setLead(l); setProposal(p[0] ?? null); })
      .catch((e) => setError(e instanceof ApiError ? e.message : "Could not load the proposal."));
  }, [id]);

  if (error) return <Notice tone="error">{error}</Notice>;
  if (!lead || proposal === undefined) return <Loading label="Loading the proposal" />;
  if (!proposal) return <EmptyState title="No proposal yet">Write one from the lead page first.</EmptyState>;
  const projection = proposal.content.projection;
  const used = new Set(proposal.content.sections.flatMap((s) => s.citations));
  return (
    <div className="mx-auto max-w-3xl">
      <div className="no-print mb-6 flex flex-wrap items-center justify-between gap-3">
        <ButtonLink href={`/advisor/leads/${id}`} variant="quiet" size="sm"><span aria-hidden="true">‹</span>{lead.full_name}</ButtonLink>
        <Button variant="secondary" onClick={() => window.print()}>Print or save as PDF</Button>
      </div>
      <div className="no-print mb-6"><ProposalBadges proposal={proposal} /></div>
      <article className="rounded-panel border border-sand-200 bg-white p-5 sm:p-10 print:border-0 print:p-0">
        <header className="flex items-start justify-between gap-6 border-b border-sand-200 pb-6">
          <div>
            <p className="flex items-center gap-2.5 text-[17px] font-semibold"><AtriumMark />Atrium</p>
            <h1 className="mt-6 text-[26px] font-semibold leading-8 tracking-[-0.02em] sm:text-[30px] sm:leading-9">A proposal for {lead.full_name}</h1>
            <p className="mt-2 text-sm leading-[21px] text-ink-700">Prepared on {formatDate(proposal.created_at)} for {formatUsd(lead.investable_usd, 0)} now and {formatUsd(lead.monthly_usd, 0)} a month over {lead.horizon_years} years.</p>
          </div>
        </header>
        <div className="mt-8"><ProposalSections proposal={proposal} /></div>
        {projection && (
          <section className="mt-10 break-inside-avoid">
            <h2 className="text-base font-semibold leading-[22px]">What your money could become</h2>
            <p className="mt-1 text-[13px] leading-5 text-ink-500">10,000 simulated paths over real monthly returns, {formatMonth(projection.window.split(" to ")[0])} to {formatMonth(projection.window.split(" to ")[1])}. A simulation, not a forecast.</p>
            <div className="mt-4">
              <FanChart scenarios={projection.scenarios as unknown as ScenarioOut[]} active={0} goal={null} colors={SERIES} />
            </div>
            <div className="mt-4 overflow-x-auto">
              <table className="w-full min-w-[420px] text-sm">
                <thead className="border-b border-sand-100 text-left text-xs text-ink-500">
                  <tr><th className="py-2.5 pr-3 font-medium">After {projection.years} years</th>{projection.scenarios.map((s) => <th key={s.label} className="py-2.5 pl-3 text-right font-medium">{s.label}</th>)}</tr>
                </thead>
                <tbody>
                  {([["Middle outcome", (s) => formatUsd(s.median_usd, 0)], ["1 in 10 ends below", (s) => formatUsd(s.lower_10pct_usd, 0)],
                    ["1 in 10 ends above", (s) => formatUsd(s.upper_10pct_usd, 0)], ["Chance of ending below what you paid in", (s) => formatPct(s.chance_below_paid_in_pct)],
                    ["Fees over the period", (s) => formatUsd(s.fees_cost_usd, 0)]] as [string, (s: ProjectionScenario) => string][]).map(([label, value]) => (
                    <tr key={label} className="border-b border-sand-100 last:border-b-0">
                      <td className="py-3 pr-3 text-ink-700">{label}</td>
                      {projection.scenarios.map((s) => <td key={s.label} className="num py-3 pl-3 text-right">{value(s)}</td>)}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="mt-2 text-xs text-ink-500">You would pay in {formatUsd(projection.paid_in_usd, 0)} in total.</p>
          </section>
        )}
        <section className="mt-10 border-t border-sand-200 pt-6 text-sm">
          <h2 className="text-base font-semibold leading-[22px]">Sources</h2>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-ink-700 marker:text-green-500">
            {proposal.content.passages.filter((p) => used.has(p.id)).map((p) => <li key={p.id}>{p.title}</li>)}
            {used.has("projection") && projection && (
              <li>Atrium simulation engine, monthly returns from {formatMonth(projection.window.split(" to ")[0])} to {formatMonth(projection.window.split(" to ")[1])}</li>
            )}
          </ul>
          <p className="mt-6 text-xs leading-[18px] text-ink-500">
            Projections are simulations over past market history, not forecasts, and you can lose money. Atrium is a prototype with
            synthetic accounts and paper trading; nothing here is investment advice.
          </p>
        </section>
      </article>
    </div>
  );
}
