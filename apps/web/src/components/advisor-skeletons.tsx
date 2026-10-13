/** The advisor's pages while they load, each shaped like the page it becomes: the leads list (its opening card and lead
 *  rows), a lead (its header, the Lead Score and Trust Score cards with the 20-segment meter, the profile and the
 *  sections), the printable proposal, and the held orders (their hold banners). Built from the skeleton primitives;
 *  each is one status for screen readers, announced by its label. */

import type { ReactNode } from "react";
import { Skeleton, SkeletonText } from "@/components/skeleton";
import { TRUST_SEGMENTS } from "@/lib/leads";

/** The lead row's columns, shared by the list and its skeleton so the two line up. */
export const LEAD_ROW = "md:grid md:grid-cols-[minmax(0,2.2fr)_110px_minmax(170px,1.3fr)_120px] md:items-center md:gap-6";

function Loading({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div role="status" aria-live="polite">
      <span className="sr-only">{label}…</span>
      <div aria-hidden="true">{children}</div>
    </div>
  );
}

const Chip = ({ className = "w-20" }: { className?: string }) => <Skeleton className={`h-7 rounded-full ${className}`} />;

/** The page header: a title, a line or two of description, and the action on the right. */
function Header({ title = "w-48", lines = 1, back = false, action }: { title?: string; lines?: number; back?: boolean; action?: ReactNode }) {
  return (
    <div className="mb-8 flex flex-wrap items-end justify-between gap-x-6 gap-y-4">
      <div className="flex w-[min(720px,100%)] min-w-0 flex-col gap-3">
        {back && <Skeleton className="mb-1 h-3.5 w-14" />}
        <Skeleton className={`h-9 max-w-full rounded-[10px] ${title}`} />
        <Skeleton className="h-3.5 w-[min(560px,92%)]" />
        {lines > 1 && <Skeleton className="h-3.5 w-[min(300px,60%)]" />}
      </div>
      {action}
    </div>
  );
}

function Card({ className = "", children }: { className?: string; children: ReactNode }) {
  return <div className={`rounded-panel border border-sand-200 bg-white p-5 sm:p-6 ${className}`}>{children}</div>;
}

/** The 20-segment meter, empty. */
function Meter({ small = false }: { small?: boolean }) {
  return (
    <span className={`flex w-full ${small ? "gap-[2px]" : "gap-[3px]"}`}>
      {Array.from({ length: TRUST_SEGMENTS }, (_, i) => (
        <Skeleton key={i} className={`flex-1 ${small ? "h-2 rounded-[2px]!" : "h-4 rounded-[4px]!"}`} />
      ))}
    </span>
  );
}

/** A Trust Score card: who (or its title), the band chip, the score, the meter and its signal rows. */
export function TrustCardSkeleton({ person = false, signals = 3, footer = false }: { person?: boolean; signals?: number; footer?: boolean }) {
  return (
    <Card className="flex flex-col gap-[18px]">
      <div className="flex items-start justify-between gap-3">
        {person ? (
          <span className="flex min-w-0 flex-1 items-center gap-3">
            <Skeleton className="h-10 w-10 shrink-0 rounded-full" />
            <span className="flex min-w-0 flex-1 flex-col gap-1.5"><Skeleton className="h-3.5 w-28" /><Skeleton className="h-3 w-36 max-w-full" /></span>
          </span>
        ) : <Skeleton className="mt-1 h-4 w-28" />}
        <Chip />
      </div>
      <div className="flex flex-col gap-2">
        <span className="flex items-baseline gap-2"><Skeleton className="h-9 w-14 rounded-[10px]" /><Skeleton className="h-3 w-16" /></span>
        <Meter />
      </div>
      <div>
        {Array.from({ length: signals }, (_, i) => (
          <span key={i} className="flex justify-between gap-3 border-t border-sand-100 py-3">
            <Skeleton className={`h-3.5 ${["w-3/5", "w-1/2", "w-2/3", "w-2/5"][i % 4]}`} /><Skeleton className="h-3.5 w-8" />
          </span>
        ))}
      </div>
      {footer && <Skeleton className="h-[62px] w-full rounded-control" />}
    </Card>
  );
}

function LeadScoreSkeleton() {
  return (
    <Card className="flex flex-col gap-[18px]">
      <div className="flex items-start justify-between gap-3">
        <span className="flex items-center gap-2"><Skeleton className="h-7 w-7 rounded-tile" /><Skeleton className="h-4 w-24" /></span>
        <Chip className="w-24" />
      </div>
      <div className="flex flex-col gap-2">
        <span className="flex items-baseline gap-2"><Skeleton className="h-9 w-14 rounded-[10px]" /><Skeleton className="h-3 w-10" /></span>
        <Skeleton className="h-3 w-52 max-w-full" />
      </div>
      <Skeleton className="h-11 w-full rounded-control" />
    </Card>
  );
}

/** A lead row: the avatar and three lines, the Lead Score, the Trust Score chip over its meter, and the amount. */
function LeadRowSkeleton({ i }: { i: number }) {
  return (
    <div className={`${LEAD_ROW} flex flex-col gap-3 border-t border-sand-100 px-5 py-4 first:border-t-0 sm:px-6`}>
      <span className="flex min-w-0 items-center gap-3">
        <Skeleton className="h-9 w-9 shrink-0 rounded-full" />
        <span className="flex min-w-0 flex-1 flex-col gap-1.5">
          <Skeleton className={`h-3.5 ${["w-32", "w-28", "w-36"][i % 3]}`} />
          <Skeleton className="h-3 w-52 max-w-full" />
          <Skeleton className={`h-3 max-w-full ${["w-64", "w-48", "w-56"][i % 3]}`} />
        </span>
      </span>
      <span className="flex flex-wrap items-center gap-x-5 gap-y-3 md:contents">
        <span className="order-1 md:order-none"><Skeleton className="h-7 w-14 rounded-[8px]" /></span>
        <span className="order-3 flex basis-full flex-col gap-2 md:order-none md:basis-auto">
          <span className="flex items-center gap-2"><Chip /><Skeleton className="h-3 w-12" /></span>
          <span className="block w-full md:max-w-[240px]"><Meter small /></span>
        </span>
        <span className="order-2 ml-auto flex flex-col items-end gap-1.5 md:order-none md:ml-0">
          <Skeleton className="h-3.5 w-20" /><Skeleton className="h-3 w-12" />
        </span>
      </span>
    </div>
  );
}

function SectionHead() {
  return (
    <div className="mb-4 flex flex-col gap-2 px-1">
      <Skeleton className="h-5 w-36 rounded-[8px]" />
      <Skeleton className="h-3 w-[min(440px,85%)]" />
    </div>
  );
}

/** The leads list: its header and scoring action, the opening card with the leads to look at first, and the rows. */
export function LeadsSkeleton({ label = "Loading the leads" }: { label?: string }) {
  return (
    <Loading label={label}>
      <Header title="w-36" lines={2} action={<Skeleton className="h-11 w-44 rounded-full" />} />
      <div className="space-y-12">
        <div className="flex flex-col gap-6 rounded-panel border border-sand-200 bg-white p-6 sm:p-7">
          <Chip className="w-32" />
          <span className="flex max-w-[620px] flex-col gap-2.5">
            <Skeleton className="h-8 w-full rounded-[10px]" /><Skeleton className="h-8 w-2/5 rounded-[10px]" />
          </span>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
            <TrustCardSkeleton person />
            <div className="hidden sm:block"><TrustCardSkeleton person /></div>
            <div className="hidden xl:block"><TrustCardSkeleton person /></div>
          </div>
        </div>
        <div>
          <SectionHead />
          <div className="overflow-hidden rounded-panel border border-sand-200 bg-white">
            <div className={`${LEAD_ROW} hidden border-b border-sand-100 px-6 py-3`}>
              <Skeleton className="h-3 w-10" /><Skeleton className="h-3 w-16" /><Skeleton className="h-3 w-20" /><Skeleton className="ml-auto h-3 w-14" />
            </div>
            {Array.from({ length: 6 }, (_, i) => <LeadRowSkeleton key={i} i={i} />)}
          </div>
        </div>
      </div>
    </Loading>
  );
}

/** A card section: its title and description, then a few lines (or what is passed). */
function SectionCard({ lines = 3, children }: { lines?: number; children?: ReactNode }) {
  return (
    <Card>
      <div className="mb-5 flex flex-col gap-2">
        <Skeleton className="h-4 w-32" />
        <Skeleton className="h-3 w-[min(520px,90%)]" />
      </div>
      {children ?? <SkeletonText lines={lines} />}
    </Card>
  );
}

/** A lead: the header with the stage, the Lead Score and Trust Score cards, the profile, and the sections below. */
export function LeadSkeleton() {
  return (
    <Loading label="Loading the lead">
      <Header back title="w-56" action={<span className="flex items-center gap-2.5"><Skeleton className="h-3.5 w-10" /><Skeleton className="h-11 w-44 rounded-control" /></span>} />
      <div className="space-y-6">
        <div className="grid gap-4 lg:grid-cols-2">
          <LeadScoreSkeleton />
          <TrustCardSkeleton footer />
        </div>
        <SectionCard>
          <div className="grid gap-x-8 gap-y-4 sm:grid-cols-2 lg:grid-cols-3">
            {["w-4/5", "w-16", "w-24", "w-20", "w-28"].map((w, i) => (
              <span key={i} className="flex flex-col gap-2"><Skeleton className="h-3 w-20" /><Skeleton className={`h-4 ${w}`} /></span>
            ))}
          </div>
          <Skeleton className="mt-6 h-[116px] w-full rounded-[16px]" />
        </SectionCard>
        <SectionCard lines={2}>
          <span className="flex flex-wrap items-center gap-3"><Skeleton className="h-10 w-[min(420px,100%)] rounded-full" /><Skeleton className="h-11 w-40 rounded-full" /></span>
        </SectionCard>
        <SectionCard>
          <span className="flex flex-wrap gap-2.5"><Skeleton className="h-11 w-56 rounded-full" /><Skeleton className="h-11 w-44 rounded-full" /></span>
        </SectionCard>
      </div>
    </Loading>
  );
}

/** The printable proposal: the way back and the print button, its badges, then the document itself. */
export function ProposalSkeleton() {
  return (
    <Loading label="Loading the proposal">
      <div className="mx-auto max-w-3xl">
        <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
          <Skeleton className="h-9 w-36 rounded-full" /><Skeleton className="h-11 w-48 rounded-full" />
        </div>
        <div className="mb-6 flex flex-wrap gap-2"><Chip className="w-32" /><Chip className="w-60" /><Chip className="w-48" /><Chip className="w-40" /></div>
        <div className="rounded-panel border border-sand-200 bg-white p-5 sm:p-10">
          <div className="flex flex-col gap-3 border-b border-sand-200 pb-6">
            <Skeleton className="h-5 w-24" />
            <Skeleton className="mt-4 h-8 w-3/4 rounded-[10px]" />
            <Skeleton className="h-3.5 w-5/6" />
          </div>
          <div className="mt-8 flex flex-col gap-6 rounded-[16px] bg-fill px-6 py-[22px]">
            {[3, 3, 2, 3].map((lines, i) => (
              <span key={i} className="flex flex-col gap-3">
                <Skeleton className="h-4 w-40" /><SkeletonText lines={lines} />
                <span className="flex gap-1.5"><Chip className="w-36" /><Chip className="w-28" /></span>
              </span>
            ))}
          </div>
          <div className="mt-10 flex flex-col gap-3">
            <Skeleton className="h-4 w-56" /><Skeleton className="h-3 w-4/5" />
            <Skeleton className="mt-2 aspect-[720/340] w-full rounded-[12px]" />
            {Array.from({ length: 5 }, (_, i) => (
              <span key={i} className="flex justify-between gap-4 border-b border-sand-100 py-2.5 last:border-b-0">
                <Skeleton className="h-3.5 w-48" /><Skeleton className="h-3.5 w-20" />
              </span>
            ))}
          </div>
        </div>
      </div>
    </Loading>
  );
}

/** A hold banner: the icon tile, what was held and why, the account's trust, and the way in. */
function HoldBannerSkeleton({ open }: { open: boolean }) {
  return (
    <div className="flex flex-wrap items-start gap-4 rounded-panel bg-coral-50 p-5 sm:p-6">
      <span className="h-10 w-10 shrink-0 rounded-control bg-white" />
      <span className="flex min-w-0 flex-1 basis-[260px] flex-col gap-2.5">
        <Skeleton className="h-4 w-[min(360px,90%)]" />
        <Skeleton className="h-3.5 w-full" />
        <Skeleton className="h-3.5 w-3/5" />
        <span className="mt-1 flex items-center gap-2"><Chip /><Skeleton className="h-3 w-24" /></span>
      </span>
      {!open && <Skeleton className="h-11 w-40 rounded-full" />}
    </div>
  );
}

/** The held orders: the first banner open on its checks, trust, review note and decision, and the next one closed. */
export function HeldSkeleton() {
  return (
    <Loading label="Loading held orders">
      <div className="space-y-6">
        <div className="space-y-4">
          <HoldBannerSkeleton open />
          <div className="grid gap-4 lg:grid-cols-2 lg:items-start">
            <div className="min-w-0 space-y-4">
              <SectionCard lines={4} />
              <TrustCardSkeleton signals={3} />
            </div>
            <div className="min-w-0 space-y-4">
              <SectionCard><Skeleton className="h-11 w-72 max-w-full rounded-full" /></SectionCard>
              <SectionCard>
                <Skeleton className="h-3.5 w-20" />
                <Skeleton className="mt-2 h-24 w-full rounded-control" />
                <span className="mt-4 flex flex-wrap gap-2"><Skeleton className="h-11 w-40 rounded-full" /><Skeleton className="h-11 w-36 rounded-full" /></span>
              </SectionCard>
            </div>
          </div>
        </div>
        <HoldBannerSkeleton open={false} />
      </div>
    </Loading>
  );
}
