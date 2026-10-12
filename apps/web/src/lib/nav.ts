export type IconName =
  | "home" | "portfolio" | "markets" | "funds" | "plan" | "leads" | "held" | "form" | "today" | "reconcile" | "approvals"
  | "blotter" | "alerts" | "log";
export type NavTab = { href: string; label: string };
/** A rail item. Its tabs (if any) are shown at the top of each of its pages; `also` lists other paths it owns. */
export type NavSection = { key: string; label: string; href: string; icon: IconName; tabs?: NavTab[]; also?: string[] };
export type WorkspaceKey = "investor" | "advisor" | "operations" | "compliance";
export type Workspace = { key: WorkspaceKey; label: string; home: string; sections: NavSection[] };

export const WORKSPACES: Record<WorkspaceKey, Workspace> = {
  investor: {
    key: "investor", label: "Investor", home: "/investor",
    sections: [
      { key: "home", label: "Home", href: "/investor", icon: "home" },
      { key: "portfolio", label: "Portfolio", href: "/investor/xray", icon: "portfolio",
        tabs: [{ href: "/investor/xray", label: "X-ray" }, { href: "/investor/risk", label: "Risk" }, { href: "/investor/profile", label: "Risk profile" }] },
      { key: "markets", label: "Markets", href: "/investor/markets", icon: "markets",
        tabs: [{ href: "/investor/markets", label: "Markets" }, { href: "/investor/trades", label: "Your trades" }] },
      { key: "funds", label: "Funds", href: "/investor/funds", icon: "funds",
        tabs: [{ href: "/investor/funds", label: "Funds" }, { href: "/investor/orders", label: "Fund orders" }] },
      { key: "plan", label: "Plan ahead", href: "/investor/what-if", icon: "plan" },
    ],
  },
  advisor: {
    key: "advisor", label: "Advisor", home: "/advisor",
    sections: [
      { key: "leads", label: "Leads", href: "/advisor", icon: "leads", also: ["/advisor/leads"] },
      { key: "held", label: "Held orders", href: "/advisor/held", icon: "held" },
      { key: "form", label: "Prospect form", href: "/apply", icon: "form" },
    ],
  },
  operations: {
    key: "operations", label: "Operations", home: "/operations",
    sections: [
      { key: "today", label: "Today", href: "/operations", icon: "today" },
      { key: "reconcile", label: "Reconciliation", href: "/operations/reconciliation", icon: "reconcile" },
      { key: "approvals", label: "Approvals", href: "/operations/approvals", icon: "approvals" },
      { key: "blotter", label: "Blotter", href: "/operations/blotter", icon: "blotter" },
    ],
  },
  compliance: {
    key: "compliance", label: "Compliance", home: "/compliance",
    sections: [
      { key: "alerts", label: "Alerts", href: "/compliance", icon: "alerts", also: ["/compliance/alerts"] },
      { key: "log", label: "Decision log", href: "/compliance/log", icon: "log" },
    ],
  },
};

const ROLE_WORKSPACE: Record<string, WorkspaceKey> = {
  investor: "investor", advisor: "advisor", admin: "advisor", ops: "operations", compliance: "compliance",
};
/** Workspace roots that own only themselves: their other pages belong to other rail items. */
const EXACT = new Set(["/investor", "/advisor", "/operations", "/compliance"]);

/** Each person sees only their own workspace. */
export function workspaceFor(roles: string[]): Workspace | null {
  const key = ROLE_WORKSPACE[roles[0] ?? ""] ?? (roles.includes("staff") ? "advisor" : null);
  return key ? WORKSPACES[key] : null;
}

function under(path: string, href: string): boolean {
  return path === href || path.startsWith(`${href}/`);
}

function owns(path: string, href: string): boolean {
  return EXACT.has(href) ? path === href : under(path, href);
}

export function sectionFor(space: Workspace, path: string): NavSection | null {
  return space.sections.find((s) => [s.href, ...(s.tabs ?? []).map((t) => t.href), ...(s.also ?? [])].some((h) => owns(path, h))) ?? null;
}

export function tabFor(section: NavSection, path: string): NavTab | null {
  const matches = (section.tabs ?? []).filter((t) => owns(path, t.href));
  return matches.sort((a, b) => b.href.length - a.href.length)[0] ?? null;
}

const PUBLIC_PATHS = ["/login", "/apply"];

export function routeKind(path: string): "front" | "public" | "app" {
  if (path === "/") return "front";
  return PUBLIC_PATHS.some((p) => under(path, p)) ? "public" : "app";
}

/** Where the front door's buttons go: a signed-in person goes home; with real sign-in, anyone else signs in first.
 *  Null means persona sign-in proceeds. */
export function entryRoute(authMode: "dev" | "firebase", signedInHome: string | null): string | null {
  if (authMode === "dev") return null;
  return signedInHome ?? "/login";
}
