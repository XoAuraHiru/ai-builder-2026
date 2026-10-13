"use client";

import { AnimatePresence, motion } from "motion/react";
import { useEffect, useState } from "react";
import { readApply } from "@/lib/analyzer";
import { api, ApiError } from "@/lib/api";
import { applicationErrors, deviceId, type ApplicationField } from "@/lib/leads";
import { FieldError } from "@/components/form-feedback";
import { DrawnCheck, EASE, Stagger, StaggerItem } from "@/components/motion";
import { Badge, Button, Field, inputClass, MoneyInput, Notice, Panel } from "@/components/ui";

const FUNDS = [["salary", "Salary"], ["business", "Business income"], ["savings", "Savings"], ["inheritance", "Inheritance"],
  ["property_sale", "Property sale"], ["investments", "Investments"], ["other", "Other"], ["unspecified", "Prefer not to say"]];
const SOURCES = [["web", "Searching online"], ["referral", "A friend or colleague"], ["email", "An email from Atrium"],
  ["event", "An event or seminar"], ["chat", "Chat"]];
const STEPS = [
  { title: "You tell us your goals.", detail: "Two minutes, in your own words." },
  { title: "An advisor gets in touch.", detail: "Within one business day." },
  { title: "You see a proposal.", detail: "Funds that fit you, what your money could become, and what it costs." },
];

export default function ApplyPage() {
  const [form, setForm] = useState({ full_name: "", email: "", phone: "", goals: "", horizon_years: "10",
    investable_usd: "", monthly_usd: "0", source_of_funds: "salary", source: "web", notes: "" });
  const [state, setState] = useState<"idle" | "sending" | "done">("idle");
  const [error, setError] = useState("");
  const [checked, setChecked] = useState(false);  // field errors show once the person has tried to send
  // From the front-door analyzer: its amounts and years fill the form, and the application carries the analysis.
  const [analysis, setAnalysis] = useState<string | null>(null);

  useEffect(() => {
    const plan = readApply(new URLSearchParams(window.location.search));
    if (!plan) return;
    setAnalysis(plan.analysis);
    setForm((f) => ({ ...f, investable_usd: String(plan.amount), monthly_usd: String(plan.monthly ?? 0),
      horizon_years: String(plan.years ?? f.horizon_years) }));
  }, []);

  const problems = applicationErrors(form);
  const fieldError = (k: ApplicationField) => (checked ? problems[k] : undefined);
  const invalid = (k: ApplicationField) => Boolean(fieldError(k)) || undefined;
  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
    setForm({ ...form, [k]: e.target.value });

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setChecked(true);
    if (Object.keys(problems).length) return;
    setState("sending");
    setError("");
    try {
      await api("/leads", { method: "POST", body: JSON.stringify({
        ...form, phone: form.phone || null, notes: form.notes || null, country: "US", horizon_years: Number(form.horizon_years),
        investable_usd: form.investable_usd || "0", monthly_usd: form.monthly_usd || "0", device_id: deviceId(localStorage),
        ...(analysis ? { analysis_id: analysis } : {}) }) });
      setState("done");
    } catch (err) {
      setState("idle");
      setError(err instanceof ApiError && err.status === 429 ? "We have received several applications from this device. Please try again later."
        : err instanceof ApiError && err.status === 422 ? "Some answers need another look. Check the fields and try again."
        : "Your application did not reach us. Please try again.");
    }
  }

  return (
    <div className="grid gap-10 lg:grid-cols-[minmax(0,0.85fr)_minmax(0,1.15fr)] lg:gap-16">
      <div className="max-w-[460px]">
        <h1 className="text-[30px] font-semibold leading-9 tracking-[-0.02em] sm:text-[36px] sm:leading-[42px] sm:tracking-[-0.025em]">
          Start investing with Atrium
        </h1>
        <p className="mt-3 text-[17px] leading-[26px] text-ink-700">Tell us what you are investing for. An advisor reads every application.</p>
        <Stagger as="ol" className="mt-8 flex flex-col gap-3">
          {STEPS.map((s, i) => (
            <StaggerItem as="li" key={s.title} className="flex gap-3.5 rounded-control bg-fill px-4 py-3.5">
              <span aria-hidden="true" className="num flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-green-100 text-xs font-semibold text-green-800">{i + 1}</span>
              <span className="text-sm leading-[21px]">
                <span className="block font-semibold">{s.title}</span>
                <span className="block text-ink-700">{s.detail}</span>
              </span>
            </StaggerItem>
          ))}
        </Stagger>
        <p className="mt-6 text-[13px] leading-[19px] text-ink-500">This is a prototype. Please do not enter real personal information.</p>
      </div>
      {state === "done" ? (
        // The application went through: the card settles in and its check draws itself. Focus stays where it was.
        <motion.div role="status" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.32, ease: EASE }}
          className="h-fit">
          <Panel className="flex h-fit flex-col items-start gap-3 p-6 sm:p-8">
            <span className="mb-1 flex h-12 w-12 items-center justify-center rounded-full bg-green-50 text-green-600"><DrawnCheck size={24} /></span>
            <Badge tone="gain">Application sent</Badge>
            <h2 className="text-[22px] font-semibold leading-7 tracking-[-0.01em]">Thank you</h2>
            <p className="text-[15px] leading-[22px] text-ink-700">An Atrium advisor will be in touch within one business day.</p>
          </Panel>
        </motion.div>
      ) : (
        <Panel className="p-5 sm:p-8">
          <form onSubmit={submit} noValidate className="space-y-5">
            {analysis && (
              <Notice tone="success" title="Filled in from your analysis">
                The amounts and years come from the analysis you ran. Your advisor sees it with your application.
              </Notice>
            )}
            <div className="grid gap-5 sm:grid-cols-2">
              <Field label="Full name">
                <input required minLength={2} aria-invalid={invalid("full_name")} className={inputClass} value={form.full_name} onChange={set("full_name")} autoComplete="name" />
                <FieldError message={fieldError("full_name")} />
              </Field>
              <Field label="Email">
                <input required type="email" aria-invalid={invalid("email")} className={inputClass} value={form.email} onChange={set("email")} autoComplete="email" />
                <FieldError message={fieldError("email")} />
              </Field>
            </div>
            <Field label="Phone" hint="Optional"><input className={inputClass} placeholder="+1 415 555 0123" value={form.phone} onChange={set("phone")} autoComplete="tel" /></Field>
            <Field label="What are you investing for?">
              <textarea required minLength={3} rows={3} aria-invalid={invalid("goals")} className={inputClass} value={form.goals} onChange={set("goals")}
                placeholder="For example: a home deposit in five years" />
              <FieldError message={fieldError("goals")} />
            </Field>
            <div className="grid gap-5 sm:grid-cols-3">
              <Field label="Years">
                <input required type="number" min={0} max={50} inputMode="numeric" aria-invalid={invalid("horizon_years")} className={`${inputClass} num`} value={form.horizon_years} onChange={set("horizon_years")} />
                <FieldError message={fieldError("horizon_years")} />
              </Field>
              <Field label="To invest now">
                {/* MoneyInput takes no aria-invalid, so its wrapper carries the same coral ring as the other fields. */}
                <span className={`block rounded-control ${invalid("investable_usd") ? "ring-[3px] ring-coral-100" : ""}`}>
                  <MoneyInput label="To invest now" value={form.investable_usd} onChange={(v) => setForm({ ...form, investable_usd: v })} placeholder="25,000" />
                </span>
                <FieldError message={fieldError("investable_usd")} />
              </Field>
              <Field label="Every month (optional)">
                <MoneyInput label="Every month" value={form.monthly_usd} onChange={(v) => setForm({ ...form, monthly_usd: v })} />
              </Field>
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
            <div className="flex flex-wrap items-center gap-3 pt-1">
              <Button type="submit" busy={state === "sending"}>{state === "sending" ? "Sending" : "Send application"}</Button>
              <AnimatePresence initial={false}>
                {checked && Object.keys(problems).length > 0 && (
                  <motion.span key="problems" role="status" className="text-[13px] text-coral-700"
                    initial={{ opacity: 0, x: -4 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.2, ease: EASE }}>
                    {Object.keys(problems).length === 1 ? "One answer needs" : `${Object.keys(problems).length} answers need`} another look.
                  </motion.span>
                )}
              </AnimatePresence>
            </div>
          </form>
        </Panel>
      )}
    </div>
  );
}
