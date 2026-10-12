"use client";

import Link from "next/link";
import { motion } from "motion/react";
import type { ButtonHTMLAttributes, ReactNode } from "react";

export const BAND_LABEL: Record<number, string> = { 1: "Preserve", 2: "Cautious", 3: "Balanced", 4: "Growth", 5: "Adventurous" };
const BAND_BG: Record<number, string> = { 1: "bg-band-1", 2: "bg-band-2", 3: "bg-band-3", 4: "bg-band-4", 5: "bg-band-5" };

export function Spinner() {
  return (
    <svg className="h-3.5 w-3.5 animate-spin motion-reduce:animate-none" viewBox="0 0 16 16" aria-hidden="true">
      <circle cx="8" cy="8" r="6.5" fill="none" stroke="currentColor" strokeOpacity="0.25" strokeWidth="2" />
      <path d="M14.5 8A6.5 6.5 0 0 0 8 1.5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

type Variant = "primary" | "secondary" | "quiet" | "danger";
const VARIANT: Record<Variant, string> = {
  primary: "bg-ink text-white hover:bg-ink-2 disabled:bg-line-strong",
  secondary: "border border-line-strong bg-surface text-ink hover:border-ink disabled:border-line disabled:text-muted",
  quiet: "text-ink underline decoration-line-strong underline-offset-4 hover:decoration-ink disabled:text-muted",
  danger: "bg-loss text-white hover:brightness-110 disabled:opacity-50",
};
const BASE = "inline-flex items-center justify-center gap-2 text-sm font-medium transition-colors duration-150 disabled:cursor-not-allowed";
const PAD = "rounded-control px-3.5 py-2";

export function Button({ variant = "primary", busy = false, className = "", children, ...rest }:
  ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; busy?: boolean }) {
  return (
    <button type="button" {...rest} disabled={rest.disabled || busy} aria-busy={busy || undefined}
      className={`${BASE} ${variant === "quiet" ? "" : PAD} ${VARIANT[variant]} ${className}`}>
      {busy && <Spinner />}
      {children}
    </button>
  );
}

export function ButtonLink({ href, variant = "primary", className = "", children }:
  { href: string; variant?: Variant; className?: string; children: ReactNode }) {
  return (
    <Link href={href} className={`${BASE} ${variant === "quiet" ? "" : PAD} ${VARIANT[variant]} ${className}`}>
      {children}
    </Link>
  );
}

export const inputClass =
  "w-full rounded-control border border-line-strong bg-surface px-3 py-2 text-[15px] text-ink placeholder:text-muted transition-colors focus:border-ink focus:outline-none disabled:bg-ground";

export function Field({ label, hint, error, className = "", children }:
  { label: string; hint?: string; error?: string; className?: string; children: ReactNode }) {
  return (
    <label className={`block ${className}`}>
      <span className="block text-sm font-medium text-ink">{label}</span>
      {hint && <span className="mt-0.5 block text-xs text-muted">{hint}</span>}
      <span className="mt-1.5 block">{children}</span>
      {error && <span role="alert" className="mt-1 block text-xs text-loss">{error}</span>}
    </label>
  );
}

export function MoneyInput({ value, onChange, placeholder, label, id }:
  { value: string; onChange: (v: string) => void; placeholder?: string; label?: string; id?: string }) {
  return (
    <span className="relative block">
      <span aria-hidden="true" className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted">$</span>
      <input id={id} inputMode="decimal" aria-label={label} className={`${inputClass} num pl-7`} value={value}
        placeholder={placeholder} onChange={(e) => onChange(e.target.value.replace(/[^\d.]/g, ""))} />
    </span>
  );
}

export function PageHeader({ title, description, actions, back }:
  { title: string; description?: ReactNode; actions?: ReactNode; back?: { href: string; label: string } }) {
  return (
    <header className="mb-8 flex flex-wrap items-end justify-between gap-x-6 gap-y-4 border-b border-line pb-6">
      <div className="min-w-0 max-w-3xl">
        {back && <Link href={back.href} className="mb-3 inline-block text-sm text-muted hover:text-ink">{back.label}</Link>}
        <h1 className="wide text-[30px] font-semibold leading-[1.15] tracking-[-0.015em]">{title}</h1>
        {description && <p className="mt-2 text-[15px] leading-relaxed text-ink-2">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </header>
  );
}

export function Figure({ label, value, detail, tone, size = "md" }:
  { label: string; value: string; detail?: ReactNode; tone?: "gain" | "loss"; size?: "md" | "lg" }) {
  const color = tone === "gain" ? "text-gain" : tone === "loss" ? "text-loss" : "text-ink";
  const scale = size === "lg" ? "text-[40px] leading-none sm:text-[48px]" : "text-[26px] leading-tight";
  return (
    <div className="min-w-0">
      <div className="text-sm text-muted">{label}</div>
      <div className={`num wider mt-1 font-semibold tracking-[-0.02em] ${scale} ${color}`}>{value}</div>
      {detail && <div className="mt-1.5 text-sm text-ink-2">{detail}</div>}
    </div>
  );
}

type Tone = "info" | "caution" | "error" | "success";
const NOTICE: Record<Tone, string> = {
  info: "border-line bg-surface", caution: "border-caution/30 bg-caution-wash",
  error: "border-loss/30 bg-danger-wash", success: "border-gain/30 bg-gain-wash",
};
const NOTICE_BAR: Record<Tone, string> = { info: "bg-ink-2", caution: "bg-caution", error: "bg-loss", success: "bg-gain" };

export function Notice({ tone = "info", title, action, children }:
  { tone?: Tone; title?: string; action?: ReactNode; children?: ReactNode }) {
  return (
    <div role={tone === "error" ? "alert" : undefined}
      className={`relative flex flex-wrap items-start justify-between gap-3 overflow-hidden rounded-panel border py-3 pl-5 pr-4 text-sm ${NOTICE[tone]}`}>
      <span aria-hidden="true" className={`absolute inset-y-0 left-0 w-[3px] ${NOTICE_BAR[tone]}`} />
      <div className="min-w-0 flex-1">
        {title && <p className="font-medium text-ink">{title}</p>}
        {children && <div className="text-ink-2">{children}</div>}
      </div>
      {action}
    </div>
  );
}

type BadgeTone = "neutral" | "gain" | "caution" | "loss" | "strong" | "ai";
const BADGE: Record<BadgeTone, string> = {
  neutral: "border-line-strong text-ink-2", gain: "border-gain/30 bg-gain-wash text-gain",
  caution: "border-caution/30 bg-caution-wash text-caution", loss: "border-loss/30 bg-danger-wash text-loss",
  strong: "border-loss bg-loss text-white", ai: "border-daylight/60 bg-daylight-wash text-daylight-ink",
};

export function Badge({ tone = "neutral", children }: { tone?: BadgeTone; children: ReactNode }) {
  return (
    <span className={`inline-flex items-center gap-1 whitespace-nowrap rounded-[4px] border px-1.5 py-px text-xs font-medium ${BADGE[tone]}`}>
      {children}
    </span>
  );
}

/** A risk band as five cells, filled up to the band in the band's colour. */
export function RiskBand({ band, size = "sm", showLabel = true }: { band: number | null; size?: "sm" | "lg"; showLabel?: boolean }) {
  const cell = size === "lg" ? "h-3 w-7" : "h-2 w-3.5";
  return (
    <span className="inline-flex items-center gap-2" role="img" aria-label={band ? `Risk band ${band} of 5, ${BAND_LABEL[band]}` : "No risk band yet"}>
      <span className="flex gap-[3px]" aria-hidden="true">
        {[1, 2, 3, 4, 5].map((i) => (
          <span key={i} className={`${cell} rounded-[2px] ${band && i <= band ? BAND_BG[band] : "bg-line"}`} />
        ))}
      </span>
      {showLabel && (
        <span aria-hidden="true" className={`${size === "lg" ? "text-base" : "text-xs"} font-medium text-ink-2`}>
          {band ? `Band ${band}, ${BAND_LABEL[band]}` : "Not set"}
        </span>
      )}
    </span>
  );
}

export function Section({ title, description, actions, id, children }:
  { title: string; description?: ReactNode; actions?: ReactNode; id?: string; children: ReactNode }) {
  return (
    <section id={id} className="scroll-mt-20 border-t border-line pt-6 first:border-t-0 first:pt-0">
      <div className="mb-4 flex flex-wrap items-baseline justify-between gap-3">
        <div className="min-w-0">
          <h2 className="text-[17px] font-semibold tracking-[-0.005em]">{title}</h2>
          {description && <p className="mt-0.5 max-w-[68ch] text-sm text-muted">{description}</p>}
        </div>
        {actions}
      </div>
      {children}
    </section>
  );
}

export function Panel({ className = "", children }: { className?: string; children: ReactNode }) {
  return <div className={`rounded-panel border border-line bg-surface ${className}`}>{children}</div>;
}

export function Loading({ label }: { label: string }) {
  return <p role="status" className="py-10 text-sm text-muted">{label}…</p>;
}

export function EmptyState({ title, action, children }: { title: string; action?: ReactNode; children?: ReactNode }) {
  return (
    <div className="rounded-panel border border-dashed border-line-strong bg-surface px-6 py-12 text-center">
      <p className="font-medium">{title}</p>
      {children && <div className="mx-auto mt-1 max-w-[52ch] text-sm text-ink-2">{children}</div>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

export function Segmented<T extends string>({ value, options, onChange, label }:
  { value: T; options: { value: T; label: string }[]; onChange: (v: T) => void; label: string }) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex flex-wrap rounded-control border border-line-strong bg-surface p-0.5">
      {options.map((o) => {
        const on = o.value === value;
        return (
          <button key={o.value} type="button" role="radio" aria-checked={on} onClick={() => onChange(o.value)}
            className={`relative rounded-[5px] px-3 py-1.5 text-sm ${on ? "text-white" : "text-ink-2 hover:text-ink"}`}>
            {on && <motion.span layoutId={`segmented-${label}`} className="absolute inset-0 rounded-[5px] bg-ink" />}
            <span className="relative">{o.label}</span>
          </button>
        );
      })}
    </div>
  );
}

export const tableStyles = {
  wrap: "overflow-x-auto",
  table: "w-full text-sm",
  head: "border-b border-line text-left text-xs text-muted",
  th: "px-3 py-2 font-medium first:pl-0 last:pr-0",
  row: "border-b border-line last:border-b-0",
  td: "px-3 py-2.5 first:pl-0 last:pr-0",
};
