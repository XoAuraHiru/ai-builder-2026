"use client";

import { AnimatePresence, motion } from "motion/react";
import { useId, useState } from "react";

export type Evidence = { label: string; detail: string };

/** The explain-everything primitive. Opening it lets the light in: a daylight rule draws down beside the evidence. */
export function WhyPanel({ title, evidence, confidence, model }:
  { title: string; evidence: Evidence[]; confidence?: number; model?: string }) {
  const [open, setOpen] = useState(false);
  const id = useId();
  return (
    <div className="rounded-panel border border-line bg-surface">
      <button type="button" aria-expanded={open} aria-controls={id} onClick={() => setOpen(!open)}
        className="flex w-full items-center justify-between gap-4 rounded-panel px-4 py-3 text-left text-sm hover:bg-ground/60">
        <span><span className="font-semibold">Why:</span> <span className="text-ink-2">{title}</span></span>
        <span className="flex shrink-0 items-center gap-3 text-xs text-muted">
          {confidence !== undefined && <span className="num">Confidence {Math.round(confidence * 100)}%</span>}
          <motion.svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true" animate={{ rotate: open ? 180 : 0 }}>
            <path d="M2 4.5 6 8l4-3.5" fill="none" stroke="currentColor" strokeWidth="1.5" />
          </motion.svg>
        </span>
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div id={id} key="body" initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }} className="overflow-hidden">
            <div className="relative border-t border-line py-3 pl-7 pr-4">
              <motion.span aria-hidden="true" className="absolute bottom-3 left-4 top-3 w-[2px] origin-top rounded-full bg-daylight"
                initial={{ scaleY: 0 }} animate={{ scaleY: 1 }} transition={{ duration: 0.5, delay: 0.05 }} />
              <dl className="space-y-2.5 text-sm">
                {evidence.map((e, i) => (
                  <div key={`${e.label}-${i}`}>
                    <dt className="font-medium text-ink">{e.label}</dt>
                    <dd className="text-ink-2">{e.detail}</dd>
                  </div>
                ))}
              </dl>
              {model && <p className="mt-3 text-xs text-muted">Source: {model}. Illustrative, not advice.</p>}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
