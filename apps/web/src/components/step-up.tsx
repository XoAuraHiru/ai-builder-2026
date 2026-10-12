"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { codeDigits, type Authenticator } from "@/lib/operations";
import { inputClass } from "@/components/ui";

export function CodeField({ value, onChange }: { value: string; onChange: (code: string) => void }) {
  return (
    <input inputMode="numeric" autoComplete="one-time-code" aria-label="Six-digit code" placeholder="000000" value={value}
      className={`${inputClass} num w-40 text-center text-lg tracking-[0.3em]`} onChange={(e) => onChange(codeDigits(e.target.value))} />
  );
}

/** What the signed-in staff member's authenticator app would show. The API offers it only with persona sign-in, so
 *  with real sign-in this renders nothing and the code comes from the person's own app. */
export function DemoAuthenticator({ onUse }: { onUse: (code: string) => void }) {
  const [auth, setAuth] = useState<Authenticator | null>(null);
  const [left, setLeft] = useState(0);
  const [hidden, setHidden] = useState(false);

  useEffect(() => {
    let alive = true;
    let next: ReturnType<typeof setTimeout> | undefined;
    const load = async () => {
      try {
        const a = await api<Authenticator>("/me/authenticator");
        if (!alive) return;
        setAuth(a);
        setLeft(a.seconds_left);
        next = setTimeout(load, a.seconds_left * 1000 + 250);
      } catch {
        if (alive) setHidden(true);
      }
    };
    load();
    return () => {
      alive = false;
      clearTimeout(next);
    };
  }, []);

  useEffect(() => {
    const tick = setInterval(() => setLeft((s) => Math.max(0, s - 1)), 1000);
    return () => clearInterval(tick);
  }, []);

  if (hidden || !auth) return null;
  return (
    <div className="flex items-center gap-5 rounded-panel border border-dashed border-line-strong px-4 py-3" title={auth.note}>
      <div>
        <p className="text-xs text-muted">Demo authenticator</p>
        <p className="num wider text-[22px] font-semibold tracking-[0.12em]">{auth.code.slice(0, 3)} {auth.code.slice(3)}</p>
        <div className="mt-1 h-px w-28 bg-line" aria-hidden="true">
          <div className="h-px bg-ink" style={{ width: `${(left / auth.period) * 100}%` }} />
        </div>
        <p className="sr-only" aria-live="off">{left} seconds left</p>
      </div>
      <button type="button" onClick={() => onUse(auth.code)}
        className="text-sm underline decoration-line-strong underline-offset-4 hover:decoration-ink">Use this code</button>
    </div>
  );
}
