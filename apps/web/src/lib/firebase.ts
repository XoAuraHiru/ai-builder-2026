import { getApps, initializeApp } from "firebase/app";
import { getAuth, type Auth } from "firebase/auth";
import type { RuntimeConfig } from "./config";

/** Firebase sign-in uses the default app; the live inbox keeps its own ("atrium-inbox"), never this one. */
export function firebaseAuth(cfg: RuntimeConfig): Auth {
  const app = getApps().find((a) => a.name === "[DEFAULT]") ?? initializeApp(cfg.firebase);
  return getAuth(app);
}
