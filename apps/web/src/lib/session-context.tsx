"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api, ApiError, type Me } from "./api";
import { isSignedIn } from "./session";

export type SessionStatus = "loading" | "signed-out" | "ready" | "error";
type SessionValue = { me: Me | null; status: SessionStatus; error: string; refresh: () => Promise<void> };

const SessionContext = createContext<SessionValue>({ me: null, status: "loading", error: "", refresh: async () => {} });

/** Loads who is signed in once for the whole app; pages read it instead of fetching /me themselves. */
export function SessionProvider({ children }: { children: React.ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [status, setStatus] = useState<SessionStatus>("loading");
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    setStatus("loading");
    setError("");
    try {
      if (!(await isSignedIn())) {
        setMe(null);
        setStatus("signed-out");
        return;
      }
      setMe(await api<Me>("/me"));
      setStatus("ready");
    } catch (e) {
      setMe(null);
      if (e instanceof ApiError && e.status === 401) {
        setStatus("signed-out");
      } else {
        setError(e instanceof ApiError ? e.message : "Atrium could not reach its server. Check your connection and reload.");
        setStatus("error");
      }
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return <SessionContext.Provider value={{ me, status, error, refresh }}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionValue {
  return useContext(SessionContext);
}

/** For pages inside the signed-in shell, which renders them only after /me has loaded. */
export function useMe(): Me {
  const { me } = useContext(SessionContext);
  if (!me) throw new Error("useMe is only available inside a signed-in workspace");
  return me;
}
