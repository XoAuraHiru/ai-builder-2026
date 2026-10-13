/** The loading shapes several investor pages share, built from the skeleton primitives. Each page composes its own
 *  skeleton from these so the page that arrives sits where its shape was. A Next private folder: not a route. */

import type { ReactNode } from "react";
import { Skeleton } from "@/components/skeleton";

/** A region that is loading: announced once by its label, its shapes hidden from screen readers. Focus never moves. */
export function LoadingRegion({ label, className = "", children }: { label: string; className?: string; children: ReactNode }) {
  return (
    <div role="status" aria-live="polite">
      <span className="sr-only">{label}…</span>
      <div aria-hidden="true" className={className}>{children}</div>
    </div>
  );
}

/** The five risk bands as the scale draws them: a chip row, five bars and the band names. */
export function ScaleSkeleton() {
  const five = [0, 1, 2, 3, 4];
  return (
    <div className="grid grid-cols-5 gap-x-1.5 gap-y-2">
      {five.map((i) => (
        <span key={`chip-${i}`} className="flex min-h-6.5 items-end">
          {(i === 2 || i === 3) && <Skeleton className="h-6.5 w-24 max-w-full rounded-[13px]" />}
        </span>
      ))}
      {five.map((i) => <Skeleton key={`bar-${i}`} className="h-3 rounded-md" />)}
      {five.map((i) => <Skeleton key={`name-${i}`} className="h-3 w-3/5" />)}
    </div>
  );
}

/** A page's opening card (KeyMoment): the chip, a two-line title, what goes under it and its buttons. */
export function MomentSkeleton({ children, actions = 0 }: { children?: ReactNode; actions?: number }) {
  return (
    <div className="flex flex-col gap-6 rounded-panel border border-sand-200 bg-white p-6 sm:p-7">
      <Skeleton className="h-7 w-52 rounded-full" />
      <span className="flex flex-col gap-2.5">
        <Skeleton className="h-7 w-[min(560px,95%)] rounded-[10px] sm:h-8" />
        <Skeleton className="h-7 w-[min(320px,65%)] rounded-[10px] sm:h-8" />
      </span>
      {children && <div className="space-y-5">{children}</div>}
      {actions > 0 && (
        <div className="flex flex-wrap gap-2">
          {Array.from({ length: actions }, (_, i) => <Skeleton key={i} className={`h-11 rounded-full ${i === 0 ? "w-56" : "w-44"}`} />)}
        </div>
      )}
    </div>
  );
}

/** A Section's title, and its line of description. */
export function SectionTitleSkeleton({ description = true }: { description?: boolean }) {
  return (
    <div className="mb-4 flex flex-col gap-2 px-1">
      <Skeleton className="h-5 w-44 rounded-[8px]" />
      {description && <Skeleton className="h-3 w-[min(460px,85%)]" />}
    </div>
  );
}

/** An engine figure: its label, the figure and a caption. */
export function FigureSkeleton({ size = "md" }: { size?: "md" | "lg" }) {
  return (
    <div className="flex flex-col gap-2">
      <Skeleton className="h-3.5 w-24" />
      <Skeleton className={size === "lg" ? "h-12 w-[min(300px,80%)] rounded-[12px] sm:h-[60px]" : "h-[34px] w-32 rounded-[10px]"} />
      <Skeleton className="h-3 w-[min(200px,70%)]" />
    </div>
  );
}

/** Named bars with a figure at the end (Home's "Where your money sits"). */
export function BarRowsSkeleton({ rows = 4 }: { rows?: number }) {
  return (
    <div className="flex flex-col gap-3">
      {Array.from({ length: rows }, (_, i) => (
        <span key={i} className="grid grid-cols-[minmax(0,120px)_minmax(0,1fr)_48px] items-center gap-3">
          <Skeleton className="h-3 w-4/5" />
          <Skeleton className="h-2 rounded-[4px]" />
          <Skeleton className="ml-auto h-3 w-9" />
        </span>
      ))}
    </div>
  );
}

/** A list row of the kind Trades and the funds list use: a ticker tile, a name over a caption, figures at the end. */
export function TileRowSkeleton({ end = 2 }: { end?: number }) {
  return (
    <div className="flex items-center justify-between gap-3 py-3.5">
      <span className="flex min-w-0 flex-1 items-center gap-3">
        <Skeleton className="h-8 w-11 shrink-0 rounded-tile" />
        <span className="flex min-w-0 flex-1 flex-col gap-2">
          <Skeleton className="h-3.5 w-[min(260px,80%)]" />
          <Skeleton className="h-3 w-[min(180px,60%)]" />
        </span>
      </span>
      <span className="flex shrink-0 items-center gap-3">
        {Array.from({ length: end }, (_, i) => <Skeleton key={i} className={i === end - 1 ? "h-7 w-20 rounded-full" : "h-3.5 w-16"} />)}
      </span>
    </div>
  );
}

/** Lines in Gemini's violet, for a panel whose words are Gemini's (Home's Ask Atrium). */
export function AiLinesSkeleton({ lines = 2 }: { lines?: number }) {
  return (
    <span className="flex flex-col gap-2">
      {Array.from({ length: lines }, (_, i) => <span key={i} className="skeleton-ai block h-11 rounded-control" />)}
    </span>
  );
}
