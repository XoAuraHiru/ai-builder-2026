/** Loading skeletons: the shape of what is coming, in sand, with a slow shimmer (none for reduced motion). Each one
 *  is a status for screen readers, announced by its label; the shapes themselves are hidden from them. */

import type { ReactNode } from "react";

export function Skeleton({ className = "" }: { className?: string }) {
  return <span aria-hidden="true" className={`skeleton block rounded-[8px] ${className}`} />;
}

export function SkeletonText({ lines = 3, className = "" }: { lines?: number; className?: string }) {
  return (
    <span aria-hidden="true" className={`flex flex-col gap-2.5 ${className}`}>
      {Array.from({ length: lines }, (_, i) => (
        <Skeleton key={i} className={`h-3.5 ${i === lines - 1 && lines > 1 ? "w-3/5" : "w-full"}`} />
      ))}
    </span>
  );
}

function Status({ label, children, className = "" }: { label: string; children: ReactNode; className?: string }) {
  return (
    <div role="status" aria-live="polite" className={className}>
      <span className="sr-only">{label}…</span>
      {children}
    </div>
  );
}

/** An outlined card: a title bar and a few lines. */
export function SkeletonCard({ lines = 3, figure = false }: { lines?: number; figure?: boolean }) {
  return (
    <div aria-hidden="true" className="flex flex-col gap-4 rounded-panel border border-sand-200 bg-white p-6">
      <Skeleton className="h-4 w-2/5" />
      {figure && <Skeleton className="h-9 w-1/2 rounded-[10px]" />}
      <SkeletonText lines={lines} />
    </div>
  );
}

/** A row of stat cards: an icon tile, a title, a figure and a caption. */
export function SkeletonStats({ count = 4 }: { count?: number }) {
  return (
    <div aria-hidden="true" className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {Array.from({ length: count }, (_, i) => (
        <div key={i} className="flex flex-col gap-3.5 rounded-panel border border-sand-200 bg-white p-[18px]">
          <span className="flex items-center gap-2"><Skeleton className="h-7 w-7" /><Skeleton className="h-3.5 w-24" /></span>
          <Skeleton className="h-8 w-2/3 rounded-[10px]" />
          <Skeleton className="h-3 w-1/2" />
        </div>
      ))}
    </div>
  );
}

/** A table card: header cells and rows on hairlines. */
export function SkeletonTable({ rows = 5, cols = 4 }: { rows?: number; cols?: number }) {
  return (
    <div aria-hidden="true" className="rounded-panel border border-sand-200 bg-white p-6">
      <Skeleton className="mb-5 h-4 w-1/4" />
      <div className="grid gap-4 border-b border-sand-100 pb-3" style={{ gridTemplateColumns: `2fr repeat(${cols - 1}, 1fr)` }}>
        {Array.from({ length: cols }, (_, i) => <Skeleton key={i} className="h-3 w-3/5" />)}
      </div>
      {Array.from({ length: rows }, (_, r) => (
        <div key={r} className="grid items-center gap-4 border-b border-sand-100 py-3.5 last:border-b-0"
          style={{ gridTemplateColumns: `2fr repeat(${cols - 1}, 1fr)` }}>
          <span className="flex items-center gap-3"><Skeleton className="h-7 w-10 shrink-0" /><Skeleton className="h-3.5 w-3/4" /></span>
          {Array.from({ length: cols - 1 }, (_, c) => <Skeleton key={c} className="h-3.5 w-2/3" />)}
        </div>
      ))}
    </div>
  );
}

/** The page header: a title and a line of description. */
export function SkeletonHeader() {
  return (
    <div aria-hidden="true" className="mb-8 flex flex-col gap-3">
      <Skeleton className="h-9 w-64 max-w-full rounded-[10px]" />
      <Skeleton className="h-3.5 w-[min(520px,90%)]" />
    </div>
  );
}

export type PageShape = "dashboard" | "table" | "detail" | "cards";

/** A whole page while its data loads, shaped like the page it will become. */
export function PageSkeleton({ label, shape = "detail", header = true }: { label: string; shape?: PageShape; header?: boolean }) {
  return (
    <Status label={label}>
      {header && <SkeletonHeader />}
      {shape === "dashboard" && (
        <div className="flex flex-col gap-4">
          <SkeletonStats />
          <div className="grid gap-4 xl:grid-cols-[minmax(0,1.75fr)_minmax(0,1fr)]"><SkeletonCard lines={4} figure /><SkeletonCard lines={4} /></div>
        </div>
      )}
      {shape === "table" && <SkeletonTable rows={7} cols={5} />}
      {shape === "detail" && (
        <div className="flex flex-col gap-4"><SkeletonCard lines={3} figure /><SkeletonCard lines={4} /><SkeletonCard lines={2} /></div>
      )}
      {shape === "cards" && (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 6 }, (_, i) => <SkeletonCard key={i} lines={2} figure />)}
        </div>
      )}
    </Status>
  );
}

/** A part of a page while it loads: a card, a table or a few lines. */
export function BlockSkeleton({ label, shape = "card" }: { label: string; shape?: "card" | "table" | "lines" | "stats" }) {
  return (
    <Status label={label}>
      {shape === "card" && <SkeletonCard />}
      {shape === "table" && <SkeletonTable />}
      {shape === "stats" && <SkeletonStats />}
      {shape === "lines" && <SkeletonText lines={3} className="py-2" />}
    </Status>
  );
}
