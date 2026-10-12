"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { AnimatePresence, LayoutGroup, motion } from "motion/react";
import type { Me } from "@/lib/api";
import { isActive, isPublic, workspacesFor, type Workspace } from "@/lib/nav";
import { useSession } from "@/lib/session-context";
import { Loading, Notice } from "@/components/ui";

const ROLE_LABEL: Record<string, string> = {
  investor: "Investor", advisor: "Advisor", ops: "Operations", compliance: "Compliance", admin: "Administrator",
};

/** The Atrium mark: a building seen from above, with daylight falling into its central well. */
export function AtriumMark({ size = 20 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 20 20" aria-hidden="true">
      <rect x="1" y="1" width="18" height="18" rx="2" fill="none" stroke="currentColor" strokeWidth="1.25" />
      <rect x="6.5" y="6.5" width="7" height="7" rx="0.5" fill="var(--color-daylight)" />
    </svg>
  );
}

function Wordmark({ href }: { href: string }) {
  return (
    <Link href={href} className="wide flex items-center gap-2 text-[17px] font-semibold tracking-[-0.01em]">
      <AtriumMark />
      Atrium
    </Link>
  );
}

function Footer() {
  return (
    <footer className="no-print mx-auto max-w-[1120px] px-4 pb-10 pt-6 text-xs text-muted sm:px-8">
      Prototype with synthetic people and paper trading. Projections are simulations, not forecasts, and nothing here
      is investment advice.
    </footer>
  );
}

function WorkspaceNav({ spaces, path, group }: { spaces: Workspace[]; path: string; group: string }) {
  return (
    <LayoutGroup id={group}>
      <nav aria-label="Workspaces" className="space-y-6">
        {spaces.map((w) => (
          <div key={w.key}>
            <p className="px-3 pb-1.5 text-xs font-medium text-muted">{w.label} workspace</p>
            <ul>
              {w.links.map((l) => {
                const active = isActive(path, l.href);
                return (
                  <li key={l.href}>
                    <Link href={l.href} aria-current={active ? "page" : undefined}
                      className={`relative flex items-center rounded-control px-3 py-1.5 text-[14px] ${active ? "font-medium text-ink" : "text-ink-2 hover:text-ink"}`}>
                      {active && <motion.span layoutId="nav-active" className="absolute inset-0 rounded-control bg-ground" />}
                      {active && <motion.span layoutId="nav-active-bar" className="absolute bottom-1.5 left-0 top-1.5 w-[2px] rounded-full bg-ink" />}
                      <span className="relative">{l.label}</span>
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </nav>
    </LayoutGroup>
  );
}

function Persona({ me }: { me: Me }) {
  return (
    <div className="border-t border-line px-5 py-4">
      <p className="truncate text-sm font-medium">{me.full_name ?? me.email}</p>
      <p className="text-xs text-muted">{ROLE_LABEL[me.roles[0]] ?? me.roles[0]}</p>
      <Link href="/login" className="mt-2 inline-block text-xs text-ink-2 underline decoration-line-strong underline-offset-4 hover:text-ink">
        Switch persona
      </Link>
    </div>
  );
}

export function Shell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const router = useRouter();
  const { me, status, error } = useSession();
  const [menuOpen, setMenuOpen] = useState(false);
  const publicRoute = isPublic(path);

  useEffect(() => {
    if (status === "signed-out" && !publicRoute) router.replace("/login");
  }, [status, publicRoute, router]);
  useEffect(() => {
    setMenuOpen(false);
  }, [path]);

  const spaces = me ? workspacesFor(me.roles) : [];

  if (publicRoute || !me || spaces.length === 0) {
    return (
      <div className="min-h-screen">
        <header className="no-print border-b border-line bg-surface">
          <div className="mx-auto flex max-w-[1120px] items-center justify-between px-4 py-3.5 sm:px-8">
            <Wordmark href={spaces[0]?.home ?? "/login"} />
            {me && spaces.length > 0 && (
              <Link href={spaces[0].home} className="text-sm text-ink-2 hover:text-ink">Open your workspace</Link>
            )}
          </div>
        </header>
        <main className="mx-auto max-w-[1120px] px-4 py-8 sm:px-8 lg:py-12">
          {publicRoute ? children
            : status === "error" ? <Notice tone="error" title="Atrium is unavailable">{error}</Notice>
            : me && spaces.length === 0 ? <Notice tone="caution" title="This persona has no workspace">Switch to another persona.</Notice>
            : <Loading label="Opening your workspace" />}
        </main>
        <Footer />
      </div>
    );
  }

  const home = spaces[0].home;
  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[240px_minmax(0,1fr)]">
      <aside className="no-print hidden border-r border-line bg-surface lg:sticky lg:top-0 lg:flex lg:h-screen lg:flex-col">
        <div className="px-5 py-5"><Wordmark href={home} /></div>
        <div className="flex-1 overflow-y-auto px-2 pb-4"><WorkspaceNav spaces={spaces} path={path} group="rail" /></div>
        <Persona me={me} />
      </aside>
      <div className="min-w-0">
        <header className="no-print sticky top-0 z-30 flex items-center justify-between border-b border-line bg-surface px-4 py-3 lg:hidden">
          <Wordmark href={home} />
          <button type="button" onClick={() => setMenuOpen((o) => !o)} aria-expanded={menuOpen} aria-controls="mobile-nav"
            className="rounded-control border border-line-strong px-3 py-1.5 text-sm">
            {menuOpen ? "Close" : "Menu"}
          </button>
        </header>
        <AnimatePresence>
          {menuOpen && (
            <motion.div id="mobile-nav" initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }}
              className="no-print fixed inset-x-0 top-[57px] z-20 max-h-[calc(100vh-57px)] overflow-y-auto border-b border-line bg-surface pt-4 shadow-[0_16px_32px_-16px_rgba(23,32,42,0.3)] lg:hidden">
              <div className="px-2 pb-2"><WorkspaceNav spaces={spaces} path={path} group="sheet" /></div>
              <Persona me={me} />
            </motion.div>
          )}
        </AnimatePresence>
        <main className="mx-auto max-w-[1120px] px-4 py-8 sm:px-8 lg:py-10">{children}</main>
        <Footer />
      </div>
    </div>
  );
}
