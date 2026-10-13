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
import { Reveal, Stagger, StaggerItem } from "@/components/motion";
import { PlanDiagram } from "@/components/plan-diagram";
import { Footer, Wordmark } from "@/components/shell";
import { Badge, Button, ButtonLink } from "@/components/ui";

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
const NAV = [{ href: "#analyze", label: "Analyze" }, { href: "#how", label: "How it works" }, { href: "#journeys", label: "Journeys" }];

function SectionHead({ id, title, children }: { id?: string; title: string; children?: React.ReactNode }) {
  return (
    <div className="flex max-w-[680px] flex-col gap-3">
      <h2 id={id} className="text-[26px] font-semibold leading-8 tracking-[-0.02em] sm:text-[30px] sm:leading-9">{title}</h2>
      {children && <p className="text-[15px] leading-[22px] text-ink-700 sm:text-[17px] sm:leading-[26px]">{children}</p>}
    </div>
  );
}

function PersonCard({ person, current, opening, disabled, onEnter }:
  { person: Persona; current: boolean; opening: boolean; disabled: boolean; onEnter: () => void }) {
  const first = person.name.split(" ")[0];
  return (
    <article className="flex flex-col gap-4 rounded-panel border border-sand-200 bg-white p-5 sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-x-3 gap-y-2">
        <div className="flex min-w-[160px] flex-1 items-center gap-3">
          <span aria-hidden="true" className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-green-200 text-[13px] font-semibold text-green-900">
            {initials(person.name)}
          </span>
          <span className="flex min-w-0 flex-col">
            <span className="text-base font-semibold leading-[22px]">{person.name}</span>
            <span className="text-[13px] text-ink-500">{person.role}</span>
          </span>
        </div>
        {current ? <Badge tone="gain">Signed in</Badge> : person.start ? <Badge tone="gain">Start here</Badge> : null}
      </div>
      <p className="text-sm leading-[21px] text-ink-900">{person.story}</p>
      <ul className="flex flex-col gap-2 text-[13px] leading-[19px] text-ink-700">
        {person.tries.map((t) => (
          <li key={t} className="flex items-baseline gap-2.5">
            <span aria-hidden="true" className="h-1.5 w-1.5 shrink-0 -translate-y-px rounded-full bg-green-500" />{t}
          </li>
        ))}
      </ul>
      <Button variant="tonal" disabled={disabled} busy={opening} onClick={onEnter} className="mt-1 w-full">
        {opening ? `Opening ${first}'s workspace` : `Enter as ${first}`}
      </Button>
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
  const firstName = me ? (me.full_name ?? me.email).split(" ")[0] : "";

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
    <div className="min-h-screen bg-white">
      <header>
        <div className="mx-auto flex h-[72px] max-w-[1240px] items-center justify-between gap-4 px-4 sm:px-8">
          <Wordmark href="/" />
          <div className="flex items-center gap-3">
            <nav aria-label="Sections" className="hidden gap-1 rounded-full border border-sand-200 bg-white p-1 md:flex">
              {NAV.map((n) => (
                <a key={n.href} href={n.href} className="whitespace-nowrap rounded-full px-4 py-2 text-sm font-medium text-ink-700 hover:bg-fill hover:text-ink-900">
                  {n.label}
                </a>
              ))}
            </nav>
            {me && space
              ? <ButtonLink href={space.home} variant="tonal" size="sm">Continue as {firstName}</ButtonLink>
              : <Button variant="tonal" size="sm" disabled={busy} onClick={() => enter(start)}>Start as {start.name.split(" ")[0]}</Button>}
          </div>
        </div>
      </header>

      <main>
        <section className="mx-auto max-w-[1240px] px-4 pb-16 pt-8 sm:px-8 lg:pb-24 lg:pt-14">
          <div className="grid items-center gap-12 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.02fr)] lg:gap-16">
            {/* The hero settles line by line, then the floor plan builds itself room by room (the page's one moment). */}
            <div className="flex flex-col gap-6">
              <Reveal>
                <h1 className="text-[36px] font-semibold leading-[42px] tracking-[-0.025em] sm:text-[44px] sm:leading-[48px]">
                  A wealth firm run by people, with an AI that shows its working.
                </h1>
              </Reveal>
              <Reveal delay={0.08}>
                <p className="max-w-[34em] text-[17px] leading-[26px] text-ink-700">
                  Atrium follows an investor from the first enquiry to a reconciled ledger: four stages, eight people, and Gemini at
                  every step, checked against the numbers it explains.
                </p>
              </Reveal>
              <Reveal delay={0.16} className="flex flex-col gap-2.5 sm:flex-row sm:flex-wrap">
                {me && space
                  ? <ButtonLink href={space.home}>Continue as {firstName}</ButtonLink>
                  : (
                    <Button disabled={busy} busy={opening === start.email} onClick={() => enter(start)}>
                      {opening === start.email ? `Opening ${start.name.split(" ")[0]}'s workspace` : `Start as ${start.name.split(" ")[0]}, an investor`}
                    </Button>
                  )}
                <ButtonLink href="#journeys" variant="tonal">Choose another person</ButtonLink>
              </Reveal>
              <Reveal delay={0.24}>
                <p className="text-[13px] leading-[19px] text-ink-500">
                  Every person, account and trade here is synthetic. Trading uses paper money at real US market prices.
                </p>
              </Reveal>
            </div>
            <PlanDiagram />
          </div>
        </section>

        <section id="how" aria-labelledby="how-title" className="mx-auto max-w-[1240px] scroll-mt-4 px-4 pb-16 sm:px-8 lg:pb-24">
          <SectionHead id="how-title" title="What the AI does, and what it never does" />
          <div className="mt-8 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            {PRINCIPLES.map((p, i) => (
              <div key={p.title} className="flex flex-col gap-2.5 rounded-panel border border-sand-200 bg-white p-6">
                <span className="code text-ink-500">0{i + 1}</span>
                <h3 className="text-[17px] font-semibold leading-6">{p.title}</h3>
                <p className="text-sm leading-[21px] text-ink-500">{p.text}</p>
              </div>
            ))}
          </div>
        </section>

        <section id="analyze" aria-labelledby="analyze-title" className="mx-auto max-w-[1240px] scroll-mt-4 px-4 pb-16 sm:px-8 lg:pb-24">
          <SectionHead id="analyze-title" title="See what your money could become">
            Pick an Atrium fund or a share, an amount and a number of years. No sign-in needed: the figures come from real
            prices since 2007, and you can turn them into an investment or a conversation with an advisor.
          </SectionHead>
          <div className="mt-8"><Analyzer /></div>
        </section>

        <section id="journeys" aria-labelledby="journeys-title" className="mx-auto max-w-[1240px] scroll-mt-4 px-4 pb-16 sm:px-8 lg:pb-24">
          <SectionHead id="journeys-title" title="Choose a person">
            Each journey takes two or three minutes. The story line at the top of every page tells you what to try next, and
            you can switch person at any time from the person switcher.
          </SectionHead>
          {cfg && cfg.authMode !== "dev" && (
            <p className="mt-3 text-sm text-ink-700">This deployment uses real sign-in. <Link href="/login" className="font-semibold text-green-600 hover:text-green-800 hover:underline">Sign in</Link> to continue.</p>
          )}
          {/* The people arrive stage by stage, in the order a client meets them. */}
          <Stagger className="mt-8 grid gap-x-4 gap-y-8 sm:grid-cols-2 xl:grid-cols-4 xl:items-start">
            {personasByAct().map(({ act, people }) => (
              <div key={act.key} className="flex flex-col gap-3">
                <StaggerItem className="flex flex-col gap-2 px-1">
                  <span aria-hidden="true" className="h-1 rounded-[2px] bg-green-500" />
                  <p className="text-[13px] text-ink-500"><span className="num font-semibold text-ink-900">{act.number}</span> · {act.label}</p>
                </StaggerItem>
                {people.map((p) => (
                  <StaggerItem key={p.email}>
                    <PersonCard person={p} current={signedInAs === p.email} opening={opening === p.email}
                      disabled={busy} onEnter={() => enter(p)} />
                  </StaggerItem>
                ))}
              </div>
            ))}
          </Stagger>
        </section>
      </main>
      <Footer />
    </div>
  );
}
