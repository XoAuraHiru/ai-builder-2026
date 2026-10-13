"use client";

/** What a form or a decision says back: a field's error easing open under it, and a confirmation whose check draws
 *  itself once the thing went through. Used by the public forms and the advisor's decisions. */

import { AnimatePresence, motion } from "motion/react";
import type { ReactNode } from "react";
import { DrawnCheck, EASE } from "@/components/motion";

/** A field's error, opening under the field (the fields below move down smoothly rather than jump) and closing again
 *  once it is fixed. Put it inside the Field, after the input, in place of Field's own `error`. */
export function FieldError({ message }: { message?: string }) {
  return (
    <AnimatePresence initial={false}>
      {message && (
        <motion.span key="error" className="block overflow-hidden" initial={{ height: 0, opacity: 0 }}
          animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} transition={{ duration: 0.22, ease: EASE }}>
          <span role="alert" className="block pt-1.5 text-[13px] text-coral-700">{message}</span>
        </motion.span>
      )}
    </AnimatePresence>
  );
}

/** A decision or a submission that went through: green, a check drawing itself in a white disc, and what happened. */
export function Confirmed({ title, children, action, className = "" }:
  { title: string; children?: ReactNode; action?: ReactNode; className?: string }) {
  return (
    <motion.div role="status" initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.24, ease: EASE }}
      className={`flex flex-wrap items-start justify-between gap-3 rounded-panel bg-green-50 px-5 py-4 text-sm ${className}`}>
      <div className="flex min-w-0 flex-1 gap-3">
        <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-white text-green-600">
          <DrawnCheck size={16} />
        </span>
        <div className="min-w-0 pt-[3px]">
          <p className="font-semibold text-ink-900">{title}</p>
          {children && <div className="mt-0.5 text-ink-700">{children}</div>}
        </div>
      </div>
      {action}
    </motion.div>
  );
}

/** A short confirmation on one line, for a row that just changed (an update applied, an order decided). */
export function ConfirmedLine({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <motion.span initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.2 }}
      className={`inline-flex items-center gap-1.5 text-xs font-medium text-green-700 ${className}`}>
      <DrawnCheck size={14} className="shrink-0" />
      <span>{children}</span>
    </motion.span>
  );
}
