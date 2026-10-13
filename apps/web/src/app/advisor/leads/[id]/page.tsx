"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { api, ApiError, apiUpload } from "@/lib/api";
import { demoFor } from "@/lib/calls";
import { formatDate, formatUsd } from "@/lib/format";
import { SCORING_STEPS, sourceLabel, topSignals, trustTone, type Lead } from "@/lib/leads";
import { LeadSkeleton } from "@/components/advisor-skeletons";
import { AiProse } from "@/components/ai-prose";
import { AiThinking } from "@/components/ai-thinking";
import { CallsSection } from "@/components/calls-section";
import { CardSection } from "@/components/card-section";
import { Confirmed } from "@/components/form-feedback";
import { Reveal, Stagger } from "@/components/motion";
import { ProposalBadges, ProposalSections, type Proposal } from "@/components/proposal-view";
import { LeadScoreStat, SignalRow, TrustScoreCard } from "@/components/score-badge";
import { WhyPanel } from "@/components/why-panel";
import { Badge, Button, ButtonLink, Field, Figure, inputClass, Notice, PageHeader, Sparkle, tableStyles } from "@/components/ui";

type Finding = { code: string; label: string; weight: number; evidence: string; source: string; blocking: boolean };
type IdentityResult = { id: string; extracted: Record<string, string | number | null>; findings: Finding[]; source: string;
  trust_score: number; trust_band: string };
type Compliance = { ok: boolean; reviewed_by: string[]; findings: { phrase: string; rule: string; explanation: string; suggestion: string }[] };
type Draft = { subject: string; body: string; compliance: Compliance };
type Decision = { id: string; created_at: string; purpose: string; model: string; confidence: number | null; cost_usd: string };

const ACTIONS: Record<string, string> = {
  clear: "Proceed with onboarding.", review: "Add friction: step-up verification or an advisor call.",
  high_risk: "Hold for review before any onboarding.", blocked: "Blocked until a person reviews it.", pending: "Not scored yet.",
};
const STAGE_NAME: Record<string, string> = { new: "New", qualified: "Qualified", proposal: "Proposal", onboarding: "Onboarding", disqualified: "Disqualified" };
const FILE_INPUT = "block w-full text-[13px] text-ink-700 file:mr-3 file:h-10 file:cursor-pointer file:rounded-full file:border file:border-sand-200 file:bg-white file:px-4 file:text-sm file:font-medium file:text-ink-900 hover:file:bg-fill";
const message = (e: unknown) => (e instanceof ApiError ? e.message : String(e));

// What each AI call on this page does, in order, for the violet panel that waits where its answer will appear.
const IDENTITY_STEPS = [
  "Gemini is reading the name, date of birth, number and expiry",
  "Document AI is screening the image for tampering",
  "Comparing the document with the form",
];
const PROPOSAL_STEPS = [
  "Simulating their own numbers and choosing a fund mix",
  "Finding the fund documents to cite",
  "Gemini Pro is writing the proposal from the simulation and the fund documents",
  "Gemini Pro is citing a fund document or the simulation in every section",
];
const DRAFT_STEPS = [
  "The Lead Intelligence agent is reading the lead's profile",
  "Drafting a first email that names at most two house funds",
  "Checking the draft against the marketing rules",
];
const ASK_STEPS = [
  "The concierge is routing your question to Lead Intelligence or Trust and Fraud",
  "The agent is reading the lead's profile and trust report",
  "Writing the answer",
];

function MarketingFindings({ findings }: { findings: Compliance["findings"] }) {
  return (
    <ul className="space-y-2 rounded-control bg-amber-50 px-4 py-3 text-sm leading-[21px] text-ink-900">
      {findings.map((f, i) => (
        <li key={i}><span className="font-semibold text-amber-800">&ldquo;{f.phrase}&rdquo;</span>: {f.explanation} {f.suggestion}</li>
      ))}
    </ul>
  );
}

function Detail({ label, children, wide = false }: { label: string; children: React.ReactNode; wide?: boolean }) {
  return (
    <div className={wide ? "sm:col-span-2" : ""}>
      <dt className="text-[13px] text-ink-500">{label}</dt>
      <dd className="mt-0.5 text-[15px] leading-[22px]">{children}</dd>
    </div>
  );
}

export default function LeadDetail() {
  const { id } = useParams<{ id: string }>();
  const [lead, setLead] = useState<Lead | null>(null);
  const [decisions, setDecisions] = useState<Decision[]>([]);
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");
  const [identity, setIdentity] = useState<IdentityResult | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [override, setOverride] = useState("");
  const [converted, setConverted] = useState<{ account_number: string } | null>(null);
  const [actionError, setActionError] = useState<Record<string, string>>({});
  const loaded = useRef(false);

  const load = useCallback(async () => {
    try {
      const [l, d, p] = await Promise.all([api<Lead>(`/leads/${id}`), api<Decision[]>(`/leads/${id}/decisions`), api<Proposal[]>(`/leads/${id}/proposals`)]);
      setLead(l);
      setDecisions(d);
      setProposals(p);
      loaded.current = true;
      setActionError((prev) => ({ ...prev, load: "" }));
    } catch (e) {
      // A failed first load replaces the page; a failed refresh must not wipe a draft the advisor is editing.
      if (loaded.current) setActionError((prev) => ({ ...prev, load: `Could not refresh: ${message(e)}` }));
      else setError(message(e));
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  async function run(name: string, action: () => Promise<void>) {
    setBusy(name);
    setActionError((prev) => ({ ...prev, [name]: "" }));
    try {
      await action();
    } catch (e) {
      setActionError((prev) => ({ ...prev, [name]: message(e) }));
    } finally {
      setBusy("");
    }
  }

  if (error) return <Notice tone="error" title="Could not load this lead">{error}</Notice>;
  if (!lead) return <LeadSkeleton />;
  const factors = lead.lead_score_factors;
  const tone = trustTone(lead.trust_band);
  const risky = lead.trust_band === "high_risk" || lead.trust_band === "blocked";
  const latest = proposals[0];
  const fail = (name: string) => actionError[name] && <div className="mt-3"><Notice tone="error">{actionError[name]}</Notice></div>;

  return (
    <>
      <PageHeader title={lead.full_name} back={{ href: "/advisor", label: "Leads" }}
        description={`${lead.email}, ${lead.phone ?? "no phone"}. ${sourceLabel(lead.source)} on ${formatDate(lead.created_at)}.`}
        actions={lead.stage !== "client" ? (
          <label className="flex items-center gap-2.5 text-[13px] font-medium">Stage
            <select value={lead.stage} disabled={Boolean(busy)} className={`${inputClass} w-44`}
              onChange={(e) => run("stage", async () => {
                setLead(await api<Lead>(`/leads/${id}/stage`, { method: "PATCH", body: JSON.stringify({ stage: e.target.value }) }));
              })}>
              {Object.entries(STAGE_NAME).map(([s, label]) => <option key={s} value={s}>{label}</option>)}
            </select>
          </label>
        ) : <Badge tone="gain">Client</Badge>} />
      <div className="space-y-6">
        {(actionError.stage || actionError.load || actionError.rescore) && (
          <Notice tone="error">{actionError.stage || actionError.load || `AI scoring failed: ${actionError.rescore}`}</Notice>
        )}
        {lead.scoring_error && (
          <Notice tone="caution" title="The AI analysis is missing" action={<Button variant="secondary" size="sm" disabled={busy === "rescore"}
            onClick={() => run("rescore", async () => { setLead(await api<Lead>(`/leads/${id}/rescore`, { method: "POST" })); })}>Retry AI scoring</Button>}>
            {lead.scoring_error}. The rule-based scores below are complete.
          </Notice>
        )}
        {!lead.scored_at && (
          <Notice tone="caution" title="Not scored yet"
            action={<Button variant="tonal" size="sm" disabled={busy === "rescore"} onClick={() => run("rescore", async () => { setLead(await api<Lead>(`/leads/${id}/rescore`, { method: "POST" })); await load(); })}>
              Score this lead
            </Button>}>
            Gemini reads the answers; the Lead Score and the Trust Score follow.
          </Notice>
        )}
        {busy === "rescore" && <AiThinking compact steps={SCORING_STEPS} usually="a few seconds" />}

        <div className="grid gap-4 lg:grid-cols-2">
          <LeadScoreStat score={lead.lead_score} probability={factors?.probability}>
            {factors && (
              <WhyPanel title="what drives this score" model={`${factors.model} (${factors.source})`}
                evidence={[...factors.for.map((f) => ({ label: `For: ${f.label}`, detail: f.value })),
                  ...factors.against.map((f) => ({ label: `Against: ${f.label}`, detail: f.value }))]} />
            )}
          </LeadScoreStat>
          <TrustScoreCard score={lead.trust_score} band={lead.trust_band} signals={lead.trust_signals ? topSignals(lead) : null}
            fit={lead.lead_score} evidence
            footer={(
              <div className="mt-auto flex flex-col gap-1 rounded-control bg-fill px-4 py-3">
                <p className="text-sm font-medium">{ACTIONS[tone]}</p>
                <p className="text-xs text-ink-500">Fixed rule weights; Gemini and Document AI supply evidence only.</p>
              </div>
            )} />
        </div>

        <CardSection title="Profile" description="The prospect's own answers, then Gemini's reading of them.">
          <dl className="grid gap-x-8 gap-y-4 sm:grid-cols-2 lg:grid-cols-3">
            <Detail label="Goals">{lead.goals}</Detail>
            <Detail label="Horizon"><span className="num">{lead.horizon_years} year{lead.horizon_years === 1 ? "" : "s"}</span></Detail>
            <Detail label="To invest now"><span className="num">{formatUsd(lead.investable_usd)}</span></Detail>
            <Detail label="Every month"><span className="num">{formatUsd(lead.monthly_usd)}</span></Detail>
            <Detail label="Source of funds">{lead.source_of_funds.replaceAll("_", " ")}</Detail>
            {lead.notes && <Detail label="Notes" wide>{lead.notes}</Detail>}
          </dl>
          {lead.enrichment && (
            <div className="mt-6">
              <AiProse caption="Gemini's reading of the form. The prospect's own words stay above.">
                <p>{lead.enrichment.goals_summary}</p>
                <p className="mt-2"><span className="font-sans text-sm font-semibold">Next best action. </span>{lead.next_best_action}</p>
                <p className="mt-3 flex flex-wrap items-center gap-1.5 font-sans text-sm">Suggested funds:
                  {lead.enrichment.suggested_funds.map((f) => <span key={f} className="code rounded-full bg-white px-2.5 py-1 text-[11px]">{f}</span>)}</p>
              </AiProse>
            </div>
          )}
        </CardSection>

        {lead.analysis && (
          <CardSection title="Their analysis" description={`Run on the front page on ${formatDate(lead.analysis.created_at)}, before they applied. The figures are a simulation, not a promise they were given.`}>
            <p className="text-sm text-ink-700">
              {formatUsd(lead.analysis.initial_usd, 0)}{Number(lead.analysis.monthly_usd) > 0 ? ` plus ${formatUsd(lead.analysis.monthly_usd, 0)} a month` : ""} in{" "}
              <span className="font-semibold text-ink-900">{lead.analysis.name}</span> ({lead.analysis.kind === "share" ? "shares" : "unit trust"}) for {lead.analysis.years} years
            </p>
            <div className="mt-5 grid gap-6 sm:grid-cols-3">
              <Figure label="Middle outcome" value={formatUsd(lead.analysis.summary.median_usd, 0)} />
              <Figure label="Likely range" value={`${formatUsd(lead.analysis.summary.p10_usd, 0)} to ${formatUsd(lead.analysis.summary.p90_usd, 0)}`} />
              <Figure label="Paid in" value={formatUsd(lead.analysis.summary.contributed_usd, 0)}
                detail={`${lead.analysis.summary.prob_loss_pct}% of futures end below it.`} />
            </div>
            {lead.analysis.summary.comparison_median_usd !== null && (
              <p className="mt-4 text-[13px] text-ink-700">The S&amp;P 500 on the same simulated months: middle outcome {formatUsd(lead.analysis.summary.comparison_median_usd, 0)}.</p>
            )}
          </CardSection>
        )}

        <CardSection title="Identity document" description="Gemini reads the fields; Document AI screens for tampering. The image is never stored.">
          <p className="mb-4 text-sm text-ink-700">
            Try a <a className="font-semibold text-green-600 hover:text-green-800 hover:underline" href="/demo/specimen-match.png" download>matching sample card</a> or a{" "}
            <a className="font-semibold text-green-600 hover:text-green-800 hover:underline" href="/demo/specimen-mismatch.png" download>mismatched one</a>.
          </p>
          <div className="flex flex-wrap items-center gap-3">
            <input type="file" aria-label="Identity document" accept="image/png,image/jpeg,application/pdf" className={`${FILE_INPUT} max-w-[420px] flex-1`}
              onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
            <Button variant="secondary" disabled={!file || busy === "identity"} onClick={() => run("identity", async () => {
              const form = new FormData();
              form.append("file", file!);
              setIdentity(await apiUpload<IdentityResult>(`/leads/${id}/documents`, form));
              await load();
            })}>Analyse document</Button>
          </div>
          {fail("identity")}
          {busy === "identity" && <div className="mt-5"><AiThinking compact steps={IDENTITY_STEPS} usually="about 8 s" /></div>}
          {identity && (
            <Reveal className="mt-5 space-y-4">
              <dl className="grid gap-x-8 gap-y-3 rounded-control bg-fill px-4 py-4 sm:grid-cols-3">
                {Object.entries(identity.extracted).map(([k, v]) => (
                  <div key={k}>
                    <dt className="text-xs capitalize text-ink-500">{k.replaceAll("_", " ")}</dt>
                    <dd className={`mt-0.5 text-sm ${v === null ? "text-ink-400" : ""}`}>{v === null ? "Not found" : String(v)}</dd>
                  </div>
                ))}
              </dl>
              {identity.findings.length === 0 ? <Confirmed title="No findings">The document matches the form.</Confirmed> : (
                <Stagger as="ul" className="border-b border-sand-100">
                  {identity.findings.map((f) => <SignalRow key={f.code} signal={f} evidence />)}
                </Stagger>
              )}
              <p className="text-xs text-ink-500">Checked by <span className="code text-[11px]">{identity.source}</span>.</p>
            </Reveal>
          )}
        </CardSection>

        <CallsSection leadId={id} demoCall={demoFor(lead.email)} onChange={load} />

        <CardSection title="Proposal"
          description="Gemini Pro writes a personalised proposal from the simulation and the fund documents. It is a draft for you to review; nothing is sent."
          actions={latest ? <ButtonLink href={`/advisor/leads/${id}/proposal`} variant="quiet" size="sm">Open the printable proposal</ButtonLink> : undefined}>
          <Button variant="ai" disabled={risky || busy === "proposal"}
            onClick={() => run("proposal", async () => { await api<Proposal>(`/leads/${id}/proposal`, { method: "POST" }); await load(); })}>
            <Sparkle />{latest ? "Write a new version" : "Write a proposal"}
          </Button>
          {risky && <p className="mt-2 text-[13px] text-ink-500">Resolve the trust review before preparing a proposal.</p>}
          {fail("proposal")}
          {busy === "proposal" && <div className="mt-6"><AiThinking steps={PROPOSAL_STEPS} usually="about 30 s" /></div>}
          {latest && (
            <div className="mt-6 space-y-4">
              <ProposalBadges proposal={latest} />
              <ProposalSections proposal={latest} />
              {!latest.compliance.ok && <MarketingFindings findings={latest.compliance.findings} />}
            </div>
          )}
        </CardSection>

        <div className="grid gap-6 lg:grid-cols-2">
          <CardSection title="First reply" description="The Lead Intelligence agent drafts it and checks it against the marketing rules.">
            <Button variant="ai" disabled={busy === "draft"} onClick={() => run("draft", async () => {
              setDraft(await api<Draft>(`/leads/${id}/draft-reply`, { method: "POST" }));
              await load();
            })}><Sparkle />Draft the first reply</Button>
            {fail("draft")}
            {busy === "draft" && <div className="mt-5"><AiThinking compact steps={DRAFT_STEPS} usually="a few seconds" /></div>}
            {draft && (
              <Reveal className="mt-5 space-y-3">
                <Field label="Subject">
                  <input className={inputClass} value={draft.subject} onChange={(e) => setDraft({ ...draft, subject: e.target.value })} />
                </Field>
                <Field label="Message">
                  <textarea className={`${inputClass} h-48 font-serif text-[16px] leading-6`} value={draft.body} onChange={(e) => setDraft({ ...draft, body: e.target.value })} />
                </Field>
                <p className="flex items-center gap-1.5 text-xs font-medium text-ai-700"><Sparkle size={12} />Drafted by Gemini. Edit it before you send it.</p>
                {draft.compliance.ok
                  ? <Confirmed title="Marketing-rule check passed">Reviewed by {draft.compliance.reviewed_by.join(" and ")}.</Confirmed>
                  : <MarketingFindings findings={draft.compliance.findings} />}
              </Reveal>
            )}
          </CardSection>
          <CardSection title="Ask the concierge" description="Routes your question to the Lead Intelligence or the Trust and Fraud agent.">
            <form className="flex flex-col gap-2 sm:flex-row" onSubmit={(e) => {
              e.preventDefault();
              run("ask", async () => {
                setAnswer((await api<{ answer: string }>(`/leads/${id}/ask`, { method: "POST", body: JSON.stringify({ question }) })).answer);
                await load();
              });
            }}>
              <input className={inputClass} aria-label="Your question" placeholder="Why is this lead flagged?" value={question} onChange={(e) => setQuestion(e.target.value)} />
              <Button type="submit" variant="ai" disabled={question.trim().length < 3 || busy === "ask"}><Sparkle />Ask</Button>
            </form>
            {fail("ask")}
            {busy === "ask" && <div className="mt-5"><AiThinking compact steps={ASK_STEPS} usually="a few seconds" /></div>}
            {answer && <div className="mt-5"><AiProse caption="Answered by the advisor concierge on Gemini"><p className="whitespace-pre-wrap">{answer}</p></AiProse></div>}
          </CardSection>
        </div>

        {lead.stage !== "client" ? (
          <CardSection title="Convert to client" description="Opens an account with everything already known. A high-risk lead needs a recorded reason.">
            {risky && (
              <div className="mb-4 max-w-[640px]">
                <Field label="Override reason" hint="Recorded with the account: what did you verify, and how?">
                  <textarea className={inputClass} rows={3} value={override} onChange={(e) => setOverride(e.target.value)}
                    placeholder="For example: Called the client on a known number and checked their ID in person." />
                </Field>
              </div>
            )}
            <Button disabled={risky && override.trim().length < 5} busy={busy === "convert"} onClick={() => run("convert", async () => {
              setConverted(await api<{ account_number: string }>(`/leads/${id}/convert`, { method: "POST", body: JSON.stringify({ override_reason: override || null }) }));
              await load();
            })}>Convert to client</Button>
            {risky && override.trim().length < 5 && <p className="mt-2 text-[13px] text-ink-500">Write the override reason first.</p>}
            {fail("convert")}
          </CardSection>
        ) : converted ? (
          <Confirmed title="Converted to client">
            Account <span className="code text-[12px]">{converted.account_number}</span> is open. They can sign in as {lead.email}.
          </Confirmed>
        ) : (
          <Notice tone="success" title="Client">Converted. They can sign in as {lead.email}.</Notice>
        )}

        <CardSection title="AI activity on this lead" description="Every model call, with its purpose, model, confidence and cost.">
          {decisions.length === 0 ? <p className="text-sm text-ink-500">No AI calls yet.</p> : (
            <div className={tableStyles.wrap}>
              <table className={`${tableStyles.table} min-w-[640px]`}>
                <thead className={tableStyles.head}>
                  <tr>
                    <th className={tableStyles.th}>Call</th><th className={tableStyles.th}>When</th><th className={tableStyles.th}>Purpose</th>
                    <th className={tableStyles.th}>Model</th><th className={`${tableStyles.th} text-right`}>Confidence</th>
                    <th className={`${tableStyles.th} text-right`}>Cost</th>
                  </tr>
                </thead>
                <tbody>
                  {decisions.map((d) => (
                    <tr key={d.id} className={tableStyles.row}>
                      <td className={`${tableStyles.td} code text-ink-700`} title={d.id}>{d.id.slice(0, 8)}</td>
                      <td className={`${tableStyles.td} num whitespace-nowrap text-ink-700`}>{new Date(d.created_at.endsWith("Z") ? d.created_at : `${d.created_at}Z`).toLocaleTimeString()}</td>
                      <td className={`${tableStyles.td} first-letter:uppercase`}>{d.purpose.replaceAll("_", " ")}</td>
                      <td className={`${tableStyles.td} code text-ink-700`}>{d.model}</td>
                      <td className={`${tableStyles.td} num text-right`}>{d.confidence === null ? "" : `${Math.round(d.confidence * 100)}%`}</td>
                      <td className={`${tableStyles.td} code text-right text-ink-700`}>${Number(d.cost_usd).toFixed(4)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardSection>
      </div>
    </>
  );
}
