"use client";

import Link from "next/link";
import { useCallback, useEffect, useId, useRef, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { arrivals, badgeText, bellLabel, isGemini, marker, ordered, relativeTime, unreadCount, type InboxItem } from "@/lib/inbox";
import { inboxUnavailable, listen, markRead, openInbox, type InboxSession } from "@/lib/inbox-live";
import { Icon } from "@/components/icons";
import { EASE } from "@/components/motion";
import { Button, Sparkle } from "@/components/ui";

const TOAST_MS = 6000;
const MotionLink = motion.create(Link);

type Arrival = { items: InboxItem[]; key: number };
type Live = { on: boolean; items: InboxItem[]; arrived: Arrival | null };
const OFF: Live = { on: false, items: [], arrived: null };

/** The signed-in person's inbox, live from Firestore. It listens again when the person changes and stays off, quietly,
 *  when the inbox is not configured or anything on the way fails. */
function useLiveInbox(personId: string | null) {
  const [live, setLive] = useState<Live>(OFF);
  const session = useRef<InboxSession | null>(null);

  useEffect(() => {
    if (!personId) return;
    let cancelled = false;
    let stop: (() => void) | null = null;
    let confirmed: InboxItem[] | null = null; // the last snapshot the server confirmed; the first is the page's start
    openInbox().then(async (opened) => {
      if (cancelled || !opened) return;
      session.current = opened;
      const unsubscribe = await listen(opened, (items, fromCache) => {
        const fresh = fromCache ? [] : arrivals(confirmed, items);
        if (!fromCache) confirmed = items;
        setLive((prev) => ({
          on: true, items: ordered(items),
          arrived: fresh.length ? { items: fresh, key: (prev.arrived?.key ?? 0) + 1 } : prev.arrived,
        }));
      }, (error) => {
        inboxUnavailable(error);
        setLive(OFF);
      });
      if (cancelled) unsubscribe();
      else stop = unsubscribe;
    }).catch(inboxUnavailable);
    return () => {
      cancelled = true;
      stop?.();
      session.current = null;
      setLive(OFF);
    };
  }, [personId]);

  const read = useCallback((ids: string[]) => {
    if (session.current && ids.length) markRead(session.current, ids).catch(inboxUnavailable);
  }, []);
  return { ...live, read };
}

/** A clock for "4 min ago" that moves on while it is on screen. */
function useNow(running: boolean): Date {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    if (!running) return;
    setNow(new Date());
    const every = setInterval(() => setNow(new Date()), 30_000);
    return () => clearInterval(every);
  }, [running]);
  return now;
}

function BellIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"
      strokeLinejoin="round" aria-hidden="true">
      <path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9" /><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0" />
    </svg>
  );
}

/** The stage's icon on a tile tinted by the signal. */
function Marker({ item, size = "sm" }: { item: InboxItem; size?: "sm" | "md" }) {
  const m = marker(item);
  return (
    <span aria-hidden="true" className={`mt-0.5 flex shrink-0 items-center justify-center rounded-tile ${size === "md" ? "h-9 w-9" : "h-8 w-8"} ${m.tile}`}>
      <Icon name={m.icon} size={size === "md" ? 17 : 16} />
    </span>
  );
}

/** Who did it, the stage and when. Gemini's own work is the one actor in violet. */
function Meta({ item, now }: { item: InboxItem; now: Date }) {
  const gemini = isGemini(item.actor);
  return (
    <span className="mt-1 flex flex-wrap items-center gap-x-1.5 text-xs text-ink-500">
      {item.actor && (
        <span className={gemini ? "inline-flex items-center gap-1 font-medium text-ai-700" : ""}>{gemini && <Sparkle size={11} />}{item.actor}</span>
      )}
      {item.actor && <span aria-hidden="true">·</span>}
      <span>{marker(item).stage}</span>
      <span aria-hidden="true">·</span>
      <time dateTime={item.createdAt?.toISOString()}>{relativeTime(item.createdAt, now)}</time>
    </span>
  );
}

function Row({ item, now, onOpen }: { item: InboxItem; now: Date; onOpen: () => void }) {
  return (
    <Link href={item.href} onClick={onOpen} className="flex gap-3 rounded-control px-3 py-2.5 hover:bg-fill">
      <Marker item={item} />
      <span className="min-w-0 flex-1">
        <span className="flex items-start justify-between gap-3">
          <span className={`text-[13px] leading-[18px] ${item.read ? "font-medium text-ink-700" : "font-semibold text-ink-900"}`}>
            {!item.read && <span className="sr-only">Unread: </span>}{item.title}
          </span>
          {!item.read && <span aria-hidden="true" className="mt-[5px] h-2 w-2 shrink-0 rounded-full bg-green-500" />}
        </span>
        {item.body && <span className="mt-0.5 line-clamp-2 text-[13px] leading-[18px] text-ink-700">{item.body}</span>}
        <Meta item={item} now={now} />
      </span>
    </Link>
  );
}

/** The bell in the top bar: the unread count, and the inbox as a popover. */
function Bell({ items, onRead }: { items: InboxItem[]; onRead: (ids: string[]) => void }) {
  const [open, setOpen] = useState(false);
  const [place, setPlace] = useState({ shift: 0, width: 400 });
  const box = useRef<HTMLDivElement>(null);
  const bell = useRef<HTMLButtonElement>(null);
  const panel = useRef<HTMLDivElement>(null);
  const panelId = useId();
  const reduce = useReducedMotion();
  const unread = unreadCount(items);
  const now = useNow(open);
  // The badge pops when the count rises, never when it falls or on first sight.
  const [counted, setCounted] = useState(unread);
  const [pop, setPop] = useState(0);
  if (unread !== counted) {
    setCounted(unread);
    if (unread > counted) setPop(pop + 1);
  }

  useEffect(() => {
    if (!open) return;
    panel.current?.focus();
    const close = (e: MouseEvent) => { if (box.current && !box.current.contains(e.target as Node)) setOpen(false); };
    const esc = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      setOpen(false);
      bell.current?.focus();
    };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", esc);
    return () => { document.removeEventListener("mousedown", close); document.removeEventListener("keydown", esc); };
  }, [open]);

  function toggle() {
    if (!open && box.current) {
      // The panel hangs from the bell's right edge; on a narrow screen it moves right so it never leaves the page.
      const width = Math.min(400, document.documentElement.clientWidth - 24);
      setPlace({ width, shift: Math.max(0, 12 + width - box.current.getBoundingClientRect().right) });
    }
    setOpen((v) => !v);
  }

  return (
    <div ref={box} className="relative w-fit shrink-0">
      <button ref={bell} type="button" data-inbox-bell aria-label={bellLabel(unread)} aria-haspopup="dialog" aria-expanded={open}
        aria-controls={open ? panelId : undefined} onClick={toggle}
        className="relative flex h-[52px] w-[52px] items-center justify-center rounded-full border border-sand-200 bg-white text-ink-900 hover:bg-fill">
        <BellIcon />
        {unread > 0 && (
          <motion.span key={pop} aria-hidden="true" initial={pop === 0 || reduce ? false : { scale: 0.55 }} animate={{ scale: 1 }}
            transition={{ type: "spring", stiffness: 520, damping: 14 }}
            className="num absolute -right-0.5 -top-0.5 flex h-5 min-w-5 items-center justify-center rounded-full bg-green-500 px-1.5 text-[11px] font-semibold leading-none text-white ring-2 ring-white">
            {badgeText(unread)}
          </motion.span>
        )}
      </button>
      <AnimatePresence>
        {open && (
          <motion.div ref={panel} id={panelId} role="dialog" aria-label="Inbox" tabIndex={-1}
            style={{ right: -place.shift, width: place.width }}
            initial={{ opacity: 0, y: -6, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: -6, scale: 0.98 }}
            transition={{ duration: 0.18, ease: EASE }}
            className="absolute top-[60px] z-40 origin-top-right rounded-panel border border-sand-200 bg-white p-2 shadow-float focus-visible:shadow-float">
            <div className="flex items-center justify-between gap-3 pb-1 pl-3 pt-1">
              <p className="text-[15px] font-semibold">
                Inbox{unread > 0 && <span className="ml-2 text-[13px] font-medium text-ink-500">{unread} unread</span>}
              </p>
              <Button variant="quiet" size="sm" disabled={unread === 0} onClick={() => onRead(items.filter((i) => !i.read).map((i) => i.id))}>
                Mark all read
              </Button>
            </div>
            {items.length === 0 ? (
              <div className="px-3 pb-5 pt-4 text-center">
                <p className="text-sm font-semibold">Nothing new</p>
                <p className="mx-auto mt-1 max-w-[34ch] text-[13px] text-ink-500">Anything that needs you arrives here the moment it happens.</p>
              </div>
            ) : (
              <ul className="max-h-[min(60vh,480px)] overflow-y-auto">
                {items.map((item) => (
                  <li key={item.id}>
                    <Row item={item} now={now} onOpen={() => { if (!item.read) onRead([item.id]); setOpen(false); }} />
                  </li>
                ))}
              </ul>
            )}
            <p className="mt-1 flex items-center gap-1.5 border-t border-sand-100 px-3 pb-1 pt-2.5 text-xs text-ink-500">
              <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-green-500" />Live from Cloud Firestore
            </p>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

/** What just arrived, at the bottom right for six seconds: hovering or focusing it holds it there, Escape puts it away,
 *  and opening it marks it read. The region is always present so screen readers hear each one, politely. */
function Toast({ arrived, onRead }: { arrived: Arrival | null; onRead: (ids: string[]) => void }) {
  const [dismissed, setDismissed] = useState(0);
  const [held, setHeld] = useState<number | null>(null);
  const shown = arrived && arrived.key !== dismissed ? arrived : null;
  const key = shown?.key;
  const now = useNow(shown !== null);

  useEffect(() => {
    if (key === undefined || held === key) return;
    const timer = setTimeout(() => setDismissed(key), TOAST_MS);
    return () => clearTimeout(timer);
  }, [key, held]);

  useEffect(() => {
    if (key === undefined) return;
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") setDismissed(key); };
    document.addEventListener("keydown", esc);
    return () => document.removeEventListener("keydown", esc);
  }, [key]);

  const item = shown?.items[0];
  const more = shown ? shown.items.length - 1 : 0;
  return (
    <div aria-live="polite" aria-atomic="true"
      className="no-print pointer-events-none fixed bottom-4 right-4 z-50 flex w-[min(380px,calc(100vw-32px))] justify-end sm:bottom-6 sm:right-6">
      <AnimatePresence>
        {shown && item && (
          <MotionLink key={shown.key} href={item.href} data-inbox-toast
            onClick={() => { onRead([item.id]); setDismissed(shown.key); }}
            onMouseEnter={() => setHeld(shown.key)} onMouseLeave={() => setHeld(null)}
            onFocus={() => setHeld(shown.key)} onBlur={() => setHeld(null)}
            initial={{ opacity: 0, y: 16, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: 8, scale: 0.98 }}
            transition={{ duration: 0.28, ease: EASE }}
            className="pointer-events-auto flex w-full gap-3 rounded-panel border border-sand-200 bg-white p-4 shadow-float hover:bg-fill">
            <Marker item={item} size="md" />
            <span className="min-w-0 flex-1">
              <span className="flex items-center gap-2 text-xs text-ink-500">
                <span className="inline-flex h-5 items-center gap-1 rounded-full bg-green-50 px-2 text-[11px] font-semibold text-green-700">
                  <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-green-500 motion-safe:animate-pulse" />Live
                </span>
                <span className="sr-only">New in your inbox:</span>
              </span>
              <span className="mt-1.5 block text-sm font-semibold leading-5 text-ink-900">{item.title}</span>
              {item.body && <span className="mt-0.5 line-clamp-2 text-[13px] leading-[18px] text-ink-700">{item.body}</span>}
              <Meta item={item} now={now} />
              {more > 0 && <span className="mt-1.5 block text-xs font-medium text-green-700">{more} more in your inbox</span>}
            </span>
          </MotionLink>
        )}
      </AnimatePresence>
    </div>
  );
}

/** The live inbox in the top bar, and its toasts. Renders nothing until Firestore has answered, and nothing at all when
 *  the inbox is off. */
export function Inbox({ personId }: { personId: string | null }) {
  const { on, items, arrived, read } = useLiveInbox(personId);
  if (!on) return null;
  return (
    <>
      <Bell items={items} onRead={read} />
      <Toast arrived={arrived} onRead={read} />
    </>
  );
}
