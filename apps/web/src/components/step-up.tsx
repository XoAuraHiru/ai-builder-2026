"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { codeDigits, type Authenticator } from "@/lib/operations";
import { Button } from "@/components/ui";

/** The one-time code as six boxes: one real input lies over them, so typing, pasting and the phone's code suggestion
 *  all work; the box the next digit goes into is ringed in green-600 while the field has focus. */
export function CodeField({ value, onChange, label = "Six-digit code from your authenticator", id }:
  { value: string; onChange: (code: string) => void; label?: string; id?: string }) {
  const [focused, setFocused] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const at = Math.min(value.length, 5);
  return (
    <span className="relative inline-flex gap-1.5" onClick={() => input.current?.focus()}>
      {Array.from({ length: 6 }, (_, i) => {
        const on = focused && i === at;
        return (
          <span key={i} aria-hidden="true"
            className={`flex h-11 w-10 items-center justify-center rounded-[10px] font-mono text-[18px] text-ink-900 transition-shadow ${on ? "bg-white shadow-[0_0_0_2px_var(--color-green-600)]" : "bg-fill"}`}>
            {value[i] ?? (on ? <span className="h-5 w-[1.5px] animate-pulse bg-green-600 motion-reduce:animate-none" /> : "")}
          </span>
        );
      })}
      <input ref={input} id={id} inputMode="numeric" autoComplete="one-time-code" aria-label={label} maxLength={6} value={value}
        onFocus={() => setFocused(true)} onBlur={() => setFocused(false)} onChange={(e) => onChange(codeDigits(e.target.value))}
        className="absolute inset-0 h-full w-full cursor-text rounded-[10px] text-transparent caret-transparent opacity-0" />
    </span>
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
    <div className="inline-flex flex-wrap items-center gap-x-4 gap-y-2 rounded-control bg-fill py-2.5 pl-4 pr-2" title={auth.note}>
      <div>
        <p className="text-xs text-ink-500">Demo authenticator</p>
        <p className="font-mono text-[20px] leading-7 tracking-[0.12em] text-ink-900">{auth.code.slice(0, 3)} {auth.code.slice(3)}</p>
        <div className="mt-1 h-1 w-28 overflow-hidden rounded-full bg-sand-200" aria-hidden="true">
          <div className="h-1 rounded-full bg-green-500 transition-[width] duration-1000 ease-linear" style={{ width: `${(left / auth.period) * 100}%` }} />
        </div>
        <p className="sr-only" aria-live="off">{left} seconds left</p>
      </div>
      <Button variant="quiet" size="sm" onClick={() => onUse(auth.code)}>Use this code</Button>
    </div>
  );
}
