const KEY = "atrium-device";

type Store = Pick<Storage, "getItem" | "setItem">;

function browserStore(): Store | null {
  try {
    return typeof window === "undefined" ? null : window.localStorage;
  } catch {
    return null;
  }
}

/** A random identifier this browser keeps, so Atrium can tell a familiar device from a new one. It says nothing about
 *  the person, and the server stores only a hash of it. With demo sign-in, each persona stands for a different
 *  person on their own device, so each keeps its own identifier: switching person in one browser must not look like
 *  several clients sharing one device (the fraud ring radar would rightly flag that). */
export function deviceId(store: Store | null = browserStore(), persona: string | null = null): string | null {
  if (!store) return null;
  const key = persona ? `${KEY}.${persona.trim().toLowerCase()}` : KEY;
  try {
    let id = store.getItem(key);
    if (!id) {
      id = crypto.randomUUID();
      store.setItem(key, id);
    }
    return id;
  } catch {
    return null;
  }
}
