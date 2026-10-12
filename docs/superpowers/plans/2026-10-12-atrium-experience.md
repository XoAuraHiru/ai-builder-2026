# Atrium Experience Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure the Atrium web app so a judge opening it cold understands what Atrium is, whose shoes they are in and what to try next, with an elegant, consistent visual system.

**Architecture:**
- **Front door.** A story-led front door at `/` replaces the persona list.
- **Shell.** One shell serves every signed-in person: a top bar with the four stages and the person, a rail with only their own workspace (five items at most, tabs for grouped pages), and a journey guide.
- **Journey guide.** It ticks off steps as the person visits their pages, from pure, unit-tested logic in `lib/journeys.ts`.
- **Kit.** The UI kit is restyled once, so every page picks up the new look.
- **Key moments.** Four pages are rebuilt around their key moment: Investor home, Leads, Reconciliation and an AML alert.
- **No API changes.**

**Tech stack:** Next.js 15 (app router, client components), Tailwind v4 tokens in `globals.css`, motion 12, Vitest.

**Spec:** `docs/superpowers/specs/2026-10-12-atrium-experience-design.md`. The visual reference is the Claude Design canvas "Atrium redesign".

## Global Constraints

- **Look, "Atrium Daylight":**
  - **Colour:** ground `#F1F3F1`, surface `#FFFFFF`, ink `#0F1B24`, ink-2 `#3A4652`, muted `#5F6B76`, line `#DCE1DE`, line-strong `#C3CAC6`.
  - **Daylight:** `#E3A72F`, ink `#7A5508`, wash `#FBF1D9`. It is used only for AI and explanation.
  - **Status:** gain `#157347` (wash `#E5F2EA`), loss `#B23A26` (wash `#FBEAE6`), caution `#8A5A00` (wash `#FCF2DF`).
  - **Shape:** panels have an 18 px radius; controls have a 12 px radius; buttons are pills at least 44 px tall.
- **Type:**
  - Archivo; `wide` (width 116) for headlines and key figures; `num` for tabular figures.
  - Source Serif 4 only for AI-written prose.
- **Copy:** sentence case. No all-caps labels. No "→" appended to links. No middle-dot joined labels. Refer to people as they/them in docs.
- **Motion:** only in answer to an action, such as the rail highlight and the tab underline following navigation. Respect reduced motion (the existing `MotionProvider` does).
- **Accessibility:** real links and buttons; `aria-current` on the current rail item and tab; text contrast of 4.5:1; no horizontal page scroll at 390 px.
- **Market scope and names:**
  - US and global markets only.
  - Never write employer or client names. `infra/.forbidden-words` is checked by `infra/preflight.sh`, and a forbidden word is never quoted, even when stating this rule.
- **Data:** synthetic data only. No API changes; every existing feature keeps working.
- **Windows:**
  - Write files containing backslashes with the Write tool, not a heredoc.
  - Gate each task with `pnpm tsc --noEmit`, `pnpm lint` and `pnpm vitest run` in `apps/web`.
  - Never run `next build` while `next dev` is running.
- **Commits:** end each commit message with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- **Deploys:** report the cost on every deploy.

## Review Focus

1. **A persona with no journey or no workspace** (an admin, or a future investor not in the demo list). The shell still renders, the guide is simply absent, and nothing throws (Tasks 2 and 3 tests).
2. **Local storage blocked or holding junk** (private mode, an old value). Journey progress and the guide's hidden flag fall back to defaults (Task 2 tests).
3. **Deep pages map to the right rail item and tab:**
   - a symbol page `/investor/markets/NVDA` to Markets;
   - a fund page `/investor/funds/ATR-BAL` to Funds;
   - a lead `/advisor/leads/x` and its proposal to Leads;
   - an alert `/compliance/alerts/x` to Alerts;
   - the Copilot to no section (Task 2 tests).
4. **Signed-out visitors** on any app page go to the front door, not a dead login page; with Firebase sign-in, persona buttons send people to `/login` (Task 4).
5. **Phone width:** the rail becomes a strip, the guide drops below the page, and wide content scrolls inside its own box (Task 9 screenshots at 390 px).

---

### Task 1: Tokens and the kit

The visual system is restyled in one place, `globals.css` and `components/ui.tsx`, so every page picks it up. The changes:
- the new tokens;
- pill buttons with a small size;
- an 18 px panel radius;
- notices marked by a small square instead of a left bar;
- rounded badges;
- headers and sections without rules;
- `KeyMoment`, the panel each restructured page opens with.

AI prose loses its left rule and gains a caption led by a daylight square.

**Files:**
- Modify: `apps/web/src/app/globals.css`
- Modify (rewrite): `apps/web/src/components/ui.tsx`
- Modify: `apps/web/src/components/ai-prose.tsx`

**Interfaces:**
- Consumes: nothing new.
- Produces (for Tasks 3 to 9):
  - Every existing export of `ui.tsx`, with the same props.
  - `Button` and `ButtonLink` gain `size?: "md" | "sm"`.
  - `KeyMoment({ tone?: "attention" | "alert" | "good" | "info", label, title, children?, actions? })`.
  - The token `--color-wash` (`bg-wash`).

- [ ] **Step 1: Update the tokens**

In `apps/web/src/app/globals.css`, replace the colour and radius lines inside `@theme` (keep the band colours, fonts and `--ease-soft`) with:

```css
  --color-ground: #f1f3f1;
  --color-surface: #ffffff;
  --color-wash: #e8ece9;
  --color-ink: #0f1b24;
  --color-ink-2: #3a4652;
  --color-muted: #5f6b76;
  --color-line: #dce1de;
  --color-line-strong: #c3cac6;
  --color-daylight: #e3a72f;
  --color-daylight-ink: #7a5508;
  --color-daylight-wash: #fbf1d9;
  --color-gain: #157347;
  --color-gain-wash: #e5f2ea;
  --color-loss: #b23a26;
  --color-danger-wash: #fbeae6;
  --color-caution: #8a5a00;
  --color-caution-wash: #fcf2df;
```

```css
  --radius-control: 12px;
  --radius-panel: 18px;
```

and change the `wide` utility to:

```css
@utility wide {
  font-variation-settings: "wdth" 116;
}
```

- [ ] **Step 2: Rewrite the kit**

```tsx
// file: apps/web/src/components/ui.tsx
"use client";

import Link from "next/link";
import { motion } from "motion/react";
import { useId, type ButtonHTMLAttributes, type ReactNode } from "react";

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
type Size = "md" | "sm";
const VARIANT: Record<Variant, string> = {
  primary: "bg-ink text-white hover:bg-[#26343f] disabled:bg-line-strong",
  secondary: "border border-line-strong bg-surface text-ink hover:border-ink disabled:border-line disabled:text-muted",
  quiet: "text-ink underline decoration-line-strong underline-offset-4 hover:decoration-ink disabled:text-muted",
  danger: "bg-loss text-white hover:bg-[#962f1e] disabled:opacity-50",
};
const BASE = "inline-flex items-center justify-center gap-2 font-semibold transition-colors duration-150 disabled:cursor-not-allowed";
const SIZE: Record<Size, string> = { md: "min-h-11 rounded-full px-5 text-sm", sm: "min-h-9 rounded-full px-4 text-[13px]" };

function classes(variant: Variant, size: Size, className: string) {
  return `${BASE} ${variant === "quiet" ? "text-sm" : SIZE[size]} ${VARIANT[variant]} ${className}`;
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

export const inputClass =
  "w-full rounded-control border border-line-strong bg-surface px-3.5 py-2.5 text-[15px] text-ink placeholder:text-muted transition-colors focus:border-ink focus:outline-none disabled:bg-ground";

export function Field({ label, hint, error, className = "", children }:
  { label: string; hint?: string; error?: string; className?: string; children: ReactNode }) {
  return (
    <label className={`block ${className}`}>
      <span className="block text-sm font-semibold text-ink">{label}</span>
      {hint && <span className="mt-0.5 block text-xs text-muted">{hint}</span>}
      <span className="mt-1.5 block">{children}</span>
      {error && <span role="alert" className="mt-1 block text-xs text-loss">{error}</span>}
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

export function MoneyInput({ value, onChange, placeholder, label, id }:
  { value: string; onChange: (v: string) => void; placeholder?: string; label?: string; id?: string }) {
  return (
    <span className="relative block">
      <span aria-hidden="true" className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-muted">$</span>
      <input id={id} inputMode="decimal" aria-label={label} className={`${inputClass} num pl-8`} value={groupDigits(value)}
        placeholder={placeholder} onChange={(e) => onChange(e.target.value.replace(/[^\d.]/g, "").replace(/(\..*)\./g, "$1"))} />
    </span>
  );
}

export function PageHeader({ title, description, actions, back }:
  { title: string; description?: ReactNode; actions?: ReactNode; back?: { href: string; label: string } }) {
  return (
    <header className="mb-8 flex flex-wrap items-end justify-between gap-x-6 gap-y-4">
      <div className="min-w-0 max-w-3xl">
        {back && (
          <Link href={back.href} className="mb-2 inline-flex min-h-8 items-center gap-1.5 text-sm text-muted hover:text-ink">
            <span aria-hidden="true">‹</span>{back.label}
          </Link>
        )}
        <h1 className="wide text-[30px] font-semibold leading-[1.12] tracking-[-0.015em] sm:text-[34px]">{title}</h1>
        {description && <p className="mt-2 max-w-[62ch] text-[15px] leading-relaxed text-ink-2">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </header>
  );
}

export function Figure({ label, value, detail, tone, size = "md" }:
  { label: string; value: string; detail?: ReactNode; tone?: "gain" | "loss"; size?: "md" | "lg" }) {
  const color = tone === "gain" ? "text-gain" : tone === "loss" ? "text-loss" : "text-ink";
  const scale = size === "lg" ? "text-[40px] leading-none sm:text-[52px]" : "text-[26px] leading-tight";
  return (
    <div className="min-w-0">
      <div className="text-sm text-muted">{label}</div>
      <div className={`num wide mt-1 font-semibold tracking-[-0.02em] ${scale} ${color}`}>{value}</div>
      {detail && <div className="mt-1.5 text-sm text-ink-2">{detail}</div>}
    </div>
  );
}

type Tone = "info" | "caution" | "error" | "success";
const NOTICE: Record<Tone, string> = {
  info: "border-line bg-surface", caution: "border-caution/25 bg-caution-wash",
  error: "border-loss/25 bg-danger-wash", success: "border-gain/25 bg-gain-wash",
};
const NOTICE_DOT: Record<Tone, string> = { info: "bg-ink-2", caution: "bg-caution", error: "bg-loss", success: "bg-gain" };

export function Notice({ tone = "info", title, action, children }:
  { tone?: Tone; title?: string; action?: ReactNode; children?: ReactNode }) {
  return (
    <div role={tone === "error" ? "alert" : undefined}
      className={`flex flex-wrap items-start justify-between gap-3 rounded-panel border px-5 py-4 text-sm ${NOTICE[tone]}`}>
      <div className="flex min-w-0 flex-1 gap-3">
        <span aria-hidden="true" className={`mt-[6px] h-2 w-2 shrink-0 rounded-[2px] ${NOTICE_DOT[tone]}`} />
        <div className="min-w-0">
          {title && <p className="font-semibold text-ink">{title}</p>}
          {children && <div className="text-ink-2">{children}</div>}
        </div>
      </div>
      {action}
    </div>
  );
}

type BadgeTone = "neutral" | "gain" | "caution" | "loss" | "strong" | "ai";
const BADGE: Record<BadgeTone, string> = {
  neutral: "border-line-strong bg-surface text-ink-2", gain: "border-gain/25 bg-gain-wash text-gain",
  caution: "border-caution/25 bg-caution-wash text-caution", loss: "border-loss/25 bg-danger-wash text-loss",
  strong: "border-loss bg-loss text-white", ai: "border-daylight/50 bg-daylight-wash text-daylight-ink",
};

export function Badge({ tone = "neutral", children }: { tone?: BadgeTone; children: ReactNode }) {
  return (
    <span className={`inline-flex items-center gap-1 whitespace-nowrap rounded-full border px-2.5 py-0.5 text-xs font-semibold ${BADGE[tone]}`}>
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
        <span aria-hidden="true" className={`${size === "lg" ? "text-base" : "text-xs"} whitespace-nowrap font-medium text-ink-2`}>
          {band ? `Band ${band}, ${BAND_LABEL[band]}` : "Not set"}
        </span>
      )}
    </span>
  );
}

export function Section({ title, description, actions, id, children }:
  { title: string; description?: ReactNode; actions?: ReactNode; id?: string; children: ReactNode }) {
  return (
    <section id={id} className="scroll-mt-24">
      <div className="mb-4 flex flex-wrap items-baseline justify-between gap-3">
        <div className="min-w-0">
          <h2 className="text-[18px] font-semibold tracking-[-0.005em]">{title}</h2>
          {description && <p className="mt-1 max-w-[68ch] text-sm text-muted">{description}</p>}
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

type MomentTone = "attention" | "alert" | "good" | "info";
const MOMENT: Record<MomentTone, { dot: string; text: string }> = {
  attention: { dot: "bg-daylight", text: "text-daylight-ink" }, alert: { dot: "bg-loss", text: "text-loss" },
  good: { dot: "bg-gain", text: "text-gain" }, info: { dot: "bg-ink-2", text: "text-ink-2" },
};

/** The panel a page opens with: what matters on this page, said as one sentence, with the proof and the next action. */
export function KeyMoment({ tone = "attention", label, title, children, actions }:
  { tone?: MomentTone; label: string; title: ReactNode; children?: ReactNode; actions?: ReactNode }) {
  const id = useId();
  return (
    <section aria-labelledby={id} className="rounded-panel border border-line bg-surface p-6 sm:p-7">
      <p className={`flex items-center gap-2.5 text-[13px] font-semibold ${MOMENT[tone].text}`}>
        <span aria-hidden="true" className={`h-2.5 w-2.5 rounded-[2px] ${MOMENT[tone].dot}`} />{label}
      </p>
      <h2 id={id} className="wide mt-3 max-w-[30ch] text-[24px] font-semibold leading-[1.18] tracking-[-0.015em] sm:text-[29px]">{title}</h2>
      {children && <div className="mt-5 space-y-5">{children}</div>}
      {actions && <div className="mt-6 flex flex-wrap gap-2.5">{actions}</div>}
    </section>
  );
}

export function Loading({ label }: { label: string }) {
  return <p role="status" className="py-10 text-sm text-muted">{label}…</p>;
}

export function EmptyState({ title, action, children }: { title: string; action?: ReactNode; children?: ReactNode }) {
  return (
    <div className="rounded-panel border border-dashed border-line-strong bg-surface px-6 py-12 text-center">
      <p className="font-semibold">{title}</p>
      {children && <div className="mx-auto mt-1 max-w-[52ch] text-sm text-ink-2">{children}</div>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

export function Segmented<T extends string>({ value, options, onChange, label }:
  { value: T; options: { value: T; label: string }[]; onChange: (v: T) => void; label: string }) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex flex-wrap rounded-full border border-line-strong bg-surface p-1">
      {options.map((o) => {
        const on = o.value === value;
        return (
          <button key={o.value} type="button" role="radio" aria-checked={on} onClick={() => onChange(o.value)}
            className={`relative min-h-9 rounded-full px-4 text-sm ${on ? "text-white" : "text-ink-2 hover:text-ink"}`}>
            {on && <motion.span layoutId={`segmented-${label}`} className="absolute inset-0 rounded-full bg-ink" />}
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
  th: "px-3 py-2.5 font-medium first:pl-0 last:pr-0",
  row: "border-b border-line last:border-b-0",
  td: "px-3 py-3 first:pl-0 last:pr-0",
};
```

- [ ] **Step 3: Give AI prose its caption instead of a rule**

In `apps/web/src/components/ai-prose.tsx`, replace the `AiProse` function with:

```tsx
/** Words written by Gemini. They are always set in the serif, captioned with who wrote them and what was checked. */
export function AiProse({ children, caption, warning }: { children: ReactNode; caption: string; warning?: string }) {
  return (
    <figure className="max-w-[68ch]">
      <div className="font-serif text-[17px] leading-[1.65] text-ink">{children}</div>
      <figcaption className="mt-3 flex items-start gap-2 text-xs text-daylight-ink">
        <span aria-hidden="true" className="mt-[4px] h-2 w-2 shrink-0 rounded-[1px] bg-daylight" />
        {caption}
      </figcaption>
      {warning && <p className="mt-2 text-xs font-medium text-caution">{warning}</p>}
    </figure>
  );
}
```

- [ ] **Step 4: Type-check, lint and test**

Run: `cd apps/web && pnpm tsc --noEmit && pnpm lint && pnpm vitest run`
Expected: no errors; all tests pass. This task changes styling only; its visual check is Task 9.

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/app/globals.css apps/web/src/components/ui.tsx apps/web/src/components/ai-prose.tsx
git commit -m "feat(web): Atrium Daylight tokens, pill buttons, key-moment panels and captioned AI prose"
```

---

### Task 2: People, navigation and journeys

This task is the pure logic the shell and the front door run on:
- **The eight personas,** each with a stage, home, story and things to try.
- **The four stages.**
- **One workspace per person,** with sections and tabs.
- **Which section and tab a path belongs to.**
- **Each persona's journey:** a step is done once its page has been visited. Visits are kept in local storage and survive blocked storage.

**Files:**
- Create: `apps/web/src/lib/personas.ts`, `apps/web/src/lib/personas.test.ts`
- Modify (rewrite): `apps/web/src/lib/nav.ts`, `apps/web/src/lib/nav.test.ts`
- Create: `apps/web/src/lib/journeys.ts`, `apps/web/src/lib/journeys.test.ts`

**Interfaces:**
- Consumes: nothing.
- Produces (for Tasks 3, 4 and 9):
  - From `personas`: `Act`, `ACTS`, `Persona`, `PERSONAS`, `personaFor(email)`, `initials(name)`, `actFor(email, roles)`, `personasByAct()`.
  - From `nav`: `IconName`, `NavTab`, `NavSection`, `Workspace`, `WORKSPACES`, `workspaceFor(roles)`, `sectionFor(space, path)`, `tabFor(section, path)`, `routeKind(path)` (returns `"front" | "public" | "app"`).
  - From `journeys`: `JourneyStep`, `Journey`, `JOURNEYS`, `journeyFor(email)`, `stepMatches(step, path)`, `progress(journey, visited)`, `addVisit(visited, path)`, `loadVisits(email)`, `saveVisits(email, visits)`.

- [ ] **Step 1: Write the failing tests**

```ts
// file: apps/web/src/lib/personas.test.ts
import { describe, expect, it } from "vitest";
import { actFor, initials, personaFor, PERSONAS, personasByAct } from "./personas";

describe("personas", () => {
  it("finds a persona by email, whatever the case", () => {
    expect(personaFor("PRIYA@atrium.demo")?.name).toBe("Priya Raman");
    expect(personaFor("nobody@example.test")).toBeNull();
    expect(personaFor(null)).toBeNull();
  });
  it("makes initials from a name", () => {
    expect(initials("Priya Raman")).toBe("PR");
    expect(initials("Kenji")).toBe("KE");
    expect(initials("  ")).toBe("?");
  });
  it("places each person in a stage, falling back on their role", () => {
    expect(actFor("tom@atrium.demo", ["investor"])).toBe("trade");
    expect(actFor("new@example.test", ["investor"])).toBe("invest");
    expect(actFor("boss@example.test", ["admin", "staff"])).toBe("acquire");
    expect(actFor("checker@example.test", ["ops", "staff"])).toBe("operate");
  });
  it("groups the eight people by stage, in story order, with Priya as the start", () => {
    expect(personasByAct().map((g) => [g.act.key, g.people.length])).toEqual([["acquire", 1], ["invest", 2], ["trade", 2], ["operate", 3]]);
    expect(PERSONAS.filter((p) => p.start).map((p) => p.name)).toEqual(["Priya Raman"]);
  });
});
```

```ts
// file: apps/web/src/lib/nav.test.ts
import { describe, expect, it } from "vitest";
import { routeKind, sectionFor, tabFor, WORKSPACES, workspaceFor } from "./nav";

const investor = WORKSPACES.investor;

describe("workspaceFor", () => {
  it("gives each person only their own workspace", () => {
    expect(workspaceFor(["investor"])?.key).toBe("investor");
    expect(workspaceFor(["advisor", "staff"])?.key).toBe("advisor");
    expect(workspaceFor(["ops", "staff"])?.key).toBe("operations");
    expect(workspaceFor(["compliance", "staff"])?.key).toBe("compliance");
    expect(workspaceFor(["admin", "staff"])?.key).toBe("advisor");
    expect(workspaceFor([])).toBeNull();
  });
  it("keeps every rail to five items at most", () => {
    for (const w of Object.values(WORKSPACES)) expect(w.sections.length).toBeLessThanOrEqual(5);
  });
});

describe("sectionFor", () => {
  it("maps deep pages to their rail item", () => {
    expect(sectionFor(investor, "/investor")?.key).toBe("home");
    expect(sectionFor(investor, "/investor/xray")?.key).toBe("portfolio");
    expect(sectionFor(investor, "/investor/profile")?.key).toBe("portfolio");
    expect(sectionFor(investor, "/investor/markets/NVDA")?.key).toBe("markets");
    expect(sectionFor(investor, "/investor/trades")?.key).toBe("markets");
    expect(sectionFor(investor, "/investor/funds/ATR-BAL")?.key).toBe("funds");
    expect(sectionFor(investor, "/investor/orders")?.key).toBe("funds");
    expect(sectionFor(investor, "/investor/what-if")?.key).toBe("plan");
    expect(sectionFor(investor, "/investor/copilot")).toBeNull();
    expect(sectionFor(WORKSPACES.advisor, "/advisor/leads/abc/proposal")?.key).toBe("leads");
    expect(sectionFor(WORKSPACES.advisor, "/advisor/held")?.key).toBe("held");
    expect(sectionFor(WORKSPACES.operations, "/operations")?.key).toBe("today");
    expect(sectionFor(WORKSPACES.operations, "/operations/approvals")?.key).toBe("approvals");
    expect(sectionFor(WORKSPACES.compliance, "/compliance/alerts/x")?.key).toBe("alerts");
    expect(sectionFor(WORKSPACES.compliance, "/compliance/log")?.key).toBe("log");
  });
  it("finds the tab inside a section", () => {
    const portfolio = sectionFor(investor, "/investor/risk")!;
    expect(tabFor(portfolio, "/investor/risk")?.label).toBe("Risk");
    const markets = sectionFor(investor, "/investor/markets/NVDA")!;
    expect(tabFor(markets, "/investor/markets/NVDA")?.label).toBe("Markets");
    expect(tabFor(markets, "/investor/trades")?.label).toBe("Your trades");
  });
});

describe("routeKind", () => {
  it("tells the front door, public pages and the app apart", () => {
    expect(routeKind("/")).toBe("front");
    expect(routeKind("/login")).toBe("public");
    expect(routeKind("/apply")).toBe("public");
    expect(routeKind("/investor")).toBe("app");
  });
});
```

```ts
// file: apps/web/src/lib/journeys.test.ts
import { describe, expect, it } from "vitest";
import { WORKSPACES, workspaceFor, sectionFor } from "./nav";
import { PERSONAS } from "./personas";
import { addVisit, JOURNEYS, journeyFor, loadVisits, progress, saveVisits, stepMatches } from "./journeys";

describe("journeys", () => {
  it("gives every persona a story of two to four steps", () => {
    for (const p of PERSONAS) {
      const j = journeyFor(p.email);
      expect(j, p.email).not.toBeNull();
      expect(j!.steps.length).toBeGreaterThanOrEqual(2);
      expect(j!.steps.length).toBeLessThanOrEqual(4);
    }
    expect(journeyFor("nobody@example.test")).toBeNull();
  });
  it("points every step at a page inside the person's own workspace or the Copilot", () => {
    const roles: Record<string, string[]> = {
      Investor: ["investor"], Advisor: ["advisor", "staff"], Operations: ["ops", "staff"], Compliance: ["compliance", "staff"],
    };
    for (const p of PERSONAS) {
      const space = workspaceFor(roles[p.role])!;
      for (const s of journeyFor(p.email)!.steps) {
        const reachable = sectionFor(space, s.href) !== null || s.href === "/investor/copilot";
        expect(reachable, `${p.email} ${s.href}`).toBe(true);
      }
    }
    expect(Object.keys(WORKSPACES)).toHaveLength(4);
  });
  it("matches a step by its exact page, or by its pattern", () => {
    const priya = journeyFor("priya@atrium.demo")!;
    expect(stepMatches(priya.steps[0], "/investor")).toBe(true);
    expect(stepMatches(priya.steps[0], "/investor/xray")).toBe(false);
    const omar = journeyFor("omar@atrium.demo")!;
    expect(stepMatches(omar.steps[1], "/compliance/alerts/abc")).toBe(true);
    expect(stepMatches(omar.steps[1], "/compliance")).toBe(false);
  });
  it("ticks the visited steps and points at the first one left", () => {
    const priya = journeyFor("priya@atrium.demo")!;
    expect(progress(priya, [])).toEqual({ done: [false, false, false, false], current: 0, count: 0 });
    expect(progress(priya, ["/investor", "/investor/markets/NVDA"])).toEqual({ done: [true, false, true, false], current: 1, count: 2 });
    const all = priya.steps.map((s) => s.href);
    expect(progress(priya, all).current).toBeNull();
  });
  it("remembers each page once, and only the latest sixty", () => {
    expect(addVisit(["/a"], "/a")).toEqual(["/a"]);
    const many = Array.from({ length: 70 }, (_, i) => `/p${i}`).reduce(addVisit, [] as string[]);
    expect(many).toHaveLength(60);
    expect(many[59]).toBe("/p69");
  });
  it("survives storage that is blocked or holds junk", () => {
    expect(loadVisits("priya@atrium.demo")).toEqual([]);   // no localStorage in the test environment
    expect(() => saveVisits("priya@atrium.demo", ["/investor"])).not.toThrow();
    const store: Record<string, string> = { "atrium.journey.priya@atrium.demo": "{not json" };
    globalThis.localStorage = { getItem: (k: string) => store[k] ?? null, setItem: (k: string, v: string) => { store[k] = v; } } as Storage;
    expect(loadVisits("priya@atrium.demo")).toEqual([]);
    saveVisits("PRIYA@atrium.demo", ["/investor", "/investor/what-if"]);
    expect(loadVisits("priya@atrium.demo")).toEqual(["/investor", "/investor/what-if"]);
    store["atrium.journey.priya@atrium.demo"] = JSON.stringify(["/investor", 7, null]);
    expect(loadVisits("priya@atrium.demo")).toEqual(["/investor"]);
    // @ts-expect-error tidy up the stand-in
    delete globalThis.localStorage;
    expect(JOURNEYS).toHaveLength(8);
  });
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd apps/web && pnpm vitest run src/lib/personas.test.ts src/lib/nav.test.ts src/lib/journeys.test.ts`
Expected: FAIL (`./personas` and `./journeys` cannot be resolved; `workspaceFor` is not exported by `./nav`)

- [ ] **Step 3: Write the personas**

```ts
// file: apps/web/src/lib/personas.ts
export type Act = "acquire" | "invest" | "trade" | "operate";
export type ActInfo = { key: Act; number: number; label: string; line: string; ai: string };

/** Atrium's four stages, in the order a client meets them. */
export const ACTS: ActInfo[] = [
  { key: "acquire", number: 1, label: "Acquire", line: "Every lead scored for fit and for fraud before an advisor calls.", ai: "Lead Score and Trust Score" },
  { key: "invest", number: 2, label: "Invest", line: "Portfolios tested against 10,000 futures drawn from real markets since 2007.", ai: "What-if Studio and Copilot" },
  { key: "trade", number: 3, label: "Trade", line: "Every order checked before it reaches the market, and held when it looks wrong.", ai: "Pre-trade Guardian" },
  { key: "operate", number: 4, label: "Operate", line: "Statements reconciled, alerts reviewed, and two people for every change to the books.", ai: "Reconciliation agent and case reviews" },
];

export type Persona = {
  email: string; name: string; role: "Investor" | "Advisor" | "Operations" | "Compliance"; act: Act; home: string;
  story: string; tries: string[]; start?: boolean;
};

/** The demo's eight people. Every one of them is synthetic. */
export const PERSONAS: Persona[] = [
  { email: "daniel@atrium.demo", name: "Daniel Okafor", role: "Advisor", act: "acquire", home: "/advisor",
    story: "Works a pipeline of new leads. Three of them are fraud stories the Trust Score catches.",
    tries: ["Open a lead marked high risk and read why", "Turn a clean lead into a Gemini Pro proposal"] },
  { email: "priya@atrium.demo", name: "Priya Raman", role: "Investor", act: "invest", home: "/investor", start: true,
    story: "Her balanced portfolio has quietly drifted above the risk she signed up for.",
    tries: ["See the drift, then test 10,000 futures", "Try buying 60 NVIDIA shares"] },
  { email: "lucas@atrium.demo", name: "Lucas Moreau", role: "Investor", act: "invest", home: "/investor/xray",
    story: "Owns about a tenth of NVIDIA without knowing it, through six different ETFs.",
    tries: ["Open the Portfolio X-ray", "Buy more NVIDIA and meet the concentration check"] },
  { email: "tom@atrium.demo", name: "Tom Becker", role: "Investor", act: "trade", home: "/investor",
    story: "Holds 120 Tesla shares. Selling them all from a browser Atrium has never seen looks like a takeover.",
    tries: ["Sell all 120 Tesla shares", "Read the trust signals behind the hold"] },
  { email: "hana@atrium.demo", name: "Hana Sato", role: "Investor", act: "trade", home: "/investor/trades",
    story: "Sold PepsiCo at a loss less than three weeks ago, and wants it back.",
    tries: ["Buy PepsiCo again", "Read the wash-sale warning"] },
  { email: "mei@atrium.demo", name: "Mei Tanaka", role: "Operations", act: "operate", home: "/operations/reconciliation",
    story: "Matches the money that arrived at the bank with the subscriptions waiting for it.",
    tries: ["Read a bank statement with Document AI", "Let the agent match a typo and a split payment"] },
  { email: "sam@atrium.demo", name: "Sam Ortiz", role: "Operations", act: "operate", home: "/operations/approvals",
    story: "The second pair of eyes on every price, manual match and reversal.",
    tries: ["Approve Mei's request with a one-time code", "Try approving your own: you can't"] },
  { email: "omar@atrium.demo", name: "Omar Haddad", role: "Compliance", act: "operate", home: "/compliance",
    story: "Decides every anti-money-laundering alert, with the rows behind it.",
    tries: ["Open the structuring alert", "Ask Gemini Pro for a cited case review"] },
];

export function personaFor(email: string | null | undefined): Persona | null {
  const wanted = (email ?? "").trim().toLowerCase();
  return PERSONAS.find((p) => p.email === wanted) ?? null;
}

export function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

/** The stage a person works in: their persona's, or one that fits their role. */
export function actFor(email: string | null | undefined, roles: string[]): Act {
  const persona = personaFor(email);
  if (persona) return persona.act;
  if (roles.includes("investor")) return "invest";
  if (roles.includes("advisor") || roles.includes("admin")) return "acquire";
  return "operate";
}

export function personasByAct(): { act: ActInfo; people: Persona[] }[] {
  return ACTS.map((act) => ({ act, people: PERSONAS.filter((p) => p.act === act.key) }));
}
```

- [ ] **Step 4: Rewrite the navigation**

```ts
// file: apps/web/src/lib/nav.ts
export type IconName =
  | "home" | "portfolio" | "markets" | "funds" | "plan" | "leads" | "held" | "form" | "today" | "reconcile" | "approvals"
  | "blotter" | "alerts" | "log";
export type NavTab = { href: string; label: string };
/** A rail item. Its tabs (if any) are shown at the top of each of its pages; `also` lists other paths it owns. */
export type NavSection = { key: string; label: string; href: string; icon: IconName; tabs?: NavTab[]; also?: string[] };
export type WorkspaceKey = "investor" | "advisor" | "operations" | "compliance";
export type Workspace = { key: WorkspaceKey; label: string; home: string; sections: NavSection[] };

export const WORKSPACES: Record<WorkspaceKey, Workspace> = {
  investor: {
    key: "investor", label: "Investor", home: "/investor",
    sections: [
      { key: "home", label: "Home", href: "/investor", icon: "home" },
      { key: "portfolio", label: "Portfolio", href: "/investor/xray", icon: "portfolio",
        tabs: [{ href: "/investor/xray", label: "X-ray" }, { href: "/investor/risk", label: "Risk" }, { href: "/investor/profile", label: "Risk profile" }] },
      { key: "markets", label: "Markets", href: "/investor/markets", icon: "markets",
        tabs: [{ href: "/investor/markets", label: "Markets" }, { href: "/investor/trades", label: "Your trades" }] },
      { key: "funds", label: "Funds", href: "/investor/funds", icon: "funds",
        tabs: [{ href: "/investor/funds", label: "Funds" }, { href: "/investor/orders", label: "Fund orders" }] },
      { key: "plan", label: "Plan ahead", href: "/investor/what-if", icon: "plan" },
    ],
  },
  advisor: {
    key: "advisor", label: "Advisor", home: "/advisor",
    sections: [
      { key: "leads", label: "Leads", href: "/advisor", icon: "leads", also: ["/advisor/leads"] },
      { key: "held", label: "Held orders", href: "/advisor/held", icon: "held" },
      { key: "form", label: "Prospect form", href: "/apply", icon: "form" },
    ],
  },
  operations: {
    key: "operations", label: "Operations", home: "/operations",
    sections: [
      { key: "today", label: "Today", href: "/operations", icon: "today" },
      { key: "reconcile", label: "Reconciliation", href: "/operations/reconciliation", icon: "reconcile" },
      { key: "approvals", label: "Approvals", href: "/operations/approvals", icon: "approvals" },
      { key: "blotter", label: "Blotter", href: "/operations/blotter", icon: "blotter" },
    ],
  },
  compliance: {
    key: "compliance", label: "Compliance", home: "/compliance",
    sections: [
      { key: "alerts", label: "Alerts", href: "/compliance", icon: "alerts", also: ["/compliance/alerts"] },
      { key: "log", label: "Decision log", href: "/compliance/log", icon: "log" },
    ],
  },
};

const ROLE_WORKSPACE: Record<string, WorkspaceKey> = {
  investor: "investor", advisor: "advisor", admin: "advisor", ops: "operations", compliance: "compliance",
};
/** Workspace roots that own only themselves: their other pages belong to other rail items. */
const EXACT = new Set(["/investor", "/advisor", "/operations", "/compliance"]);

/** Each person sees only their own workspace. */
export function workspaceFor(roles: string[]): Workspace | null {
  const key = ROLE_WORKSPACE[roles[0] ?? ""] ?? (roles.includes("staff") ? "advisor" : null);
  return key ? WORKSPACES[key] : null;
}

function under(path: string, href: string): boolean {
  return path === href || path.startsWith(`${href}/`);
}

function owns(path: string, href: string): boolean {
  return EXACT.has(href) ? path === href : under(path, href);
}

export function sectionFor(space: Workspace, path: string): NavSection | null {
  return space.sections.find((s) => [s.href, ...(s.tabs ?? []).map((t) => t.href), ...(s.also ?? [])].some((h) => owns(path, h))) ?? null;
}

export function tabFor(section: NavSection, path: string): NavTab | null {
  const matches = (section.tabs ?? []).filter((t) => owns(path, t.href));
  return matches.sort((a, b) => b.href.length - a.href.length)[0] ?? null;
}

const PUBLIC_PATHS = ["/login", "/apply"];

export function routeKind(path: string): "front" | "public" | "app" {
  if (path === "/") return "front";
  return PUBLIC_PATHS.some((p) => under(path, p)) ? "public" : "app";
}
```

- [ ] **Step 5: Write the journeys**

```ts
// file: apps/web/src/lib/journeys.ts
/** Each persona's story: three or four steps, each a page to visit. A step is done once its page has been seen. */
export type JourneyStep = { title: string; detail: string; href: string; action: string; match?: string };
export type Journey = { email: string; title: string; intro: string; steps: JourneyStep[] };

export const JOURNEYS: Journey[] = [
  { email: "priya@atrium.demo", title: "Priya's story", intro: "A balanced investor whose portfolio took on more risk than she chose.",
    steps: [
      { title: "See the drift", detail: "Home shows your risk profile and your portfolio side by side.", href: "/investor", action: "Open Home" },
      { title: "Test 10,000 futures", detail: "Plan ahead replays markets since 2007 to show the range of outcomes.", href: "/investor/what-if", action: "Open Plan ahead" },
      { title: "Try buying 60 NVIDIA shares", detail: "The Pre-trade Guardian holds the order for an advisor and says why.", href: "/investor/markets/NVDA", action: "Open NVIDIA" },
      { title: "Ask Atrium", detail: "Ask whether to rebalance; the answer comes from your own figures.", href: "/investor/copilot", action: "Ask Atrium" },
    ] },
  { email: "lucas@atrium.demo", title: "Lucas's story", intro: "A growth investor who owns more NVIDIA than he thinks.",
    steps: [
      { title: "See the X-ray", detail: "Look-through finds one company behind six of your ETFs.", href: "/investor/xray", action: "Open the X-ray" },
      { title: "Buy more NVIDIA", detail: "The Guardian counts the shares you already hold through funds.", href: "/investor/markets/NVDA", action: "Open NVIDIA" },
      { title: "Read your risk report", detail: "Volatility, drawdown and what drives them.", href: "/investor/risk", action: "Open Risk" },
    ] },
  { email: "tom@atrium.demo", title: "Tom's story", intro: "An investor whose large sale looks like an account takeover.",
    steps: [
      { title: "See what you hold", detail: "120 Tesla shares and two funds.", href: "/investor", action: "Open Home" },
      { title: "Sell all 120 Tesla shares", detail: "From a browser Atrium has never seen, the Guardian holds the sale.", href: "/investor/markets/TSLA", action: "Open Tesla" },
      { title: "Read why it was held", detail: "Your trades list the trust signals behind the hold.", href: "/investor/trades", action: "Open Your trades" },
    ] },
  { email: "hana@atrium.demo", title: "Hana's story", intro: "An investor about to trip the wash-sale rule.",
    steps: [
      { title: "See your PepsiCo sale", detail: "Sold at a loss less than three weeks ago.", href: "/investor/trades", action: "Open Your trades" },
      { title: "Buy PepsiCo again", detail: "The Guardian warns that the loss may not count for tax.", href: "/investor/markets/PEP", action: "Open PepsiCo" },
      { title: "Ask Atrium", detail: "Ask what a wash sale is and what it means for you.", href: "/investor/copilot", action: "Ask Atrium" },
    ] },
  { email: "daniel@atrium.demo", title: "Daniel's story", intro: "An advisor whose pipeline hides three fraud stories among real prospects.",
    steps: [
      { title: "Spot the ring", detail: "Four leads from one device, each with a throwaway email address.", href: "/advisor", action: "Open Leads" },
      { title: "Read a lead's signals", detail: "Open any lead to see why it scored as it did.", href: "/advisor", match: "^/advisor/leads/[^/]+$", action: "Open Leads" },
      { title: "Write a proposal", detail: "Gemini Pro writes it from the client's answers and the fund documents.", href: "/advisor", match: "^/advisor/leads/[^/]+/proposal$", action: "Open Leads" },
      { title: "Decide a held order", detail: "Release or reject an order the Guardian held.", href: "/advisor/held", action: "Open Held orders" },
    ] },
  { email: "mei@atrium.demo", title: "Mei's story", intro: "Matching today's payments, with an agent doing the fiddly ones.",
    steps: [
      { title: "Reconcile today's statement", detail: "Read the sample statement, find matches and decide them.", href: "/operations/reconciliation", action: "Open Reconciliation" },
      { title: "Run the day-end", detail: "Draft today's prices and ask for them to be published.", href: "/operations", action: "Open Today" },
      { title: "Follow an instruction", detail: "The blotter shows every step from received to settled.", href: "/operations/blotter", action: "Open Blotter" },
    ] },
  { email: "sam@atrium.demo", title: "Sam's story", intro: "The second pair of eyes: nothing changes the books on one person's word.",
    steps: [
      { title: "Approve a request", detail: "Use the code from the demo authenticator. You cannot approve your own.", href: "/operations/approvals", action: "Open Approvals" },
      { title: "Decide the agent's matches", detail: "Accept or reject what the reconciliation agent proposed.", href: "/operations/reconciliation", action: "Open Reconciliation" },
    ] },
  { email: "omar@atrium.demo", title: "Omar's story", intro: "Deciding alerts with the exact rows behind them and a cited second opinion.",
    steps: [
      { title: "See the open alerts", detail: "Each one comes from a rule or the anomaly model.", href: "/compliance", action: "Open Alerts" },
      { title: "Review an alert", detail: "Its evidence, who is linked, and a Gemini Pro case review.", href: "/compliance", match: "^/compliance/alerts/", action: "Open Alerts" },
      { title: "Open the decision log", detail: "Every AI decision with its model and cost.", href: "/compliance/log", action: "Open the log" },
    ] },
];

export function journeyFor(email: string | null | undefined): Journey | null {
  const wanted = (email ?? "").trim().toLowerCase();
  return JOURNEYS.find((j) => j.email === wanted) ?? null;
}

export function stepMatches(step: JourneyStep, path: string): boolean {
  return step.match ? new RegExp(step.match).test(path) : path === step.href;
}

export function progress(journey: Journey, visited: string[]): { done: boolean[]; current: number | null; count: number } {
  const done = journey.steps.map((s) => visited.some((v) => stepMatches(s, v)));
  const next = done.indexOf(false);
  return { done, current: next === -1 ? null : next, count: done.filter(Boolean).length };
}

export function addVisit(visited: string[], path: string): string[] {
  return visited.includes(path) ? visited : [...visited, path].slice(-60);
}

const key = (email: string) => `atrium.journey.${email.trim().toLowerCase()}`;

export function loadVisits(email: string): string[] {
  try {
    const raw = localStorage.getItem(key(email));
    const value: unknown = raw ? JSON.parse(raw) : [];
    return Array.isArray(value) ? value.filter((v): v is string => typeof v === "string") : [];
  } catch {
    return [];
  }
}

export function saveVisits(email: string, visits: string[]): void {
  try {
    localStorage.setItem(key(email), JSON.stringify(visits));
  } catch {
    // Storage blocked: the guide still works for this page view.
  }
}
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `cd apps/web && pnpm vitest run src/lib/personas.test.ts src/lib/nav.test.ts src/lib/journeys.test.ts`
Expected: PASS

- [ ] **Step 7: Commit**

Task 3 replaces the shell, which still imports the old navigation, so `tsc` passes only after it. Commit Tasks 2 and 3 together at the end of Task 3.

---

### Task 3: The shell

Every signed-in page sits in one shell:
- a sticky top bar (wordmark, the four stages with the person's lit, "Ask Atrium" for investors, and the person chip linking to "Switch person");
- the rail (a column from 1024 px, a strip above the page below that);
- the section's tabs above the page;
- the journey guide (a right-hand column from 1280 px, under the page below that), which the person can hide and show again.

Public pages keep a slim header. The front door (`/`) draws its own.

**Files:**
- Create: `apps/web/src/components/icons.tsx`
- Create: `apps/web/src/components/journey-guide.tsx`
- Modify (rewrite): `apps/web/src/components/shell.tsx`

**Interfaces:**
- Consumes: Task 2 (everything), Task 1 (`ButtonLink` with `size`).
- Produces (for Task 4): `AtriumMark`, `Wordmark({ href })` and `Footer` from `shell.tsx`; `Icon({ name, size? })`.

- [ ] **Step 1: Write the icons**

```tsx
// file: apps/web/src/components/icons.tsx
import type { ReactNode } from "react";
import type { IconName } from "@/lib/nav";

const PATHS: Record<IconName, ReactNode> = {
  home: <path d="M4 11 12 4l8 7v9H4z" />,
  portfolio: <><circle cx="12" cy="12" r="8" /><path d="M12 4v8l6 4" /></>,
  markets: <><path d="M4 17l5-5 4 3 7-8" /><path d="M15 7h5v5" /></>,
  funds: <><rect x="4" y="4" width="16" height="16" rx="2" /><path d="M9 4v16M4 10h5" /></>,
  plan: <><path d="M4 18c4-1 6-5 8-9s5-5 8-5" /><path d="M4 21h16" /></>,
  leads: <path d="M4 5h16l-6 7v6l-4 2v-8z" />,
  held: <><rect x="5" y="4" width="14" height="16" rx="2" /><path d="M9 9h6M9 13h6" /></>,
  form: <><rect x="5" y="4" width="14" height="16" rx="2" /><path d="M12 9v6M9 12h6" /></>,
  today: <><circle cx="12" cy="12" r="4" /><path d="M12 3v2M12 19v2M3 12h2M19 12h2" /></>,
  reconcile: <path d="M5 8h10l-3-3M19 16H9l3 3" />,
  approvals: <path d="M5 12l4 4 10-10" />,
  blotter: <path d="M5 6h14M5 12h14M5 18h9" />,
  alerts: <><path d="M12 4l9 16H3z" /><path d="M12 10v4M12 17v.5" /></>,
  log: <><rect x="5" y="4" width="14" height="16" rx="2" /><path d="M9 9h6M9 13h6M9 17h3" /></>,
};

export function Icon({ name, size = 18 }: { name: IconName; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6}
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {PATHS[name]}
    </svg>
  );
}
```

- [ ] **Step 2: Write the journey guide**

```tsx
// file: apps/web/src/components/journey-guide.tsx
"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { addVisit, journeyFor, loadVisits, progress, saveVisits } from "@/lib/journeys";
import { ButtonLink } from "@/components/ui";

/** "Your story": the persona's steps, ticked off as their pages are visited, with the next one's button. */
export function JourneyGuide({ email, path, onHide }: { email: string; path: string; onHide: () => void }) {
  const journey = journeyFor(email);
  const [visited, setVisited] = useState<string[]>([]);

  useEffect(() => {
    if (!journey) return;
    const next = addVisit(loadVisits(email), path);
    saveVisits(email, next);
    setVisited(next);
  }, [email, path, journey]);

  if (!journey) return null;
  const { done, current, count } = progress(journey, visited);
  return (
    <aside aria-label={journey.title} className="rounded-panel border border-line bg-surface p-6">
      <div className="flex items-baseline justify-between gap-3">
        <h2 className="text-base font-semibold">{journey.title}</h2>
        <span className="num text-[13px] text-muted">{count} of {journey.steps.length}</span>
      </div>
      <p className="mt-1 text-sm text-ink-2">{journey.intro}</p>
      <ol className="mt-3">
        {journey.steps.map((s, i) => {
          const isDone = done[i];
          const isNow = current === i;
          return (
            <li key={s.title} className="grid grid-cols-[28px_minmax(0,1fr)] gap-3 border-t border-line py-4 first:border-t-0">
              <span aria-hidden="true"
                className={`flex h-7 w-7 items-center justify-center rounded-full border text-[13px] font-semibold ${isDone ? "border-gain bg-gain text-white" : isNow ? "border-ink bg-ink text-white" : "border-line-strong text-ink-2"}`}>
                {isDone ? "✓" : i + 1}
              </span>
              <span className="flex min-w-0 flex-col gap-1">
                <span className="font-semibold">{s.title}<span className="sr-only">{isDone ? ", done" : isNow ? ", next" : ""}</span></span>
                <span className="text-[13px] text-muted">{s.detail}</span>
                {isNow && path !== s.href && <ButtonLink href={s.href} size="sm" className="mt-1.5 self-start">{s.action}</ButtonLink>}
              </span>
            </li>
          );
        })}
      </ol>
      {current === null && (
        <p className="border-t border-line pt-4 text-sm text-ink-2">
          You have seen this story. <Link href="/#journeys" className="font-semibold underline underline-offset-4">Try another person</Link>.
        </p>
      )}
      <button type="button" onClick={onHide} className="mt-3 text-[13px] text-muted underline decoration-line-strong underline-offset-4 hover:text-ink">
        Hide this guide
      </button>
    </aside>
  );
}
```

- [ ] **Step 3: Rewrite the shell**

```tsx
// file: apps/web/src/components/shell.tsx
"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { LayoutGroup, motion } from "motion/react";
import type { Me } from "@/lib/api";
import { routeKind, sectionFor, tabFor, workspaceFor, type NavSection, type Workspace } from "@/lib/nav";
import { ACTS, actFor, initials } from "@/lib/personas";
import { useSession } from "@/lib/session-context";
import { Icon } from "@/components/icons";
import { JourneyGuide } from "@/components/journey-guide";
import { ButtonLink, Loading, Notice } from "@/components/ui";

const ROLE_LABEL: Record<string, string> = {
  investor: "Investor", advisor: "Advisor", ops: "Operations", compliance: "Compliance", admin: "Administrator",
};
const GUIDE_KEY = "atrium.guide.hidden";

/** The Atrium mark: a building seen from above, with daylight falling into its central well. */
export function AtriumMark({ size = 22 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 20 20" aria-hidden="true">
      <rect x="1" y="1" width="18" height="18" rx="2" fill="none" stroke="currentColor" strokeWidth="1.4" />
      <rect x="6.5" y="6.5" width="7" height="7" rx="0.6" fill="var(--color-daylight)" />
    </svg>
  );
}

export function Wordmark({ href }: { href: string }) {
  return (
    <Link href={href} className="wide flex min-h-11 items-center gap-2.5 text-[19px] font-semibold tracking-[-0.01em]">
      <AtriumMark />
      Atrium
    </Link>
  );
}

export function Footer() {
  return (
    <footer className="no-print border-t border-line">
      <div className="mx-auto flex max-w-[1240px] flex-wrap justify-between gap-3 px-4 py-6 text-[13px] text-muted sm:px-8">
        <span>Atrium, by team Ctrl+Alt+Hiru for the AI Builder Cup 2026.</span>
        <span>Synthetic people and paper trading. Projections are simulations, and nothing here is investment advice.</span>
      </div>
    </footer>
  );
}

function Stages({ me }: { me: Me }) {
  const current = actFor(me.email, me.roles);
  return (
    <ol aria-label="Atrium's four stages" className="hidden items-center gap-5 md:flex">
      {ACTS.map((a) => {
        const on = a.key === current;
        return (
          <li key={a.key} aria-current={on ? "step" : undefined}
            className={`flex items-center gap-1.5 text-[13px] ${on ? "font-semibold text-ink" : "text-muted"}`}>
            <span aria-hidden="true" className={`h-2.5 w-2.5 rounded-[2px] border ${on ? "border-daylight bg-daylight" : "border-[#8c979f]"}`} />
            {a.label}
          </li>
        );
      })}
    </ol>
  );
}

function PersonaChip({ me }: { me: Me }) {
  const name = me.full_name ?? me.email;
  return (
    <Link href="/#journeys" aria-label={`${name}, ${ROLE_LABEL[me.roles[0]] ?? me.roles[0]}. Switch person`}
      className="flex min-h-11 items-center gap-2.5 rounded-full border border-line py-1 pl-1 pr-1 hover:border-line-strong sm:pr-3.5">
      <span aria-hidden="true" className="flex h-8 w-8 items-center justify-center rounded-full bg-ink text-xs font-semibold text-white">{initials(name)}</span>
      <span aria-hidden="true" className="hidden flex-col leading-tight sm:flex">
        <span className="text-sm font-semibold">{name}</span>
        <span className="text-xs text-muted">{ROLE_LABEL[me.roles[0]] ?? me.roles[0]}. Switch person</span>
      </span>
    </Link>
  );
}

function TopBar({ me, space, guideHidden, onShowGuide }: { me: Me; space: Workspace; guideHidden: boolean; onShowGuide: () => void }) {
  return (
    <header className="no-print sticky top-0 z-30 border-b border-line bg-surface">
      <div className="flex h-[68px] items-center justify-between gap-4 px-4 sm:px-6">
        <Wordmark href={space.home} />
        <Stages me={me} />
        <div className="flex items-center gap-2.5">
          {guideHidden && (
            <button type="button" onClick={onShowGuide}
              className="hidden min-h-11 text-sm text-ink-2 underline decoration-line-strong underline-offset-4 hover:text-ink lg:inline">
              Show your story
            </button>
          )}
          {space.key === "investor" && (
            <ButtonLink href="/investor/copilot" variant="secondary" size="sm">
              <span aria-hidden="true" className="h-2 w-2 rounded-[1px] bg-daylight" />Ask Atrium
            </ButtonLink>
          )}
          <PersonaChip me={me} />
        </div>
      </div>
    </header>
  );
}

function RailLink({ section, on, layout }: { section: NavSection; on: boolean; layout: "column" | "strip" }) {
  return (
    <Link href={section.href} aria-current={on ? "page" : undefined}
      className={`relative flex min-h-11 items-center rounded-control px-3.5 text-[15px] ${layout === "strip" ? "whitespace-nowrap" : ""} ${on ? "text-white" : "text-ink-2 hover:bg-wash hover:text-ink"}`}>
      {on && <motion.span layoutId={`rail-${layout}`} className="absolute inset-0 rounded-control bg-ink" />}
      <span className="relative flex items-center gap-3"><Icon name={section.icon} />{section.label}</span>
    </Link>
  );
}

function Rail({ space, active, layout }: { space: Workspace; active: NavSection | null; layout: "column" | "strip" }) {
  return (
    <LayoutGroup id={`rail-${layout}`}>
      <nav aria-label={`${space.label} workspace`}
        className={layout === "strip" ? "no-print border-b border-line bg-surface lg:hidden" : "no-print hidden border-r border-line lg:block"}>
        <ul className={layout === "strip" ? "flex gap-1 overflow-x-auto px-3 py-2" : "sticky top-[68px] space-y-1 px-3.5 py-5"}>
          {space.sections.map((s) => (
            <li key={s.key} className={layout === "strip" ? "shrink-0" : ""}>
              <RailLink section={s} on={active?.key === s.key} layout={layout} />
            </li>
          ))}
        </ul>
      </nav>
    </LayoutGroup>
  );
}

function SectionTabs({ section, path }: { section: NavSection; path: string }) {
  const current = tabFor(section, path);
  return (
    <LayoutGroup id="tabs">
      <nav aria-label={`${section.label} pages`} className="no-print mb-8 flex gap-1 overflow-x-auto border-b border-line">
        {(section.tabs ?? []).map((t) => {
          const on = current?.href === t.href;
          return (
            <Link key={t.href} href={t.href} aria-current={on ? "page" : undefined}
              className={`relative flex min-h-11 items-center whitespace-nowrap px-3.5 text-[15px] ${on ? "font-semibold text-ink" : "text-ink-2 hover:text-ink"}`}>
              {t.label}
              {on && <motion.span layoutId="tab-underline" className="absolute inset-x-2 -bottom-px h-[2px] rounded-full bg-ink" />}
            </Link>
          );
        })}
      </nav>
    </LayoutGroup>
  );
}

export function Shell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const router = useRouter();
  const { me, status, error } = useSession();
  const [guideHidden, setGuideHidden] = useState(false);
  const kind = routeKind(path);

  useEffect(() => {
    try {
      setGuideHidden(localStorage.getItem(GUIDE_KEY) === "1");
    } catch {
      // Storage blocked: the guide shows.
    }
  }, []);
  useEffect(() => {
    if (status === "signed-out" && kind === "app") router.replace("/");
  }, [status, kind, router]);

  function setGuide(hidden: boolean) {
    setGuideHidden(hidden);
    try {
      localStorage.setItem(GUIDE_KEY, hidden ? "1" : "0");
    } catch {
      // Storage blocked: the choice lasts for this page view.
    }
  }

  if (kind === "front") return <>{children}</>;
  const space = me ? workspaceFor(me.roles) : null;

  if (kind === "public" || !me || !space) {
    return (
      <div className="flex min-h-screen flex-col">
        <header className="no-print border-b border-line bg-surface">
          <div className="mx-auto flex h-[68px] max-w-[1240px] items-center justify-between px-4 sm:px-8">
            <Wordmark href="/" />
            {me && space
              ? <Link href={space.home} className="text-sm text-ink-2 hover:text-ink">Open your workspace</Link>
              : <Link href="/#journeys" className="text-sm text-ink-2 hover:text-ink">Choose a person</Link>}
          </div>
        </header>
        <main className="mx-auto w-full max-w-[1240px] flex-1 px-4 py-10 sm:px-8 lg:py-14">
          {kind === "public" ? children
            : status === "error" ? <Notice tone="error" title="Atrium is unavailable">{error}</Notice>
            : me && !space ? <Notice tone="caution" title="This person has no workspace">Choose another person on the front page.</Notice>
            : <Loading label="Opening your workspace" />}
        </main>
        <Footer />
      </div>
    );
  }

  const section = sectionFor(space, path);
  return (
    <div className="flex min-h-screen flex-col">
      <TopBar me={me} space={space} guideHidden={guideHidden} onShowGuide={() => setGuide(false)} />
      <Rail space={space} active={section} layout="strip" />
      <div className="flex-1 lg:grid lg:grid-cols-[232px_minmax(0,1fr)] xl:grid-cols-[232px_minmax(0,1fr)_340px]">
        <Rail space={space} active={section} layout="column" />
        <main className="min-w-0 px-4 py-8 sm:px-8 lg:px-10 lg:py-9">
          {section?.tabs && <SectionTabs section={section} path={path} />}
          {children}
        </main>
        {!guideHidden && (
          <div className="no-print px-4 pb-12 sm:px-8 lg:col-start-2 lg:px-10 xl:col-start-3 xl:row-start-1 xl:px-0 xl:pr-6 xl:pt-9">
            <div className="xl:sticky xl:top-[92px]">
              <JourneyGuide email={me.email} path={path} onHide={() => setGuide(true)} />
            </div>
          </div>
        )}
      </div>
      <Footer />
    </div>
  );
}
```

- [ ] **Step 4: Type-check, lint and test**

Run: `cd apps/web && pnpm tsc --noEmit && pnpm lint && pnpm vitest run`
Expected: no errors; all tests pass

- [ ] **Step 5: Commit Tasks 2 and 3**

```bash
git add apps/web/src/lib/personas.ts apps/web/src/lib/personas.test.ts apps/web/src/lib/nav.ts apps/web/src/lib/nav.test.ts apps/web/src/lib/journeys.ts apps/web/src/lib/journeys.test.ts apps/web/src/components/icons.tsx apps/web/src/components/journey-guide.tsx apps/web/src/components/shell.tsx
git commit -m "feat(web): one shell per person: stages, a rail of five, section tabs and a journey guide"
```

---

### Task 4: The front door

`/` tells Atrium's story:
- the headline;
- the floor plan of four stages around the lit well;
- what the AI does and never does;
- the eight people, grouped by stage.

Choosing a person signs in as them (persona sign-in) and opens their home. With Firebase sign-in, the buttons lead to `/login`, which keeps only the email form; with persona sign-in, `/login` forwards to the front door's people.

**Files:**
- Create: `apps/web/src/components/plan-diagram.tsx`
- Modify (rewrite): `apps/web/src/app/page.tsx`
- Modify (rewrite): `apps/web/src/app/login/page.tsx`

**Interfaces:**
- Consumes:
  - From Task 2: `ACTS`, `PERSONAS`, `personasByAct`, `personaFor`, `initials`, `workspaceFor`.
  - From Task 3: `Wordmark`, `Footer`.
  - `setDevUser`, `useSession`, `getConfig`.
- Produces: the routes `/` and `/login`.

- [ ] **Step 1: Write the floor plan**

```tsx
// file: apps/web/src/components/plan-diagram.tsx
import { ACTS, type Act } from "@/lib/personas";

const PLACE: Record<Act, string> = {
  acquire: "col-start-1 row-start-1", invest: "col-start-3 row-start-1",
  trade: "col-start-3 row-start-3", operate: "col-start-1 row-start-3",
};

function Arrow({ className, rotate }: { className: string; rotate: number }) {
  return (
    <div className={`flex items-center justify-center ${className}`} aria-hidden="true">
      <svg width="48" height="12" viewBox="0 0 48 12" style={{ transform: `rotate(${rotate}deg)` }}>
        <path d="M2 6h42M38 1l7 5-7 5" fill="none" stroke="#8c979f" strokeWidth="1.4" />
      </svg>
    </div>
  );
}

/** Atrium as a floor plan: four rooms, one per stage, around a lit well, which is the shared ledger and AI decision log. */
export function PlanDiagram() {
  return (
    <figure aria-label="How Atrium is laid out: four stages around one ledger" className="m-0">
      <div className="grid w-full grid-cols-[minmax(0,1fr)_56px_minmax(0,1fr)] grid-rows-[auto_56px_auto] sm:aspect-square sm:grid-cols-[minmax(0,1fr)_112px_minmax(0,1fr)] sm:grid-rows-[minmax(0,1fr)_112px_minmax(0,1fr)]">
        {ACTS.map((a) => (
          <div key={a.key} className={`${PLACE[a.key]} flex min-w-0 flex-col gap-2 rounded-panel border border-line bg-surface p-3.5 sm:p-5`}>
            <div className="flex items-baseline justify-between gap-2">
              <span className="wide text-[16px] font-semibold sm:text-[21px]">{a.label}</span>
              <span className="num text-[13px] text-muted">{a.number}</span>
            </div>
            <p className="text-[12.5px] leading-snug text-ink-2 sm:text-sm">{a.line}</p>
            <p className="mt-auto hidden items-center gap-2 text-[13px] text-daylight-ink sm:flex">
              <span aria-hidden="true" className="h-2 w-2 shrink-0 rounded-[1px] bg-daylight" />{a.ai}
            </p>
          </div>
        ))}
        <Arrow className="col-start-2 row-start-1" rotate={0} />
        <Arrow className="col-start-3 row-start-2" rotate={90} />
        <Arrow className="col-start-2 row-start-3" rotate={180} />
        <div className="col-start-2 row-start-2 p-1.5 sm:p-2.5">
          <div className="flex h-full w-full items-center justify-center rounded-[14px] bg-ink">
            <div className="h-[44%] w-[44%] rounded-[4px] bg-daylight shadow-[0_0_36px_10px_rgba(227,167,47,0.35)]" />
          </div>
        </div>
      </div>
      <figcaption className="mt-4 max-w-[38em] text-sm text-ink-2">
        At the centre is one ledger and one log of every AI decision, with its model and its cost. Every figure Gemini writes is
        checked against the engine that produced it.
      </figcaption>
    </figure>
  );
}
```

- [ ] **Step 2: Write the front door**

```tsx
// file: apps/web/src/app/page.tsx
"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { getConfig, type RuntimeConfig } from "@/lib/config";
import { workspaceFor } from "@/lib/nav";
import { initials, PERSONAS, personaFor, personasByAct, type Persona } from "@/lib/personas";
import { setDevUser } from "@/lib/session";
import { useSession } from "@/lib/session-context";
import { PlanDiagram } from "@/components/plan-diagram";
import { Footer, Wordmark } from "@/components/shell";

const PRINCIPLES = [
  { title: "It explains; the engines count",
    text: "Prices, simulations, matches and checks are code. Gemini writes the words, and any dollar or percentage it writes that the engine did not produce is flagged on the page." },
  { title: "It proposes; people decide",
    text: "Orders, matches and alerts wait for a person. Publishing prices or changing the ledger needs a second person with a one-time code." },
  { title: "It shows where it looked",
    text: "Answers about funds cite the fact-sheet section; case reviews cite the evidence rows. Anything Gemini wrote is set in a serif, so you always know." },
];
const PILL = "inline-flex min-h-11 items-center justify-center gap-2 rounded-full px-5 text-sm font-semibold transition-colors disabled:cursor-wait disabled:opacity-70";
const PRIMARY = `${PILL} bg-ink text-white hover:bg-[#26343f]`;
const SECONDARY = `${PILL} border border-line-strong bg-surface text-ink hover:border-ink`;

function PersonCard({ person, current, opening, disabled, onEnter }:
  { person: Persona; current: boolean; opening: boolean; disabled: boolean; onEnter: () => void }) {
  const first = person.name.split(" ")[0];
  return (
    <article className={`flex flex-col gap-3 rounded-panel border bg-surface p-5 ${person.start ? "border-ink" : "border-line"}`}>
      <div className="flex items-center gap-3">
        <span aria-hidden="true" className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full border border-ink text-sm font-semibold">
          {initials(person.name)}
        </span>
        <span className="flex flex-col">
          <span className="text-[17px] font-semibold">{person.name}</span>
          <span className="text-[13px] text-muted">{person.role}{person.start ? ", start here" : ""}{current ? ", signed in now" : ""}</span>
        </span>
      </div>
      <p className="text-sm">{person.story}</p>
      <ul className="flex flex-col gap-1.5 text-sm text-ink-2">
        {person.tries.map((t) => (
          <li key={t} className="flex items-baseline gap-2.5">
            <span aria-hidden="true" className="h-1.5 w-1.5 shrink-0 -translate-y-0.5 rounded-[1px] bg-daylight" />{t}
          </li>
        ))}
      </ul>
      <button type="button" disabled={disabled} onClick={onEnter} className={`${person.start ? PRIMARY : SECONDARY} mt-1`}>
        {opening ? "Opening…" : `Enter as ${first}`}
      </button>
    </article>
  );
}

export default function FrontDoor() {
  const router = useRouter();
  const { me, refresh } = useSession();
  const [cfg, setCfg] = useState<RuntimeConfig | null>(null);
  const [opening, setOpening] = useState("");
  const space = me ? workspaceFor(me.roles) : null;
  const start = PERSONAS.find((p) => p.start) ?? PERSONAS[0];
  const signedInAs = personaFor(me?.email)?.email;

  useEffect(() => {
    getConfig().then(setCfg);
  }, []);

  async function enter(person: Persona) {
    if (!cfg) return;
    if (cfg.authMode !== "dev") {
      router.push("/login");
      return;
    }
    setOpening(person.email);
    setDevUser(person.email);
    await refresh();
    router.push(person.home);
  }

  const busy = Boolean(opening) || !cfg;
  return (
    <div className="min-h-screen">
      <header className="border-b border-line bg-surface">
        <div className="mx-auto flex h-[72px] max-w-[1240px] items-center justify-between gap-4 px-4 sm:px-8">
          <Wordmark href="/" />
          <nav aria-label="Sections" className="flex items-center gap-3 sm:gap-7">
            <a href="#how" className="hidden min-h-11 items-center text-[15px] text-ink-2 hover:text-ink sm:flex">How it works</a>
            <a href="#journeys" className="flex min-h-11 items-center text-[15px] text-ink-2 hover:text-ink">Journeys</a>
            {me && space
              ? <Link href={space.home} className={`${PRIMARY} hidden sm:inline-flex`}>Continue as {(me.full_name ?? me.email).split(" ")[0]}</Link>
              : <button type="button" disabled={busy} onClick={() => enter(start)} className={`${PRIMARY} hidden sm:inline-flex`}>Start as {start.name.split(" ")[0]}</button>}
          </nav>
        </div>
      </header>

      <main>
        <section className="mx-auto max-w-[1240px] px-4 pb-20 pt-12 sm:px-8 lg:pb-28 lg:pt-20">
          <div className="grid items-center gap-12 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.02fr)] lg:gap-16">
            <div className="flex flex-col gap-7">
              <h1 className="wide text-[38px] font-semibold leading-[1.05] tracking-[-0.025em] sm:text-[52px] lg:text-[58px]">
                A wealth firm run by people, with an AI that shows its working.
              </h1>
              <p className="max-w-[34em] text-[17px] leading-relaxed text-ink-2 sm:text-[19px]">
                Atrium follows an investor from the first enquiry to a reconciled ledger: four stages, eight people, and Gemini at
                every step, checked against the numbers it explains.
              </p>
              <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap">
                <button type="button" disabled={busy} onClick={() => enter(start)} className={PRIMARY}>
                  {opening === start.email ? "Opening…" : `Start as ${start.name.split(" ")[0]}, an investor`}
                </button>
                <a href="#journeys" className={SECONDARY}>Choose another person</a>
              </div>
              <p className="text-sm text-muted">Every person, account and trade here is synthetic. Trading uses paper money at real US market prices.</p>
            </div>
            <PlanDiagram />
          </div>
        </section>

        <section id="how" className="scroll-mt-4 border-y border-line bg-surface">
          <div className="mx-auto max-w-[1240px] px-4 py-16 sm:px-8 lg:py-20">
            <h2 className="wide max-w-[22em] text-[28px] font-semibold leading-[1.15] tracking-[-0.015em] sm:text-[34px]">
              What the AI does, and what it never does
            </h2>
            <div className="mt-10 grid gap-8 md:grid-cols-3">
              {PRINCIPLES.map((p) => (
                <div key={p.title} className="border-t-2 border-ink pt-5">
                  <h3 className="text-lg font-semibold">{p.title}</h3>
                  <p className="mt-2 text-ink-2">{p.text}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section id="journeys" className="mx-auto max-w-[1240px] scroll-mt-4 px-4 py-16 sm:px-8 lg:py-24">
          <h2 className="wide text-[28px] font-semibold leading-[1.15] tracking-[-0.015em] sm:text-[34px]">Choose a person</h2>
          <p className="mt-3 max-w-[40em] text-[17px] text-ink-2">
            Each journey takes two or three minutes. A guide beside every page tells you what to try next, and you can switch
            person at any time from the top bar.
          </p>
          {cfg && cfg.authMode !== "dev" && (
            <p className="mt-3 text-sm text-ink-2">This deployment uses real sign-in. <Link href="/login" className="font-semibold underline underline-offset-4">Sign in</Link> to continue.</p>
          )}
          <div className="mt-10 grid gap-x-5 gap-y-8 sm:grid-cols-2 xl:grid-cols-4 xl:items-start">
            {personasByAct().map(({ act, people }) => (
              <div key={act.key} className="flex flex-col gap-3.5">
                <p className="text-sm text-muted"><span className="num font-semibold text-ink">{act.number}</span>&ensp;{act.label}</p>
                {people.map((p) => (
                  <PersonCard key={p.email} person={p} current={signedInAs === p.email} opening={opening === p.email}
                    disabled={busy} onEnter={() => enter(p)} />
                ))}
              </div>
            ))}
          </div>
        </section>
      </main>
      <Footer />
    </div>
  );
}
```

- [ ] **Step 3: Keep the login page for real sign-in only**

```tsx
// file: apps/web/src/app/login/page.tsx
"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { signInWithEmailAndPassword } from "firebase/auth";
import { getConfig, type RuntimeConfig } from "@/lib/config";
import { firebaseAuth } from "@/lib/firebase";
import { useSession } from "@/lib/session-context";
import { Button, Field, inputClass, Loading, Notice } from "@/components/ui";

/** Email sign-in for deployments with real accounts. With persona sign-in, people are chosen on the front door. */
export default function LoginPage() {
  const router = useRouter();
  const { refresh } = useSession();
  const [cfg, setCfg] = useState<RuntimeConfig | null>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    getConfig().then((c) => {
      if (c.authMode === "dev") router.replace("/#journeys");
      else setCfg(c);
    });
  }, [router]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    try {
      await signInWithEmailAndPassword(firebaseAuth(cfg!), email, password);
      await refresh();
      router.push("/");
    } catch (err) {
      setError((err as Error).message);
    }
  }

  if (!cfg) return <Loading label="Opening sign-in" />;
  return (
    <div className="mx-auto max-w-sm">
      <h1 className="wide text-[30px] font-semibold tracking-[-0.015em]">Sign in</h1>
      <form onSubmit={submit} className="mt-6 space-y-4">
        <Field label="Email"><input className={inputClass} type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} /></Field>
        <Field label="Password"><input className={inputClass} type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} /></Field>
        {error && <Notice tone="error">{error}</Notice>}
        <Button type="submit">Sign in</Button>
      </form>
      <p className="mt-6 text-sm text-ink-2">New here? <Link href="/" className="font-semibold underline underline-offset-4">See what Atrium is</Link>.</p>
    </div>
  );
}
```

- [ ] **Step 4: Type-check, lint and test**

Run: `cd apps/web && pnpm tsc --noEmit && pnpm lint && pnpm vitest run`
Expected: no errors; all tests pass

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/components/plan-diagram.tsx apps/web/src/app/page.tsx apps/web/src/app/login/page.tsx
git commit -m "feat(web): a front door that tells Atrium's story and lets you choose a person"
```

---

### Task 5: Investor home

Home opens with the one thing that matters: how the portfolio's risk compares with the profile. It shows a five-band scale with both marked, the plain-English verdict, and the two next steps. Below are what the person holds, how it is spread, and how the valuation was computed.

**Files:**
- Create: `apps/web/src/components/risk-scale.tsx`
- Modify (rewrite): `apps/web/src/app/investor/page.tsx`

**Interfaces:**
- Consumes:
  - From Task 1: `KeyMoment`, `ButtonLink`, `Section`.
  - From `lib/invest`: `BAND_COLOR`, `CATEGORY`, `verdictText`, `RiskReport`, `XRay`.
  - `AllocationBar` and `WhyPanel`.
- Produces: `RiskScale({ profile, portfolio })`.

- [ ] **Step 1: Write the risk scale**

```tsx
// file: apps/web/src/components/risk-scale.tsx
import { BAND_COLOR } from "@/lib/invest";
import { BAND_LABEL } from "@/components/ui";

const BANDS = [1, 2, 3, 4, 5];

/** The five risk bands with the investor's profile (solid ring) and their portfolio (dashed ring) marked. */
export function RiskScale({ profile, portfolio }: { profile: number | null; portfolio: number }) {
  const said = profile
    ? `Risk scale from 1 to 5: your profile is band ${profile}, ${BAND_LABEL[profile]}; your portfolio behaves like band ${portfolio}, ${BAND_LABEL[portfolio]}`
    : `Risk scale from 1 to 5: your portfolio behaves like band ${portfolio}, ${BAND_LABEL[portfolio]}`;
  return (
    <div role="img" aria-label={said} className="space-y-2.5">
      <div className="grid grid-cols-5 gap-1.5" aria-hidden="true">
        {BANDS.map((b) => (
          <div key={b} className="h-3.5 rounded-[4px]"
            style={{
              background: BAND_COLOR[b], outlineOffset: 2,
              outline: b === profile ? "2px solid var(--color-ink)" : b === portfolio ? "2px dashed var(--color-loss)" : undefined,
            }} />
        ))}
      </div>
      <div className="grid grid-cols-5 gap-1.5 text-[12px] leading-snug text-muted sm:text-[13px]" aria-hidden="true">
        {BANDS.map((b) => (
          <span key={b} className={b === profile ? "font-semibold text-ink" : b === portfolio ? "font-semibold text-loss" : ""}>
            {b} {BAND_LABEL[b]}
            {b === profile && <span className="block">{b === portfolio ? "your profile and portfolio" : "your profile"}</span>}
            {b === portfolio && b !== profile && <span className="block">your portfolio now</span>}
          </span>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Rewrite the investor home**

```tsx
// file: apps/web/src/app/investor/page.tsx
"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, ApiError, type Holding, type Portfolio } from "@/lib/api";
import { formatDate, formatPct, formatSignedUsd, formatUsd } from "@/lib/format";
import { BAND_COLOR, CATEGORY, verdictText, type RiskReport, type XRay } from "@/lib/invest";
import { useMe } from "@/lib/session-context";
import { AllocationBar, type Slice } from "@/components/allocation-bar";
import { RiskScale } from "@/components/risk-scale";
import { WhyPanel } from "@/components/why-panel";
import { ButtonLink, EmptyState, KeyMoment, Loading, Notice, Section, tableStyles } from "@/components/ui";

const ASSET: Record<string, string> = { equity: "Stocks", bond: "Bonds", cash: "Cash and T-bills" };
const REGION: Record<string, string> = { US: "United States", DM_ex_US: "Developed outside the US", EM: "Emerging markets", Global: "Global" };
const CASH_GREY = "#9aa3aa";

function slices(map: Record<string, string>, names: Record<string, string>): Slice[] {
  return Object.entries(map).map(([k, v], i) => ({ key: k, label: names[k] ?? k, value: Number(v), color: CATEGORY[i % CATEGORY.length] }));
}

function holdingHref(h: Holding): string | null {
  if (h.kind === "fund") return `/investor/funds/${h.instrument}`;
  if (h.kind === "cash") return "/investor/trades";
  return `/investor/markets/${h.instrument}`;
}

const MOMENT = {
  above: { tone: "attention", label: "One thing needs your attention", title: "Your mix has drifted above the risk you chose." },
  below: { tone: "info", label: "Worth knowing", title: "Your mix is calmer than the risk you chose." },
  within: { tone: "good", label: "All in order", title: "Your mix matches the risk you chose." },
  no_profile: { tone: "attention", label: "One thing to do", title: "Set your risk profile, so Atrium can check your mix against it." },
} as const;

function RiskMoment({ risk }: { risk: RiskReport }) {
  const m = MOMENT[risk.verdict];
  const actions = risk.verdict === "no_profile"
    ? <ButtonLink href="/investor/profile">Set your risk profile</ButtonLink>
    : risk.verdict === "within"
      ? <ButtonLink href="/investor/risk" variant="secondary">Open your risk report</ButtonLink>
      : <><ButtonLink href="/investor/what-if">See what it means for your future</ButtonLink><ButtonLink href="/investor/risk" variant="secondary">Open your risk report</ButtonLink></>;
  return (
    <KeyMoment tone={m.tone} label={m.label} title={m.title} actions={actions}>
      <RiskScale profile={risk.profile_band} portfolio={risk.portfolio_band} />
      <p className="max-w-[60ch] text-[15px] text-ink-2">{verdictText(risk.verdict, risk.portfolio_band, risk.profile_band)}</p>
    </KeyMoment>
  );
}

export default function InvestorHome() {
  const me = useMe();
  const account = me.accounts[0];
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [risk, setRisk] = useState<RiskReport | null>(null);
  const [xray, setXray] = useState<XRay | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!account) return;
    (async () => {
      try {
        setPortfolio(await api<Portfolio>(`/accounts/${account.id}/portfolio`));
      } catch (e) {
        setError(e instanceof ApiError ? e.message : "Atrium could not value your portfolio. Try again.");
        return;
      }
      const [r, x] = await Promise.allSettled([api<RiskReport>(`/accounts/${account.id}/risk`), api<XRay>(`/accounts/${account.id}/xray`)]);
      if (r.status === "fulfilled") setRisk(r.value);
      if (x.status === "fulfilled") setXray(x.value);
    })();
  }, [account]);

  if (!account) return <EmptyState title="No investment account yet">Choose an investor on the front page to see a portfolio.</EmptyState>;
  if (error) return <Notice tone="error" title="Could not load your portfolio">{error}</Notice>;
  if (!portfolio) return <Loading label="Valuing your portfolio" />;

  const total = Number(portfolio.total_value);
  const up = Number(portfolio.pnl) >= 0;
  const pricedOn = portfolio.holdings.map((h) => h.price_as_of).sort().at(-1) ?? portfolio.as_of;
  const holdingSlices = portfolio.holdings.map((h) => ({
    key: h.instrument, label: h.name, value: Number(h.value), color: h.kind === "cash" ? CASH_GREY : BAND_COLOR[h.risk_band ?? 3] }));
  const warnings = xray?.warnings ?? [];

  return (
    <div className="space-y-10">
      <div className="flex flex-wrap items-end justify-between gap-5">
        <div>
          <h1 className="text-[15px] font-semibold text-muted">Your portfolio</h1>
          <p className="num wide mt-1.5 text-[44px] font-semibold leading-none tracking-[-0.03em] sm:text-[54px]">{formatUsd(portfolio.total_value)}</p>
          <p className="num mt-2 text-[15px]">
            <span className={`font-semibold ${up ? "text-gain" : "text-loss"}`}>{formatSignedUsd(portfolio.pnl)}, {up ? "up" : "down"} {formatPct(Math.abs(Number(portfolio.pnl_pct)), 2)}</span>
            <span className="text-muted"> on what you paid in. Account {account.number}, priced {formatDate(pricedOn)}.</span>
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <ButtonLink href="/investor/orders" variant="secondary">Invest or withdraw</ButtonLink>
          <ButtonLink href="/investor/markets" variant="secondary">Trade shares</ButtonLink>
        </div>
      </div>

      {risk ? <RiskMoment risk={risk} /> : <Loading label="Checking your mix against your risk profile" />}

      {warnings.length > 0 && (
        <Notice tone="caution" title={`The Portfolio X-ray found ${warnings.length} thing${warnings.length > 1 ? "s" : ""} to look at`}
          action={<ButtonLink href="/investor/xray" variant="secondary" size="sm">Open the X-ray</ButtonLink>}>
          Starting with: {warnings[0].title.charAt(0).toLowerCase()}{warnings[0].title.slice(1)}.
        </Notice>
      )}

      <Section title="What you hold" description="Each holding's colour shows its risk band, from 1 (calmest) to 5 (most volatile). Cash for trading is grey.">
        <AllocationBar slices={holdingSlices} total={total} />
        <div className={`${tableStyles.wrap} mt-6 rounded-panel border border-line bg-surface px-5`}>
          <table className={tableStyles.table}>
            <thead className={tableStyles.head}>
              <tr>
                <th className={tableStyles.th}>Holding</th>
                <th className={`${tableStyles.th} text-right`}>Units</th>
                <th className={`${tableStyles.th} text-right`}>Price</th>
                <th className={`${tableStyles.th} text-right`}>Value</th>
                <th className={`${tableStyles.th} text-right`}>Gain or loss</th>
              </tr>
            </thead>
            <tbody>
              {portfolio.holdings.map((h) => {
                const href = holdingHref(h);
                const cash = h.kind === "cash";
                return (
                  <tr key={h.instrument} className={tableStyles.row}>
                    <td className={tableStyles.td}>
                      {href ? <Link href={href} className="font-semibold hover:underline">{h.name}</Link> : <span className="font-semibold">{h.name}</span>}
                      {!cash && <span className="ml-2 text-xs text-muted">{h.instrument}</span>}
                    </td>
                    <td className={`${tableStyles.td} num text-right`}>{cash ? "" : Number(h.units).toFixed(h.kind === "fund" ? 4 : 0)}</td>
                    <td className={`${tableStyles.td} num text-right`}>
                      {cash ? "" : <>{formatUsd(h.price)}<span className="block text-xs text-muted">{formatDate(h.price_as_of)}</span></>}
                    </td>
                    <td className={`${tableStyles.td} num text-right font-semibold`}>{formatUsd(h.value)}</td>
                    <td className={`${tableStyles.td} num text-right ${Number(h.pnl) >= 0 ? "text-gain" : "text-loss"}`}>
                      {cash ? "" : <>{formatSignedUsd(h.pnl)}<span className="block text-xs">{formatPct(h.pnl_pct, 2, true)}</span></>}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Section>

      <Section title="How it is spread">
        <div className="grid gap-8 md:grid-cols-2">
          <AllocationBar title="By asset class" slices={slices(portfolio.by_asset_class, ASSET)} total={total} />
          <AllocationBar title="By region" slices={slices(portfolio.by_region, REGION)} total={total} />
        </div>
      </Section>

      <WhyPanel title="how this valuation was computed" model="deterministic valuation engine (no AI)"
        evidence={[
          { label: "Prices", detail: "Each fund is valued at its last published price. Shares and ETFs you hold directly are valued at the latest quote, and paper cash at face value." },
          { label: "Paid in", detail: "The purchase cost of the units and shares you still hold, first in, first out, plus your paper cash. Realised gains are excluded." },
          { label: "Asset class and region", detail: "Each fund's value is split across the ETFs it holds, using their fixed weights; a share counts as a US stock." },
        ]} />
    </div>
  );
}
```

- [ ] **Step 3: Type-check, lint and test**

Run: `cd apps/web && pnpm tsc --noEmit && pnpm lint && pnpm vitest run`
Expected: no errors; all tests pass

- [ ] **Step 4: Commit**

```bash
git add apps/web/src/components/risk-scale.tsx apps/web/src/app/investor/page.tsx
git commit -m "feat(web): investor home opens with the risk drift on a five-band scale"
```

---

### Task 6: Leads

Leads opens with the leads to look at first. If several came from one device, it says so as a sentence, with each lead's trust score and strongest signal. Then come the leads worth a call, sorted by fit with a fit bar and the trust band, then leads not yet scored, then clients. The stage board gives way to this triage; each lead still shows its stage.

**Files:**
- Modify: `apps/web/src/lib/leads.ts` (`triage`, `attentionHeadline`, `strongestSignal`)
- Modify: `apps/web/src/lib/leads.test.ts`
- Modify (rewrite): `apps/web/src/app/advisor/page.tsx`

**Interfaces:**
- Consumes:
  - `Lead`, `STAGE_LABEL` and `TrustBadge`.
  - From Task 1: `KeyMoment`, `Section` and `Button`.
- Produces: `Triage`, `triage(leads)`, `attentionHeadline(attention)`, `strongestSignal(lead)`.

- [ ] **Step 1: Write the failing tests**

Append to `apps/web/src/lib/leads.test.ts` (and add `attentionHeadline, strongestSignal, triage` to its import from `./leads`):

```ts
const scored = (id: string, over: Partial<Lead>) =>
  ({ id, full_name: id, stage: "new", lead_score: 50, trust_score: 100, trust_band: "clear", trust_signals: [],
     scored_at: "2026-10-12T10:00:00Z", ...over }) as Lead;
const signal = (code: string, label: string, weight: number) => ({ code, label, weight, evidence: "", source: "rules", blocking: false });

describe("triage", () => {
  it("puts risky leads first, then the ones worth a call by fit, and keeps clients and unscored apart", () => {
    const leads = [
      scored("ring", { trust_band: "high_risk", trust_score: 27 }), scored("blocked", { trust_band: "blocked", trust_score: 0 }),
      scored("good", { lead_score: 66 }), scored("ok", { lead_score: 39, trust_band: "review" }),
      scored("client", { stage: "client", lead_score: 91 }), scored("fresh", { scored_at: null }),
      scored("lost", { stage: "disqualified" }),
    ];
    const t = triage(leads);
    expect(t.attention.map((l) => l.id)).toEqual(["blocked", "ring"]);
    expect(t.call.map((l) => l.id)).toEqual(["good", "ok"]);
    expect([t.clients.map((l) => l.id), t.unscored.map((l) => l.id), t.closed.map((l) => l.id)]).toEqual([["client"], ["fresh"], ["lost"]]);
  });
  it("says what the risky leads have in common, in one sentence", () => {
    const ring = ["a", "b", "c", "d"].map((id) => scored(id, {
      trust_band: "high_risk", trust_signals: [signal("T01", "Disposable email domain", 30), signal("T05", "Many leads from one device", 40)] }));
    expect(attentionHeadline(ring)).toBe("4 leads arrived from one device within 24 hours, each with a throwaway email address.");
    expect(attentionHeadline([scored("x", { full_name: "Linda Morales", trust_band: "blocked" })])).toBe("Linda Morales needs a look before anyone calls.");
    expect(attentionHeadline([scored("x", { trust_band: "blocked" }), scored("y", { trust_band: "blocked" })])).toBe("2 leads need a look before anyone calls them.");
    expect(strongestSignal(ring[0])).toBe("Many leads from one device");
    expect(strongestSignal(scored("z", {}))).toBeNull();
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd apps/web && pnpm vitest run src/lib/leads.test.ts`
Expected: FAIL (`triage` is not exported)

- [ ] **Step 3: Write the triage**

Append to `apps/web/src/lib/leads.ts`:

```ts
export type Triage = { attention: Lead[]; call: Lead[]; clients: Lead[]; unscored: Lead[]; closed: Lead[] };

/** Leads in the order an advisor should see them: the risky ones first, then the ones worth a call by fit. */
export function triage(leads: Lead[]): Triage {
  const out: Triage = { attention: [], call: [], clients: [], unscored: [], closed: [] };
  for (const l of leads) {
    if (l.stage === "client") out.clients.push(l);
    else if (l.stage === "disqualified") out.closed.push(l);
    else if (!l.scored_at) out.unscored.push(l);
    else if (l.trust_band === "high_risk" || l.trust_band === "blocked") out.attention.push(l);
    else out.call.push(l);
  }
  const byFit = (a: Lead, b: Lead) => (b.lead_score ?? -1) - (a.lead_score ?? -1) || a.full_name.localeCompare(b.full_name);
  out.attention.sort((a, b) => (a.trust_score ?? 101) - (b.trust_score ?? 101) || a.full_name.localeCompare(b.full_name));
  out.call.sort(byFit);
  out.clients.sort(byFit);
  return out;
}

const has = (l: Lead, code: string) => (l.trust_signals ?? []).some((s) => s.code === code);

export function attentionHeadline(attention: Lead[]): string {
  const ring = attention.filter((l) => has(l, "T05"));
  if (ring.length >= 2) {
    const throwaway = ring.every((l) => has(l, "T01"));
    return `${ring.length} leads arrived from one device within 24 hours${throwaway ? ", each with a throwaway email address" : ""}.`;
  }
  if (attention.length === 1) return `${attention[0].full_name} needs a look before anyone calls.`;
  return `${attention.length} leads need a look before anyone calls them.`;
}

export function strongestSignal(lead: Lead): string | null {
  const signals = [...(lead.trust_signals ?? [])].sort((a, b) => b.weight - a.weight);
  return signals[0]?.label ?? null;
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd apps/web && pnpm vitest run src/lib/leads.test.ts`
Expected: PASS

- [ ] **Step 5: Rewrite the leads page**

```tsx
// file: apps/web/src/app/advisor/page.tsx
"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { formatUsd } from "@/lib/format";
import { attentionHeadline, STAGE_LABEL, strongestSignal, triage, type Lead } from "@/lib/leads";
import { useMe } from "@/lib/session-context";
import { TrustBadge } from "@/components/score-badge";
import { Button, KeyMoment, Loading, Notice, PageHeader, Section } from "@/components/ui";

function FitBar({ score }: { score: number | null }) {
  return (
    <span className="flex items-center gap-2.5">
      <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-line" aria-hidden="true">
        <span className="block h-full rounded-full bg-ink" style={{ width: `${score ?? 0}%` }} />
      </span>
      <span className="num w-7 text-right text-[13px] font-semibold">{score ?? "?"}</span>
    </span>
  );
}

function LeadRow({ lead }: { lead: Lead }) {
  return (
    <li>
      <Link href={`/advisor/leads/${lead.id}`}
        className="grid gap-x-5 gap-y-1 border-t border-line py-4 hover:bg-ground/60 sm:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)_auto_110px] sm:items-center">
        <span className="min-w-0">
          <span className="block font-semibold">{lead.full_name}</span>
          <span className="block truncate text-[13px] text-muted">{STAGE_LABEL[lead.stage]}. {lead.goals}</span>
        </span>
        <span className="flex items-center gap-2 text-[13px] text-muted sm:block"><span className="sm:sr-only">Fit</span><FitBar score={lead.lead_score} /></span>
        <span><TrustBadge band={lead.trust_band} score={lead.trust_score} /></span>
        <span className="num font-semibold sm:text-right">{formatUsd(lead.investable_usd, 0)}</span>
      </Link>
    </li>
  );
}

export default function Leads() {
  const me = useMe();
  const [leads, setLeads] = useState<Lead[] | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState("");
  const staff = me.roles.includes("staff");

  const load = useCallback(async () => {
    try {
      setLeads(await api<Lead[]>("/leads"));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    if (staff) load();
  }, [staff, load]);

  async function scorePending() {
    setBusy(true);
    setError("");
    setProgress("");
    try {
      // The API scores a small batch per request; keep going until nothing is left, showing progress as we go.
      for (let round = 0; round < 20; round++) {
        const r = await api<{ scored: number; remaining: number }>("/leads/score-pending", { method: "POST" });
        await load();
        if (r.remaining === 0 || r.scored === 0) break;
        setProgress(`${r.remaining} still to score`);
      }
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(false);
      setProgress("");
      await load();
    }
  }

  if (!staff) return <Notice tone="caution" title="Leads are for Atrium staff">Choose Daniel on the front page.</Notice>;
  if (error && !leads) return <Notice tone="error" title="Could not load the leads">{error}</Notice>;
  if (!leads) return <Loading label="Loading the leads" />;
  const t = triage(leads);
  const scoreButton = t.unscored.length > 0 && (
    <Button busy={busy} onClick={scorePending}>
      {busy ? `Scoring with Gemini${progress ? `, ${progress}` : ""}` : `Score ${t.unscored.length} new lead${t.unscored.length > 1 ? "s" : ""}`}
    </Button>
  );

  return (
    <>
      <PageHeader title="Leads"
        description="Every lead is scored twice before you call: for fit, how likely they are to become a client, and for trust, how likely they are to be real."
        actions={scoreButton || undefined} />
      {error && <div className="mb-6"><Notice tone="error">{error}</Notice></div>}
      <div className="space-y-10">
        {t.attention.length > 0 && (
          <KeyMoment tone="alert" label="Look at these first" title={attentionHeadline(t.attention)}>
            <ul className="grid gap-3 sm:grid-cols-2 2xl:grid-cols-4">
              {t.attention.map((l) => (
                <li key={l.id}>
                  <Link href={`/advisor/leads/${l.id}`}
                    className="flex h-full flex-col gap-1 rounded-[14px] border border-loss/25 bg-danger-wash p-4 hover:border-loss">
                    <span className="font-semibold">{l.full_name}</span>
                    <span className="num text-[13px] text-ink-2">{formatUsd(l.investable_usd, 0)} to invest</span>
                    <span className="num text-[13px] font-semibold text-loss">
                      {l.trust_band === "blocked" ? "Blocked" : `Trust ${l.trust_score}, high risk`}
                    </span>
                    {strongestSignal(l) && <span className="text-[13px] text-ink-2">{strongestSignal(l)}</span>}
                  </Link>
                </li>
              ))}
            </ul>
          </KeyMoment>
        )}

        <Section title="Worth a call" description="Sorted by fit. The bar is the Lead Score; the badge is the Trust Score.">
          {t.call.length === 0 ? <p className="text-sm text-muted">No leads are waiting for a call.</p> : (
            <ul className="rounded-panel border border-line bg-surface px-5 [&>li:first-child>a]:border-t-0">
              {t.call.map((l) => <LeadRow key={l.id} lead={l} />)}
            </ul>
          )}
        </Section>

        {t.unscored.length > 0 && (
          <Section title="Not scored yet" actions={scoreButton || undefined}>
            <ul className="rounded-panel border border-line bg-surface px-5 [&>li:first-child>a]:border-t-0">
              {t.unscored.map((l) => <LeadRow key={l.id} lead={l} />)}
            </ul>
          </Section>
        )}

        {t.clients.length > 0 && (
          <Section title="Clients" description="Leads that opened an account.">
            <ul className="rounded-panel border border-line bg-surface px-5 [&>li:first-child>a]:border-t-0">
              {t.clients.map((l) => <LeadRow key={l.id} lead={l} />)}
            </ul>
          </Section>
        )}
        {t.closed.length > 0 && <p className="text-sm text-muted">{t.closed.length} disqualified lead{t.closed.length > 1 ? "s are" : " is"} not shown.</p>}
      </div>
    </>
  );
}
```

- [ ] **Step 6: Type-check, lint and test**

Run: `cd apps/web && pnpm tsc --noEmit && pnpm lint && pnpm vitest run`
Expected: no errors; all tests pass

- [ ] **Step 7: Commit**

```bash
git add apps/web/src/lib/leads.ts apps/web/src/lib/leads.test.ts apps/web/src/app/advisor/page.tsx
git commit -m "feat(web): leads open with the ones to look at first, then the ones worth a call"
```

---

### Task 7: Reconciliation

The page opens with the latest statement: how many transactions were read, how many are matched, how many wait for a decision and how many are left over, with the balance check. Then:
- the reconciliation agent's proposals as statement-to-subscription pairs, with a mistyped reference highlighted, a confidence meter, the reasons, and Accept or Reject;
- the rules' exact matches as one panel with "Accept all";
- the deposits left for a person.

Match by hand, recent decisions and earlier statements sit in expandable sections below.

**Files:**
- Modify: `apps/web/src/lib/operations.ts` (`diffMarks`, `splitProposals`, `statementFlow`, `balanceNote`, `meterCells`)
- Modify: `apps/web/src/lib/operations.test.ts`
- Modify (rewrite): `apps/web/src/app/operations/reconciliation/page.tsx`

**Interfaces:**
- Consumes:
  - From Plan 5 (the operations library): `Match`, `Statement`, `Reconciliation`, `ReconcileResult`, `Approval`, `TIER_COPY`, `confidenceWords`, `proposerLabel` and `matchTotals`.
  - From Task 1: `KeyMoment`, `Panel`, `Button`.
  - `AiProse`.
- Produces: `diffMarks(a, b)`, `splitProposals(proposals)`, `statementFlow(statement)`, `balanceNote(statement)`, `meterCells(confidence)`.

- [ ] **Step 1: Write the failing tests**

Append to `apps/web/src/lib/operations.test.ts` (and add the five names to its import from `./operations`):

```ts
describe("reconciliation views", () => {
  it("marks the characters where two references differ", () => {
    expect(diffMarks("ATR-97B3905C", "ATR-97B39D5C").filter((m) => m.diff).map((m) => m.ch)).toEqual(["0"]);
    expect(diffMarks("ATR-1", "ATR-12").map((m) => m.diff)).toEqual([false, false, false, false, false]);
  });
  it("keeps the rules' exact matches apart from the agent's proposals", () => {
    const m = (id: string, by: string, state = "proposed") => ({ id, proposed_by: by, state }) as never;
    const split = splitProposals([m("a", "rules"), m("b", "agent"), m("c", "scorer"), m("d", "mei@atrium.demo", "awaiting_approval")]);
    expect(split.rules.map((x: { id: string }) => x.id)).toEqual(["a"]);
    expect(split.others.map((x: { id: string }) => x.id)).toEqual(["b", "c", "d"]);
  });
  it("counts a statement's lines and reads its balance check", () => {
    const s = { counts: { unmatched: 1, proposed: 2, matched: 5, ignored: 2 },
      notes: ["Read 10.", "The transactions add up to the change in balance, $16,778.42."] } as never;
    expect(statementFlow(s)).toEqual({ read: 10, matched: 5, waiting: 2, left: 1, ignored: 2 });
    expect(balanceNote(s)).toEqual({ ok: true, text: "The transactions add up to the change in balance, $16,778.42." });
    expect(balanceNote({ counts: {}, notes: ["They do not add up, so check the statement."] } as never)?.ok).toBe(false);
    expect(balanceNote({ counts: {}, notes: ["Read from CSV."] } as never)).toBeNull();
  });
  it("fills a five-cell meter from a confidence", () => {
    expect([meterCells(0.99), meterCells(0.85), meterCells(0.5), meterCells(0)]).toEqual([5, 4, 3, 0]);
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd apps/web && pnpm vitest run src/lib/operations.test.ts`
Expected: FAIL (`diffMarks` is not exported)

- [ ] **Step 3: Write the helpers**

Append to `apps/web/src/lib/operations.ts`:

```ts
/** Each character of `a`, marked where it differs from `b` at the same place: a mistyped reference, highlighted. */
export function diffMarks(a: string, b: string): { ch: string; diff: boolean }[] {
  return [...a].map((ch, i) => ({ ch, diff: b[i] !== undefined && b[i] !== ch }));
}

export function splitProposals(proposals: Match[]): { rules: Match[]; others: Match[] } {
  return {
    rules: proposals.filter((m) => m.proposed_by === "rules" && m.state === "proposed"),
    others: proposals.filter((m) => !(m.proposed_by === "rules" && m.state === "proposed")),
  };
}

export function statementFlow(s: Pick<Statement, "counts">): { read: number; matched: number; waiting: number; left: number; ignored: number } {
  const c = s.counts;
  const n = (k: keyof Statement["counts"]) => c[k] ?? 0;
  return { read: n("unmatched") + n("proposed") + n("matched") + n("ignored"), matched: n("matched"), waiting: n("proposed"),
    left: n("unmatched"), ignored: n("ignored") };
}

export function balanceNote(s: Pick<Statement, "notes">): { ok: boolean; text: string } | null {
  const note = s.notes.find((n) => /add up/i.test(n));
  return note ? { ok: !/do not add up/i.test(note), text: note } : null;
}

export function meterCells(confidence: number): number {
  return Math.max(0, Math.min(5, Math.round(confidence * 5)));
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd apps/web && pnpm vitest run src/lib/operations.test.ts`
Expected: PASS

- [ ] **Step 5: Rewrite the reconciliation page**

```tsx
// file: apps/web/src/app/operations/reconciliation/page.tsx
"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { api, ApiError, apiDownload, apiUpload } from "@/lib/api";
import { formatDate, formatUsd } from "@/lib/format";
import {
  balanceNote, confidenceWords, diffMarks, matchTotals, meterCells, proposerLabel, splitProposals, statementFlow, TIER_COPY,
  type Approval, type Match, type ReconcileResult, type Reconciliation, type Statement,
} from "@/lib/operations";
import { AiProse } from "@/components/ai-prose";
import { Badge, Button, EmptyState, Field, inputClass, Loading, Notice, PageHeader, Panel, Section, tableStyles as t } from "@/components/ui";

const msg = (e: unknown, fallback: string) => (e instanceof ApiError ? e.message : fallback);
const UPLOAD = "inline-flex min-h-11 cursor-pointer items-center justify-center gap-2 rounded-full border border-line-strong bg-surface px-5 text-sm font-semibold text-ink transition-colors hover:border-ink focus-within:ring-2 focus-within:ring-ink";

function saveBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function Meter({ confidence }: { confidence: number }) {
  const filled = meterCells(confidence);
  return (
    <span className="flex items-center gap-2.5 text-[13px] text-ink-2">
      <span className="flex gap-[3px]" aria-hidden="true">
        {[0, 1, 2, 3, 4].map((i) => <span key={i} className={`h-1.5 w-4 rounded-[2px] ${i < filled ? "bg-gain" : "bg-line"}`} />)}
      </span>
      <span className="num">{confidenceWords(confidence)}, {Math.round(confidence * 100)}%</span>
    </span>
  );
}

function Reference({ text, against }: { text: string; against: string }) {
  return (
    <span className="num">
      {diffMarks(text, against).map((m, i) => m.diff
        ? <mark key={i} className="rounded-[3px] bg-daylight-wash px-0.5 text-daylight-ink">{m.ch}</mark>
        : <span key={i}>{m.ch}</span>)}
    </span>
  );
}

function Pair({ match, busy, onDecide }: { match: Match; busy: string; onDecide: (id: string, action: "accept" | "reject") => void }) {
  const sub = match.subscriptions[0];
  const typed = match.lines.length === 1 && match.lines[0].reference && sub && match.lines[0].reference !== sub.reference
    ? match.lines[0].reference : null;
  return (
    <Panel className="space-y-4 p-5 sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <span className="font-semibold">{TIER_COPY[match.tier]}</span>
        <Meter confidence={match.confidence} />
      </div>
      <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_40px_minmax(0,1fr)] md:items-stretch">
        <div className="space-y-1 rounded-[14px] border border-line bg-ground/60 p-4">
          <p className="text-xs text-muted">On the statement{match.lines.length > 1 ? `, ${match.lines.length} lines` : ""}</p>
          {match.lines.map((l) => (
            <p key={l.id} className="text-sm"><span className="num font-semibold">{formatUsd(l.amount)}</span> <span className="text-ink-2">{l.description}</span></p>
          ))}
          {typed && sub && <p className="text-[13px] text-ink-2">Reference written as <Reference text={typed} against={sub.reference} /></p>}
        </div>
        <div className="hidden items-center justify-center md:flex" aria-hidden="true">
          <svg width="36" height="12" viewBox="0 0 36 12"><path d="M2 6h30M27 1l6 5-6 5" fill="none" stroke="#8c979f" strokeWidth="1.4" /></svg>
        </div>
        <div className="space-y-1 rounded-[14px] border border-line bg-ground/60 p-4">
          <p className="text-xs text-muted">Waiting for money</p>
          {match.subscriptions.map((s) => (
            <p key={s.instruction_id} className="text-sm"><span className="num font-semibold">{formatUsd(s.amount)}</span> <span className="text-ink-2">{s.reference}, {s.holder}, {s.fund_name}</span></p>
          ))}
        </div>
      </div>
      <ul className="flex flex-wrap gap-2">
        {match.evidence.map((e, i) => <li key={i} className="rounded-full bg-ground px-3 py-1 text-[13px] text-ink-2">{e}</li>)}
      </ul>
      <div className="flex flex-wrap items-center gap-2.5">
        {match.state === "awaiting_approval" ? (
          <p className="text-sm text-ink-2">Matched by hand; waiting for a second person in <Link href="/operations/approvals" className="font-semibold underline underline-offset-4">Approvals</Link>.</p>
        ) : (
          <>
            <Button busy={busy === `accept:${match.id}`} disabled={Boolean(busy)} onClick={() => onDecide(match.id, "accept")}>Accept the match</Button>
            <Button variant="secondary" busy={busy === `reject:${match.id}`} disabled={Boolean(busy)} onClick={() => onDecide(match.id, "reject")}>Reject</Button>
          </>
        )}
        <span className="flex items-center gap-2 text-[13px] text-muted">
          {match.proposed_by === "agent" && <span aria-hidden="true" className="h-2 w-2 rounded-[1px] bg-daylight" />}
          Proposed by {proposerLabel(match.proposed_by)}
        </span>
      </div>
    </Panel>
  );
}

function Flow({ statement }: { statement: Statement }) {
  const f = statementFlow(statement);
  const balance = balanceNote(statement);
  const tiles = [
    { n: f.read, label: "transactions read", cls: "bg-ground" },
    { n: f.matched, label: "matched", cls: "bg-gain-wash text-gain" },
    { n: f.waiting, label: "waiting for your decision", cls: "bg-daylight-wash text-daylight-ink" },
    { n: f.left, label: "left for you", cls: "border border-dashed border-line-strong bg-surface" },
  ];
  return (
    <Panel className="space-y-5 p-6 sm:p-7">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h2 className="text-[18px] font-semibold">Latest statement, read by {statement.source === "documentai" ? "Document AI" : "the CSV reader"}</h2>
        <span className="text-[13px] text-muted">{statement.filename}{statement.account_last4 ? `, account ending ${statement.account_last4}` : ""}</span>
      </div>
      <ul className="grid grid-cols-2 gap-2.5 md:grid-cols-4">
        {tiles.map((x) => (
          <li key={x.label} className={`rounded-[14px] p-4 ${x.cls}`}>
            <span className="num wide block text-[30px] font-semibold leading-none">{x.n}</span>
            <span className="mt-1.5 block text-sm text-ink-2">{x.label}</span>
          </li>
        ))}
      </ul>
      {balance && (
        <p className={`flex items-center gap-2.5 text-sm font-semibold ${balance.ok ? "text-gain" : "text-caution"}`}>
          <span aria-hidden="true">{balance.ok ? "✓" : "!"}</span>{balance.text}
        </p>
      )}
      {f.ignored > 0 && <p className="text-[13px] text-muted">{f.ignored} line{f.ignored > 1 ? "s" : ""} (interest and fees) need no match.</p>}
    </Panel>
  );
}

export default function ReconciliationPage() {
  const [data, setData] = useState<Reconciliation | null>(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [read, setRead] = useState<Statement | null>(null);
  const [found, setFound] = useState<ReconcileResult | null>(null);
  const [lineIds, setLineIds] = useState<string[]>([]);
  const [subIds, setSubIds] = useState<string[]>([]);
  const [reason, setReason] = useState("");
  const [asked, setAsked] = useState<Approval | null>(null);
  const [showExact, setShowExact] = useState(false);
  const file = useRef<HTMLInputElement>(null);
  const byHand = useRef<HTMLDetailsElement>(null);

  const load = useCallback(async () => setData(await api<Reconciliation>("/ops/reconciliation")), []);
  useEffect(() => {
    load().catch((e) => setError(msg(e, "Atrium could not load reconciliation. Try again.")));
  }, [load]);

  async function act(key: string, fallback: string, work: () => Promise<void>) {
    setBusy(key);
    setError("");
    try {
      await work();
      await load();
    } catch (e) {
      setError(msg(e, fallback));
    } finally {
      setBusy("");
    }
  }

  const fmt = data?.reads_pdf ? "pdf" : "csv";
  const readSample = () => act("sample", "Atrium could not read the sample statement. Try again.", async () => {
    setRead(await api<Statement>("/ops/statements/sample", { method: "POST", body: JSON.stringify({ fmt }) }));
    setFound(null);
  });
  const upload = (f: File) => act("upload", "Atrium could not read that statement.", async () => {
    const form = new FormData();
    form.append("file", f);
    try {
      setRead(await apiUpload<Statement>("/ops/statements", form));
      setFound(null);
    } finally {
      if (file.current) file.current.value = "";
    }
  });
  const findMatches = () => act("find", "Atrium could not look for matches. Try again.", async () => {
    setFound(await api<ReconcileResult>("/ops/reconcile", { method: "POST" }));
  });
  const decide = (id: string, action: "accept" | "reject") => act(`${action}:${id}`, "Atrium could not record the decision. Try again.", async () => {
    await api<Match>(`/ops/matches/${id}/${action}`, { method: "POST", body: JSON.stringify({}) });
  });
  const acceptAll = (ids: string[]) => act("accept-all", "Atrium could not accept every match. Try again.", async () => {
    for (const id of ids) await api<Match>(`/ops/matches/${id}/accept`, { method: "POST", body: JSON.stringify({}) });
  });
  const download = (kind: "pdf" | "csv") => act(`download:${kind}`, "Atrium could not write the sample statement.", async () => {
    saveBlob(await apiDownload(`/ops/statements/sample?fmt=${kind}`), `atrium-sample-statement.${kind}`);
  });
  const askManual = () => act("manual", "Atrium could not ask for the match.", async () => {
    setAsked(await api<Approval>("/ops/matches/manual", { method: "POST", body: JSON.stringify({ line_ids: lineIds, instruction_ids: subIds, reason }) }));
    setLineIds([]);
    setSubIds([]);
    setReason("");
  });
  const addDemoPayments = () => act("demo", "Atrium could not add the demo payments. Try again.", async () => {
    await api<{ added: number }>("/ops/demo/payments", { method: "POST" });
  });
  const toggle = (list: string[], set: (v: string[]) => void, id: string) => set(list.includes(id) ? list.filter((x) => x !== id) : [...list, id]);
  function openByHand(lineId: string) {
    setLineIds([lineId]);
    if (byHand.current) {
      byHand.current.open = true;
      byHand.current.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }

  const header = (
    <PageHeader title="Reconciliation"
      description="Match the money that reached the client money account with the subscriptions waiting for it. Rules take the clear cases, an agent proposes the rest, and you decide each one."
      actions={
        <>
          <label className={UPLOAD}>
            Upload a statement
            <input ref={file} type="file" accept=".pdf,.csv,application/pdf,text/csv" className="sr-only" disabled={Boolean(busy)}
              onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])} />
          </label>
          <Button busy={busy === "sample"} disabled={Boolean(busy) || !data} onClick={readSample}>Read the sample statement</Button>
        </>
      } />
  );
  if (!data) return <>{header}{error ? <Notice tone="error">{error}</Notice> : <Loading label="Loading reconciliation" />}</>;

  const latest = read ?? data.statements[0] ?? null;
  const { rules, others } = splitProposals(data.proposals);
  const proposedLines = new Set(data.proposals.flatMap((m) => m.lines.map((l) => l.id)));
  const left = data.unmatched.filter((l) => !proposedLines.has(l.id));
  const waiting = data.receipts.filter((r) => !r.in_proposal);
  const chosenLines = data.unmatched.filter((l) => lineIds.includes(l.id));
  const chosenSubs = data.receipts.filter((r) => subIds.includes(r.instruction_id));
  const totals = matchTotals(chosenLines, chosenSubs);

  return (
    <>
      {header}
      <p className="-mt-4 mb-8 max-w-[70ch] text-sm text-muted">
        The sample statement is written for the payments Atrium is waiting for, with the imperfections real statements have
        {data.reads_pdf ? ", and as a PDF it is read by Document AI" : "; Document AI is not configured here, so it is read as a CSV"}.
        Download it as a <button type="button" className="underline underline-offset-4" onClick={() => download("pdf")}>PDF</button> or
        a <button type="button" className="underline underline-offset-4" onClick={() => download("csv")}>CSV</button>.
      </p>
      <div className="space-y-10">
        {error && <Notice tone="error">{error}</Notice>}
        {latest ? <Flow statement={latest} /> : (
          <EmptyState title="No statement yet" action={<Button busy={busy === "sample"} onClick={readSample}>Read the sample statement</Button>}>
            Read the sample statement, or upload the client money account&apos;s statement as a PDF or CSV.
          </EmptyState>
        )}

        {data.unmatched.length > 0 && waiting.length > 0 && (
          <Panel className="flex flex-wrap items-center justify-between gap-4 p-5 sm:p-6">
            <p className="text-[15px]">
              <span className="font-semibold">{data.unmatched.length} deposit{data.unmatched.length === 1 ? " waits" : "s wait"}</span>
              <span className="text-ink-2"> to be matched with {waiting.length} subscription{waiting.length === 1 ? "" : "s"} waiting for money.</span>
            </p>
            <Button busy={busy === "find"} disabled={Boolean(busy)} onClick={findMatches}>Find matches</Button>
          </Panel>
        )}
        {found && (
          <div className="space-y-3">
            <p className="text-sm text-ink-2">The rules proposed {found.rules}; {found.used_agent ? `the agent proposed ${found.agent}` : `the scorer proposed ${found.scorer}`}.</p>
            {found.used_agent
              ? <AiProse caption="Written by the reconciliation agent (Gemini Flash) after it scored and checked each candidate."><p>{found.summary}</p></AiProse>
              : <p className="text-sm text-ink-2">{found.summary}</p>}
          </div>
        )}
        {data.demo && data.receipts.length === 0 && (
          <Notice title="No subscription is waiting for money"
            action={<Button variant="secondary" size="sm" busy={busy === "demo"} disabled={Boolean(busy)} onClick={addDemoPayments}>Add demo payments</Button>}>
            Earlier visitors matched them all. Add a new set of client subscriptions; the sample statement is then written for them.
          </Notice>
        )}

        {others.length > 0 && (
          <Section title="The agent's proposals" description="You decide each one.">
            <div className="space-y-4">{others.map((m) => <Pair key={m.id} match={m} busy={busy} onDecide={decide} />)}</div>
          </Section>
        )}

        {rules.length > 0 && (
          <Panel className="space-y-4 p-5 sm:p-6">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <h2 className="font-semibold">{rules.length} exact match{rules.length === 1 ? "" : "es"} by the rules</h2>
                <p className="text-sm text-ink-2">Reference and amount agree, or the only payment of its amount came from the holder: {rules.slice(0, 3).map((m) => m.subscriptions[0]?.holder).filter(Boolean).join(", ")}{rules.length > 3 ? ` and ${rules.length - 3} more` : ""}.</p>
              </div>
              <div className="flex flex-wrap gap-2.5">
                <Button variant="secondary" aria-expanded={showExact} onClick={() => setShowExact((v) => !v)}>{showExact ? "Hide them" : "Review them"}</Button>
                <Button busy={busy === "accept-all"} disabled={Boolean(busy)} onClick={() => acceptAll(rules.map((m) => m.id))}>
                  Accept all {rules.length}
                </Button>
              </div>
            </div>
            {showExact && <div className="space-y-4">{rules.map((m) => <Pair key={m.id} match={m} busy={busy} onDecide={decide} />)}</div>}
          </Panel>
        )}

        {left.length > 0 && (
          <Section title="Left for you" description="No rule or agent found a subscription for these deposits.">
            <ul className="space-y-3">
              {left.map((l) => (
                <li key={l.id} className="flex flex-wrap items-center justify-between gap-4 rounded-panel border border-dashed border-line-strong bg-surface p-5">
                  <p className="text-sm"><span className="num font-semibold">{formatUsd(l.amount)}</span> <span className="text-ink-2">{formatDate(l.value_date)}, {l.description}</span></p>
                  <Button variant="secondary" size="sm" onClick={() => openByHand(l.id)}>Match by hand</Button>
                </li>
              ))}
            </ul>
          </Section>
        )}

        <details ref={byHand} className="group rounded-panel border border-line bg-surface">
          <summary className="flex min-h-14 cursor-pointer items-center justify-between gap-4 px-5 font-semibold sm:px-6">
            Match by hand<span className="text-sm font-normal text-muted">A second person approves the match</span>
          </summary>
          <div className="space-y-5 border-t border-line p-5 sm:p-6">
            <div className="grid gap-6 lg:grid-cols-2">
              <fieldset>
                <legend className="text-sm font-semibold">Deposits on the statement</legend>
                {data.unmatched.length === 0 ? <p className="mt-2 text-sm text-muted">Every deposit is matched or proposed.</p> : (
                  <ul className="mt-2 divide-y divide-line border-y border-line">
                    {data.unmatched.map((l) => (
                      <li key={l.id}>
                        <label className="flex min-h-11 cursor-pointer items-start gap-3 py-2.5 text-sm">
                          <input type="checkbox" className="mt-1" checked={lineIds.includes(l.id)} onChange={() => toggle(lineIds, setLineIds, l.id)} />
                          <span className="min-w-0"><span className="num font-semibold">{formatUsd(l.amount)}</span> <span className="text-muted">{formatDate(l.value_date)}</span><span className="block text-ink-2">{l.description}</span></span>
                        </label>
                      </li>
                    ))}
                  </ul>
                )}
              </fieldset>
              <fieldset>
                <legend className="text-sm font-semibold">Subscriptions waiting for money</legend>
                {data.receipts.length === 0 ? <p className="mt-2 text-sm text-muted">No subscription is waiting for money.</p> : (
                  <ul className="mt-2 divide-y divide-line border-y border-line">
                    {data.receipts.map((r) => (
                      <li key={r.instruction_id}>
                        <label className={`flex min-h-11 items-start gap-3 py-2.5 text-sm ${r.in_proposal ? "opacity-60" : "cursor-pointer"}`}>
                          <input type="checkbox" className="mt-1" disabled={r.in_proposal} checked={subIds.includes(r.instruction_id)} onChange={() => toggle(subIds, setSubIds, r.instruction_id)} />
                          <span className="min-w-0"><span className="num font-semibold">{formatUsd(r.amount)}</span> <span className="num text-muted">{r.reference}</span><span className="block text-ink-2">{r.holder}, {r.fund_name}{r.in_proposal ? "; in a proposal" : ""}</span></span>
                        </label>
                      </li>
                    ))}
                  </ul>
                )}
              </fieldset>
            </div>
            {(lineIds.length > 0 || subIds.length > 0) && (
              <div className="max-w-xl space-y-3">
                <p className="text-sm">
                  The lines total <span className="num font-semibold">{formatUsd(totals.paid)}</span> and the subscriptions <span className="num font-semibold">{formatUsd(totals.due)}</span>.{" "}
                  <span className={totals.agrees ? "text-gain" : "text-caution"}>{totals.agrees ? "They agree." : "They do not agree yet."}</span>
                </p>
                <Field label="Why these belong together" hint="The approver reads this before deciding.">
                  <textarea className={`${inputClass} min-h-20`} value={reason} maxLength={500} onChange={(e) => setReason(e.target.value)}
                    placeholder="For example: The client confirmed by phone that this check pays for their October subscription." />
                </Field>
                <Button busy={busy === "manual"} disabled={!lineIds.length || !subIds.length || !reason.trim()} onClick={askManual}>Ask for approval</Button>
              </div>
            )}
            {asked && <Notice tone="success" title="Sent for approval">{asked.summary}.</Notice>}
          </div>
        </details>

        {data.recent.length > 0 && (
          <details className="rounded-panel border border-line bg-surface">
            <summary className="flex min-h-14 cursor-pointer items-center px-5 font-semibold sm:px-6">Recently decided</summary>
            <ul className="divide-y divide-line border-t border-line px-5 text-sm sm:px-6">
              {data.recent.map((m) => (
                <li key={m.id} className="flex flex-wrap items-baseline justify-between gap-2 py-3">
                  <span className="min-w-0">
                    {m.subscriptions.map((s) => `${s.reference} for ${s.holder}`).join(", ")}
                    <span className="block text-xs text-muted">{TIER_COPY[m.tier]}; {m.state} by {m.decided_by ?? "operations"}{m.decided_at ? ` on ${formatDate(m.decided_at)}` : ""}</span>
                  </span>
                  <Badge tone={m.state === "accepted" ? "gain" : "neutral"}>{m.state === "accepted" ? "Accepted" : "Rejected"}</Badge>
                </li>
              ))}
            </ul>
          </details>
        )}

        {data.statements.length > 0 && (
          <details className="rounded-panel border border-line bg-surface">
            <summary className="flex min-h-14 cursor-pointer items-center px-5 font-semibold sm:px-6">Statements</summary>
            <div className={`${t.wrap} border-t border-line px-5 sm:px-6`}>
              <table className={t.table}>
                <thead className={t.head}><tr><th className={t.th}>File</th><th className={t.th}>Read by</th><th className={t.th}>Uploaded</th><th className={`${t.th} text-right`}>To match</th><th className={`${t.th} text-right`}>Matched</th></tr></thead>
                <tbody>
                  {data.statements.map((s) => (
                    <tr key={s.id} className={t.row}>
                      <td className={t.td}>{s.filename}{s.bank_name && <span className="block text-xs text-muted">{s.bank_name}{s.account_last4 ? `, account ending ${s.account_last4}` : ""}</span>}</td>
                      <td className={t.td}>{s.source === "documentai" ? "Document AI" : "CSV"}</td>
                      <td className={t.td}>{formatDate(s.uploaded_at)}<span className="block text-xs text-muted">{s.uploaded_by}</span></td>
                      <td className={`${t.td} num text-right`}>{(s.counts.unmatched ?? 0) + (s.counts.proposed ?? 0)}</td>
                      <td className={`${t.td} num text-right`}>{s.counts.matched ?? 0}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
        )}
      </div>
    </>
  );
}
```

- [ ] **Step 6: Type-check, lint and test**

Run: `cd apps/web && pnpm tsc --noEmit && pnpm lint && pnpm vitest run`
Expected: no errors; all tests pass

- [ ] **Step 7: Commit**

```bash
git add apps/web/src/lib/operations.ts apps/web/src/lib/operations.test.ts apps/web/src/app/operations/reconciliation/page.tsx
git commit -m "feat(web): reconciliation opens with the statement's counts, then the agent's proposals as pairs"
```

---

### Task 8: An alert

The alert opens with its finding as a headline. For structuring, a chart shows each payment against the $10,000 line, labelled with its evidence row. Then come the case review and the decision side by side, who is linked, and the evidence.

**Files:**
- Modify: `apps/web/src/lib/compliance.ts` (`thresholdBars`)
- Modify: `apps/web/src/lib/compliance.test.ts`
- Modify (rewrite): `apps/web/src/app/compliance/alerts/[id]/page.tsx`

**Interfaces:**
- Consumes:
  - From Plan 5 (the compliance library): `AlertDetail`, `CaseReview`, `citationLabels`, `EVIDENCE_KIND`, `SCENARIO_COPY`, `SEVERITY_LABEL`, `SEVERITY_TONE`, `STATE_LABEL`, `TRIAGE_COPY`.
  - `EntityGraph` and `AiProse`.
  - From Task 1: `KeyMoment` and `Panel`.
- Produces: `thresholdBars(evidence, threshold)`.

- [ ] **Step 1: Write the failing test**

Append to `apps/web/src/lib/compliance.test.ts` (and add `thresholdBars` and `type EvidenceRow` to its import):

```ts
describe("thresholdBars", () => {
  it("scales each payment against the reporting line, labelled by its evidence row", () => {
    const ev = (id: string, amount: string | null, kind = "instruction") => ({ kind, id, date: "2026-10-06", amount, detail: "" }) as EvidenceRow;
    const { bars, linePct } = thresholdBars([ev("a", "9400.00"), ev("b", "9750.00"), ev("c", "9900.00"), ev("bank", null, "bank_link")], 10000);
    expect(bars.map((b) => [b.label, Math.round(b.pct)])).toEqual([["E1", 87], ["E2", 90], ["E3", 92]]);
    expect(Math.round(linePct)).toBe(93);
    expect(thresholdBars([ev("x", null, "feature")], 10000).bars).toEqual([]);
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd apps/web && pnpm vitest run src/lib/compliance.test.ts`
Expected: FAIL (`thresholdBars` is not exported)

- [ ] **Step 3: Write the helper**

Append to `apps/web/src/lib/compliance.ts`:

```ts
export type ThresholdBar = { id: string; label: string; date: string; amount: number; pct: number };

/** Payment rows drawn against a reporting threshold: each bar's height and the line's, as a share of the chart. */
export function thresholdBars(evidence: EvidenceRow[], threshold: number): { bars: ThresholdBar[]; linePct: number } {
  const labels = citationLabels(evidence);
  const rows = evidence.filter((e) => e.amount !== null && (e.kind === "instruction" || e.kind === "posting"));
  const top = Math.max(threshold * 1.08, ...rows.map((r) => Number(r.amount)));
  return {
    bars: rows.map((r) => ({ id: r.id, label: labels[r.id], date: r.date, amount: Number(r.amount), pct: (Number(r.amount) / top) * 100 })),
    linePct: (threshold / top) * 100,
  };
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd apps/web && pnpm vitest run src/lib/compliance.test.ts`
Expected: PASS

- [ ] **Step 5: Rewrite the alert page**

```tsx
// file: apps/web/src/app/compliance/alerts/[id]/page.tsx
"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import { formatDate, formatUsd } from "@/lib/format";
import {
  citationLabels, EVIDENCE_KIND, SCENARIO_COPY, SEVERITY_LABEL, SEVERITY_TONE, STATE_LABEL, thresholdBars, TRIAGE_COPY,
  type AlertDetail, type CaseReview, type EvidenceRow,
} from "@/lib/compliance";
import { AiProse } from "@/components/ai-prose";
import { EntityGraph } from "@/components/entity-graph";
import { Badge, Button, Field, inputClass, KeyMoment, Loading, Notice, PageHeader, Panel, Section } from "@/components/ui";

const msg = (e: unknown, fallback: string) => (e instanceof ApiError ? e.message : fallback);
const CHIP = "num inline-flex h-5 min-w-6 items-center justify-center rounded-[5px] bg-daylight-wash px-1 align-[2px] font-sans text-[11px] font-semibold text-daylight-ink no-underline hover:bg-daylight hover:text-ink";

function ThresholdChart({ evidence }: { evidence: EvidenceRow[] }) {
  const { bars, linePct } = thresholdBars(evidence, 10000);
  if (bars.length === 0) return null;
  const columns = { gridTemplateColumns: `repeat(${bars.length}, minmax(0, 1fr))` };
  return (
    <figure className="m-0">
      <div role="img" className="relative h-56 border-b border-line-strong"
        aria-label={`${bars.length} payments, ${bars.map((b) => `${formatUsd(b.amount)} on ${formatDate(b.date)}`).join(", ")}, each below the $10,000 reporting threshold`}>
        <div aria-hidden="true" className="absolute inset-x-0 border-t-2 border-dashed border-loss" style={{ bottom: `${linePct}%` }} />
        <span aria-hidden="true" className="num absolute right-0 bg-surface pl-2 text-xs font-semibold text-loss" style={{ bottom: `calc(${linePct}% + 6px)` }}>
          $10,000 reporting threshold
        </span>
        <div aria-hidden="true" className="absolute inset-0 grid items-end gap-6 px-4 sm:gap-12 sm:px-12" style={columns}>
          {bars.map((b) => <div key={b.id} className="rounded-t-[8px] bg-ink" style={{ height: `${b.pct}%` }} />)}
        </div>
      </div>
      <div className="mt-3 grid gap-6 px-4 sm:gap-12 sm:px-12" style={columns}>
        {bars.map((b) => (
          <span key={b.id} className="flex flex-col items-center text-center">
            <span className="num font-semibold">{formatUsd(b.amount)}</span>
            <span className="text-[13px] text-muted">{formatDate(b.date)} <a href={`#ev-${b.id}`} className={CHIP}>{b.label}</a></span>
          </span>
        ))}
      </div>
    </figure>
  );
}

function Review({ review, labels }: { review: CaseReview; labels: Record<string, string> }) {
  const problems = [
    review.unsupported_figures.length ? `${review.unsupported_figures.join(", ")} did not come from the evidence` : "",
    review.dropped_citations.length ? `${review.dropped_citations.length} citation${review.dropped_citations.length === 1 ? "" : "s"} to rows that are not in the evidence were removed` : "",
  ].filter(Boolean);
  return (
    <AiProse caption={`Written by ${review.model} from the alert, its evidence and the linked accounts. A suggestion only: you decide.`}
      warning={review.verified ? undefined : `Check before relying on this: ${problems.join("; ")}.`}>
      <p><span className="font-semibold">Suggestion: {TRIAGE_COPY[review.triage]}.</span> {review.triage_reason}</p>
      {review.narrative.map((part, i) => (
        <p key={i} className="mt-3">
          {part.text}{" "}
          {part.evidence.map((id) => <a key={id} href={`#ev-${id}`} className={`${CHIP} ml-0.5`}>{labels[id]}</a>)}
        </p>
      ))}
      {review.questions.length > 0 && (
        <>
          <p className="mt-4 font-semibold">Questions worth asking</p>
          <ul className="mt-1 list-disc space-y-1 pl-5">{review.questions.map((q, i) => <li key={i}>{q}</li>)}</ul>
        </>
      )}
    </AiProse>
  );
}

export default function AlertPage() {
  const { id } = useParams<{ id: string }>();
  const [alert, setAlert] = useState<AlertDetail | null>(null);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(async () => setAlert(await api<AlertDetail>(`/compliance/alerts/${id}`)), [id]);
  useEffect(() => {
    load().catch((e) => setError(msg(e, "Atrium could not load this alert. Try again.")));
  }, [load]);

  async function post(key: string, path: string, body: object | undefined, fallback: string) {
    setBusy(key);
    setError("");
    try {
      setAlert(await api<AlertDetail>(path, { method: "POST", body: body ? JSON.stringify(body) : undefined }));
    } catch (e) {
      setError(msg(e, fallback));
    } finally {
      setBusy("");
    }
  }

  if (!alert) return error ? <Notice tone="error">{error}</Notice> : <Loading label="Loading the alert" />;
  const labels = citationLabels(alert.evidence);
  return (
    <>
      <PageHeader title={alert.title} back={{ href: "/compliance", label: "Alerts" }}
        description={`${alert.person.name}${alert.account_number ? `, account ${alert.account_number}` : ""}. Raised ${formatDate(alert.raised_at)}.`}
        actions={<><Badge tone={SEVERITY_TONE[alert.severity]}>{SEVERITY_LABEL[alert.severity]} severity</Badge><Badge>{STATE_LABEL[alert.state]}</Badge></>} />
      <div className="space-y-10">
        <KeyMoment tone="alert" label="What monitoring found" title={alert.summary}>
          {alert.scenario === "structuring" && <ThresholdChart evidence={alert.evidence} />}
          {SCENARIO_COPY[alert.scenario] && <p className="max-w-[72ch] text-sm text-muted">The rule: {SCENARIO_COPY[alert.scenario]}</p>}
        </KeyMoment>

        <div className="grid gap-6 lg:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)] lg:items-start">
          <Panel className="space-y-4 p-6">
            <div className="flex flex-wrap items-baseline justify-between gap-3">
              <h2 className="text-[17px] font-semibold">Case review</h2>
              {alert.ai_review?.verified && <Badge tone="gain">Figures and citations checked</Badge>}
            </div>
            {alert.ai_review ? <Review review={alert.ai_review} labels={labels} /> : (
              <div className="space-y-3">
                <p className="text-sm text-ink-2">Gemini Pro reads the alert, its evidence and the linked accounts, and suggests what to do. It takes about half a minute.</p>
                <Button variant="secondary" busy={busy === "review"} disabled={Boolean(busy)}
                  onClick={() => post("review", `/compliance/alerts/${alert.id}/review`, undefined, "The case review is unavailable right now.")}>
                  Ask Gemini Pro for a case review
                </Button>
              </div>
            )}
          </Panel>

          <Panel className="space-y-4 p-6">
            <h2 className="text-[17px] font-semibold">Your decision</h2>
            {alert.state === "open" ? (
              <>
                <Field label="Your note" hint="The record of why. Escalating means filing a suspicious activity report.">
                  <textarea className={`${inputClass} min-h-24`} value={note} maxLength={1000} onChange={(e) => setNote(e.target.value)} />
                </Field>
                {error && <Notice tone="error">{error}</Notice>}
                <div className="flex flex-wrap gap-2.5">
                  <Button variant="danger" busy={busy === "escalate"} disabled={!note.trim() || Boolean(busy)}
                    onClick={() => post("escalate", `/compliance/alerts/${alert.id}/decide`, { decision: "escalate", note }, "Atrium could not record the decision.")}>Escalate</Button>
                  <Button variant="secondary" busy={busy === "close"} disabled={!note.trim() || Boolean(busy)}
                    onClick={() => post("close", `/compliance/alerts/${alert.id}/decide`, { decision: "close", note }, "Atrium could not record the decision.")}>Close the alert</Button>
                </div>
              </>
            ) : (
              <Notice tone={alert.state === "escalated" ? "caution" : "info"} title={`${STATE_LABEL[alert.state]} by ${alert.decided_by} on ${formatDate(alert.decided_at ?? alert.raised_at)}`}>
                {alert.decision_note}
              </Notice>
            )}
          </Panel>
        </div>

        <Section title="Who is linked" description="People joined to the subject by a shared bank account, a shared device or an outside payer.">
          <Panel className="p-5 sm:p-6"><EntityGraph nodes={alert.graph.nodes} edges={alert.graph.edges} /></Panel>
        </Section>

        <Section title="Evidence" description="The exact rows behind the alert.">
          <ol className="rounded-panel border border-line bg-surface px-5 text-sm">
            {alert.evidence.map((e) => (
              <li key={e.id} id={`ev-${e.id}`} className="grid scroll-mt-24 grid-cols-[2.5rem_minmax(0,1fr)] gap-x-3 border-t border-line py-3.5 first:border-t-0 target:bg-daylight-wash">
                <span className="num font-semibold">{labels[e.id]}</span>
                <div className="min-w-0">
                  <div className="flex flex-wrap items-baseline justify-between gap-x-4">
                    <span className="text-muted">{EVIDENCE_KIND[e.kind] ?? e.kind}, {formatDate(e.date)}</span>
                    {e.amount && <span className="num font-semibold">{formatUsd(e.amount)}</span>}
                  </div>
                  <p className="mt-0.5 text-[15px]">{e.detail}</p>
                </div>
              </li>
            ))}
          </ol>
        </Section>
      </div>
    </>
  );
}
```

- [ ] **Step 6: Type-check, lint and test**

Run: `cd apps/web && pnpm tsc --noEmit && pnpm lint && pnpm vitest run`
Expected: no errors; all tests pass

- [ ] **Step 7: Commit**

```bash
git add apps/web/src/lib/compliance.ts apps/web/src/lib/compliance.test.ts "apps/web/src/app/compliance/alerts/[id]/page.tsx"
git commit -m "feat(web): an alert opens with its finding, the payments against the line, then review and decision side by side"
```

---

### Task 9: Every page, looked at

This task screenshots every page at 1280 px and 390 px, as the persona whose journey reaches it, and fixes what the screenshots show. Typical fixes:
- a header whose description runs long;
- a component still drawing the old left rule;
- a table without its own scroll box;
- a panel that breaks the 18 px radius;
- a button below 44 px.

Each fix is a ledger ruling.

**Files:**
- Modify: whichever pages and components the screenshots show need it.

**Interfaces:**
- Consumes: everything above.
- Produces: no new interfaces.

- [ ] **Step 1: Start the API on a freshly seeded database and the web app**

Run, each in the background:
- `cd services/api && DATABASE_URL="sqlite+pysqlite:///<scratch>/ux.db" AUTO_SEED=true uv run uvicorn app.main:app --port 8000`
- `cd apps/web && pnpm dev`

Expected: `curl -s localhost:8000/health` answers `{"status":"ok",...}`, and `localhost:3000/` serves the front door.

- [ ] **Step 2: Screenshot every page**

Use the headless-Chrome DevTools script from earlier plans (it sets `atrium.devUser`, navigates and captures). Capture these pages, at 1280 px unless a phone width is noted:

| Persona | Pages |
|---|---|
| (none) | `/` at 1280 and 390 px |
| Priya | `/investor` at 1280 and 390 px, `/investor/xray`, `/investor/risk`, `/investor/profile`, `/investor/markets`, `/investor/markets/NVDA` at 1280 and 390 px, `/investor/trades`, `/investor/funds`, `/investor/funds/ATR-BAL`, `/investor/orders`, `/investor/what-if`, `/investor/copilot` |
| Daniel | `/advisor` at 1280 and 390 px, one lead, `/advisor/held`, `/apply` |
| Mei | `/operations`, `/operations/reconciliation` at 1280 and 390 px, `/operations/approvals`, `/operations/blotter` |
| Omar | `/compliance`, one alert at 1280 and 390 px, `/compliance/log` |

Expected:
- every page renders with the new shell;
- the rail item and tab are right;
- the guide shows the persona's story;
- `document.documentElement.scrollWidth` is 390 at phone width.

- [ ] **Step 3: Fix what the screenshots show**

For each problem: make the smallest change, re-shoot that page, and add a ledger line `Task 9: Ruling: <page>: <what was wrong> — <the fix> — <cost if wrong>`.

- [ ] **Step 4: Type-check, lint and test, then commit**

Run: `cd apps/web && pnpm tsc --noEmit && pnpm lint && pnpm vitest run`
Expected: no errors; all tests pass

```bash
git add apps/web/src
git commit -m "fix(web): visual pass across every page at desktop and phone width"
```

---

### Task 10: Release

**Files:**
- Modify: `README.md` (what you can try now starts at the front door)
- Modify: `docs/superpowers/plans/README.md` (Plan 6 progress)

- [ ] **Step 1: Update the docs**

In `README.md`, replace the line under "Live demo" with:

```markdown
https://atrium-web-1070337126396.us-central1.run.app opens on Atrium's front door: what it is, the four stages, and eight people to choose from. Each person has a short guided story beside every page. Every person and number is synthetic.
```

In `docs/superpowers/plans/README.md`, change the Plan 6 row's status to:

```markdown
In progress: the experience restructure ([plan](2026-10-12-atrium-experience.md), front door, one shell per person, journey guides, key-moment pages) is done and deployed; the deck, the video and the demo-data reset remain
```

- [ ] **Step 2: Check, commit and deploy**

Run: `bash infra/preflight.sh`
Expected: ends `preflight passed`, with `ok   forbidden words absent`

```bash
git add README.md docs/superpowers/plans/README.md
git commit -m "docs: the experience restructure"
```

Run: `bash infra/deploy.sh`
Expected: `API:` and `WEB:` URLs.

- [ ] **Step 3: Look at the live site**

Screenshot the live front door at 1280 and 390 px. Enter as Priya and as Omar.
Expected:
- the same as locally;
- the journey guide ticks a step after its page is visited.

- [ ] **Step 4: Report the cost**

The release changes only the web service, which scales to zero; no AI calls were added. The cost report restates the monthly estimate from the README and the cost of this session's live checks.
