import type { IconName } from "./nav";

/** The live inbox: what each person should know, written by the API to Firestore (people/{id}/inbox) and read here
 *  as it changes. Items are plain data; lib/inbox-live.ts does the listening and the writing back. */
export type Stage = "acquire" | "invest" | "trade" | "operate" | "govern";
export type Severity = "info" | "attention" | "urgent";
export type InboxItem = {
  id: string; kind: string; stage: Stage; title: string; body: string; href: string; severity: Severity; actor: string;
  read: boolean; createdAt: Date | null; // null only while Firestore's server timestamp is on its way
};

/** Each stage keeps the icon its workspace uses for the same work. */
export const STAGES: Record<Stage, { label: string; icon: IconName }> = {
  acquire: { label: "Acquire", icon: "leads" },
  invest: { label: "Invest", icon: "portfolio" },
  trade: { label: "Trade", icon: "markets" },
  operate: { label: "Operate", icon: "approvals" },
  govern: { label: "Govern", icon: "models" },
};

/** The marker's tint is the signal, as in Notice and KeyMoment: coral for holds, fraud and alerts that need someone
 *  now, amber for what waits on a person, sand for news. Green stays for unread and action, violet for Gemini. */
export const SEVERITY: Record<Severity, { label: string; tile: string }> = {
  urgent: { label: "Urgent", tile: "bg-coral-50 text-coral-700" },
  attention: { label: "Needs a look", tile: "bg-amber-50 text-amber-800" },
  info: { label: "For your information", tile: "bg-fill text-ink-700" },
};

export function marker(item: Pick<InboxItem, "stage" | "severity">): { icon: IconName; stage: string; tile: string; signal: string } {
  const stage = STAGES[item.stage] ?? STAGES.operate;
  const severity = SEVERITY[item.severity] ?? SEVERITY.info;
  return { icon: stage.icon, stage: stage.label, tile: severity.tile, signal: severity.label };
}

/** A Firestore Timestamp (anything with toDate), a Date, or nothing yet. */
function toDate(value: unknown): Date | null {
  if (value instanceof Date) return value;
  if (value && typeof (value as { toDate?: unknown }).toDate === "function") return (value as { toDate: () => Date }).toDate();
  return null;
}

/** A document as an item, or null if it is not one. Only app routes are followed, never another site. */
export function fromDoc(id: string, data: Record<string, unknown>): InboxItem | null {
  const text = (v: unknown) => (typeof v === "string" ? v.trim() : "");
  const title = text(data.title);
  const href = text(data.href);
  if (!id || !title || !href.startsWith("/") || href.startsWith("//")) return null;
  const stage = (text(data.stage) in STAGES ? text(data.stage) : "operate") as Stage;
  const severity = (text(data.severity) in SEVERITY ? text(data.severity) : "info") as Severity;
  return { id, kind: text(data.kind), stage, title, body: text(data.body), href, severity, actor: text(data.actor),
           read: data.read === true, createdAt: toDate(data.created_at) };
}

/** Newest first; an item still waiting for its server time is the newest of all. */
export function ordered(items: InboxItem[]): InboxItem[] {
  const at = (i: InboxItem) => i.createdAt?.getTime() ?? Number.POSITIVE_INFINITY;
  return [...items].sort((a, b) => at(b) - at(a) || a.id.localeCompare(b.id));
}

export function unreadCount(items: InboxItem[]): number {
  return items.filter((i) => !i.read).length;
}

/** The unread count as the badge shows it. */
export function badgeText(count: number): string {
  return count > 9 ? "9+" : String(count);
}

export function bellLabel(count: number): string {
  return count === 0 ? "Inbox, nothing unread" : `Inbox, ${count} unread`;
}

/** What arrived since the last snapshot: items that are new, or that the API sent again (a fresh time). The first
 *  snapshot is the inbox as it was when the page opened, so it brings nothing (previous is null). */
export function arrivals(previous: InboxItem[] | null, next: InboxItem[]): InboxItem[] {
  if (previous === null) return [];
  const seen = new Map(previous.map((i) => [i.id, i.createdAt?.getTime() ?? null]));
  return ordered(next.filter((i) => !i.read && (!seen.has(i.id) || seen.get(i.id) !== (i.createdAt?.getTime() ?? null))));
}

/** Only Gemini's own work wears violet. */
export function isGemini(actor: string): boolean {
  return actor.trim().toLowerCase() === "gemini";
}

/** "just now", "4 min ago", "2 hr ago", "yesterday", "3 days ago", then the date. */
export function relativeTime(at: Date | null, now: Date = new Date()): string {
  if (!at) return "just now";
  const minutes = Math.floor((now.getTime() - at.getTime()) / 60_000);
  if (minutes < 1) return "just now";  // also a clock a little ahead of this one
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} hr ago`;
  if (hours < 48) return "yesterday";
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days} days ago`;
  const sameYear = at.getFullYear() === now.getFullYear();
  return at.toLocaleDateString("en-US", { month: "short", day: "numeric", ...(sameYear ? {} : { year: "numeric" }) });
}
