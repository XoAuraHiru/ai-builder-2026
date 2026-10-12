"use client";

import { useEffect, useState } from "react";
import { motion } from "motion/react";
import { api, ApiError } from "@/lib/api";
import { formatDate } from "@/lib/format";
import { AiProse } from "@/components/ai-prose";
import { BAND_LABEL, Button, inputClass, Loading, Notice, PageHeader, Panel, RiskBand, Section, Segmented } from "@/components/ui";

type Option = { value: string | number; label: string };
type Question = { key: keyof Answers; text: string; options: Option[] | null };
type Answers = { horizon_years: number | null; withdraw_within_2y: string | null; max_loss_pct: number | null;
  reaction_to_drop: string | null; experience: string | null };
type Profile = { id: string; created_at: string; band: number; capacity_band: number; tolerance_band: number;
  answers: Answers; reasons: string[]; source: string };
type State = { current_band: number | null; profile: Profile | null; questions: Question[] };
type Preview = { band: number; capacity_band: number; tolerance_band: number; reasons: string[] };
type ChatOut = { reply: string; answers: Answers; missing: string[]; complete: boolean; preview: Preview | null };
type Message = { role: "user" | "assistant"; text: string; ai: boolean };

const EMPTY: Answers = { horizon_years: null, withdraw_within_2y: null, max_loss_pct: null, reaction_to_drop: null, experience: null };
const SHORT: Record<keyof Answers, string> = {
  horizon_years: "Horizon", withdraw_within_2y: "Withdrawals", max_loss_pct: "Largest fall", reaction_to_drop: "Reaction", experience: "Experience",
};
const OPENING = "Let's set your risk profile together: five short questions, answered in your own words. First, how many years until you expect to need most of this money?";

function Reasons({ band, reasons, capacity, tolerance }: { band: number; reasons: string[]; capacity: number; tolerance: number }) {
  return (
    <div className="space-y-4">
      <RiskBand band={band} size="lg" />
      <p className="text-sm text-ink-2">Capacity band {capacity}, tolerance band {tolerance}. Your band is the lower of the two.</p>
      <ul className="list-disc space-y-1 pl-5 text-sm text-ink-2">{reasons.map((r) => <li key={r}>{r}</li>)}</ul>
    </div>
  );
}

export default function ProfilePage() {
  const [state, setState] = useState<State | null>(null);
  const [mode, setMode] = useState<"chat" | "form">("chat");
  const [messages, setMessages] = useState<Message[]>([{ role: "assistant", text: OPENING, ai: false }]);
  const [draft, setDraft] = useState("");
  const [known, setKnown] = useState<Answers>(EMPTY);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [form, setForm] = useState<Answers>(EMPTY);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState("");

  const load = () => api<State>("/me/risk-profile").then(setState).catch((e) => setError(e instanceof ApiError ? e.message : "Atrium could not load your profile."));
  useEffect(() => { load(); }, []);

  async function send(e: React.FormEvent) {
    e.preventDefault();
    const text = draft.trim();
    if (!text || busy) return;
    const next: Message[] = [...messages, { role: "user", text, ai: false }];
    setMessages(next);
    setDraft("");
    setBusy(true);
    setError("");
    try {
      const r = await api<ChatOut>("/me/risk-profile/chat", { method: "POST", body: JSON.stringify({
        messages: next.slice(-12).map(({ role, text: t }) => ({ role, text: t })), known }) });
      setKnown(r.answers);
      setMessages([...next, { role: "assistant", text: r.reply, ai: true }]);
      setPreview(r.preview);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "The conversation is unavailable right now. Answer the five questions instead.");
    } finally {
      setBusy(false);
    }
  }

  async function save(answers: Answers, source: "conversation" | "questionnaire") {
    setBusy(true);
    setError("");
    try {
      await api("/me/risk-profile", { method: "POST", body: JSON.stringify({ answers, source }) });
      setSaved(source === "conversation" ? "Saved. Your profile now comes from this conversation." : "Saved. Your profile now comes from your answers.");
      setPreview(null);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Atrium could not save your profile.");
    } finally {
      setBusy(false);
    }
  }

  if (!state) return error ? <Notice tone="error">{error}</Notice> : <Loading label="Loading your risk profile" />;
  const formComplete = Object.values(form).every((v) => v !== null && v !== "");
  return (
    <>
      <PageHeader title="Risk profile" description="Your band, from 1 (preserve) to 5 (adventurous), is the lower of what you can afford to risk and what you are comfortable with. Atrium checks every instruction against it." />
      <div className="space-y-12">
        <Section title="Your band now">
          {state.profile ? (
            <div>
              <Reasons band={state.profile.band} reasons={state.profile.reasons} capacity={state.profile.capacity_band} tolerance={state.profile.tolerance_band} />
              <p className="mt-3 text-xs text-muted">Set on {formatDate(state.profile.created_at)} from {state.profile.source === "conversation" ? "a conversation" : "the questionnaire"}.</p>
            </div>
          ) : (
            <div className="space-y-2">
              <RiskBand band={state.current_band} size="lg" />
              <p className="text-sm text-ink-2">{state.current_band ? "Set when your account opened. Retake the profile below to see the reasoning behind it." : "Not set yet. Answer the five questions below."}</p>
            </div>
          )}
          {saved && <div className="mt-4"><Notice tone="success">{saved}</Notice></div>}
        </Section>
        <Section title="Retake your profile" actions={<Segmented label="How to answer" value={mode} onChange={setMode}
          options={[{ value: "chat", label: "Talk it through" }, { value: "form", label: "Answer five questions" }]} />}>
          {mode === "chat" ? (
            <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_260px]">
              <Panel className="flex min-h-[420px] flex-col">
                <ol className="flex-1 space-y-4 p-5" aria-live="polite">
                  {messages.map((m, i) => (
                    <li key={i} className={m.role === "user" ? "flex justify-end" : ""}>
                      {m.role === "user" ? (
                        <p className="max-w-[80%] rounded-panel bg-ink px-4 py-2.5 text-[15px] text-white">{m.text}</p>
                      ) : m.ai ? (
                        <AiProse caption="Gemini"><p>{m.text}</p></AiProse>
                      ) : (
                        <p className="max-w-[60ch] text-[15px] text-ink">{m.text}</p>
                      )}
                    </li>
                  ))}
                  {busy && <li className="text-sm text-muted" role="status">Gemini is reading your answer…</li>}
                </ol>
                <form onSubmit={send} className="flex gap-2 border-t border-line p-3">
                  <label htmlFor="answer" className="sr-only">Your answer</label>
                  <input id="answer" className={inputClass} value={draft} maxLength={1000} onChange={(e) => setDraft(e.target.value)}
                    placeholder="Answer in your own words" disabled={busy || Boolean(preview)} />
                  <Button type="submit" busy={busy} disabled={!draft.trim() || Boolean(preview)}>Send</Button>
                </form>
              </Panel>
              <div className="space-y-6">
                <div>
                  <p className="text-sm font-medium">What Atrium has understood</p>
                  <ul className="mt-3 space-y-2 text-sm">
                    {(Object.keys(SHORT) as (keyof Answers)[]).map((k) => (
                      <li key={k} className="grid grid-cols-[6.5rem_1fr] items-center gap-3">
                        <span className="text-ink-2">{SHORT[k]}</span>
                        <span className="h-1.5 overflow-hidden rounded-full bg-line">
                          <motion.span className="block h-1.5 origin-left rounded-full bg-ink" initial={false} animate={{ scaleX: known[k] === null ? 0 : 1 }} />
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
                {preview && (
                  <Panel className="space-y-4 p-4">
                    <p className="text-sm font-medium">Your result</p>
                    <Reasons band={preview.band} reasons={preview.reasons} capacity={preview.capacity_band} tolerance={preview.tolerance_band} />
                    <p className="text-xs text-muted">Computed by Atrium&apos;s rules from your answers, not by the AI. Nothing is saved until you choose.</p>
                    <Button busy={busy} onClick={() => save(known, "conversation")}>Save this profile</Button>
                  </Panel>
                )}
              </div>
            </div>
          ) : (
            <form className="max-w-2xl space-y-6" onSubmit={(e) => { e.preventDefault(); if (formComplete) save(form, "questionnaire"); }}>
              {state.questions.map((q) => (
                <fieldset key={q.key}>
                  <legend className="text-sm font-medium">{q.text}</legend>
                  {q.options === null ? (
                    <input type="number" min={0} max={60} required className={`${inputClass} num mt-2 max-w-32`} aria-label="Years"
                      value={form.horizon_years ?? ""} onChange={(e) => setForm({ ...form, horizon_years: e.target.value === "" ? null : Number(e.target.value) })} />
                  ) : (
                    <div className="mt-2 flex flex-wrap gap-2">
                      {q.options.map((o) => {
                        const on = form[q.key] === o.value;
                        return (
                          <label key={String(o.value)} className={`cursor-pointer rounded-control border px-3 py-1.5 text-sm ${on ? "border-ink bg-ink text-white" : "border-line-strong hover:border-ink"}`}>
                            <input type="radio" className="sr-only" name={q.key} checked={on} onChange={() => setForm({ ...form, [q.key]: o.value })} />
                            {o.label}
                          </label>
                        );
                      })}
                    </div>
                  )}
                </fieldset>
              ))}
              <Button type="submit" busy={busy} disabled={!formComplete}>Save my profile</Button>
            </form>
          )}
          {error && <div className="mt-4"><Notice tone="caution">{error}</Notice></div>}
        </Section>
        <p className="text-xs text-muted">Bands: {Object.entries(BAND_LABEL).map(([b, l]) => `${b} ${l}`).join(", ")}.</p>
      </div>
    </>
  );
}
