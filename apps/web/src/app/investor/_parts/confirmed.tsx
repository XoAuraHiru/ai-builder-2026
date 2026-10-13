"use client";

import { motion } from "motion/react";
import type { ReactNode } from "react";
import { DrawnCheck, EASE } from "@/components/motion";

type Tone = "success" | "caution" | "info";
const TONE: Record<Tone, { box: string; check: string }> = {
  success: { box: "bg-green-50", check: "text-green-600" },
  caution: { box: "bg-amber-50", check: "text-amber-800" },
  info: { box: "bg-fill", check: "text-ink-700" },
};

/** A decision that just went through (an order placed or sent to an advisor, an instruction accepted, a profile
 *  saved): the Notice's shape, with a check that draws itself in place of the dot. A polite status; focus stays put. */
export function Confirmed({ tone = "success", title, action, children }:
  { tone?: Tone; title?: string; action?: ReactNode; children?: ReactNode }) {
  return (
    <motion.div role="status" initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.24, ease: EASE }}
      className={`flex flex-wrap items-start justify-between gap-3 rounded-panel px-5 py-4 text-sm ${TONE[tone].box}`}>
      <div className="flex min-w-0 flex-1 gap-2.5">
        <DrawnCheck size={18} className={`mt-px shrink-0 ${TONE[tone].check}`} />
        <div className="min-w-0">
          {title && <p className="font-semibold text-ink-900">{title}</p>}
          {children && <div className="text-ink-700">{children}</div>}
        </div>
      </div>
      {action}
    </motion.div>
  );
}
