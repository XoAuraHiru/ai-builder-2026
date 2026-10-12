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
import { Button, EmptyState, Loading, Notice } from "@/components/ui";

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
    <article className="mx-auto max-w-3xl">
      <div className="no-print mb-6 flex items-center justify-between gap-3">
        <ProposalBadges proposal={proposal} />
        <Button variant="secondary" onClick={() => window.print()}>Print or save as PDF</Button>
      </div>
      <header className="flex items-start justify-between gap-6 border-b border-ink pb-6">
        <div>
          <p className="wide flex items-center gap-2 text-[17px] font-semibold"><AtriumMark />Atrium</p>
          <h1 className="wide mt-6 text-[30px] font-semibold leading-tight tracking-[-0.015em]">A proposal for {lead.full_name}</h1>
          <p className="mt-2 text-sm text-ink-2">Prepared on {formatDate(proposal.created_at)} for {formatUsd(lead.investable_usd, 0)} now and {formatUsd(lead.monthly_usd, 0)} a month over {lead.horizon_years} years.</p>
        </div>
      </header>
      <div className="mt-8"><ProposalSections proposal={proposal} /></div>
      {projection && (
        <section className="mt-10 break-inside-avoid">
          <h2 className="text-[17px] font-semibold">What your money could become</h2>
          <p className="mt-1 text-sm text-ink-2">10,000 simulated paths over real monthly returns, {formatMonth(projection.window.split(" to ")[0])} to {formatMonth(projection.window.split(" to ")[1])}. A simulation, not a forecast.</p>
          <div className="mt-4">
            <FanChart scenarios={projection.scenarios as unknown as ScenarioOut[]} active={0} goal={null} colors={SERIES} />
          </div>
          <table className="mt-4 w-full text-sm">
            <thead className="border-b border-line text-left text-xs text-muted">
              <tr><th className="py-2 font-medium">After {projection.years} years</th>{projection.scenarios.map((s) => <th key={s.label} className="py-2 text-right font-medium">{s.label}</th>)}</tr>
            </thead>
            <tbody>
              {([["Middle outcome", (s) => formatUsd(s.median_usd, 0)], ["1 in 10 ends below", (s) => formatUsd(s.lower_10pct_usd, 0)],
                ["1 in 10 ends above", (s) => formatUsd(s.upper_10pct_usd, 0)], ["Chance of ending below what you paid in", (s) => formatPct(s.chance_below_paid_in_pct)],
                ["Fees over the period", (s) => formatUsd(s.fees_cost_usd, 0)]] as [string, (s: ProjectionScenario) => string][]).map(([label, value]) => (
                <tr key={label} className="border-b border-line last:border-b-0">
                  <td className="py-2 text-ink-2">{label}</td>
                  {projection.scenarios.map((s) => <td key={s.label} className="num py-2 text-right">{value(s)}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
          <p className="mt-2 text-xs text-muted">You would pay in {formatUsd(projection.paid_in_usd, 0)} in total.</p>
        </section>
      )}
      <section className="mt-10 border-t border-line pt-6 text-sm">
        <h2 className="font-semibold">Sources</h2>
        <ul className="mt-2 list-disc space-y-1 pl-5 text-ink-2">
          {proposal.content.passages.filter((p) => used.has(p.id)).map((p) => <li key={p.id}>{p.title}</li>)}
          {used.has("projection") && projection && (
            <li>Atrium simulation engine, monthly returns from {formatMonth(projection.window.split(" to ")[0])} to {formatMonth(projection.window.split(" to ")[1])}</li>
          )}
        </ul>
        <p className="mt-6 text-xs text-muted">
          Projections are simulations over past market history, not forecasts, and you can lose money. Atrium is a prototype with
          synthetic accounts and paper trading; nothing here is investment advice.
        </p>
      </section>
    </article>
  );
}
