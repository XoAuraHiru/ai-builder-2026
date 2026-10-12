"use client";

import { useState } from "react";
import { api, ApiError } from "@/lib/api";
import { deviceId } from "@/lib/leads";

const FUNDS = ["salary", "business", "savings", "inheritance", "property_sale", "investments", "other", "unspecified"];
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
        ...form, phone: form.phone || null, notes: form.notes || null, country: "US",
        horizon_years: Number(form.horizon_years), device_id: deviceId(localStorage) }) });
      setState("done");
    } catch (err) {
      setState("idle");
      setError(err instanceof ApiError && err.status === 429
        ? "We've received several submissions from this device; please try again later."
        : err instanceof ApiError && err.status === 422 ? "Please check the highlighted fields and try again."
        : "Something went wrong; please try again.");
    }
  }

  if (state === "done")
    return <div className="mx-auto max-w-lg rounded-lg border border-slate-200 bg-white p-6">
      <h1 className="text-xl font-semibold">Thank you</h1>
      <p className="mt-2 text-slate-600">An Atrium advisor will be in touch within one business day.</p></div>;

  const input = "mt-1 w-full rounded border border-slate-300 px-3 py-2";
  return (
    <form onSubmit={submit} className="mx-auto max-w-lg space-y-3">
      <h1 className="text-2xl font-semibold">Start investing with Atrium</h1>
      <p className="text-sm text-slate-600">Tell us about your goals. Every field helps us match you with the right advisor.</p>
      <label className="block text-sm">Full name<input required minLength={2} className={input} value={form.full_name} onChange={set("full_name")} /></label>
      <label className="block text-sm">Email<input required type="email" className={input} value={form.email} onChange={set("email")} /></label>
      <label className="block text-sm">Phone<input className={input} placeholder="+1 415 555 0123" value={form.phone} onChange={set("phone")} /></label>
      <label className="block text-sm">What are you investing for?<textarea required minLength={3} className={input} value={form.goals} onChange={set("goals")} /></label>
      <div className="grid grid-cols-3 gap-3">
        <label className="block text-sm">Years<input required type="number" min={0} max={50} className={input} value={form.horizon_years} onChange={set("horizon_years")} /></label>
        <label className="block text-sm">To invest ($)<input required type="number" min={0} className={input} value={form.investable_usd} onChange={set("investable_usd")} /></label>
        <label className="block text-sm">Monthly ($)<input type="number" min={0} className={input} value={form.monthly_usd} onChange={set("monthly_usd")} /></label>
      </div>
      <label className="block text-sm">Source of funds
        <select className={input} value={form.source_of_funds} onChange={set("source_of_funds")}>
          {FUNDS.map((f) => <option key={f} value={f}>{f.replace("_", " ")}</option>)}</select></label>
      <label className="block text-sm">How did you hear about us?
        <select className={input} value={form.source} onChange={set("source")}>
          {SOURCES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>
      <label className="block text-sm">Anything else?<textarea className={input} value={form.notes} onChange={set("notes")} /></label>
      {error && <p className="text-sm text-red-600">{error}</p>}
      <button disabled={state === "sending"} className="rounded bg-[#0b5fff] px-4 py-2 text-white disabled:opacity-60">
        {state === "sending" ? "Sending…" : "Send"}</button>
      <p className="text-xs text-slate-500">Prototype: please do not enter real personal information.</p>
    </form>
  );
}
