import { describe, expect, it } from "vitest";
import { arrivals, badgeText, bellLabel, fromDoc, isGemini, marker, ordered, relativeTime, STAGES, unreadCount, type InboxItem } from "./inbox";

const NOW = new Date("2026-10-18T15:00:00Z");

function item(id: string, minutesAgo: number | null, more: Partial<InboxItem> = {}): InboxItem {
  return {
    id, kind: "order_held", stage: "trade", title: `Notice ${id}`, body: "Held for an advisor's review: suitability.",
    href: "/advisor/held", severity: "attention", actor: "Pre-trade Guardian", read: false,
    createdAt: minutesAgo === null ? null : new Date(NOW.getTime() - minutesAgo * 60_000), ...more,
  };
}

describe("reading Firestore documents", () => {
  it("turns a document into an item, reading the server's timestamp", () => {
    const stamp = { toDate: () => new Date("2026-10-18T14:56:00Z") };
    const read = fromDoc("order_held-1", {
      kind: "order_held", stage: "trade", title: "Tom Becker's sale of 120 TSLA is held", body: "Possible account takeover.",
      href: "/advisor/held", severity: "urgent", actor: "Pre-trade Guardian", read: false, created_at: stamp,
    });
    expect(read).toEqual({
      id: "order_held-1", kind: "order_held", stage: "trade", title: "Tom Becker's sale of 120 TSLA is held",
      body: "Possible account takeover.", href: "/advisor/held", severity: "urgent", actor: "Pre-trade Guardian",
      read: false, createdAt: new Date("2026-10-18T14:56:00Z"),
    });
  });
  it("follows only the app's own routes, and fills in what an older document lacks", () => {
    expect(fromDoc("x", { title: "Away", href: "https://example.test/phish" })).toBeNull();
    expect(fromDoc("x", { title: "Away", href: "//example.test" })).toBeNull();
    expect(fromDoc("x", { title: "", href: "/operations" })).toBeNull();
    const sparse = fromDoc("x", { title: "Day-end finished", href: "/operations", stage: "later", severity: "loud", read: "yes" })!;
    expect([sparse.stage, sparse.severity, sparse.read, sparse.createdAt, sparse.body]).toEqual(["operate", "info", false, null, ""]);
  });
});

describe("the inbox list", () => {
  it("puts the newest first, and an item still waiting for its server time before all of them", () => {
    const list = ordered([item("old", 60), item("pending", null), item("new", 2)]);
    expect(list.map((i) => i.id)).toEqual(["pending", "new", "old"]);
  });
  it("counts what is unread, and the badge stops at 9+", () => {
    expect(unreadCount([item("a", 1), item("b", 2, { read: true }), item("c", 3)])).toBe(2);
    expect([badgeText(3), badgeText(9), badgeText(12)]).toEqual(["3", "9", "9+"]);
    expect([bellLabel(0), bellLabel(2)]).toEqual(["Inbox, nothing unread", "Inbox, 2 unread"]);
  });
  it("says when, briefly", () => {
    const ago = (minutes: number) => new Date(NOW.getTime() - minutes * 60_000);
    expect(relativeTime(null, NOW)).toBe("just now");
    expect(relativeTime(ago(0.5), NOW)).toBe("just now");
    expect(relativeTime(new Date(NOW.getTime() + 20_000), NOW)).toBe("just now");
    expect(relativeTime(ago(4), NOW)).toBe("4 min ago");
    expect(relativeTime(ago(135), NOW)).toBe("2 hr ago");
    expect(relativeTime(ago(30 * 60), NOW)).toBe("yesterday");
    expect(relativeTime(ago(3 * 24 * 60), NOW)).toBe("3 days ago");
    expect(relativeTime(new Date("2026-09-01T12:00:00Z"), NOW)).toBe("Sep 1");
    expect(relativeTime(new Date("2025-09-01T12:00:00Z"), NOW)).toBe("Sep 1, 2025");
  });
});

describe("what counts as arriving", () => {
  it("brings nothing on the first snapshot: that is the inbox as the page found it", () => {
    expect(arrivals(null, [item("a", 1), item("b", 2)])).toEqual([]);
  });
  it("brings items that are new, or sent again with a fresh time, newest first", () => {
    const before = [item("a", 10), item("b", 20)];
    const after = [item("c", 0), item("a", 10, { read: true }), item("b", 1), item("d", 0.5, { read: true })];
    expect(arrivals(before, after).map((i) => i.id)).toEqual(["c", "b"]);
  });
  it("does not count marking an item read as an arrival", () => {
    const before = [item("a", 3)];
    expect(arrivals(before, [item("a", 3, { read: true })])).toEqual([]);
  });
});

describe("markers", () => {
  it("gives each stage its workspace icon and tints by the signal, not the stage", () => {
    expect(marker({ stage: "acquire", severity: "urgent" })).toEqual({ icon: "leads", stage: "Acquire", tile: "bg-coral-50 text-coral-700", signal: "Urgent" });
    expect(marker({ stage: "operate", severity: "attention" }).tile).toBe("bg-amber-50 text-amber-800");
    expect(marker({ stage: "govern", severity: "info" })).toMatchObject({ icon: "models", tile: "bg-fill text-ink-700" });
    expect(Object.keys(STAGES)).toEqual(["acquire", "invest", "trade", "operate", "govern"]);
    for (const { icon } of Object.values(STAGES)) expect(icon).toMatch(/^[a-z]+$/);
  });
  it("keeps violet for Gemini alone", () => {
    expect([isGemini("Gemini"), isGemini(" gemini "), isGemini("Day-end"), isGemini("Daniel Okafor")]).toEqual([true, true, false, false]);
  });
});
