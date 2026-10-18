import type { Auth } from "firebase/auth";
import type { Firestore } from "firebase/firestore";
import { api } from "./api";
import { getConfig } from "./config";
import { fromDoc, type InboxItem } from "./inbox";

/** The live inbox on Cloud Firestore. The API mints a custom token for the signed-in person (GET /me/realtime); a
 *  second Firebase app, kept apart from the one real sign-in uses, signs in with it and listens to that person's
 *  inbox. The Firebase SDK loads only when the inbox is on, and nothing here ever throws into a page. */
export type Realtime = { enabled: boolean; token: string | null; path: string | null; project_id: string | null };
export type InboxSession = { db: Firestore; path: string };

const APP_NAME = "atrium-inbox";
const LIMIT = 20;
let auth: Auth | null = null;
let queue: Promise<unknown> = Promise.resolve();
let warned = false;

/** Says once why the inbox is not showing, then stays quiet: the inbox is a convenience, never an error. */
export function inboxUnavailable(reason: unknown) {
  if (warned) return;
  warned = true;
  console.info("Live inbox unavailable:", reason instanceof Error ? reason.message : reason);
}

async function signIn(): Promise<InboxSession | null> {
  const realtime = await api<Realtime>("/me/realtime");
  if (!realtime.enabled || !realtime.token || !realtime.path) return null;
  const cfg = await getConfig();
  if (!cfg.firebase.apiKey) {
    inboxUnavailable("the web service has no Firebase web config (FIREBASE_API_KEY)");
    return null;
  }
  const [{ getApps, initializeApp }, fireAuth, { getFirestore }] = await Promise.all([
    import("firebase/app"), import("firebase/auth"), import("firebase/firestore"),
  ]);
  const app = getApps().find((a) => a.name === APP_NAME)
    ?? initializeApp({ ...cfg.firebase, projectId: realtime.project_id || cfg.firebase.projectId }, APP_NAME);
  if (!auth) {
    try {
      // In memory only: every page load asks the API who this is, so a person switched in the demo never lingers.
      auth = fireAuth.initializeAuth(app, { persistence: fireAuth.inMemoryPersistence });
    } catch {
      auth = fireAuth.getAuth(app); // already set up: a hot reload kept the app but not this module
    }
  }
  await fireAuth.signInWithCustomToken(auth, realtime.token);
  return { db: getFirestore(app), path: realtime.path };
}

/** Signs this browser in as the current person. Sign-ins queue behind each other, so switching person quickly can
 *  never leave the browser signed in as the one before. */
export function openInbox(): Promise<InboxSession | null> {
  const next = queue.then(signIn, signIn);
  queue = next.catch(() => undefined);
  return next;
}

/** Calls back with the newest items on every change. `fromCache` marks a snapshot the server has not confirmed yet. */
export async function listen(session: InboxSession, onItems: (items: InboxItem[], fromCache: boolean) => void,
  onError: (error: unknown) => void): Promise<() => void> {
  const { collection, limit, onSnapshot, orderBy, query } = await import("firebase/firestore");
  const newest = query(collection(session.db, session.path), orderBy("created_at", "desc"), limit(LIMIT));
  return onSnapshot(newest, (snap) => {
    const items = snap.docs.map((d) => fromDoc(d.id, d.data())).filter((i): i is InboxItem => i !== null);
    onItems(items, snap.metadata.fromCache);
  }, onError);
}

/** Marks items read. The only field a browser may change (firestore.rules allows `read` and nothing else). */
export async function markRead(session: InboxSession, ids: string[]): Promise<void> {
  if (ids.length === 0) return;
  const { doc, writeBatch } = await import("firebase/firestore");
  const batch = writeBatch(session.db);
  for (const id of ids) batch.update(doc(session.db, session.path, id), { read: true });
  await batch.commit();
}
