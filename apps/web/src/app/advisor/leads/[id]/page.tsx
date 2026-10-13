"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { api, ApiError, apiUpload } from "@/lib/api";
import { formatDate, formatUsd } from "@/lib/format";
import { TRUST_LABEL, trustTone, type Lead } from "@/lib/leads";
import { AiProse } from "@/components/ai-prose";
import { CallsSection } from "@/components/calls-section";
import { ProposalBadges, ProposalSections, type Proposal } from "@/components/proposal-view";
import { TrustBadge } from "@/components/score-badge";
import { WhyPanel } from "@/components/why-panel";
import { Badge, Button, Figure, inputClass, Loading, Notice, PageHeader, Panel, Section, tableStyles } from "@/components/ui";

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
const message = (e: unknown) => (e instanceof ApiError ? e.message : String(e));

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
  if (!lead) return <Loading label="Loading the lead" />;
  const factors = lead.lead_score_factors;
  const tone = trustTone(lead.trust_band);
  const risky = lead.trust_band === "high_risk" || lead.trust_band === "blocked";
  const latest = proposals[0];
  const fail = (name: string) => actionError[name] && <div className="mt-3"><Notice tone="error">{actionError[name]}</Notice></div>;

  return (
    <>
      <PageHeader title={lead.full_name} back={{ href: "/advisor", label: "Leads" }}
        description={`${lead.email}, ${lead.phone ?? "no phone"}. Came via ${lead.source} on ${formatDate(lead.created_at)}.`}
        actions={lead.stage !== "client" ? (
          <label className="flex items-center gap-2 text-sm">Stage
            <select value={lead.stage} disabled={Boolean(busy)} className={`${inputClass} w-40 py-1.5`}
              onChange={(e) => run("stage", async () => {
                setLead(await api<Lead>(`/leads/${id}/stage`, { method: "PATCH", body: JSON.stringify({ stage: e.target.value }) }));
              })}>
              {Object.entries(STAGE_NAME).map(([s, label]) => <option key={s} value={s}>{label}</option>)}
            </select>
          </label>
        ) : <Badge tone="gain">Client</Badge>} />
      <div className="space-y-12">
        {(actionError.stage || actionError.load || actionError.rescore) && (
          <Notice tone="error">{actionError.stage || actionError.load || `AI scoring failed: ${actionError.rescore}`}</Notice>
        )}
        {lead.scoring_error && (
          <Notice tone="caution" title="The AI analysis is missing" action={<Button variant="secondary" busy={busy === "rescore"}
            onClick={() => run("rescore", async () => { setLead(await api<Lead>(`/leads/${id}/rescore`, { method: "POST" })); })}>Retry AI scoring</Button>}>
            {lead.scoring_error}. The rule-based scores below are complete.
          </Notice>
        )}
        {!lead.scored_at && (
          <Button busy={busy === "rescore"} onClick={() => run("rescore", async () => { setLead(await api<Lead>(`/leads/${id}/rescore`, { method: "POST" })); await load(); })}>
            {busy === "rescore" ? "Scoring with Gemini" : "Score this lead with AI"}
          </Button>
        )}
        <div className="grid gap-6 md:grid-cols-2">
          <Panel className="space-y-4 p-5">
            <Figure label="Lead Score" value={String(lead.lead_score ?? "Not scored")}
              detail={factors ? `${Math.round(factors.probability * 100)}% likely to become a client` : undefined} />
            {factors && (
              <WhyPanel title="what drives this score" model={`${factors.model} (${factors.source})`}
                evidence={[...factors.for.map((f) => ({ label: `For: ${f.label}`, detail: f.value })),
                  ...factors.against.map((f) => ({ label: `Against: ${f.label}`, detail: f.value }))]} />
            )}
          </Panel>
          <Panel className="space-y-4 p-5">
            <div className="flex items-start justify-between gap-3">
              <Figure label="Trust Score" value={String(lead.trust_score ?? "Not scored")} detail={ACTIONS[tone]} />
              <TrustBadge band={lead.trust_band} score={lead.trust_score} />
            </div>
            {lead.trust_signals && (
              <WhyPanel title={`trust signals (${TRUST_LABEL[tone]})`} model="fixed rule weights; Gemini and Document AI supply evidence"
                evidence={lead.trust_signals.length
                  ? lead.trust_signals.map((s) => ({ label: `${s.code} ${s.label} (${s.weight})`, detail: s.evidence + (s.blocking ? " A person must decide." : "") }))
                  : [{ label: "No risk signals", detail: "Nothing in the form, the history or the documents raised a flag." }]} />
            )}
          </Panel>
        </div>
        <Section title="Profile">
          <dl className="grid gap-x-8 gap-y-3 text-sm sm:grid-cols-2 lg:grid-cols-3">
            <div><dt className="text-muted">Goals</dt><dd>{lead.goals}</dd></div>
            <div><dt className="text-muted">Horizon</dt><dd className="num">{lead.horizon_years} years</dd></div>
            <div><dt className="text-muted">To invest now</dt><dd className="num">{formatUsd(lead.investable_usd)}</dd></div>
            <div><dt className="text-muted">Every month</dt><dd className="num">{formatUsd(lead.monthly_usd)}</dd></div>
            <div><dt className="text-muted">Source of funds</dt><dd>{lead.source_of_funds.replace("_", " ")}</dd></div>
            {lead.notes && <div className="sm:col-span-2"><dt className="text-muted">Notes</dt><dd>{lead.notes}</dd></div>}
          </dl>
          {lead.enrichment && (
            <div className="mt-6">
              <AiProse caption="Gemini's reading of the form. The prospect's own words stay above.">
                <p>{lead.enrichment.goals_summary}</p>
                <p className="mt-2"><span className="font-sans text-sm font-medium">Next best action. </span>{lead.next_best_action}</p>
                <p className="mt-2 flex flex-wrap items-center gap-1 font-sans text-sm">Suggested funds:
                  {lead.enrichment.suggested_funds.map((f) => <Badge key={f}>{f}</Badge>)}</p>
              </AiProse>
            </div>
          )}
        </Section>
        <Section title="Identity document" description="Gemini reads the fields; Document AI screens for tampering. The image is never stored.">
          <p className="mb-3 text-sm text-ink-2">
            Try a <a className="underline underline-offset-4" href="/demo/specimen-match.png" download>matching sample card</a> or a{" "}
            <a className="underline underline-offset-4" href="/demo/specimen-mismatch.png" download>mismatched one</a>.
          </p>
          <div className="flex flex-wrap items-center gap-3">
            <input type="file" accept="image/png,image/jpeg,application/pdf" className="text-sm file:mr-3 file:rounded-control file:border file:border-line-strong file:bg-surface file:px-3 file:py-1.5"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
            <Button disabled={!file} busy={busy === "identity"} onClick={() => run("identity", async () => {
              const form = new FormData();
              form.append("file", file!);
              setIdentity(await apiUpload<IdentityResult>(`/leads/${id}/documents`, form));
              await load();
            })}>{busy === "identity" ? "Analysing" : "Analyse document"}</Button>
          </div>
          {fail("identity")}
          {identity && (
            <div className="mt-4 space-y-3 text-sm">
              <dl className="grid gap-x-8 gap-y-2 sm:grid-cols-3">
                {Object.entries(identity.extracted).map(([k, v]) => (
                  <div key={k}><dt className="text-muted">{k.replaceAll("_", " ")}</dt><dd>{v === null ? "Not found" : String(v)}</dd></div>
                ))}
              </dl>
              {identity.findings.length === 0 ? <Notice tone="success">No findings: the document matches the form.</Notice> : (
                <ul className="divide-y divide-line border-y border-line">
                  {identity.findings.map((f) => (
                    <li key={f.code} className="py-2"><span className="font-medium">{f.code} {f.label} ({f.weight})</span>: {f.evidence}</li>
                  ))}
                </ul>
              )}
              <p className="text-xs text-muted">Checked by {identity.source}.</p>
            </div>
          )}
        </Section>
        <CallsSection leadId={id} onChange={load} />
        <Section title="Proposal" description="Gemini Pro writes a personalised proposal from the simulation and the fund documents. It is a draft for you to review; nothing is sent."
          actions={latest ? <Link href={`/advisor/leads/${id}/proposal`} className="text-sm underline underline-offset-4">Open the printable proposal</Link> : undefined}>
          <Button variant={latest ? "secondary" : "primary"} busy={busy === "proposal"} disabled={risky}
            onClick={() => run("proposal", async () => { await api<Proposal>(`/leads/${id}/proposal`, { method: "POST" }); await load(); })}>
            {busy === "proposal" ? "Gemini Pro is writing, which can take up to a minute" : latest ? "Write a new version" : "Write a proposal"}
          </Button>
          {risky && <p className="mt-2 text-sm text-muted">Resolve the trust review before preparing a proposal.</p>}
          {fail("proposal")}
          {latest && (
            <div className="mt-6 space-y-4">
              <ProposalBadges proposal={latest} />
              <ProposalSections proposal={latest} />
              {!latest.compliance.ok && (
                <ul className="space-y-1 rounded-panel border border-caution/30 bg-caution-wash p-3 text-sm">
                  {latest.compliance.findings.map((f, i) => <li key={i}><span className="font-medium">&ldquo;{f.phrase}&rdquo;</span>: {f.explanation} {f.suggestion}</li>)}
                </ul>
              )}
            </div>
          )}
        </Section>
        <div className="grid gap-12 lg:grid-cols-2">
          <Section title="First reply" description="The Lead Intelligence agent drafts it and checks it against the marketing rules.">
            <Button variant="secondary" busy={busy === "draft"} onClick={() => run("draft", async () => {
              setDraft(await api<Draft>(`/leads/${id}/draft-reply`, { method: "POST" }));
              await load();
            })}>{busy === "draft" ? "The agent is writing" : "Draft the first reply"}</Button>
            {fail("draft")}
            {draft && (
              <div className="mt-4 space-y-2">
                <input className={inputClass} aria-label="Subject" value={draft.subject} onChange={(e) => setDraft({ ...draft, subject: e.target.value })} />
                <textarea className={`${inputClass} h-48 font-serif text-[15.5px]`} aria-label="Message" value={draft.body} onChange={(e) => setDraft({ ...draft, body: e.target.value })} />
                <p className="text-xs text-daylight-ink">Drafted by Gemini. Edit it before you send it.</p>
                {draft.compliance.ok ? <Notice tone="success">Marketing-rule check passed ({draft.compliance.reviewed_by.join(" and ")}).</Notice> : (
                  <ul className="space-y-1 rounded-panel border border-caution/30 bg-caution-wash p-3 text-sm">
                    {draft.compliance.findings.map((f, i) => <li key={i}><span className="font-medium">&ldquo;{f.phrase}&rdquo;</span>: {f.explanation} {f.suggestion}</li>)}
                  </ul>
                )}
              </div>
            )}
          </Section>
          <Section title="Ask the concierge" description="Routes your question to the Lead Intelligence or the Trust and Fraud agent.">
            <form className="flex gap-2" onSubmit={(e) => {
              e.preventDefault();
              run("ask", async () => {
                setAnswer((await api<{ answer: string }>(`/leads/${id}/ask`, { method: "POST", body: JSON.stringify({ question }) })).answer);
                await load();
              });
            }}>
              <input className={inputClass} placeholder="Why is this lead flagged?" value={question} onChange={(e) => setQuestion(e.target.value)} />
              <Button type="submit" busy={busy === "ask"} disabled={question.trim().length < 3}>Ask</Button>
            </form>
            {fail("ask")}
            {answer && <div className="mt-4"><AiProse caption="Answered by the advisor concierge on Gemini"><p className="whitespace-pre-wrap">{answer}</p></AiProse></div>}
          </Section>
        </div>
        {lead.stage !== "client" ? (
          <Section title="Convert to client" description="Opens an account with everything already known. A high-risk lead needs a recorded reason.">
            {risky && (
              <textarea className={`${inputClass} mb-3`} rows={3} placeholder="Override reason (recorded): what did you verify, and how?"
                value={override} onChange={(e) => setOverride(e.target.value)} />
            )}
            <Button disabled={risky && override.trim().length < 5} busy={busy === "convert"} onClick={() => run("convert", async () => {
              setConverted(await api<{ account_number: string }>(`/leads/${id}/convert`, { method: "POST", body: JSON.stringify({ override_reason: override || null }) }));
              await load();
            })}>Convert to client</Button>
            {fail("convert")}
          </Section>
        ) : (
          <Notice tone="success" title="Client">
            Converted{converted ? ` with account ${converted.account_number}` : ""}. They can sign in as {lead.email}.
          </Notice>
        )}
        <Section title="AI activity on this lead" description="Every model call, with its purpose, model, confidence and cost.">
          {decisions.length === 0 ? <p className="text-sm text-muted">No AI calls yet.</p> : (
            <div className={tableStyles.wrap}>
              <table className={tableStyles.table}>
                <thead className={tableStyles.head}>
                  <tr><th className={tableStyles.th}>When</th><th className={tableStyles.th}>Purpose</th><th className={tableStyles.th}>Model</th>
                    <th className={`${tableStyles.th} text-right`}>Confidence</th><th className={`${tableStyles.th} text-right`}>Cost</th></tr>
                </thead>
                <tbody>
                  {decisions.map((d) => (
                    <tr key={d.id} className={tableStyles.row}>
                      <td className={`${tableStyles.td} num`}>{new Date(d.created_at).toLocaleTimeString()}</td>
                      <td className={tableStyles.td}>{d.purpose.replaceAll("_", " ")}</td>
                      <td className={`${tableStyles.td} text-ink-2`}>{d.model}</td>
                      <td className={`${tableStyles.td} num text-right`}>{d.confidence === null ? "" : `${Math.round(d.confidence * 100)}%`}</td>
                      <td className={`${tableStyles.td} num text-right`}>${Number(d.cost_usd).toFixed(4)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Section>
      </div>
    </>
  );
}
