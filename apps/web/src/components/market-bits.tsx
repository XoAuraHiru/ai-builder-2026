"use client";

import { motion } from "motion/react";
import { sessionChip, type Session } from "@/lib/markets";
import { Badge } from "@/components/ui";

/** The market's state as a status chip: green while open, neutral while closed, always with the next time. */
export function SessionChip({ session }: { session: Session }) {
  const chip = sessionChip(session);
  return <Badge tone={chip.open ? "gain" : "neutral"}>{chip.text}</Badge>;
}

/** A ticker as a small tile in Geist Mono: sand for shares and cash, tonal green for ETFs and funds. Inside a row that
 *  highlights in fill (`group`), a sand tile turns white so it stays visible. */
export function TickerTile({ symbol, tone = "stock", size = "md" }:
  { symbol: string; tone?: "stock" | "etf" | "fund" | "cash"; size?: "md" | "sm" }) {
  const box = size === "md" ? "h-8 w-11 text-[11px]" : "h-7 w-10 text-[10px]";
  const color = tone === "etf" || tone === "fund" ? "bg-green-50 text-green-700"
    : "bg-fill text-ink-900 group-hover:bg-white group-focus-within:bg-white";
  return (
    <span aria-hidden="true" className={`code flex shrink-0 items-center justify-center rounded-tile font-medium tracking-normal ${box} ${color}`}>
      {symbol}
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
        ? "inline-flex min-h-11 items-center gap-2 whitespace-nowrap rounded-full border border-sand-200 bg-white px-5 text-sm font-medium text-ink-900 hover:bg-fill"
        : "grid h-8 w-8 place-items-center rounded-full text-ink-400 hover:bg-sand-100 hover:text-ink-700"}>
      <svg viewBox="0 0 16 16" className={`h-4 w-4 ${watched ? "text-amber-400" : ""}`} aria-hidden="true">
        <path d="M8 1.8l1.9 3.9 4.3.6-3.1 3 .7 4.3L8 11.6l-3.8 2 .7-4.3-3.1-3 4.3-.6z" fill={watched ? "currentColor" : "none"}
          stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round" />
      </svg>
      {withLabel && (watched ? "On your watchlist" : "Add to watchlist")}
    </motion.button>
  );
}
