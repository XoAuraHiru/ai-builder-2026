"use client";

import { useState } from "react";
import { api, ApiError } from "@/lib/api";
import { deviceId } from "@/lib/leads";
import { Button, Field, inputClass, MoneyInput, Notice, Panel } from "@/components/ui";

const FUNDS = [["salary", "Salary"], ["business", "Business income"], ["savings", "Savings"], ["inheritance", "Inheritance"],
  ["property_sale", "Property sale"], ["investments", "Investments"], ["other", "Other"], ["unspecified", "Prefer not to say"]];
const SOURCES = [["web", "Searching online"], ["referral", "A friend or colleague"], ["email", "An email from Atrium"],
  ["event", "An event or seminar"], ["chat", "Chat"]];

export default function ApplyPage() {
  const [form, setForm] = useState({ full_name: "", email: "", phone: "", goals: "", horizon_years: "10",
    investable_usd: "", monthly_usd: "0", source_of_funds: "salary", source: "web", notes: "" });
  const [state, setState] = useState<"idle" | "sending" | "done">("idle");
  const [error, setError] = useState("");
  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
    setForm({ ...form, [k]: e.target.value });

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setState("sending");
    setError("");
    try {
      await api("/leads", { method: "POST", body: JSON.stringify({
        ...form, phone: form.phone || null, notes: form.notes || null, country: "US", horizon_years: Number(form.horizon_years),
        investable_usd: form.investable_usd || "0", monthly_usd: form.monthly_usd || "0", device_id: deviceId(localStorage) }) });
      setState("done");
    } catch (err) {
      setState("idle");
      setError(err instanceof ApiError && err.status === 429 ? "We have received several applications from this device. Please try again later."
        : err instanceof ApiError && err.status === 422 ? "Some answers need another look. Check the fields and try again."
        : "Your application did not reach us. Please try again.");
    }
  }

  return (
    <div className="grid gap-12 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
      <div className="max-w-md">
        <h1 className="wide text-[34px] font-semibold leading-[1.1] tracking-[-0.02em]">Start investing with Atrium</h1>
        <p className="mt-4 text-[17px] leading-relaxed text-ink-2">Tell us what you are investing for. An advisor reads every application.</p>
        <ol className="mt-8 space-y-4 border-t border-line pt-6 text-sm">
          <li><span className="num font-semibold">1</span> <span className="font-medium">You tell us your goals.</span> <span className="text-ink-2">Two minutes, in your own words.</span></li>
          <li><span className="num font-semibold">2</span> <span className="font-medium">An advisor gets in touch.</span> <span className="text-ink-2">Within one business day.</span></li>
          <li><span className="num font-semibold">3</span> <span className="font-medium">You see a proposal.</span> <span className="text-ink-2">Funds that fit you, what your money could become, and what it costs.</span></li>
        </ol>
        <p className="mt-8 text-xs text-muted">This is a prototype. Please do not enter real personal information.</p>
      </div>
      {state === "done" ? (
        <Panel className="h-fit p-6">
          <h2 className="text-lg font-semibold">Thank you</h2>
          <p className="mt-2 text-ink-2">An Atrium advisor will be in touch within one business day.</p>
        </Panel>
      ) : (
        <Panel className="p-6">
          <form onSubmit={submit} className="space-y-5">
            <div className="grid gap-5 sm:grid-cols-2">
              <Field label="Full name"><input required minLength={2} className={inputClass} value={form.full_name} onChange={set("full_name")} autoComplete="name" /></Field>
              <Field label="Email"><input required type="email" className={inputClass} value={form.email} onChange={set("email")} autoComplete="email" /></Field>
            </div>
            <Field label="Phone" hint="Optional"><input className={inputClass} placeholder="+1 415 555 0123" value={form.phone} onChange={set("phone")} autoComplete="tel" /></Field>
            <Field label="What are you investing for?"><textarea required minLength={3} rows={3} className={inputClass} value={form.goals} onChange={set("goals")} /></Field>
            <div className="grid gap-5 sm:grid-cols-3">
              <Field label="Years"><input required type="number" min={0} max={50} className={`${inputClass} num`} value={form.horizon_years} onChange={set("horizon_years")} /></Field>
              <Field label="To invest now"><MoneyInput value={form.investable_usd} onChange={(v) => setForm({ ...form, investable_usd: v })} /></Field>
              <Field label="Every month"><MoneyInput value={form.monthly_usd} onChange={(v) => setForm({ ...form, monthly_usd: v })} /></Field>
            </div>
            <div className="grid gap-5 sm:grid-cols-2">
              <Field label="Where the money comes from">
                <select className={inputClass} value={form.source_of_funds} onChange={set("source_of_funds")}>
                  {FUNDS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                </select>
              </Field>
              <Field label="How did you hear about us?">
                <select className={inputClass} value={form.source} onChange={set("source")}>
                  {SOURCES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                </select>
              </Field>
            </div>
            <Field label="Anything else?" hint="Optional"><textarea rows={2} className={inputClass} value={form.notes} onChange={set("notes")} /></Field>
            {error && <Notice tone="error">{error}</Notice>}
            <Button type="submit" busy={state === "sending"} disabled={!form.investable_usd}>Send application</Button>
          </form>
        </Panel>
      )}
    </div>
  );
}
