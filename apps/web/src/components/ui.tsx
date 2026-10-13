"use client";

import Link from "next/link";
import { motion } from "motion/react";
import { createContext, useContext, useId, type ButtonHTMLAttributes, type ReactNode, type SelectHTMLAttributes } from "react";

export const BAND_LABEL: Record<number, string> = { 1: "Preserve", 2: "Cautious", 3: "Balanced", 4: "Growth", 5: "Adventurous" };

export function Spinner() {
  return (
    <svg className="h-3.5 w-3.5 animate-spin motion-reduce:animate-none" viewBox="0 0 16 16" aria-hidden="true">
      <circle cx="8" cy="8" r="6.5" fill="none" stroke="currentColor" strokeOpacity="0.25" strokeWidth="2" />
      <path d="M14.5 8A6.5 6.5 0 0 0 8 1.5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

/** Gemini's mark: a four-point sparkle, used only where the AI wrote or answers something. */
export function Sparkle({ size = 14 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M12 2l2.2 7.8L22 12l-7.8 2.2L12 22l-2.2-7.8L2 12l7.8-2.2z" />
    </svg>
  );
}

// Solid green for the main action (one per view), tonal green for entering a journey, outlined white for the rest,
// a text button for "View all", tonal coral for destructive actions, and violet only for asking Gemini.
type Variant = "primary" | "tonal" | "secondary" | "quiet" | "danger" | "ai";
type Size = "md" | "sm";
const VARIANT: Record<Variant, string> = {
  primary: "bg-green-500 font-semibold text-white hover:bg-green-600 disabled:bg-sand-100 disabled:text-ink-400",
  tonal: "bg-green-100 font-semibold text-green-800 hover:bg-green-200 disabled:bg-sand-100 disabled:text-ink-400",
  secondary: "border border-sand-200 bg-white font-medium text-ink-900 hover:bg-fill disabled:text-ink-400",
  quiet: "font-semibold text-green-600 hover:bg-green-50 disabled:text-ink-400",
  danger: "bg-coral-50 font-semibold text-coral-700 hover:bg-coral-100 disabled:bg-sand-100 disabled:text-ink-400",
  ai: "bg-ai-50 font-semibold text-ai-700 hover:bg-ai-100 disabled:text-ink-400",
};
const BASE = "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-full transition-colors duration-150 disabled:cursor-not-allowed";
const SIZE: Record<Size, string> = { md: "min-h-11 px-5 text-sm", sm: "min-h-9 px-4 text-[13px]" };

function classes(variant: Variant, size: Size, className: string) {
  return `${BASE} ${variant === "quiet" ? (size === "sm" ? "min-h-9 px-3 text-[13px]" : "min-h-10 px-3.5 text-sm") : SIZE[size]} ${VARIANT[variant]} ${className}`;
}

export function Button({ variant = "primary", size = "md", busy = false, className = "", children, ...rest }:
  ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: Size; busy?: boolean }) {
  return (
    <button type="button" {...rest} disabled={rest.disabled || busy} aria-busy={busy || undefined} className={classes(variant, size, className)}>
      {busy && <Spinner />}
      {children}
    </button>
  );
}

export function ButtonLink({ href, variant = "primary", size = "md", className = "", children }:
  { href: string; variant?: Variant; size?: Size; className?: string; children: ReactNode }) {
  return <Link href={href} className={classes(variant, size, className)}>{children}</Link>;
}

/** Fields are filled sand, 44px tall, with the label above; focus shows the green ring. */
export const inputClass =
  "w-full min-h-11 rounded-control border-0 bg-fill px-3.5 py-2.5 text-[15px] text-ink-900 placeholder:text-ink-400 transition-shadow focus:outline-none focus:ring-[3px] focus:ring-green-200 aria-[invalid=true]:ring-[3px] aria-[invalid=true]:ring-coral-100 disabled:text-ink-400";

export function Field({ label, hint, error, className = "", children }:
  { label: string; hint?: string; error?: string; className?: string; children: ReactNode }) {
  return (
    <label className={`block ${className}`}>
      <span className="block text-[13px] font-medium leading-[18px] text-ink-900">{label}</span>
      {hint && <span className="mt-0.5 block text-xs text-ink-500">{hint}</span>}
      <span className="mt-1.5 block">{children}</span>
      {error && <span role="alert" className="mt-1.5 block text-[13px] text-coral-700">{error}</span>}
    </label>
  );
}

/** Digits with thousands separators for display; the value passed around stays plain ("25000.5"). */
export function groupDigits(raw: string): string {
  if (!raw) return "";
  const [whole, fraction] = raw.split(".");
  const grouped = whole ? Number(whole).toLocaleString("en-US") : "0";
  return fraction !== undefined ? `${grouped}.${fraction.slice(0, 2)}` : grouped;
}

export function MoneyInput({ value, onChange, placeholder, label, id, invalid }:
  { value: string; onChange: (v: string) => void; placeholder?: string; label?: string; id?: string; invalid?: boolean }) {
  return (
    <span className="relative block">
      <span aria-hidden="true" className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-ink-500">$</span>
      <input id={id} inputMode="decimal" aria-label={label} aria-invalid={invalid || undefined} className={`${inputClass} num pl-8`} value={groupDigits(value)}
        placeholder={placeholder} onChange={(e) => onChange(e.target.value.replace(/[^\d.]/g, "").replace(/(\..*)\./g, "$1"))} />
    </span>
  );
}

/** A select styled as a field: filled sand, 44px, the design's chevron in place of the browser's arrow. */
export function Select({ className = "", children, ...rest }: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <span className="relative block">
      <select {...rest} className={`${inputClass} appearance-none pr-10 ${className}`}>{children}</select>
      <svg aria-hidden="true" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
        strokeLinecap="round" strokeLinejoin="round" className="pointer-events-none absolute right-3.5 top-1/2 -translate-y-1/2 text-ink-500">
        <path d="m6 9 6 6 6-6" />
      </svg>
    </span>
  );
}

/** The section's pages (X-ray, Risk, Scenarios…), set by the shell and shown in the page header as a segmented control. */
export const PageTabsContext = createContext<ReactNode>(null);

export function PageHeader({ title, description, actions, back, badge }:
  { title: string; description?: ReactNode; actions?: ReactNode; back?: { href: string; label: string }; badge?: ReactNode }) {
  const tabs = useContext(PageTabsContext);
  return (
    <header className="mb-8 flex flex-wrap items-end justify-between gap-x-6 gap-y-4">
      <div className="min-w-0 max-w-[720px]">
        {back && (
          <Link href={back.href} className="mb-2 inline-flex min-h-8 items-center gap-1.5 text-[13px] font-medium text-ink-500 hover:text-ink-900">
            <span aria-hidden="true">‹</span>{back.label}
          </Link>
        )}
        <div className="flex flex-wrap items-center gap-x-3.5 gap-y-2">
          <h1 className="text-[30px] font-semibold leading-9 tracking-[-0.02em] sm:text-[36px] sm:leading-[42px] sm:tracking-[-0.025em]">{title}</h1>
          {badge}
        </div>
        {description && <p className="mt-2 max-w-[64ch] text-[15px] leading-[22px] text-ink-700">{description}</p>}
      </div>
      {(tabs || actions) && (
        <div className="flex flex-wrap items-center gap-2">
          {actions}
          {tabs}
        </div>
      )}
    </header>
  );
}

/** A figure from an engine: Schibsted Grotesk, medium weight, proportional numerals. */
export function Figure({ label, value, detail, tone, size = "md" }:
  { label: string; value: string; detail?: ReactNode; tone?: "gain" | "loss"; size?: "md" | "lg" }) {
  const color = tone === "gain" ? "text-green-700" : tone === "loss" ? "text-coral-700" : "text-ink-900";
  const scale = size === "lg" ? "text-[44px] leading-[48px] tracking-[-0.03em] sm:text-[60px] sm:leading-[60px] sm:tracking-[-0.035em]"
    : "text-[30px] leading-[34px] tracking-[-0.02em]";
  return (
    <div className="min-w-0">
      <div className="text-sm font-medium text-ink-700">{label}</div>
      <div className={`mt-1.5 font-medium ${scale} ${color}`}>{value}</div>
      {detail && <div className="mt-2 text-sm text-ink-700">{detail}</div>}
    </div>
  );
}

type Tone = "info" | "caution" | "error" | "success";
const NOTICE: Record<Tone, { box: string; dot: string }> = {
  info: { box: "bg-fill", dot: "bg-ink-400" }, caution: { box: "bg-amber-50", dot: "bg-amber-400" },
  error: { box: "bg-coral-50", dot: "bg-coral-500" }, success: { box: "bg-green-50", dot: "bg-green-500" },
};

export function Notice({ tone = "info", title, action, children }:
  { tone?: Tone; title?: string; action?: ReactNode; children?: ReactNode }) {
  return (
    <div role={tone === "error" ? "alert" : undefined}
      className={`flex flex-wrap items-start justify-between gap-3 rounded-panel px-5 py-4 text-sm ${NOTICE[tone].box}`}>
      <div className="flex min-w-0 flex-1 gap-3">
        <span aria-hidden="true" className={`mt-[7px] h-1.5 w-1.5 shrink-0 rounded-full ${NOTICE[tone].dot}`} />
        <div className="min-w-0">
          {title && <p className="font-semibold text-ink-900">{title}</p>}
          {children && <div className="text-ink-700">{children}</div>}
        </div>
      </div>
      {action}
    </div>
  );
}

// Status chips carry a dot so colour is never the only signal.
type BadgeTone = "neutral" | "white" | "gain" | "caution" | "loss" | "strong" | "ai";
const BADGE: Record<BadgeTone, { chip: string; dot: string }> = {
  neutral: { chip: "bg-fill text-ink-700", dot: "bg-ink-400" },
  white: { chip: "bg-white text-ink-700", dot: "bg-ink-400" },
  gain: { chip: "bg-green-50 text-green-700", dot: "bg-green-500" },
  caution: { chip: "bg-amber-50 text-amber-800", dot: "bg-amber-400" },
  loss: { chip: "bg-coral-50 text-coral-700", dot: "bg-coral-500" },
  strong: { chip: "bg-coral-700 text-white", dot: "bg-white" },
  ai: { chip: "bg-ai-50 text-ai-700", dot: "" },
};

export function Badge({ tone = "neutral", size = "md", children }: { tone?: BadgeTone; size?: "md" | "sm"; children: ReactNode }) {
  const scale = size === "sm" ? "h-[26px] px-2.5 text-xs" : "h-7 px-3 text-[13px]";  // sm in table rows
  return (
    <span className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full font-medium ${scale} ${BADGE[tone].chip}`}>
      {tone === "ai" ? <Sparkle size={12} /> : <span aria-hidden="true" className={`h-1.5 w-1.5 rounded-full ${BADGE[tone].dot}`} />}
      {children}
    </span>
  );
}

/** A change chip: always with an arrow or a sign, so the direction never rests on colour. */
export function ChangeChip({ value, tone, size = "sm", children }:
  { value?: number; tone?: "gain" | "loss" | "caution"; size?: "sm" | "md"; children: ReactNode }) {
  const t = tone ?? (value === undefined || value === 0 ? "caution" : value > 0 ? "gain" : "loss");
  const cls = t === "gain" ? "bg-green-50 text-green-700" : t === "loss" ? "bg-coral-50 text-coral-700" : "bg-amber-50 text-amber-800";
  const scale = size === "md" ? "h-[26px] px-2.5 text-[13px]" : "h-[22px] px-2 text-xs";
  return <span className={`num inline-flex items-center gap-1 whitespace-nowrap rounded-full font-semibold ${scale} ${cls}`}>{children}</span>;
}

/** A risk band as a five-step meter: green at or within the profile, amber above it. */
export function RiskBand({ band, size = "sm", showLabel = true, profile = 3 }:
  { band: number | null; size?: "sm" | "lg"; showLabel?: boolean; profile?: number | null }) {
  const cell = size === "lg" ? "h-3 w-7" : "h-2 w-3.5";
  const above = band !== null && profile !== null && band > (profile ?? 3);
  const fill = above ? "bg-amber-400" : "bg-green-500";
  return (
    <span className="inline-flex items-center gap-2.5" role="img" aria-label={band ? `Risk band ${band} of 5, ${BAND_LABEL[band]}${above ? ", above the profile" : ""}` : "No risk band yet"}>
      <span className="flex gap-[3px]" aria-hidden="true">
        {[1, 2, 3, 4, 5].map((i) => (
          <span key={i} className={`${cell} rounded-[3px] ${band && i <= band ? fill : "bg-sand-200"}`} />
        ))}
      </span>
      {showLabel && (
        <span aria-hidden="true" className={`${size === "lg" ? "text-base" : "text-[13px]"} whitespace-nowrap font-medium ${band ? (above ? "text-amber-800" : "text-green-700") : "text-ink-500"}`}>
          {band ? `${band} ${BAND_LABEL[band]}` : "Not set"}
        </span>
      )}
    </span>
  );
}

export function Section({ title, description, actions, id, children }:
  { title: string; description?: ReactNode; actions?: ReactNode; id?: string; children: ReactNode }) {
  return (
    <section id={id} className="scroll-mt-24">
      <div className="mb-4 flex flex-wrap items-baseline justify-between gap-3 px-1">
        <div className="min-w-0">
          <h2 className="text-[20px] font-semibold leading-7 tracking-[-0.01em]">{title}</h2>
          {description && <p className="mt-1 max-w-[72ch] text-[13px] leading-5 text-ink-500">{description}</p>}
        </div>
        {actions}
      </div>
      {children}
    </section>
  );
}

/** A card: white, outlined with the sand hairline, 20px corners. Shadows are kept for things that float. */
export function Panel({ className = "", children }: { className?: string; children: ReactNode }) {
  return <div className={`rounded-panel border border-sand-200 bg-white ${className}`}>{children}</div>;
}

type MomentTone = "attention" | "alert" | "good" | "info";
const MOMENT: Record<MomentTone, BadgeTone> = { attention: "caution", alert: "loss", good: "gain", info: "neutral" };

/** The card a page opens with: what matters on this page, said as one sentence, with the proof and the next action. */
export function KeyMoment({ tone = "attention", label, title, children, actions }:
  { tone?: MomentTone; label: string; title: ReactNode; children?: ReactNode; actions?: ReactNode }) {
  const id = useId();
  return (
    <section aria-labelledby={id} className="flex flex-col gap-6 rounded-panel border border-sand-200 bg-white p-6 sm:p-7">
      <span className="self-start"><Badge tone={MOMENT[tone]}>{label}</Badge></span>
      <h2 id={id} className="max-w-[620px] text-[26px] font-semibold leading-8 tracking-[-0.02em] sm:text-[32px] sm:leading-[38px]">{title}</h2>
      {children && <div className="space-y-5">{children}</div>}
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </section>
  );
}

export function Loading({ label }: { label: string }) {
  return <p role="status" className="py-10 text-sm text-ink-500">{label}…</p>;
}

export function EmptyState({ title, action, children }: { title: string; action?: ReactNode; children?: ReactNode }) {
  return (
    <div className="rounded-panel border border-dashed border-sand-300 bg-white px-6 py-12 text-center">
      <p className="font-semibold">{title}</p>
      {children && <div className="mx-auto mt-1 max-w-[52ch] text-sm text-ink-700">{children}</div>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

/** An input-style segmented control: sand fill, the chosen option raised in white. */
export function Segmented<T extends string>({ value, options, onChange, label }:
  { value: T; options: { value: T; label: string }[]; onChange: (v: T) => void; label: string }) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex flex-wrap gap-1 rounded-full bg-fill p-1">
      {options.map((o) => {
        const on = o.value === value;
        return (
          <button key={o.value} type="button" role="radio" aria-checked={on} onClick={() => onChange(o.value)}
            className={`relative min-h-9 rounded-full px-4 text-[13px] ${on ? "font-semibold text-ink-900" : "font-medium text-ink-700 hover:text-ink-900"}`}>
            {on && <motion.span layoutId={`segmented-${label}`} className="absolute inset-0 rounded-full bg-white shadow-pressed" />}
            <span className="relative">{o.label}</span>
          </button>
        );
      })}
    </div>
  );
}

/** Navigation as a segmented pill (the section's pages): white with a hairline, the current page in tonal green. */
export function NavSegmented({ label, items }: { label: string; items: { href: string; label: string; on: boolean }[] }) {
  return (
    <nav aria-label={label} className="no-print inline-flex max-w-full gap-1 overflow-x-auto rounded-full border border-sand-200 bg-white p-1">
      {items.map((t) => (
        <Link key={t.href} href={t.href} aria-current={t.on ? "page" : undefined}
          className={`whitespace-nowrap rounded-full px-[18px] py-[9px] text-sm font-medium ${t.on ? "bg-green-100 text-green-800" : "text-ink-700 hover:bg-fill"}`}>
          {t.label}
        </Link>
      ))}
    </nav>
  );
}

export const tableStyles = {
  wrap: "overflow-x-auto",
  table: "w-full text-sm",
  head: "border-b border-sand-100 text-left text-xs text-ink-500",
  th: "px-3 py-2.5 font-medium first:pl-0 last:pr-0",
  row: "border-b border-sand-100 last:border-b-0",
  td: "px-3 py-3 first:pl-0 last:pr-0",
  id: "code whitespace-nowrap text-ink-700",
  amount: "whitespace-nowrap text-right tabular-nums",
};
