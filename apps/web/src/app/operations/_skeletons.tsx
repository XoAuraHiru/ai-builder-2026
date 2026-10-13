/** Loading shapes for the operations and compliance desks, built from components/skeleton.tsx: each page's skeleton is
 *  laid out like the page it becomes (its stat cards, its opening card, its tables and cards), so nothing jumps when
 *  the data arrives. A region is one status for screen readers, announced by its label; the shapes are hidden. */

import type { ReactNode } from "react";
import { Skeleton, SkeletonText } from "@/components/skeleton";

export function LoadingRegion({ label, children, className = "" }: { label: string; children: ReactNode; className?: string }) {
  return (
    <div role="status" aria-live="polite" className={className}>
      <span className="sr-only">{label}…</span>
      <div aria-hidden="true">{children}</div>
    </div>
  );
}

const CARD = "rounded-panel border border-sand-200 bg-white";

/** The stat cards' row, as the desks lay it out: two across on a phone, four on a wide screen. */
export function StatsSkeleton({ count = 4, className = "" }: { count?: number; className?: string }) {
  return (
    <div className={`grid grid-cols-2 gap-3 sm:gap-4 xl:grid-cols-4 ${className}`}>
      {Array.from({ length: count }, (_, i) => (
        <div key={i} className={`flex min-w-0 flex-col gap-3.5 p-[18px] ${CARD}`}>
          <span className="flex items-center gap-2"><Skeleton className="h-7 w-7 shrink-0 rounded-tile" /><Skeleton className="h-3.5 w-3/5" /></span>
          <Skeleton className="h-9 w-16 rounded-[10px]" />
          <Skeleton className="h-3 w-4/5" />
        </div>
      ))}
    </div>
  );
}

/** A section's title and its line of description. */
export function SectionTitleSkeleton({ width = "w-56" }: { width?: string }) {
  return (
    <div className="mb-4 flex flex-col gap-2 px-1">
      <Skeleton className={`h-6 max-w-full rounded-[8px] ${width}`} />
      <Skeleton className="h-3 w-[min(420px,85%)]" />
    </div>
  );
}

/** The card a page opens with: its label chip, a sentence in two lines, then what the page puts under it. */
export function MomentSkeleton({ children, actions = 0 }: { children?: ReactNode; actions?: number }) {
  return (
    <div className={`flex flex-col gap-6 p-6 sm:p-7 ${CARD}`}>
      <Skeleton className="h-7 w-36 rounded-full" />
      <span className="flex max-w-[620px] flex-col gap-2.5">
        <Skeleton className="h-7 w-full rounded-[10px] sm:h-8" />
        <Skeleton className="h-7 w-3/5 rounded-[10px] sm:h-8" />
      </span>
      {children}
      {actions > 0 && (
        <span className="flex flex-wrap gap-2">
          {Array.from({ length: actions }, (_, i) => <Skeleton key={i} className={`h-11 rounded-full ${i === 0 ? "w-44" : "w-36"}`} />)}
        </span>
      )}
    </div>
  );
}

/** A row of status chips. */
export function ChipsSkeleton({ count = 3 }: { count?: number }) {
  return (
    <span className="flex flex-wrap gap-2">
      {Array.from({ length: count }, (_, i) => <Skeleton key={i} className={`h-[26px] rounded-full ${i % 2 ? "w-20" : "w-28"}`} />)}
    </span>
  );
}

/** A table card: its title and description, header cells and rows on hairlines. `widths` sets each column's share;
 *  `tile` puts a fund tile in the first column (or the column it names), and `chip` a status chip in the last. On a
 *  phone the rows become the stacked list the desks show there. */
export function TableCardSkeleton({ rows = 6, widths = [2, 1, 1, 1], tile = false, title = true, chip = false }:
  { rows?: number; widths?: number[]; tile?: boolean | number; title?: boolean; chip?: boolean }) {
  const columns = { gridTemplateColumns: widths.map((w) => `${w}fr`).join(" ") };
  const tileCol = tile === true ? 0 : tile === false ? -1 : tile;
  const lead = (withTile: boolean) => (
    <span className="flex items-center gap-2.5">
      {withTile && <Skeleton className="h-7 w-11 shrink-0 rounded-tile" />}
      <span className="flex min-w-0 flex-1 flex-col gap-1.5"><Skeleton className="h-3.5 w-4/5" /><Skeleton className="h-2.5 w-2/5" /></span>
    </span>
  );
  return (
    <div className={`p-5 sm:p-6 ${CARD}`}>
      {title && (
        <div className="mb-4 flex flex-col gap-2">
          <Skeleton className="h-4 w-40" />
          <Skeleton className="h-3 w-[min(360px,80%)]" />
        </div>
      )}
      <div className="hidden md:block">
        <div className="grid gap-4 border-b border-sand-100 pb-3" style={columns}>
          {widths.map((_, i) => <Skeleton key={i} className="h-3 w-1/2" />)}
        </div>
        {Array.from({ length: rows }, (_, r) => (
          <div key={r} className="grid items-center gap-4 border-b border-sand-100 py-3.5 last:border-b-0" style={columns}>
            {widths.map((_, c) => (
              c === 0 || c === tileCol ? <span key={c}>{lead(c === tileCol)}</span>
                : c === widths.length - 1 && chip ? <Skeleton key={c} className="h-[26px] w-24 rounded-full" />
                  : <Skeleton key={c} className={`h-3.5 ${c % 2 ? "w-3/4" : "w-1/2"}`} />
            ))}
          </div>
        ))}
      </div>
      <div className="divide-y divide-sand-100 md:hidden">
        {Array.from({ length: Math.min(rows, 5) }, (_, r) => (
          <div key={r} className="flex items-start gap-3 py-3.5">
            {tileCol >= 0 && <Skeleton className="h-7 w-11 shrink-0 rounded-tile" />}
            <span className="flex min-w-0 flex-1 flex-col gap-2">
              <span className="flex justify-between gap-3"><Skeleton className="h-3.5 w-2/5" /><Skeleton className="h-3.5 w-16" /></span>
              <Skeleton className="h-3 w-4/5" />
              {chip && <Skeleton className="h-[26px] w-24 rounded-full" />}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

/** An outlined card of a few lines, with an optional title bar and chip. */
export function CardSkeleton({ lines = 3, chip = false, className = "" }: { lines?: number; chip?: boolean; className?: string }) {
  return (
    <div className={`flex min-w-0 flex-col gap-4 p-5 sm:p-6 ${CARD} ${className}`}>
      <span className="flex items-center justify-between gap-3">
        <Skeleton className="h-4 w-2/5" />
        {chip && <Skeleton className="h-[26px] w-24 rounded-full" />}
      </span>
      <SkeletonText lines={lines} />
    </div>
  );
}

/** The page header of a detail page: the way back, the title and a line of description. */
export function DetailHeaderSkeleton({ badges = 2 }: { badges?: number }) {
  return (
    <div className="mb-8 flex flex-wrap items-end justify-between gap-x-6 gap-y-4">
      <div className="flex min-w-0 max-w-[720px] flex-1 flex-col gap-3">
        <Skeleton className="h-3.5 w-16" />
        <Skeleton className="h-9 w-[min(460px,90%)] rounded-[10px]" />
        <Skeleton className="h-3.5 w-[min(520px,95%)]" />
      </div>
      {badges > 0 && (
        <span className="flex gap-2">{Array.from({ length: badges }, (_, i) => <Skeleton key={i} className="h-7 w-28 rounded-full" />)}</span>
      )}
    </div>
  );
}
