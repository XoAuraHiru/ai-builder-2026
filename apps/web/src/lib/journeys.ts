/** Each persona's story: three or four steps, each a page to visit. A step is done once its page has been seen. */
export type JourneyStep = { title: string; detail: string; href: string; action: string; match?: string };
export type Journey = { email: string; title: string; intro: string; steps: JourneyStep[] };

export const JOURNEYS: Journey[] = [
  { email: "priya@atrium.demo", title: "Priya's story", intro: "A balanced investor whose portfolio took on more risk than Priya chose.",
    steps: [
      { title: "See the drift", detail: "Home shows your risk profile and your portfolio side by side.", href: "/investor", action: "Open Home" },
      { title: "Test 10,000 futures", detail: "Plan ahead replays markets since 2007 to show the range of outcomes.", href: "/investor/what-if", action: "Open Plan ahead" },
      { title: "Try buying 60 NVIDIA shares", detail: "The Pre-trade Guardian holds the order for an advisor and says why.", href: "/investor/markets/NVDA", action: "Open NVIDIA" },
      { title: "Stress-test your portfolio", detail: "Replay 2008, 2020 and 2022 on what you hold, or describe your own scenario.", href: "/investor/scenarios", action: "Open Scenarios" },
    ] },
  { email: "lucas@atrium.demo", title: "Lucas's story", intro: "A growth investor who owns more NVIDIA than Lucas thinks.",
    steps: [
      { title: "See the X-ray", detail: "Look-through finds one company behind six of your ETFs.", href: "/investor/xray", action: "Open the X-ray" },
      { title: "Buy more NVIDIA", detail: "The Guardian counts the shares you already hold through funds.", href: "/investor/markets/NVDA", action: "Open NVIDIA" },
      { title: "Read your risk report", detail: "Volatility, drawdown and what drives them.", href: "/investor/risk", action: "Open Risk" },
    ] },
  { email: "tom@atrium.demo", title: "Tom's story", intro: "An investor whose large sale looks like an account takeover.",
    steps: [
      { title: "See what you hold", detail: "120 Tesla shares and two funds.", href: "/investor", action: "Open Home" },
      { title: "Sell all 120 Tesla shares", detail: "From a browser Atrium has never seen, the Guardian holds the sale.", href: "/investor/markets/TSLA", action: "Open Tesla" },
      { title: "Read why it was held", detail: "Your trades list the trust signals behind the hold.", href: "/investor/trades", action: "Open Your trades" },
    ] },
  { email: "hana@atrium.demo", title: "Hana's story", intro: "An investor about to trip the wash-sale rule.",
    steps: [
      { title: "See your PepsiCo sale", detail: "Sold at a loss less than three weeks ago.", href: "/investor/trades", action: "Open Your trades" },
      { title: "Buy PepsiCo again", detail: "The Guardian warns that the loss may not count for tax.", href: "/investor/markets/PEP", action: "Open PepsiCo" },
      { title: "Ask Atrium", detail: "Ask what a wash sale is and what it means for you.", href: "/investor/copilot", action: "Ask Atrium" },
    ] },
  { email: "daniel@atrium.demo", title: "Daniel's story", intro: "An advisor whose pipeline hides three fraud stories among real prospects.",
    steps: [
      { title: "Spot the ring", detail: "Four leads from one device, each with a throwaway email address.", href: "/advisor", action: "Open Leads" },
      { title: "Review a client call", detail: "Open Ruth Alvarez and analyse the pressure call: each flag quotes the call and gives the second it was said.", href: "/advisor", match: "^/advisor/leads/[^/]+$", action: "Open Leads" },
      { title: "Write a proposal", detail: "Gemini Pro writes it from the client's answers and the fund documents.", href: "/advisor", match: "^/advisor/leads/[^/]+/proposal$", action: "Open Leads" },
      { title: "Decide a held order", detail: "Release or reject an order the Guardian held.", href: "/advisor/held", action: "Open Held orders" },
    ] },
  { email: "mei@atrium.demo", title: "Mei's story", intro: "Matching today's payments, with an agent doing the fiddly ones.",
    steps: [
      { title: "Reconcile today's statement", detail: "Read the sample statement, find matches and decide them.", href: "/operations/reconciliation", action: "Open Reconciliation" },
      { title: "Run the day-end", detail: "Draft today's prices and ask for them to be published.", href: "/operations", action: "Open Today" },
      { title: "Follow an instruction", detail: "The blotter shows every step from received to settled.", href: "/operations/blotter", action: "Open Blotter" },
    ] },
  { email: "sam@atrium.demo", title: "Sam's story", intro: "The second pair of eyes: nothing changes the books on one person's word.",
    steps: [
      { title: "Approve a request", detail: "Use the code from the demo authenticator. You cannot approve your own.", href: "/operations/approvals", action: "Open Approvals" },
      { title: "Decide the agent's matches", detail: "Accept or reject what the reconciliation agent proposed.", href: "/operations/reconciliation", action: "Open Reconciliation" },
    ] },
  { email: "omar@atrium.demo", title: "Omar's story", intro: "Deciding alerts, finding fraud rings across the whole lifecycle, and governing every model.",
    steps: [
      { title: "Review an alert", detail: "Open any alert: its evidence, who is linked, and a Gemini Pro case review.", href: "/compliance", match: "^/compliance/alerts/", action: "Open Alerts" },
      { title: "Look at a fraud ring", detail: "Four identities and a client account joined by one device, explained by Gemini.", href: "/compliance/rings", action: "Open Fraud rings" },
      { title: "Check the models", detail: "Every model's validation, the red team's attacks, the fair-lending check and the breakers.", href: "/compliance/models", match: "^/compliance/models", action: "Open Models" },
      { title: "Open the decision log", detail: "Every AI decision with its model and cost.", href: "/compliance/log", action: "Open the log" },
    ] },
];

export function journeyFor(email: string | null | undefined): Journey | null {
  const wanted = (email ?? "").trim().toLowerCase();
  return JOURNEYS.find((j) => j.email === wanted) ?? null;
}

export function stepMatches(step: JourneyStep, path: string): boolean {
  return step.match ? new RegExp(step.match).test(path) : path === step.href;
}

export function progress(journey: Journey, visited: string[]): { done: boolean[]; current: number | null; count: number } {
  const done = journey.steps.map((s) => visited.some((v) => stepMatches(s, v)));
  const next = done.indexOf(false);
  return { done, current: next === -1 ? null : next, count: done.filter(Boolean).length };
}

export function addVisit(visited: string[], path: string): string[] {
  return visited.includes(path) ? visited : [...visited, path].slice(-60);
}

const key = (email: string) => `atrium.journey.${email.trim().toLowerCase()}`;

export function loadVisits(email: string): string[] {
  try {
    const raw = localStorage.getItem(key(email));
    const value: unknown = raw ? JSON.parse(raw) : [];
    return Array.isArray(value) ? value.filter((v): v is string => typeof v === "string") : [];
  } catch {
    return [];
  }
}

export function saveVisits(email: string, visits: string[]): void {
  try {
    localStorage.setItem(key(email), JSON.stringify(visits));
  } catch {
    // Storage blocked: the guide still works for this page view.
  }
}

const hiddenKey = (email: string) => `atrium.guide.hidden.${email.trim().toLowerCase()}`;

/** Whether this person hid their guide. Each person has their own choice; blocked storage means shown. */
export function loadGuideHidden(email: string): boolean {
  try {
    return localStorage.getItem(hiddenKey(email)) === "1";
  } catch {
    return false;
  }
}

export function saveGuideHidden(email: string, hidden: boolean): void {
  try {
    localStorage.setItem(hiddenKey(email), hidden ? "1" : "0");
  } catch {
    // Storage blocked: the choice lasts for this page view.
  }
}

/** What the shell does with the guide: show it, offer to bring it back, or leave no trace (no journey). */
export function guideState(email: string, hidden: boolean): "shown" | "hidden" | "none" {
  if (journeyFor(email) === null) return "none";
  return hidden ? "hidden" : "shown";
}
