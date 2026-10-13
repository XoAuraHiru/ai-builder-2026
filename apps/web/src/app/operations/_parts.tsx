"use client";

import Link from "next/link";
import { motion } from "motion/react";
import type { ReactNode } from "react";
import { arriveDelay } from "@/lib/operations";
import { CountUp, DrawnCheck, EASE, GrowBar } from "@/components/motion";

/** Parts the operations and compliance desks share: stat cards, table-sized status chips, the table card and the
 *  small glyphs their tiles carry, and the few motions they share (rows arriving in order, a decision confirming and
 *  leaving its queue). Built from design system 0.2; candidates for components/ui.tsx. */

export type Tone = "gain" | "caution" | "loss" | "neutral";

const GLYPHS = {
  chart: <><path d="M3 3v18h18" /><path d="m19 9-5 5-4-4-3 3" /></>,
  shield: <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />,
  money: <><path d="M12 2v20" /><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" /></>,
  match: <path d="M5 8h10l-3-3M19 16H9l3 3" />,
  check: <path d="M20 6 9 17l-5-5" />,
  people: <><circle cx="9" cy="8" r="3.5" /><path d="M2.5 20a6.5 6.5 0 0 1 13 0" /><path d="M16 4.5a3.5 3.5 0 0 1 0 7M18.5 20a6.5 6.5 0 0 0-2.5-5.1" /></>,
  list: <><path d="M8 6h13M8 12h13M8 18h13" /><path d="M3 6h.01M3 12h.01M3 18h.01" /></>,
  clock: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>,
  inbox: <><path d="M3 13h5l1.5 3h5l1.5-3h5" /><path d="M5 5h14l2 8v6H3v-6z" /></>,
  hand: <><path d="M8 13V5.5a1.5 1.5 0 0 1 3 0V12" /><path d="M11 11V4.5a1.5 1.5 0 0 1 3 0V12" /><path d="M14 11.5V6a1.5 1.5 0 0 1 3 0v8a7 7 0 0 1-12.6 4.2L2.8 15a1.6 1.6 0 0 1 2.6-1.8L8 15.5" /></>,
  hash: <><path d="M4 9h16M4 15h16" /><path d="M10 3 8 21M16 3l-2 18" /></>,
  alert: <><path d="M12 3 2 20h20z" /><path d="M12 10v4M12 17v.5" /></>,
} as const;
export type GlyphName = keyof typeof GLYPHS;

export function Glyph({ name, size = 15 }: { name: GlyphName; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round"
      strokeLinejoin="round" aria-hidden="true">
      {GLYPHS[name]}
    </svg>
  );
}

const TILE: Record<Tone, string> = {
  gain: "bg-green-50 text-green-600", caution: "bg-amber-50 text-amber-800", loss: "bg-coral-50 text-coral-700",
  neutral: "bg-fill text-ink-700",
};

/** A stat card: an icon tile and a title, the figure at 32px (counting up to itself when it is a figure), then a
 *  caption with a change or status chip. */
export function StatCard({ icon, title, value, unit, caption, chip, tone = "gain", href }:
  { icon: GlyphName; title: string; value: ReactNode; unit?: string; caption?: ReactNode; chip?: ReactNode; tone?: Tone; href?: string }) {
  const figure = typeof value === "number" || typeof value === "string" ? <CountUp text={String(value)} /> : value;
  const body = (
    <>
      <span className="flex items-center gap-2">
        <span className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-tile ${TILE[tone]}`}><Glyph name={icon} /></span>
        <span className="text-sm font-semibold leading-5">{title}</span>
      </span>
      <span className="flex flex-wrap items-baseline gap-x-1.5">
        <span className="num text-[32px] font-medium leading-9 tracking-[-0.02em]">{figure}</span>
        {unit && <span className="text-[13px] text-ink-500">{unit}</span>}
      </span>
      {(caption || chip) && (
        <span className="mt-auto flex flex-wrap items-center justify-between gap-2">
          <span className="text-xs leading-4 text-ink-500">{caption}</span>
          {chip}
        </span>
      )}
    </>
  );
  const box = "flex min-w-0 flex-col gap-3.5 rounded-panel border border-sand-200 bg-white p-[18px]";
  return href
    ? <Link href={href} className={`${box} transition-colors hover:border-sand-300 hover:bg-fill`}>{body}</Link>
    : <div className={box}>{body}</div>;
}

const CHIP: Record<Tone | "ai", { chip: string; dot: string }> = {
  gain: { chip: "bg-green-50 text-green-700", dot: "bg-green-500" },
  caution: { chip: "bg-amber-50 text-amber-800", dot: "bg-amber-400" },
  loss: { chip: "bg-coral-50 text-coral-700", dot: "bg-coral-500" },
  neutral: { chip: "bg-fill text-ink-700", dot: "bg-ink-400" },
  ai: { chip: "bg-ai-50 text-ai-700", dot: "bg-ai-500" },
};

/** A status chip at table size (26px, 12px type), with its dot so colour is never the only signal. */
export function StatusChip({ tone = "neutral", children }: { tone?: Tone | "ai"; children: ReactNode }) {
  return (
    <span className={`inline-flex h-[26px] items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 text-xs font-medium ${CHIP[tone].chip}`}>
      <span aria-hidden="true" className={`h-1.5 w-1.5 shrink-0 rounded-full ${CHIP[tone].dot}`} />
      {children}
    </span>
  );
}

/** The table spec: a card with its title, header cells in 12px ink-500, rows on sand-100 hairlines. */
export const tbl = {
  wrap: "-mx-5 overflow-x-auto px-5 sm:-mx-6 sm:px-6",
  table: "w-full border-collapse text-sm",
  head: "border-b border-sand-100 text-left text-xs text-ink-500",
  th: "whitespace-nowrap py-2.5 pr-4 font-medium last:pr-0",
  row: "border-b border-sand-100 last:border-b-0",
  td: "py-3 pr-4 align-middle last:pr-0",
  id: "code whitespace-nowrap text-ink-700",
  amount: "whitespace-nowrap text-right tabular-nums",
};

export function TableCard({ title, description, action, children, id }:
  { title: string; description?: ReactNode; action?: ReactNode; children: ReactNode; id?: string }) {
  return (
    <section id={id} className="scroll-mt-24 rounded-panel border border-sand-200 bg-white p-5 sm:p-6">
      <div className="mb-2 flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <div className="min-w-0">
          <h2 className="text-base font-semibold">{title}</h2>
          {description && <p className="mt-0.5 text-[13px] leading-5 text-ink-500">{description}</p>}
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

/** A green bar on a sand track, growing to its share when it appears. */
export function Bar({ pct, tone = "gain", label, delay = 0 }: { pct: number; tone?: Tone; label?: string; delay?: number }) {
  const fill = tone === "loss" ? "bg-coral-500" : tone === "caution" ? "bg-amber-400" : tone === "neutral" ? "bg-ink-400" : "bg-green-500";
  return (
    <span role={label ? "img" : undefined} aria-label={label} aria-hidden={label ? undefined : true}
      className="block h-2 w-full overflow-hidden rounded-full bg-sand-100">
      <GrowBar pct={pct} className={fill} delay={delay} />
    </span>
  );
}

const ARRIVE = { tr: motion.tr, li: motion.li, div: motion.div, span: motion.span };

/** One row of a list that arrives in order when it appears: it rises 6px and fades in, 45 ms after the row before;
 *  every row after the twelfth comes with the twelfth (arriveDelay), so a long table is not still arriving later. */
export function Arrive({ index, as = "div", className = "", children, ...rest }:
  { index: number; as?: keyof typeof ARRIVE; className?: string; children: ReactNode; id?: string; role?: string }) {
  const Tag = ARRIVE[as];
  return (
    <Tag className={className} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.28, delay: arriveDelay(index), ease: EASE }} {...rest}>
      {children}
    </Tag>
  );
}

/** A chip or mark arriving in order down a list: a short fade, after the one above it. */
export function ArriveChip({ index, children }: { index: number; children: ReactNode }) {
  return (
    <motion.span className="inline-flex" initial={{ opacity: 0, y: 3 }} animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.24, delay: 0.12 + arriveDelay(index), ease: EASE }}>
      {children}
    </motion.span>
  );
}

/** A decision that just went through: a filled circle whose check draws itself, then what was recorded. Green for a
 *  decision that changed something, ink for one that was kept (a rejection, a pause). */
export function Confirmed({ tone = "gain", children, className = "" }: { tone?: "gain" | "neutral"; children: ReactNode; className?: string }) {
  return (
    <motion.span initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.18 }}
      className={`inline-flex items-center gap-2 text-sm font-semibold ${tone === "gain" ? "text-green-700" : "text-ink-700"} ${className}`}>
      <CheckDot tone={tone} />
      <span className="min-w-0">{children}</span>
    </motion.span>
  );
}

/** The 24px circle with a check that draws itself. */
export function CheckDot({ tone = "gain", size = 24 }: { tone?: "gain" | "neutral" | "loss"; size?: number }) {
  const fill = tone === "gain" ? "bg-green-500" : tone === "loss" ? "bg-coral-500" : "bg-ink-700";
  return (
    <motion.span aria-hidden="true" initial={{ scale: 0.6, opacity: 0 }} animate={{ scale: 1, opacity: 1 }}
      transition={{ duration: 0.22, ease: EASE }} style={{ width: size, height: size }}
      className={`flex shrink-0 items-center justify-center rounded-full text-white ${fill}`}>
      <DrawnCheck size={Math.round(size * 0.55)} />
    </motion.span>
  );
}

/** The 24px coral circle with a cross that draws itself: a request that was turned down. */
export function CrossDot({ size = 24 }: { size?: number }) {
  const s = Math.round(size * 0.5);
  return (
    <motion.span aria-hidden="true" initial={{ scale: 0.6, opacity: 0 }} animate={{ scale: 1, opacity: 1 }}
      transition={{ duration: 0.22, ease: EASE }} style={{ width: size, height: size }}
      className="flex shrink-0 items-center justify-center rounded-full bg-coral-500 text-white">
      <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round">
        <motion.path d="M18 6 6 18M6 6l12 12" initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 0.4, ease: EASE }} />
      </svg>
    </motion.span>
  );
}

/** The notice after a decision went through: the success notice's place and voice, with the check drawing itself
 *  where its dot would be. */
export function ConfirmedNotice({ tone = "gain", title, children }: { tone?: "gain" | "neutral"; title: string; children?: ReactNode }) {
  return (
    <motion.div role="status" initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.24, ease: EASE }}
      className={`flex gap-3 rounded-panel px-5 py-4 text-sm ${tone === "gain" ? "bg-green-50" : "bg-fill"}`}>
      <CheckDot tone={tone} size={22} />
      <div className="min-w-0 pt-px">
        <p className="font-semibold text-ink-900">{title}</p>
        {children && <div className="text-ink-700">{children}</div>}
      </div>
    </motion.div>
  );
}

/** A card in a queue: it arrives in order with the cards around it, and once it is decided it fades and its height
 *  closes, so the cards below move up smoothly. Put each one directly in an AnimatePresence, in a list with "-mb-4"
 *  (or its own gap's negative): the gap below a card is its own padding, so the gap closes with it. Four pixels of
 *  room on every other side keep a focus ring from being clipped while the card closes. */
export function QueueItem({ index, children, gap = "pb-4", as = "div" }:
  { index: number; children: ReactNode; gap?: string; as?: "div" | "li" }) {
  const close = { duration: 0.3, delay: 0.08, ease: EASE };
  const Tag = as === "li" ? motion.li : motion.div;
  return (
    <Tag className="-mx-1 -mt-1 overflow-hidden px-1 pt-1" initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.28, delay: arriveDelay(index), ease: EASE }}
      exit={{ opacity: 0, height: 0, paddingTop: 0, marginTop: 0,
        transition: { opacity: { duration: 0.16 }, height: close, paddingTop: close, marginTop: close } }}>
      <div className={gap}>{children}</div>
    </Tag>
  );
}
