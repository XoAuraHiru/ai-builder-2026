"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { getConfig, type RuntimeConfig } from "@/lib/config";
import { entryRoute, workspaceFor } from "@/lib/nav";
import { initials, PERSONAS, personaFor, personasByAct, type Persona } from "@/lib/personas";
import { setDevUser } from "@/lib/session";
import { useSession } from "@/lib/session-context";
import { Analyzer } from "@/components/analyzer";
import { PlanDiagram } from "@/components/plan-diagram";
import { Footer, Wordmark } from "@/components/shell";

const PRINCIPLES = [
  { title: "It explains; the engines count",
    text: "Prices, simulations, matches and checks are code. In a scenario, Gemini proposes the shocks and you can change each one; the engine computes the result. Any dollar or percentage Gemini writes that the engine did not produce is flagged on the page." },
  { title: "It proposes; people decide",
    text: "Orders, matches and alerts wait for a person. Publishing prices or changing the ledger needs a second person with a one-time code." },
  { title: "It shows where it looked",
    text: "Answers about funds cite the fact-sheet section; case reviews cite the evidence rows; a call's flags quote the call and give the second they were said. Fraud rings are found by the graph, and Gemini only explains them. Anything Gemini wrote is set in a serif." },
  { title: "It is checked, attacked and paused when it slips",
    text: "Every model is validated before and after each deploy, attacked by a red team, tested for fair lending and watched against people's decisions. A model that slips is paused, and its feature falls back to the engine." },
];
const PILL = "inline-flex min-h-11 items-center justify-center gap-2 rounded-full px-5 text-sm font-semibold transition-colors disabled:cursor-wait disabled:opacity-70";
const PRIMARY = `${PILL} bg-ink text-white hover:bg-[#26343f]`;
const SECONDARY = `${PILL} border border-line-strong bg-surface text-ink hover:border-ink`;

function PersonCard({ person, current, opening, disabled, onEnter }:
  { person: Persona; current: boolean; opening: boolean; disabled: boolean; onEnter: () => void }) {
  const first = person.name.split(" ")[0];
  return (
    <article className={`flex flex-col gap-3 rounded-panel border bg-surface p-5 ${person.start ? "border-ink" : "border-line"}`}>
      <div className="flex items-center gap-3">
        <span aria-hidden="true" className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full border border-ink text-sm font-semibold">
          {initials(person.name)}
        </span>
        <span className="flex flex-col">
          <span className="text-[17px] font-semibold">{person.name}</span>
          <span className="text-[13px] text-muted">{person.role}{person.start ? ", start here" : ""}{current ? ", signed in now" : ""}</span>
        </span>
      </div>
      <p className="text-sm">{person.story}</p>
      <ul className="flex flex-col gap-1.5 text-sm text-ink-2">
        {person.tries.map((t) => (
          <li key={t} className="flex items-baseline gap-2.5">
            <span aria-hidden="true" className="h-1.5 w-1.5 shrink-0 -translate-y-0.5 rounded-[1px] bg-daylight" />{t}
          </li>
        ))}
      </ul>
      <button type="button" disabled={disabled} onClick={onEnter} className={`${person.start ? PRIMARY : SECONDARY} mt-1`}>
        {opening ? "Opening…" : `Enter as ${first}`}
      </button>
    </article>
  );
}

export default function FrontDoor() {
  const router = useRouter();
  const { me, refresh } = useSession();
  const [cfg, setCfg] = useState<RuntimeConfig | null>(null);
  const [opening, setOpening] = useState("");
  const space = me ? workspaceFor(me.roles) : null;
  const start = PERSONAS.find((p) => p.start) ?? PERSONAS[0];
  const signedInAs = personaFor(me?.email)?.email;

  useEffect(() => {
    getConfig().then(setCfg);
  }, []);

  async function enter(person: Persona) {
    if (!cfg) return;
    const target = entryRoute(cfg.authMode, space?.home ?? null);
    if (target) {
      router.push(target);
      return;
    }
    setOpening(person.email);
    setDevUser(person.email);
    await refresh();
    router.push(person.home);
  }

  const busy = Boolean(opening) || !cfg;
  return (
    <div className="min-h-screen">
      <header className="border-b border-line bg-surface">
        <div className="mx-auto flex h-[72px] max-w-[1240px] items-center justify-between gap-4 px-4 sm:px-8">
          <Wordmark href="/" />
          <nav aria-label="Sections" className="flex items-center gap-3 sm:gap-7">
            <a href="#analyze" className="flex min-h-11 items-center text-[15px] text-ink-2 hover:text-ink">Analyze</a>
            <a href="#how" className="hidden min-h-11 items-center text-[15px] text-ink-2 hover:text-ink sm:flex">How it works</a>
            <a href="#journeys" className="flex min-h-11 items-center text-[15px] text-ink-2 hover:text-ink">Journeys</a>
            {me && space
              ? <Link href={space.home} className={PRIMARY}>Continue as {(me.full_name ?? me.email).split(" ")[0]}</Link>
              : <button type="button" disabled={busy} onClick={() => enter(start)} className={PRIMARY}>Start as {start.name.split(" ")[0]}</button>}
          </nav>
        </div>
      </header>

      <main>
        <section className="mx-auto max-w-[1240px] px-4 pb-20 pt-12 sm:px-8 lg:pb-28 lg:pt-20">
          <div className="grid items-center gap-12 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.02fr)] lg:gap-16">
            <div className="flex flex-col gap-7">
              <h1 className="wide text-[38px] font-semibold leading-[1.05] tracking-[-0.025em] sm:text-[52px] lg:text-[58px]">
                A wealth firm run by people, with an AI that shows its working.
              </h1>
              <p className="max-w-[34em] text-[17px] leading-relaxed text-ink-2 sm:text-[19px]">
                Atrium follows an investor from the first enquiry to a reconciled ledger: four stages, eight people, and Gemini at
                every step, checked against the numbers it explains.
              </p>
              <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap">
                {me && space
                  ? <Link href={space.home} className={PRIMARY}>Continue as {(me.full_name ?? me.email).split(" ")[0]}</Link>
                  : (
                    <button type="button" disabled={busy} onClick={() => enter(start)} className={PRIMARY}>
                      {opening === start.email ? "Opening…" : `Start as ${start.name.split(" ")[0]}, an investor`}
                    </button>
                  )}
                <a href="#journeys" className={SECONDARY}>Choose another person</a>
              </div>
              <p className="text-sm text-muted">Every person, account and trade here is synthetic. Trading uses paper money at real US market prices.</p>
            </div>
            <PlanDiagram />
          </div>
        </section>

        <section id="how" className="scroll-mt-4 border-y border-line bg-surface">
          <div className="mx-auto max-w-[1240px] px-4 py-16 sm:px-8 lg:py-20">
            <h2 className="wide max-w-[22em] text-[28px] font-semibold leading-[1.15] tracking-[-0.015em] sm:text-[34px]">
              What the AI does, and what it never does
            </h2>
            <div className="mt-10 grid gap-8 md:grid-cols-2 xl:grid-cols-4">
              {PRINCIPLES.map((p) => (
                <div key={p.title} className="border-t-2 border-ink pt-5">
                  <h3 className="text-lg font-semibold">{p.title}</h3>
                  <p className="mt-2 text-ink-2">{p.text}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section id="analyze" className="mx-auto max-w-[1240px] scroll-mt-4 px-4 pt-16 sm:px-8 lg:pt-24">
          <h2 className="wide text-[28px] font-semibold leading-[1.15] tracking-[-0.015em] sm:text-[34px]">See what your money could become</h2>
          <p className="mt-3 max-w-[40em] text-[17px] text-ink-2">
            Pick an Atrium fund or a share, an amount and a number of years. No sign-in needed: the figures come from real
            prices since 2007, and you can turn them into an investment or a conversation with an advisor.
          </p>
          <div className="mt-10"><Analyzer /></div>
        </section>

        <section id="journeys" className="mx-auto max-w-[1240px] scroll-mt-4 px-4 py-16 sm:px-8 lg:py-24">
          <h2 className="wide text-[28px] font-semibold leading-[1.15] tracking-[-0.015em] sm:text-[34px]">Choose a person</h2>
          <p className="mt-3 max-w-[40em] text-[17px] text-ink-2">
            Each journey takes two or three minutes. A guide beside every page tells you what to try next, and you can switch
            person at any time from the top bar.
          </p>
          {cfg && cfg.authMode !== "dev" && (
            <p className="mt-3 text-sm text-ink-2">This deployment uses real sign-in. <Link href="/login" className="font-semibold underline underline-offset-4">Sign in</Link> to continue.</p>
          )}
          <div className="mt-10 grid gap-x-5 gap-y-8 sm:grid-cols-2 xl:grid-cols-4 xl:items-start">
            {personasByAct().map(({ act, people }) => (
              <div key={act.key} className="flex flex-col gap-3.5">
                <p className="text-sm text-muted"><span className="num font-semibold text-ink">{act.number}</span>&ensp;{act.label}</p>
                {people.map((p) => (
                  <PersonCard key={p.email} person={p} current={signedInAs === p.email} opening={opening === p.email}
                    disabled={busy} onEnter={() => enter(p)} />
                ))}
              </div>
            ))}
          </div>
        </section>
      </main>
      <Footer />
    </div>
  );
}
