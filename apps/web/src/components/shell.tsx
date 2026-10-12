"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { LayoutGroup, motion } from "motion/react";
import type { Me } from "@/lib/api";
import { guideState, loadGuideHidden, saveGuideHidden } from "@/lib/journeys";
import { routeKind, sectionFor, tabFor, workspaceFor, type NavSection, type Workspace } from "@/lib/nav";
import { ACTS, actFor, initials } from "@/lib/personas";
import { useSession } from "@/lib/session-context";
import { Icon } from "@/components/icons";
import { JourneyGuide } from "@/components/journey-guide";
import { ButtonLink, Loading, Notice } from "@/components/ui";

const ROLE_LABEL: Record<string, string> = {
  investor: "Investor", advisor: "Advisor", ops: "Operations", compliance: "Compliance", admin: "Administrator",
};

/** The Atrium mark: a building seen from above, with daylight falling into its central well. */
export function AtriumMark({ size = 22 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 20 20" aria-hidden="true">
      <rect x="1" y="1" width="18" height="18" rx="2" fill="none" stroke="currentColor" strokeWidth="1.4" />
      <rect x="6.5" y="6.5" width="7" height="7" rx="0.6" fill="var(--color-daylight)" />
    </svg>
  );
}

export function Wordmark({ href }: { href: string }) {
  return (
    <Link href={href} className="wide flex min-h-11 items-center gap-2.5 text-[19px] font-semibold tracking-[-0.01em]">
      <AtriumMark />
      Atrium
    </Link>
  );
}

export function Footer() {
  return (
    <footer className="no-print border-t border-line">
      <div className="mx-auto flex max-w-[1240px] flex-wrap justify-between gap-3 px-4 py-6 text-[13px] text-muted sm:px-8">
        <span>Atrium, by team Ctrl+Alt+Hiru for the AI Builder Cup 2026.</span>
        <span>Synthetic people and paper trading. Projections are simulations, and nothing here is investment advice.</span>
      </div>
    </footer>
  );
}

function Stages({ me }: { me: Me }) {
  const current = actFor(me.email, me.roles);
  return (
    <ol aria-label="Atrium's four stages" className="hidden items-center gap-5 md:flex">
      {ACTS.map((a) => {
        const on = a.key === current;
        return (
          <li key={a.key} aria-current={on ? "step" : undefined}
            className={`flex items-center gap-1.5 text-[13px] ${on ? "font-semibold text-ink" : "text-muted"}`}>
            <span aria-hidden="true" className={`h-2.5 w-2.5 rounded-[2px] border ${on ? "border-daylight bg-daylight" : "border-[#8c979f]"}`} />
            {a.label}
          </li>
        );
      })}
    </ol>
  );
}

function PersonaChip({ me }: { me: Me }) {
  const name = me.full_name ?? me.email;
  return (
    <Link href="/#journeys" aria-label={`${name}, ${ROLE_LABEL[me.roles[0]] ?? me.roles[0]}. Switch person`}
      className="flex min-h-11 items-center gap-2.5 rounded-full border border-line py-1 pl-1 pr-1 hover:border-line-strong sm:pr-3.5">
      <span aria-hidden="true" className="flex h-8 w-8 items-center justify-center rounded-full bg-ink text-xs font-semibold text-white">{initials(name)}</span>
      <span aria-hidden="true" className="hidden flex-col leading-tight sm:flex">
        <span className="text-sm font-semibold">{name}</span>
        <span className="text-xs text-muted">{ROLE_LABEL[me.roles[0]] ?? me.roles[0]}. Switch person</span>
      </span>
    </Link>
  );
}

function TopBar({ me, space, guideHidden, onShowGuide }: { me: Me; space: Workspace; guideHidden: boolean; onShowGuide: () => void }) {
  return (
    <header className="no-print sticky top-0 z-30 border-b border-line bg-surface">
      <div className="flex h-[68px] items-center justify-between gap-4 px-4 sm:px-6">
        <Wordmark href={space.home} />
        <Stages me={me} />
        <div className="flex items-center gap-2.5">
          {guideHidden && (
            <button type="button" onClick={onShowGuide}
              className="hidden min-h-11 text-sm text-ink-2 underline decoration-line-strong underline-offset-4 hover:text-ink lg:inline">
              Show your story
            </button>
          )}
          {space.key === "investor" && (
            <ButtonLink href="/investor/copilot" variant="secondary" size="sm">
              <span aria-hidden="true" className="h-2 w-2 rounded-[1px] bg-daylight" />Ask Atrium
            </ButtonLink>
          )}
          <PersonaChip me={me} />
        </div>
      </div>
    </header>
  );
}

function RailLink({ section, on, layout }: { section: NavSection; on: boolean; layout: "column" | "strip" }) {
  return (
    <Link href={section.href} aria-current={on ? "page" : undefined}
      className={`relative flex min-h-11 items-center rounded-control px-3.5 text-[15px] ${layout === "strip" ? "whitespace-nowrap" : ""} ${on ? "text-white" : "text-ink-2 hover:bg-wash hover:text-ink"}`}>
      {on && <motion.span layoutId={`rail-${layout}`} className="absolute inset-0 rounded-control bg-ink" />}
      <span className="relative flex items-center gap-3"><Icon name={section.icon} />{section.label}</span>
    </Link>
  );
}

function Rail({ space, active, layout }: { space: Workspace; active: NavSection | null; layout: "column" | "strip" }) {
  return (
    <LayoutGroup id={`rail-${layout}`}>
      <nav aria-label={`${space.label} workspace`}
        className={layout === "strip" ? "no-print border-b border-line bg-surface lg:hidden" : "no-print hidden border-r border-line lg:block"}>
        <ul className={layout === "strip" ? "flex gap-1 overflow-x-auto px-3 py-2" : "sticky top-[68px] space-y-1 px-3.5 py-5"}>
          {space.sections.map((s) => (
            <li key={s.key} className={layout === "strip" ? "shrink-0" : ""}>
              <RailLink section={s} on={active?.key === s.key} layout={layout} />
            </li>
          ))}
        </ul>
      </nav>
    </LayoutGroup>
  );
}

function SectionTabs({ section, path }: { section: NavSection; path: string }) {
  const current = tabFor(section, path);
  return (
    <LayoutGroup id="tabs">
      <nav aria-label={`${section.label} pages`} className="no-print mb-8 flex gap-1 overflow-x-auto border-b border-line">
        {(section.tabs ?? []).map((t) => {
          const on = current?.href === t.href;
          return (
            <Link key={t.href} href={t.href} aria-current={on ? "page" : undefined}
              className={`relative flex min-h-11 items-center whitespace-nowrap px-3.5 text-[15px] ${on ? "font-semibold text-ink" : "text-ink-2 hover:text-ink"}`}>
              {t.label}
              {on && <motion.span layoutId="tab-underline" className="absolute inset-x-2 -bottom-px h-[2px] rounded-full bg-ink" />}
            </Link>
          );
        })}
      </nav>
    </LayoutGroup>
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
        <header className="no-print border-b border-line bg-surface">
          <div className="mx-auto flex h-[68px] max-w-[1240px] items-center justify-between px-4 sm:px-8">
            <Wordmark href="/" />
            {me && space
              ? <Link href={space.home} className="text-sm text-ink-2 hover:text-ink">Open your workspace</Link>
              : <Link href="/#journeys" className="text-sm text-ink-2 hover:text-ink">Choose a person</Link>}
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
  const guide = guideState(me.email, guideHidden);
  const showGuide = guide === "shown";
  return (
    <div className="flex min-h-screen flex-col">
      <TopBar me={me} space={space} guideHidden={guide === "hidden"} onShowGuide={() => setGuide(false)} />
      <Rail space={space} active={section} layout="strip" />
      <div className={`flex-1 lg:grid lg:grid-cols-[232px_minmax(0,1fr)] ${showGuide ? "xl:grid-cols-[232px_minmax(0,1fr)_340px]" : ""}`}>
        <Rail space={space} active={section} layout="column" />
        <main className="min-w-0 px-4 py-8 sm:px-8 lg:px-10 lg:py-9">
          {section?.tabs && <SectionTabs section={section} path={path} />}
          {children}
          {guide === "hidden" && (
            <button type="button" onClick={() => setGuide(false)}
              className="no-print mt-10 min-h-11 text-sm text-ink-2 underline decoration-line-strong underline-offset-4 hover:text-ink lg:hidden">
              Show your story
            </button>
          )}
        </main>
        {showGuide && (
          <div className="no-print px-4 pb-12 sm:px-8 lg:col-start-2 lg:px-10 xl:col-start-3 xl:row-start-1 xl:px-0 xl:pr-6 xl:pt-9">
            <div className="xl:sticky xl:top-[92px]">
              <JourneyGuide email={me.email} path={path} onHide={() => setGuide(true)} />
            </div>
          </div>
        )}
      </div>
      <Footer />
    </div>
  );
}
