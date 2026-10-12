export type NavLink = { href: string; label: string };
export type WorkspaceKey = "investor" | "advisor" | "operations" | "compliance";
export type Workspace = { key: WorkspaceKey; label: string; home: string; links: NavLink[] };

export const WORKSPACES: Record<WorkspaceKey, Workspace> = {
  investor: {
    key: "investor", label: "Investor", home: "/investor",
    links: [
      { href: "/investor", label: "Overview" },
      { href: "/investor/markets", label: "Markets" },
      { href: "/investor/trades", label: "Trades" },
      { href: "/investor/what-if", label: "What-if Studio" },
      { href: "/investor/xray", label: "Portfolio X-ray" },
      { href: "/investor/risk", label: "Risk" },
      { href: "/investor/funds", label: "Funds" },
      { href: "/investor/orders", label: "Fund orders" },
      { href: "/investor/copilot", label: "Copilot" },
      { href: "/investor/profile", label: "Risk profile" },
    ],
  },
  advisor: {
    key: "advisor", label: "Advisor", home: "/advisor",
    links: [
      { href: "/advisor", label: "Lead pipeline" },
      { href: "/advisor/held", label: "Held orders" },
      { href: "/apply", label: "Prospect form" },
    ],
  },
  operations: {
    key: "operations", label: "Operations", home: "/operations",
    links: [
      { href: "/operations", label: "Day-end" },
      { href: "/operations/reconciliation", label: "Reconciliation" },
      { href: "/operations/approvals", label: "Approvals" },
      { href: "/operations/blotter", label: "Blotter" },
    ],
  },
  compliance: {
    key: "compliance", label: "Compliance", home: "/compliance",
    links: [
      { href: "/compliance", label: "Alerts" },
      { href: "/compliance/log", label: "Decision log" },
    ],
  },
};

const STAFF_HOME: Record<string, WorkspaceKey> = { advisor: "advisor", admin: "advisor", ops: "operations", compliance: "compliance" };
const STAFF_ORDER: WorkspaceKey[] = ["advisor", "operations", "compliance"];

/** Investors see their own workspace; staff see the staff workspaces with their own first. */
export function workspacesFor(roles: string[]): Workspace[] {
  if (roles.includes("staff")) {
    const own = STAFF_HOME[roles[0]] ?? "advisor";
    return [own, ...STAFF_ORDER.filter((k) => k !== own)].map((k) => WORKSPACES[k]);
  }
  if (roles.includes("investor")) return [WORKSPACES.investor];
  return [];
}

export function isActive(path: string, href: string): boolean {
  if (href === "/advisor") return path === href || path.startsWith("/advisor/leads");
  if (href === "/compliance") return path === href || path.startsWith("/compliance/alerts");
  if (href === "/investor" || href === "/operations") return path === href;
  return path === href || path.startsWith(`${href}/`);
}

export const PUBLIC_PATHS = ["/login", "/apply"];

export function isPublic(path: string): boolean {
  return PUBLIC_PATHS.some((p) => path === p || path.startsWith(`${p}/`));
}
