"use client";

import { useEffect, useRef, useState } from "react";
import { motion, useReducedMotion } from "motion/react";
import { api, ApiError } from "@/lib/api";
import { useMe } from "@/lib/session-context";
import { AiProse } from "@/components/ai-prose";
import { WhyPanel } from "@/components/why-panel";
import { Button, EmptyState, Notice, PageHeader } from "@/components/ui";

type Trace = { tool: string; label: string };
type Source = { id: string; title: string };
type Turn = { role: "user" | "assistant"; text: string; trace?: Trace[]; sources?: Source[] };

const SUGGESTIONS = [
  "Why did my portfolio move this week?",
  "What happens if I withdraw $10,000?",
  "Which of my funds costs the most in fees?",
  "How risky is my portfolio compared with my profile?",
];
const TOOL_DETAIL: Record<string, string> = {
  get_portfolio: "Your holdings, values and gains.",
  get_recent_performance: "Published fund prices over the period.",
  get_transactions: "Your recent instructions.",
  get_risk_report: "Risk analytics over market history since 2007.",
  get_xray: "A look through your funds to companies, sectors and fees.",
  get_profile: "Your risk profile.",
  run_what_if: "Atrium's simulation engine: a simulation, not a forecast.",
  preview_withdrawal: "Your purchase lots, first in, first out, at the latest prices.",
  search_fund_documents: "Atrium's fund documents.",
};

function Thinking() {
  const reduce = useReducedMotion();
  return (
    <div role="status" className="space-y-2">
      <p className="text-sm text-muted">The copilot is checking your data and the fund documents…</p>
      <div className="h-[2px] w-48 overflow-hidden rounded-full bg-line">
        <motion.span className="block h-full w-1/3 rounded-full bg-daylight" animate={reduce ? undefined : { x: ["-100%", "300%"] }}
          transition={{ duration: 1.4, repeat: Infinity, ease: "easeInOut" }} />
      </div>
    </div>
  );
}

export default function CopilotPage() {
  const me = useMe();
  const account = me.accounts[0];
  const [turns, setTurns] = useState<Turn[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const end = useRef<HTMLDivElement>(null);

  useEffect(() => {
    end.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [turns, busy]);

  async function ask(question: string) {
    const q = question.trim();
    if (q.length < 3 || busy || !account) return;
    const history = turns.slice(-8).map(({ role, text }) => ({ role, text: text.slice(0, 2000) }));
    setTurns((t) => [...t, { role: "user", text: q }]);
    setDraft("");
    setBusy(true);
    setError("");
    try {
      const r = await api<{ answer: string; trace: Trace[]; sources: Source[] }>(`/accounts/${account.id}/copilot`,
        { method: "POST", body: JSON.stringify({ question: q, history }) });
      setTurns((t) => [...t, { role: "assistant", text: r.answer, trace: r.trace, sources: r.sources }]);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "The copilot could not answer right now. Try again in a minute.");
    } finally {
      setBusy(false);
    }
  }

  if (!account) return <EmptyState title="No investment account yet">Choose an investor persona to talk to the copilot.</EmptyState>;
  return (
    <>
      <PageHeader title="Copilot" description="Ask about your portfolio, your fees or any Atrium fund. The copilot looks up your data and the fund documents before it answers, and shows you what it checked." />
      <div className="max-w-3xl">
        {turns.length === 0 && (
          <div className="mb-8">
            <p className="text-sm font-medium">Try asking</p>
            <ul className="mt-3 grid gap-2 sm:grid-cols-2">
              {SUGGESTIONS.map((s) => (
                <li key={s}>
                  <button type="button" onClick={() => ask(s)} className="w-full rounded-panel border border-line bg-surface px-4 py-3 text-left text-sm hover:border-ink">
                    {s}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}
        <ol className="space-y-7" aria-live="polite">
          {turns.map((t, i) => (
            <li key={i} className={t.role === "user" ? "flex justify-end" : ""}>
              {t.role === "user" ? (
                <p className="max-w-[80%] rounded-panel bg-ink px-4 py-2.5 text-[15px] text-white">{t.text}</p>
              ) : (
                <div className="space-y-3">
                  <AiProse caption="Written by Gemini from your data and Atrium's fund documents"><p className="whitespace-pre-line">{t.text}</p></AiProse>
                  {(t.trace?.length || t.sources?.length) ? (
                    <WhyPanel title="what the copilot checked" model="Investor Copilot agent on Gemini (Vertex AI, ADK)"
                      evidence={[...(t.trace ?? []).map((x) => ({ label: x.label, detail: TOOL_DETAIL[x.tool] ?? x.tool })),
                        ...(t.sources ?? []).map((s) => ({ label: "Fund document", detail: s.title }))]} />
                  ) : null}
                </div>
              )}
            </li>
          ))}
        </ol>
        {busy && <div className="mt-6"><Thinking /></div>}
        {error && <div className="mt-6"><Notice tone="caution">{error}</Notice></div>}
        <div ref={end} />
        <form onSubmit={(e) => { e.preventDefault(); ask(draft); }}
          className="sticky bottom-4 mt-8 flex gap-2 rounded-panel border border-line bg-surface p-2 shadow-[0_12px_32px_-16px_rgba(23,32,42,0.35)]">
          <label htmlFor="question" className="sr-only">Your question</label>
          <input id="question" value={draft} maxLength={500} onChange={(e) => setDraft(e.target.value)} placeholder="Ask about your portfolio or a fund"
            className="min-w-0 flex-1 bg-transparent px-2 py-2 text-[15px] placeholder:text-muted focus:outline-none" />
          <Button type="submit" busy={busy} disabled={draft.trim().length < 3}>Ask</Button>
        </form>
      </div>
    </>
  );
}
