"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { signInWithEmailAndPassword } from "firebase/auth";
import { getConfig, type RuntimeConfig } from "@/lib/config";
import { workspaceFor } from "@/lib/nav";
import { firebaseAuth } from "@/lib/firebase";
import { useSession } from "@/lib/session-context";
import { FieldError } from "@/components/form-feedback";
import { DrawnCheck } from "@/components/motion";
import { Skeleton } from "@/components/skeleton";
import { Button, Field, inputClass, Panel } from "@/components/ui";

/** The sign-in card while the deployment's settings load: its heading, line, two fields and the button. */
function LoginSkeleton() {
  return (
    <div role="status" aria-live="polite" className="mx-auto w-full max-w-[420px]">
      <span className="sr-only">Opening sign-in…</span>
      <div aria-hidden="true">
        <div className="rounded-panel border border-sand-200 bg-white p-6 sm:p-8">
          <Skeleton className="h-9 w-28 rounded-[10px]" />
          <Skeleton className="mt-3 h-3.5 w-4/5" />
          <Skeleton className="mt-2 h-3.5 w-1/4" />
          <div className="mt-6 space-y-4">
            {[0, 1].map((i) => (
              <span key={i} className="block"><Skeleton className="h-3.5 w-16" /><Skeleton className="mt-2 h-11 w-full rounded-control" /></span>
            ))}
            <Skeleton className="h-11 w-full rounded-full" />
          </div>
        </div>
        <Skeleton className="mx-auto mt-6 h-3.5 w-52" />
      </div>
    </div>
  );
}

/** Email sign-in for deployments with real accounts. With persona sign-in, people are chosen on the front door. */
export default function LoginPage() {
  const router = useRouter();
  const { me, refresh } = useSession();
  const home = me ? workspaceFor(me.roles)?.home ?? null : null;
  const [cfg, setCfg] = useState<RuntimeConfig | null>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [signedIn, setSignedIn] = useState(false);

  useEffect(() => {
    getConfig().then((c) => {
      if (c.authMode === "dev") router.replace("/#journeys");
      else if (home) router.replace(home);  // already signed in: go to your workspace
      else setCfg(c);
    });
  }, [router, home]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      await signInWithEmailAndPassword(firebaseAuth(cfg!), email, password);
      setSignedIn(true);  // confirmed while the workspace opens
      await refresh();
      router.push("/");
    } catch (err) {
      setSignedIn(false);
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (!cfg) return <LoginSkeleton />;
  return (
    <div className="mx-auto w-full max-w-[420px]">
      <Panel className="p-6 sm:p-8">
        <h1 className="text-[30px] font-semibold leading-9 tracking-[-0.02em]">Sign in</h1>
        <p className="mt-2 text-[15px] leading-[22px] text-ink-700">With the email and password of your Atrium account.</p>
        <form onSubmit={submit} className="mt-6 space-y-4">
          <Field label="Email">
            <input className={inputClass} type="email" required autoComplete="email" aria-invalid={Boolean(error) || undefined}
              value={email} onChange={(e) => setEmail(e.target.value)} />
          </Field>
          <Field label="Password">
            <input className={inputClass} type="password" required autoComplete="current-password" aria-invalid={Boolean(error) || undefined}
              value={password} onChange={(e) => setPassword(e.target.value)} />
            <FieldError message={error ? `Atrium could not sign you in: ${error}` : undefined} />
          </Field>
          {signedIn ? (
            // Same height as the button it replaces, so nothing moves while Atrium opens.
            <p role="status" className="flex min-h-11 items-center justify-center gap-2 rounded-full bg-green-50 text-sm font-semibold text-green-700">
              <DrawnCheck size={18} />Signed in
            </p>
          ) : (
            <Button type="submit" busy={busy} className="w-full">{busy ? "Signing in" : "Sign in"}</Button>
          )}
        </form>
      </Panel>
      <p className="mt-6 text-center text-sm text-ink-700">
        New here? <Link href="/" className="font-semibold text-green-600 hover:text-green-800 hover:underline">See what Atrium is</Link>.
      </p>
    </div>
  );
}
