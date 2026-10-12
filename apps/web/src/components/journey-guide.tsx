"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { addVisit, journeyFor, loadVisits, progress, saveVisits } from "@/lib/journeys";
import { ButtonLink } from "@/components/ui";

/** "Your story": the persona's steps, ticked off as their pages are visited, with the next one's button. */
export function JourneyGuide({ email, path, onHide }: { email: string; path: string; onHide: () => void }) {
  const journey = journeyFor(email);
  const [visited, setVisited] = useState<string[]>([]);

  useEffect(() => {
    if (!journey) return;
    const next = addVisit(loadVisits(email), path);
    saveVisits(email, next);
    setVisited(next);
  }, [email, path, journey]);

  if (!journey) return null;
  const { done, current, count } = progress(journey, visited);
  return (
    <aside aria-label={journey.title} className="rounded-panel border border-line bg-surface p-6">
      <div className="flex items-baseline justify-between gap-3">
        <h2 className="text-base font-semibold">{journey.title}</h2>
        <span className="num text-[13px] text-muted">{count} of {journey.steps.length}</span>
      </div>
      <p className="mt-1 text-sm text-ink-2">{journey.intro}</p>
      <ol className="mt-3">
        {journey.steps.map((s, i) => {
          const isDone = done[i];
          const isNow = current === i;
          return (
            <li key={s.title} className="grid grid-cols-[28px_minmax(0,1fr)] gap-3 border-t border-line py-4 first:border-t-0">
              <span aria-hidden="true"
                className={`flex h-7 w-7 items-center justify-center rounded-full border text-[13px] font-semibold ${isDone ? "border-gain bg-gain text-white" : isNow ? "border-ink bg-ink text-white" : "border-line-strong text-ink-2"}`}>
                {isDone ? "✓" : i + 1}
              </span>
              <span className="flex min-w-0 flex-col gap-1">
                <span className="font-semibold">{s.title}<span className="sr-only">{isDone ? ", done" : isNow ? ", next" : ""}</span></span>
                <span className="text-[13px] text-muted">{s.detail}</span>
                {isNow && path !== s.href && <ButtonLink href={s.href} size="sm" className="mt-1.5 self-start">{s.action}</ButtonLink>}
              </span>
            </li>
          );
        })}
      </ol>
      {current === null && (
        <p className="border-t border-line pt-4 text-sm text-ink-2">
          You have seen this story. <Link href="/#journeys" className="font-semibold underline underline-offset-4">Try another person</Link>.
        </p>
      )}
      <button type="button" onClick={onHide} className="mt-3 text-[13px] text-muted underline decoration-line-strong underline-offset-4 hover:text-ink">
        Hide this guide
      </button>
    </aside>
  );
}
