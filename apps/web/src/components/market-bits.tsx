"use client";

import { motion } from "motion/react";
import type { Session } from "@/lib/markets";

export function SessionDot({ session }: { session: Session }) {
  return (
    <span className="inline-flex items-center gap-2 text-sm text-ink-2">
      <span aria-hidden="true" className={`h-2 w-2 rounded-full ${session.is_open ? "bg-gain" : "bg-line-strong"}`} />
      US market: {session.label}
    </span>
  );
}

/** A star that adds a symbol to the watchlist or takes it off. It answers the press with a small give. */
export function WatchButton({ symbol, watched, onToggle, withLabel = false }:
  { symbol: string; watched: boolean; onToggle: () => void; withLabel?: boolean }) {
  return (
    <motion.button type="button" onClick={onToggle} aria-pressed={watched} whileTap={{ scale: 0.86 }}
      aria-label={withLabel ? undefined : watched ? `Remove ${symbol} from your watchlist` : `Add ${symbol} to your watchlist`}
      className={withLabel
        ? "inline-flex items-center gap-2 rounded-control border border-line-strong bg-surface px-3.5 py-2 text-sm font-medium hover:border-ink"
        : "grid h-8 w-8 place-items-center rounded-control text-muted hover:text-ink"}>
      <svg viewBox="0 0 16 16" className={`h-4 w-4 ${watched ? "text-ink" : ""}`} aria-hidden="true">
        <path d="M8 1.8l1.9 3.9 4.3.6-3.1 3 .7 4.3L8 11.6l-3.8 2 .7-4.3-3.1-3 4.3-.6z" fill={watched ? "currentColor" : "none"}
          stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round" />
      </svg>
      {withLabel && (watched ? "On your watchlist" : "Add to watchlist")}
    </motion.button>
  );
}
