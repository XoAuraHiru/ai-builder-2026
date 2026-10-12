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
 *  the person, and the server stores only a hash of it. */
export function deviceId(store: Store | null = browserStore()): string | null {
  if (!store) return null;
  try {
    let id = store.getItem(KEY);
    if (!id) {
      id = crypto.randomUUID();
      store.setItem(KEY, id);
    }
    return id;
  } catch {
    return null;
  }
}
