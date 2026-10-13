"use client";

/** Atrium's motion: quiet, quick and meaningful. Engine figures count up to themselves, bars grow from zero, content
 *  rises a few pixels into place, and lists arrive one row after another. Everything here is calm (160-600 ms,
 *  ease-out, no bounce), runs when the content appears rather than when it is scrolled to (so printing and full-page
 *  captures are always complete), and falls back to the final state for anyone who asks for reduced motion. */

import { animate, motion, useReducedMotion, type TargetAndTransition, type Variants } from "motion/react";
import { useEffect, useLayoutEffect, useMemo, useRef, type ReactNode } from "react";
import { formatLike, parseFigure } from "@/lib/motion-figures";

export const EASE = [0.22, 1, 0.36, 1] as const;

// useLayoutEffect sets the first frame of a count before it is painted; on the server there is nothing to set.
const useIsoLayoutEffect = typeof window === "undefined" ? useEffect : useLayoutEffect;

/** Rises 8px and fades into place when it appears. */
export function Reveal({ children, delay = 0, y = 8, className = "" }:
  { children: ReactNode; delay?: number; y?: number; className?: string }) {
  return (
    <motion.div className={className} initial={{ opacity: 0, y }} animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.32, delay, ease: EASE }}>
      {children}
    </motion.div>
  );
}

const LIST: Variants = { hidden: {}, show: { transition: { staggerChildren: 0.045, delayChildren: 0.04 } } };
const ITEM: Variants = { hidden: { opacity: 0, y: 6 }, show: { opacity: 1, y: 0, transition: { duration: 0.28, ease: EASE } } };
const TAGS = { div: motion.div, ul: motion.ul, ol: motion.ol, li: motion.li, tbody: motion.tbody, tr: motion.tr, section: motion.section };

/** A list whose items arrive one after another, 45 ms apart, when it appears. Pair with StaggerItem; keep it to
 *  lists of a dozen or so items. */
export function Stagger({ children, as = "div", className = "" }:
  { children: ReactNode; as?: keyof typeof TAGS; className?: string }) {
  const Tag = TAGS[as];
  return (
    <Tag className={className} variants={LIST} initial="hidden" animate="show">
      {children}
    </Tag>
  );
}

export function StaggerItem({ children, as = "div", className = "", exit }:
  { children: ReactNode; as?: keyof typeof TAGS; className?: string; exit?: TargetAndTransition }) {
  const Tag = TAGS[as];
  return <Tag className={className} variants={ITEM} exit={exit}>{children}</Tag>;
}

/** An engine figure that counts up to itself ("$45,635.00", "7.78%", "6.2 / 10") when it appears on screen, and from
 *  its old value to its new one when it changes. A figure that appears off screen simply shows its value. Its final
 *  width is reserved, so nothing around it moves, and screen readers hear only the final figure. Text that is not one
 *  figure is shown as it is. */
export function CountUp({ text, duration = 0.9, className = "" }: { text: string; duration?: number; className?: string }) {
  const spec = useMemo(() => parseFigure(text), [text]);
  const reduce = useReducedMotion();
  const node = useRef<HTMLSpanElement>(null);
  const from = useRef<number | null>(null);

  useIsoLayoutEffect(() => {
    const el = node.current;
    if (!spec || !el) return;
    const first = from.current === null;
    const box = el.getBoundingClientRect();
    const onScreen = box.bottom > 0 && box.top < window.innerHeight;
    if (reduce || (first && !onScreen)) {
      el.textContent = text;
      from.current = spec.value;
      return;
    }
    if (first) el.textContent = formatLike(0, spec);
    const controls = animate(from.current ?? 0, spec.value, {
      duration: from.current === null ? duration : Math.min(duration, 0.5), ease: EASE,
      onUpdate: (v) => { el.textContent = formatLike(v, spec); },
      onComplete: () => { el.textContent = text; },
    });
    from.current = spec.value;
    return () => controls.stop();
  }, [spec, text, reduce, duration]);

  if (!spec) return <span className={className}>{text}</span>;
  return (
    <span className={`relative inline-grid ${className}`}>
      <span aria-hidden="true" className="invisible col-start-1 row-start-1">{text}</span>
      <span aria-hidden="true" ref={node} className="col-start-1 row-start-1">{text}</span>
      <span className="sr-only">{text}</span>
    </span>
  );
}

/** The fill of a bar, growing from nothing to its share when it appears. The caller draws the track. */
export function GrowBar({ pct, className = "", delay = 0 }: { pct: number; className?: string; delay?: number }) {
  const width = `${Math.max(0, Math.min(100, pct))}%`;
  const reduce = useReducedMotion();
  return (
    <motion.span aria-hidden="true" className={`block h-full rounded-[inherit] ${className}`} initial={reduce ? false : { width: 0 }}
      animate={{ width }} transition={{ duration: 0.6, delay, ease: EASE }} />
  );
}

/** Segments that fill one after another (a meter, a score, a risk scale), each in its own colour. */
export function FillSegments({ fills, className = "", segment = "h-4 flex-1 rounded-[4px]", empty = "bg-sand-100" }:
  { fills: (string | null)[]; className?: string; segment?: string; empty?: string }) {
  return (
    <span aria-hidden="true" className={`flex gap-[3px] ${className}`}>
      {fills.map((fill, i) => (
        <span key={i} className={`relative overflow-hidden ${segment} ${empty}`}>
          {fill && (
            <motion.span className={`absolute inset-0 ${fill}`} initial={{ opacity: 0, scaleY: 0.4 }}
              animate={{ opacity: 1, scaleY: 1 }} transition={{ duration: 0.22, delay: 0.03 * i, ease: EASE }} />
          )}
        </span>
      ))}
    </span>
  );
}

/** The page entering after a route change: a short fade and a 6px rise. */
export function PageEnter({ id, children }: { id: string; children: ReactNode }) {
  return (
    <motion.div key={id} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.28, ease: EASE }}>
      {children}
    </motion.div>
  );
}

/** A check that draws itself, for a decision that just went through (approved, matched, applied). */
export function DrawnCheck({ size = 20, className = "" }: { size?: number; className?: string }) {
  const reduce = useReducedMotion();
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.6"
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className={className}>
      <motion.path d="M20 6 9 17l-5-5" initial={reduce ? false : { pathLength: 0 }} animate={{ pathLength: 1 }}
        transition={{ duration: 0.4, ease: EASE }} />
    </svg>
  );
}
