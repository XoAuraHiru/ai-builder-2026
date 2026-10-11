import { getConfig } from "./config";
import { firebaseAuth } from "./firebase";

const DEV_KEY = "atrium.devUser";

function readDevUser(): string | null {
  try {
    return localStorage.getItem(DEV_KEY);
  } catch {
    return null;
  }
}

export function setDevUser(email: string) {
  try {
    localStorage.setItem(DEV_KEY, email);
  } catch {
    // Storage blocked (private mode); the session lasts until reload.
  }
}

export async function signOut() {
  const cfg = await getConfig();
  try {
    localStorage.removeItem(DEV_KEY);
  } catch {}
  if (cfg.authMode === "firebase") await firebaseAuth(cfg).signOut();
}

export async function authHeaders(): Promise<Record<string, string>> {
  const cfg = await getConfig();
  if (cfg.authMode === "dev") {
    const email = readDevUser();
    return email ? { "X-Dev-User": email } : {};
  }
  const user = firebaseAuth(cfg).currentUser;
  if (!user) return {};
  return { Authorization: `Bearer ${await user.getIdToken()}` };
}

export async function isSignedIn(): Promise<boolean> {
  const cfg = await getConfig();
  if (cfg.authMode === "dev") return !!readDevUser();
  const auth = firebaseAuth(cfg);
  await auth.authStateReady();
  return !!auth.currentUser;
}
