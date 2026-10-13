"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import type { Me } from "@/lib/api";
import { addVisit, guideState, journeyFor, loadGuideHidden, loadVisits, progress, saveGuideHidden, saveVisits } from "@/lib/journeys";
import { routeKind, sectionFor, tabFor, workspaceFor, type NavSection, type Workspace } from "@/lib/nav";
import { ACTS, actFor, initials } from "@/lib/personas";
import { useSession } from "@/lib/session-context";
import { Icon } from "@/components/icons";
import { ButtonLink, Loading, NavSegmented, Notice, PageTabsContext, Sparkle } from "@/components/ui";

const ROLE_LABEL: Record<string, string> = {
  investor: "Investor", advisor: "Advisor", ops: "Operations", compliance: "Compliance", admin: "Administrator",
};

/** The Atrium mark: a serif A on a tonal green tile. */
export function AtriumMark({ size = 32 }: { size?: number }) {
  return (
    <span aria-hidden="true" style={{ width: size, height: size, fontSize: Math.round(size * 0.58) }}
      className="flex shrink-0 items-center justify-center rounded-[10px] bg-green-100 font-serif font-medium leading-none text-green-700">
      A
    </span>
  );
}

export function Wordmark({ href }: { href: string }) {
  return (
    <Link href={href} className="flex min-h-11 items-center gap-2.5 text-[18px] font-semibold tracking-[-0.01em]">
      <AtriumMark />
      Atrium
    </Link>
  );
}

export function Footer() {
  return (
    <footer className="no-print border-t border-sand-200">
      <div className="mx-auto flex max-w-[1240px] flex-wrap justify-between gap-3 px-4 py-6 text-xs text-ink-500 sm:px-8">
        <span>Atrium, by team Ctrl+Alt+Hiru for the AI Builder Cup 2026.</span>
        <span>Synthetic people and paper trading. Projections are simulations, and nothing here is investment advice.</span>
      </div>
    </footer>
  );
}

/** The person switcher: who you are, their role, and the stage of the story they belong to. */
function PersonSwitcher({ me }: { me: Me }) {
  const name = me.full_name ?? me.email;
  const role = ROLE_LABEL[me.roles[0]] ?? me.roles[0];
  const act = ACTS.find((a) => a.key === actFor(me.email, me.roles));
  const line = act ? `${role} · Stage ${act.number}, ${act.label}` : role;
  return (
    <Link href="/#journeys" aria-label={`${name}, ${line}. Switch person`}
      className="flex h-[52px] shrink-0 items-center gap-2.5 rounded-full border border-sand-200 bg-white pl-1.5 pr-1.5 hover:bg-fill sm:pr-3.5">
      <span aria-hidden="true" className="flex h-10 w-10 items-center justify-center rounded-full bg-green-200 text-[13px] font-semibold text-green-900">{initials(name)}</span>
      <span aria-hidden="true" className="hidden flex-col leading-4 sm:flex">
        <span className="text-[13px] font-semibold">{name}</span>
        <span className="whitespace-nowrap text-xs text-ink-500">{line}</span>
      </span>
      <svg aria-hidden="true" className="hidden sm:block" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#6F6C62" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m6 9 6 6 6-6" /></svg>
    </Link>
  );
}

/** The journey as one line in the top bar: progress, the current step and its action; the chevron opens every step. */
function StoryBar({ email, path, hidden, onHide, onShow }:
  { email: string; path: string; hidden: boolean; onHide: () => void; onShow: () => void }) {
  const journey = journeyFor(email);
  const [visited, setVisited] = useState<string[]>([]);
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!journey) return;
    const next = addVisit(loadVisits(email), path);
    saveVisits(email, next);
    setVisited(next);
  }, [email, path, journey]);

  useEffect(() => {
    setOpen(false);
  }, [path]);

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => { if (box.current && !box.current.contains(e.target as Node)) setOpen(false); };
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", esc);
    return () => { document.removeEventListener("mousedown", close); document.removeEventListener("keydown", esc); };
  }, [open]);

  if (!journey) return null;
  if (hidden) {
    return (
      <button type="button" onClick={onShow}
        className="h-10 shrink-0 rounded-full border border-sand-200 bg-white px-4 text-[13px] font-semibold hover:bg-fill">
        Show your story
      </button>
    );
  }
  const { done, current, count } = progress(journey, visited);
  const step = current === null ? null : journey.steps[current];
  return (
    <div ref={box} className="relative min-w-0 flex-[3] lg:max-w-[760px]">
      <div className="flex h-[52px] items-center gap-3 rounded-full border border-sand-200 bg-white pl-[18px] pr-1.5">
        <span className="hidden whitespace-nowrap text-[13px] font-semibold md:inline">{journey.title}</span>
        <span aria-hidden="true" className="flex gap-[3px]">
          {journey.steps.map((s, i) => (
            <span key={s.title} className={`h-1.5 w-4 rounded-[3px] ${done[i] ? "bg-green-500" : current === i ? "bg-green-300" : "bg-sand-200"}`} />
          ))}
        </span>
        <span className="num whitespace-nowrap text-xs text-ink-500">{count} of {journey.steps.length}</span>
        <span aria-hidden="true" className="hidden h-[22px] w-px bg-sand-200 sm:block" />
        <span className="hidden min-w-0 flex-1 flex-col leading-4 sm:flex">
          <span className="truncate text-[13px] font-semibold">{step ? step.title : "You have seen this story"}</span>
          <span className="truncate text-xs text-ink-500">{step ? step.detail : "Try another person from the front door."}</span>
        </span>
        <span className="flex-1 sm:hidden" />
        {step && path !== step.href
          ? <ButtonLink href={step.href} variant="tonal" size="sm" className="!min-h-10 shrink-0">{step.action}</ButtonLink>
          : !step && <ButtonLink href="/#journeys" variant="tonal" size="sm" className="!min-h-10 shrink-0">Choose a person</ButtonLink>}
        <button type="button" aria-label="Show all steps" aria-expanded={open} onClick={() => setOpen((v) => !v)}
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-fill hover:bg-sand-100">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#3E3C35" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"
            className={`transition-transform ${open ? "rotate-180" : ""}`}><path d="m6 9 6 6 6-6" /></svg>
        </button>
      </div>
      {open && (
        <div className="absolute left-0 right-0 top-[60px] z-40 rounded-panel border border-sand-200 bg-white p-2 shadow-float sm:right-auto sm:w-[420px]">
          <p className="px-3 pb-1 pt-2 text-[13px] text-ink-700">{journey.intro}</p>
          <ol>
            {journey.steps.map((s, i) => (
              <li key={s.title}>
                <Link href={s.href} className="flex gap-3 rounded-control px-3 py-2.5 hover:bg-fill">
                  <span aria-hidden="true" className={`mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-semibold ${done[i] ? "bg-green-500 text-white" : current === i ? "bg-green-100 text-green-800" : "border-[1.5px] border-dashed border-sand-300 text-ink-500"}`}>
                    {done[i] ? "✓" : i + 1}
                  </span>
                  <span className="flex min-w-0 flex-col">
                    <span className="text-sm font-semibold">{s.title}<span className="sr-only">{done[i] ? ", done" : current === i ? ", next" : ""}</span></span>
                    <span className="text-xs text-ink-500">{s.detail}</span>
                  </span>
                </Link>
              </li>
            ))}
          </ol>
          <div className="flex justify-between gap-2 border-t border-sand-100 px-3 pb-1 pt-2.5">
            <Link href="/#journeys" className="text-[13px] font-semibold text-green-600">Try another person</Link>
            <button type="button" onClick={onHide} className="text-[13px] text-ink-500 hover:text-ink-900">Hide the story</button>
          </div>
        </div>
      )}
    </div>
  );
}

function RailItem({ section, on }: { section: NavSection; on: boolean }) {
  return (
    <Link href={section.href} aria-current={on ? "page" : undefined} className="group flex w-[76px] flex-col items-center gap-1">
      <span className={`flex h-9 w-12 items-center justify-center rounded-control ${on ? "bg-green-100 text-green-700" : "text-ink-700 group-hover:bg-fill"}`}>
        <Icon name={section.icon} size={19} />
      </span>
      <span className={`text-center text-[11px] leading-[13px] ${on ? "font-semibold text-ink-900" : "font-medium text-ink-500"}`}>{section.label}</span>
    </Link>
  );
}

/** The icon rail: one place for the workspace's pages, each with its label under the icon. */
function IconRail({ space, active }: { space: Workspace; active: NavSection | null }) {
  return (
    <aside className="no-print sticky top-4 hidden h-[calc(100vh-32px)] w-[84px] shrink-0 flex-col items-center gap-2 rounded-panel border border-sand-200 bg-white py-[18px] lg:flex">
      <Link href={space.home} aria-label="Atrium, workspace home" className="mb-5"><AtriumMark size={38} /></Link>
      <nav aria-label={`${space.label} workspace`} className="flex flex-col items-center gap-2">
        {space.sections.map((s) => <RailItem key={s.key} section={s} on={active?.key === s.key} />)}
      </nav>
    </aside>
  );
}

/** Below the large breakpoint the rail becomes a strip under the top bar, still with labels. */
function StripNav({ space, active }: { space: Workspace; active: NavSection | null }) {
  return (
    <nav aria-label={`${space.label} workspace`} className="no-print -mx-1 flex gap-1 overflow-x-auto pb-1 lg:hidden">
      {space.sections.map((s) => {
        const on = active?.key === s.key;
        return (
          <Link key={s.key} href={s.href} aria-current={on ? "page" : undefined}
            className={`flex min-h-10 shrink-0 items-center gap-2 rounded-full px-3.5 text-[13px] ${on ? "bg-green-100 font-semibold text-green-800" : "font-medium text-ink-700 hover:bg-fill"}`}>
            <Icon name={s.icon} size={16} />{s.label}
          </Link>
        );
      })}
    </nav>
  );
}

export function Shell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const router = useRouter();
  const { me, status, error } = useSession();
  const [guideHidden, setGuideHidden] = useState(false);
  const kind = routeKind(path);

  useEffect(() => {
    if (me) setGuideHidden(loadGuideHidden(me.email));
  }, [me]);
  useEffect(() => {
    if (status === "signed-out" && kind === "app") router.replace("/");
  }, [status, kind, router]);

  function setGuide(hidden: boolean) {
    setGuideHidden(hidden);
    if (me) saveGuideHidden(me.email, hidden);
  }

  if (kind === "front") return <>{children}</>;
  const space = me ? workspaceFor(me.roles) : null;

  if (kind === "public" || !me || !space) {
    return (
      <div className="flex min-h-screen flex-col">
        <header className="no-print border-b border-sand-200 bg-white">
          <div className="mx-auto flex h-[68px] max-w-[1240px] items-center justify-between px-4 sm:px-8">
            <Wordmark href="/" />
            {me && space
              ? <Link href={space.home} className="text-sm font-semibold text-green-600">Open your workspace</Link>
              : <Link href="/#journeys" className="text-sm font-semibold text-green-600">Choose a person</Link>}
          </div>
        </header>
        <main className="mx-auto w-full max-w-[1240px] flex-1 px-4 py-10 sm:px-8 lg:py-14">
          {kind === "public" ? children
            : status === "error" ? <Notice tone="error" title="Atrium is unavailable">{error}</Notice>
            : me && !space ? <Notice tone="caution" title="This person has no workspace">Choose another person on the front page.</Notice>
            : <Loading label="Opening your workspace" />}
        </main>
        <Footer />
      </div>
    );
  }

  const section = sectionFor(space, path);
  const tab = section ? tabFor(section, path) : null;
  const tabs = section?.tabs
    ? <NavSegmented label={`${section.label} pages`} items={section.tabs.map((t) => ({ href: t.href, label: t.label, on: tab?.href === t.href }))} />
    : null;
  const guide = guideState(me.email, guideHidden);
  return (
    <div className="flex min-h-screen flex-col">
      <div className="flex flex-1 gap-4 p-3 sm:p-4">
        <IconRail space={space} active={section} />
        <div className="flex min-w-0 flex-1 flex-col">
          <header className="no-print flex flex-col gap-3 lg:gap-0">
            <div className="flex items-center gap-3">
              <Link href={space.home} aria-label="Atrium, workspace home" className="lg:hidden"><AtriumMark /></Link>
              {guide !== "none" && (
                <StoryBar email={me.email} path={path} hidden={guide === "hidden"} onHide={() => setGuide(true)} onShow={() => setGuide(false)} />
              )}
              <span className="flex-1" />
              {space.key === "investor" && (
                <Link href="/investor/copilot" className="inline-flex h-11 shrink-0 items-center gap-2 rounded-full bg-ai-50 px-4 text-sm font-semibold text-ai-700 hover:bg-ai-100">
                  <Sparkle /><span className="hidden sm:inline">Ask Atrium</span>
                </Link>
              )}
              <PersonSwitcher me={me} />
            </div>
            <StripNav space={space} active={section} />
          </header>
          <main className="mx-auto w-full min-w-0 max-w-[1440px] flex-1 px-1 pb-12 pt-6 sm:px-2 lg:pt-8">
            <PageTabsContext.Provider value={tabs}>{children}</PageTabsContext.Provider>
          </main>
        </div>
      </div>
      <Footer />
    </div>
  );
}
