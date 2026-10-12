import { AiProse } from "@/components/ai-prose";
import { Badge, RiskBand } from "@/components/ui";

export type Proposal = {
  id: string; created_at: string; created_by: string; band: number; allocation: Record<string, number>; model: string;
  content: {
    sections: { key: string; heading: string; body: string; citations: string[]; grounded: boolean }[];
    projection: null | {
      years: number; paid_in_usd: number; window: string;
      scenarios: { label: string; yearly: { year: number; p10: number; p25: number; p50: number; p75: number; p90: number; contributed: number }[];
        median_usd: number; lower_10pct_usd: number; upper_10pct_usd: number; chance_below_paid_in_pct: number; fees_cost_usd: number }[];
    };
    band_reasons: string[]; retriever: string; passages: { id: string; title: string; text: string }[];
  };
  compliance: { ok: boolean; reviewed_by: string[]; findings: { phrase: string; rule: string; explanation: string; suggestion: string }[] };
  unsupported_figures: string[]; verified: boolean;
};

export function ProposalBadges({ proposal }: { proposal: Proposal }) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <RiskBand band={proposal.band} />
      {proposal.verified ? <Badge tone="gain">Every section cited, every figure checked</Badge>
        : <Badge tone="caution">Needs review: {proposal.unsupported_figures.length ? `unchecked figures ${proposal.unsupported_figures.join(", ")}` : "an uncited section"}</Badge>}
      {proposal.compliance.ok ? <Badge tone="gain">Marketing-rule check passed</Badge>
        : <Badge tone="caution">{proposal.compliance.findings.length} marketing-rule flag{proposal.compliance.findings.length === 1 ? "" : "s"}</Badge>}
      <Badge tone="ai">Written by {proposal.model}</Badge>
    </div>
  );
}

/** The proposal's sections in the serif reserved for AI writing, each with the passages it cites. */
export function ProposalSections({ proposal }: { proposal: Proposal }) {
  const titles = Object.fromEntries(proposal.content.passages.map((p) => [p.id, p.title]));
  return (
    <AiProse caption={`Drafted by ${proposal.model} for ${proposal.created_by}. A draft for the advisor to review; nothing has been sent.`}>
      <div className="space-y-5">
        {proposal.content.sections.map((s) => (
          <section key={s.key}>
            <h3 className="font-sans text-[15px] font-semibold">{s.heading}</h3>
            <p className="mt-1">{s.body}</p>
            <p className="mt-1.5 flex flex-wrap gap-1 font-sans">
              {s.citations.length === 0 && <Badge tone="caution">No source cited</Badge>}
              {s.citations.map((c) => <Badge key={c} tone="ai">{c === "projection" ? "Simulation" : titles[c] ?? c}</Badge>)}
            </p>
          </section>
        ))}
      </div>
    </AiProse>
  );
}
