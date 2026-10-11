"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { api, ApiError, apiUpload } from "@/lib/api";
import { formatUsd } from "@/lib/allocation";
import { TRUST_LABEL, trustTone, type Lead } from "@/lib/leads";
import { isSignedIn } from "@/lib/session";
import { TrustBadge } from "@/components/score-badge";
import { WhyPanel } from "@/components/why-panel";

type Finding = { code: string; label: string; weight: number; evidence: string; source: string; blocking: boolean };
type IdentityResult = { id: string; extracted: Record<string, string | number | null>; findings: Finding[];
  source: string; trust_score: number; trust_band: string };
type Compliance = { ok: boolean; reviewed_by: string[];
  findings: { phrase: string; rule: string; explanation: string; suggestion: string }[] };
type Draft = { subject: string; body: string; compliance: Compliance };
type Decision = { id: string; created_at: string; purpose: string; model: string; confidence: number | null;
  cost_usd: string };

const ACTIONS: Record<string, string> = {
  clear: "Proceed with onboarding.", review: "Add friction: step-up verification or an advisor call.",
  high_risk: "Hold for review before any onboarding.", blocked: "Blocked pending human review.",
  pending: "Not scored yet.",
};
const EDITABLE_STAGES = ["new", "qualified", "proposal", "onboarding", "disqualified"];

function message(e: unknown) {
  return e instanceof ApiError ? `${e.message}` : String(e);
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4">
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">{title}</h2>
      {children}
    </section>
  );
}

export default function LeadDetail() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [lead, setLead] = useState<Lead | null>(null);
  const [decisions, setDecisions] = useState<Decision[]>([]);
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

  const load = useCallback(async () => {
    try {
      setLead(await api<Lead>(`/leads/${id}`));
      setDecisions(await api<Decision[]>(`/leads/${id}/decisions`));
    } catch (e) {
      setError(message(e));
    }
  }, [id]);

  useEffect(() => {
    (async () => {
      if (!(await isSignedIn())) return router.push("/login");
      await load();
    })();
  }, [router, load]);

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

  if (error) return <p className="text-red-600">{error}</p>;
  if (!lead) return <p>Loading lead…</p>;
  const factors = lead.lead_score_factors;
  const tone = trustTone(lead.trust_band);
  const risky = lead.trust_band === "high_risk" || lead.trust_band === "blocked";

  return (
    <div className="space-y-4">
      <Link href="/advisor" className="text-sm text-[#0b5fff]">← Pipeline</Link>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">{lead.full_name}</h1>
          <p className="text-sm text-slate-500">{lead.email} · {lead.phone ?? "no phone"} · came via {lead.source} ·{" "}
            {new Date(lead.created_at).toLocaleString()}</p>
        </div>
        {lead.stage !== "client" && (
          <label className="text-sm">Stage{" "}
            <select value={lead.stage} disabled={!!busy} className="ml-1 rounded border border-slate-300 px-2 py-1"
              onChange={(e) => run("stage", async () => {
                setLead(await api<Lead>(`/leads/${id}/stage`, { method: "PATCH", body: JSON.stringify({ stage: e.target.value }) }));
              })}>
              {EDITABLE_STAGES.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </label>
        )}
      </div>

      {lead.scoring_error && (
        <div className="flex items-center justify-between rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm">
          <span>{lead.scoring_error}. Deterministic scores are shown; the AI analysis is missing.</span>
          <button className="rounded border border-amber-400 px-3 py-1" disabled={!!busy}
            onClick={() => run("rescore", async () => { setLead(await api<Lead>(`/leads/${id}/rescore`, { method: "POST" })); })}>
            Retry AI scoring
          </button>
        </div>
      )}
      {!lead.scored_at && (
        <button className="rounded bg-[#0b5fff] px-4 py-2 text-sm text-white" disabled={!!busy}
          onClick={() => run("rescore", async () => { setLead(await api<Lead>(`/leads/${id}/rescore`, { method: "POST" })); await load(); })}>
          {busy === "rescore" ? "Scoring with Gemini…" : "Score this lead with AI"}
        </button>
      )}

      <div className="grid gap-4 md:grid-cols-2">
        <Card title="Lead Score">
          <div className="flex items-baseline gap-3">
            <span className="text-4xl font-semibold">{lead.lead_score ?? "–"}</span>
            {factors && <span className="text-sm text-slate-500">{Math.round(factors.probability * 100)}% likely to convert</span>}
          </div>
          {factors && (
            <div className="mt-3">
              <WhyPanel title="what drives this score" model={`${factors.model} (${factors.source})`}
                evidence={[...factors.for.map((f) => ({ label: `+ ${f.label}`, detail: f.value })),
                  ...factors.against.map((f) => ({ label: `− ${f.label}`, detail: f.value }))]} />
            </div>
          )}
        </Card>
        <Card title="Trust Score">
          <div className="flex items-baseline gap-3">
            <span className="text-4xl font-semibold">{lead.trust_score ?? "–"}</span>
            <TrustBadge band={lead.trust_band} score={lead.trust_score} />
          </div>
          <p className="mt-1 text-sm text-slate-600">{ACTIONS[tone]}</p>
          {lead.trust_signals && (
            <div className="mt-3">
              <WhyPanel title={`trust signals (${TRUST_LABEL[tone]})`} model="fixed rule weights; Gemini and Document AI supply evidence"
                evidence={lead.trust_signals.length
                  ? lead.trust_signals.map((s) => ({ label: `${s.code} ${s.label} (${s.weight})`,
                      detail: s.evidence + (s.blocking ? " — needs a person to decide" : "") }))
                  : [{ label: "No risk signals", detail: "Nothing in the form, history or documents raised a flag." }]} />
            </div>
          )}
        </Card>
      </div>

      <Card title="Profile and AI analysis">
        <dl className="grid gap-x-6 gap-y-2 text-sm md:grid-cols-2">
          <div><dt className="text-slate-500">Goals</dt><dd>{lead.goals}</dd></div>
          <div><dt className="text-slate-500">Horizon</dt><dd>{lead.horizon_years} years</dd></div>
          <div><dt className="text-slate-500">Investable</dt><dd>{formatUsd(lead.investable_usd)}</dd></div>
          <div><dt className="text-slate-500">Monthly</dt><dd>{formatUsd(lead.monthly_usd)}</dd></div>
          <div><dt className="text-slate-500">Source of funds</dt><dd>{lead.source_of_funds}</dd></div>
          {lead.notes && <div className="md:col-span-2"><dt className="text-slate-500">Notes</dt><dd>{lead.notes}</dd></div>}
        </dl>
        {lead.enrichment && (
          <div className="mt-4 space-y-2 border-t border-slate-100 pt-3 text-sm">
            <p><span className="font-medium">AI summary:</span> {lead.enrichment.goals_summary}</p>
            <p className="flex flex-wrap items-center gap-1"><span className="font-medium">Suggested funds:</span>
              {lead.enrichment.suggested_funds.map((f) => <span key={f} className="rounded bg-slate-100 px-2 py-0.5 text-xs">{f}</span>)}</p>
            <p><span className="font-medium">Next best action:</span> {lead.next_best_action}</p>
          </div>
        )}
      </Card>

      <Card title="Identity document">
        <p className="mb-2 text-sm text-slate-600">Gemini reads the fields; Document AI screens for tampering. The image is not stored.
          Try a <a className="text-[#0b5fff]" href="/demo/specimen-match.png" download>matching SPECIMEN</a> or a{" "}
          <a className="text-[#0b5fff]" href="/demo/specimen-mismatch.png" download>mismatched one</a>.</p>
        <div className="flex flex-wrap items-center gap-2">
          <input type="file" accept="image/png,image/jpeg,application/pdf" className="text-sm"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
          <button className="rounded bg-[#0b5fff] px-3 py-1.5 text-sm text-white disabled:opacity-60" disabled={!file || !!busy}
            onClick={() => run("identity", async () => {
              const form = new FormData();
              form.append("file", file!);
              setIdentity(await apiUpload<IdentityResult>(`/leads/${id}/documents`, form));
              await load();
            })}>{busy === "identity" ? "Analysing…" : "Analyse document"}</button>
        </div>
        {actionError.identity && <p className="mt-2 text-sm text-red-600">{actionError.identity}</p>}
        {identity && (
          <div className="mt-3 space-y-2 text-sm">
            <dl className="grid gap-x-6 gap-y-1 md:grid-cols-3">
              {Object.entries(identity.extracted).map(([k, v]) => (
                <div key={k}><dt className="text-slate-500">{k.replaceAll("_", " ")}</dt><dd>{v === null ? "—" : String(v)}</dd></div>))}
            </dl>
            {identity.findings.length === 0
              ? <p className="text-emerald-700">No findings: the document matches the form.</p>
              : <ul className="list-disc pl-5">{identity.findings.map((f) => (
                  <li key={f.code}><span className="font-medium">{f.code} {f.label} ({f.weight})</span>: {f.evidence}</li>))}</ul>}
            <p className="text-xs text-slate-500">Checked by {identity.source}.</p>
          </div>
        )}
      </Card>

      <div className="grid gap-4 md:grid-cols-2">
        <Card title="AI first reply">
          <button className="rounded bg-[#0b5fff] px-3 py-1.5 text-sm text-white disabled:opacity-60" disabled={!!busy}
            onClick={() => run("draft", async () => { setDraft(await api<Draft>(`/leads/${id}/draft-reply`, { method: "POST" })); await load(); })}>
            {busy === "draft" ? "Lead Intelligence agent is writing…" : "Draft first reply"}</button>
          {actionError.draft && <p className="mt-2 text-sm text-red-600">{actionError.draft}</p>}
          {draft && (
            <div className="mt-3 space-y-2">
              <input className="w-full rounded border border-slate-300 px-2 py-1 text-sm" value={draft.subject}
                onChange={(e) => setDraft({ ...draft, subject: e.target.value })} />
              <textarea className="h-44 w-full rounded border border-slate-300 px-2 py-1 text-sm" value={draft.body}
                onChange={(e) => setDraft({ ...draft, body: e.target.value })} />
              {draft.compliance.ok
                ? <p className="text-sm text-emerald-700">Compliance check passed ({draft.compliance.reviewed_by.join(" + ")}).</p>
                : <ul className="list-disc rounded bg-amber-50 p-2 pl-6 text-sm">{draft.compliance.findings.map((f, i) => (
                    <li key={i}><span className="font-medium">“{f.phrase}”</span>: {f.explanation} {f.suggestion}</li>))}</ul>}
            </div>
          )}
        </Card>
        <Card title="Ask the advisor concierge">
          <div className="flex gap-2">
            <input className="flex-1 rounded border border-slate-300 px-2 py-1 text-sm" placeholder="Why is this lead flagged?"
              value={question} onChange={(e) => setQuestion(e.target.value)} />
            <button className="rounded bg-[#0b5fff] px-3 py-1.5 text-sm text-white disabled:opacity-60"
              disabled={question.trim().length < 3 || !!busy}
              onClick={() => run("ask", async () => {
                setAnswer((await api<{ answer: string }>(`/leads/${id}/ask`, { method: "POST", body: JSON.stringify({ question }) })).answer);
                await load();
              })}>{busy === "ask" ? "Thinking…" : "Ask"}</button>
          </div>
          {actionError.ask && <p className="mt-2 text-sm text-red-600">{actionError.ask}</p>}
          {answer && <p className="mt-3 whitespace-pre-wrap text-sm">{answer}</p>}
        </Card>
      </div>

      {lead.stage !== "client" ? (
        <Card title="Convert to client">
          {risky && (
            <textarea className="mb-2 w-full rounded border border-slate-300 px-2 py-1 text-sm"
              placeholder="Override reason (recorded): what did you verify, and how?"
              value={override} onChange={(e) => setOverride(e.target.value)} />
          )}
          <button className="rounded bg-emerald-700 px-3 py-1.5 text-sm text-white disabled:opacity-60"
            disabled={!!busy || (risky && override.trim().length < 5)}
            onClick={() => run("convert", async () => {
              setConverted(await api<{ account_number: string }>(`/leads/${id}/convert`,
                { method: "POST", body: JSON.stringify({ override_reason: override || null }) }));
              await load();
            })}>Convert to client</button>
          {actionError.convert && <p className="mt-2 text-sm text-red-600">{actionError.convert}</p>}
        </Card>
      ) : (
        <Card title="Client">
          <p className="text-sm">Converted{converted ? ` — account ${converted.account_number}` : ""}. They can sign in as {lead.email}.</p>
        </Card>
      )}

      <Card title="AI activity on this lead">
        {decisions.length === 0 ? <p className="text-sm text-slate-500">No AI calls yet.</p> : (
          <table className="w-full text-sm">
            <thead className="text-left text-slate-500"><tr><th>When</th><th>Purpose</th><th>Model</th><th>Confidence</th><th className="text-right">Cost</th></tr></thead>
            <tbody>{decisions.map((d) => (
              <tr key={d.id} className="border-t border-slate-100">
                <td>{new Date(d.created_at).toLocaleTimeString()}</td><td>{d.purpose.replaceAll("_", " ")}</td><td>{d.model}</td>
                <td>{d.confidence === null ? "—" : `${Math.round(d.confidence * 100)}%`}</td>
                <td className="text-right">${Number(d.cost_usd).toFixed(4)}</td></tr>))}</tbody>
          </table>
        )}
      </Card>
    </div>
  );
}
