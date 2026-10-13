"use client";

/** While Gemini works: the violet panel its answer will fill, a breathing sparkle, what it is doing now, and how long
 *  this usually takes. Steps advance on a timer and stop at the last one (they never loop back and pretend to start
 *  over); the elapsed seconds keep counting, so a slow answer still looks alive and honest. */

import { AnimatePresence, motion } from "motion/react";
import { useEffect, useState } from "react";
import { Sparkle } from "@/components/ui";

export function AiThinking({ steps, usually, compact = false }:
  { steps: string[]; usually?: string; compact?: boolean }) {
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    const started = Date.now();
    const timer = window.setInterval(() => setElapsed(Math.floor((Date.now() - started) / 1000)), 1000);
    return () => window.clearInterval(timer);
  }, []);
  const at = Math.min(steps.length - 1, Math.floor(elapsed / 4));
  const step = steps[at] ?? "Gemini is working";

  return (
    <motion.figure role="status" aria-live="polite" initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.28 }}
      className={`flex max-w-[860px] flex-col rounded-[16px] bg-ai-50 ${compact ? "gap-3 px-5 py-4" : "gap-4 px-6 py-[22px]"}`}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <span className="inline-flex items-center gap-2 text-[13px] font-semibold text-ai-700">
          <motion.span className="inline-flex" animate={{ scale: [0.85, 1.1, 0.85], opacity: [0.55, 1, 0.55] }}
            transition={{ duration: 1.8, repeat: Infinity, ease: "easeInOut" }}>
            <Sparkle />
          </motion.span>
          <span className="relative block overflow-hidden">
            <AnimatePresence mode="wait" initial={false}>
              <motion.span key={step} className="block" initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -6 }} transition={{ duration: 0.2 }}>
                {step}
              </motion.span>
            </AnimatePresence>
          </span>
        </span>
        <span className="code text-[11px] text-ai-700">
          {elapsed}s{usually ? <span className="hidden sm:inline"> · usually {usually}</span> : null}
        </span>
      </div>
      {!compact && (
        <span aria-hidden="true" className="flex flex-col gap-2.5">
          <span className="skeleton-ai block h-3.5 w-full rounded-[8px]" />
          <span className="skeleton-ai block h-3.5 w-[92%] rounded-[8px]" />
          <span className="skeleton-ai block h-3.5 w-3/5 rounded-[8px]" />
        </span>
      )}
    </motion.figure>
  );
}
