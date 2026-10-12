import { getApps, initializeApp } from "firebase/app";
import { getAuth, type Auth } from "firebase/auth";
import type { RuntimeConfig } from "./config";

export function firebaseAuth(cfg: RuntimeConfig): Auth {
  const app = getApps()[0] ?? initializeApp(cfg.firebase);
  return getAuth(app);
}
