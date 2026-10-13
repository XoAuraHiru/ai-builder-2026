export type Act = "acquire" | "invest" | "trade" | "operate";
export type ActInfo = { key: Act; number: number; label: string; line: string; ai: string };

/** Atrium's four stages, in the order a client meets them. */
export const ACTS: ActInfo[] = [
  { key: "acquire", number: 1, label: "Acquire", line: "Every lead scored for fit and for fraud before an advisor calls.", ai: "Lead Score and Trust Score" },
  { key: "invest", number: 2, label: "Invest", line: "Portfolios tested against 10,000 futures drawn from real markets since 2007.", ai: "What-if Studio and Copilot" },
  { key: "trade", number: 3, label: "Trade", line: "Every order checked before it reaches the market, and held when it looks wrong.", ai: "Pre-trade Guardian" },
  { key: "operate", number: 4, label: "Operate", line: "Statements reconciled, alerts reviewed, and two people for every change to the books.", ai: "Reconciliation agent and case reviews" },
];

export type Persona = {
  email: string; name: string; role: "Investor" | "Advisor" | "Operations" | "Compliance"; act: Act; home: string;
  story: string; tries: string[]; start?: boolean;
};

/** The demo's eight people. Every one of them is synthetic. */
export const PERSONAS: Persona[] = [
  { email: "daniel@atrium.demo", name: "Daniel Okafor", role: "Advisor", act: "acquire", home: "/advisor",
    story: "Works a pipeline of new leads. Three of them are fraud stories the Trust Score catches.",
    tries: ["Open a lead marked high risk and read why", "Turn a clean lead into a Gemini Pro proposal"] },
  { email: "priya@atrium.demo", name: "Priya Raman", role: "Investor", act: "invest", home: "/investor", start: true,
    story: "A balanced portfolio that has quietly drifted above the risk Priya signed up for.",
    tries: ["See the drift, then test 10,000 futures", "Try buying 60 NVIDIA shares"] },
  { email: "lucas@atrium.demo", name: "Lucas Moreau", role: "Investor", act: "invest", home: "/investor/xray",
    story: "Owns about a tenth of NVIDIA without knowing it, through six different ETFs.",
    tries: ["Open the Portfolio X-ray", "Buy more NVIDIA and meet the concentration check"] },
  { email: "tom@atrium.demo", name: "Tom Becker", role: "Investor", act: "trade", home: "/investor",
    story: "Holds 120 Tesla shares. Selling them all from a browser Atrium has never seen looks like a takeover.",
    tries: ["Sell all 120 Tesla shares", "Read the trust signals behind the hold"] },
  { email: "hana@atrium.demo", name: "Hana Sato", role: "Investor", act: "trade", home: "/investor/trades",
    story: "Sold PepsiCo at a loss less than three weeks ago, and wants it back.",
    tries: ["Buy PepsiCo again", "Read the wash-sale warning"] },
  { email: "mei@atrium.demo", name: "Mei Tanaka", role: "Operations", act: "operate", home: "/operations/reconciliation",
    story: "Matches the money that arrived at the bank with the subscriptions waiting for it.",
    tries: ["Read a bank statement with Document AI", "Let the agent match a typo and a split payment"] },
  { email: "sam@atrium.demo", name: "Sam Ortiz", role: "Operations", act: "operate", home: "/operations/approvals",
    story: "The second pair of eyes on every price, manual match and reversal.",
    tries: ["Approve Mei's request with a one-time code", "Try approving your own: you can't"] },
  { email: "omar@atrium.demo", name: "Omar Haddad", role: "Compliance", act: "operate", home: "/compliance",
    story: "Decides every anti-money-laundering alert, with the rows behind it.",
    tries: ["Open the structuring alert", "Ask Gemini Pro for a cited case review"] },
];

export function personaFor(email: string | null | undefined): Persona | null {
  const wanted = (email ?? "").trim().toLowerCase();
  return PERSONAS.find((p) => p.email === wanted) ?? null;
}

export function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

/** The stage a person works in: their persona's, or one that fits their role. */
export function actFor(email: string | null | undefined, roles: string[]): Act {
  const persona = personaFor(email);
  if (persona) return persona.act;
  if (roles.includes("investor")) return "invest";
  if (roles.includes("advisor") || roles.includes("admin")) return "acquire";
  return "operate";
}

export function personasByAct(): { act: ActInfo; people: Persona[] }[] {
  return ACTS.map((act) => ({ act, people: PERSONAS.filter((p) => p.act === act.key) }));
}
