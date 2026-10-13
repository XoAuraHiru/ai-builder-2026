"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { signInWithEmailAndPassword } from "firebase/auth";
import { getConfig, type RuntimeConfig } from "@/lib/config";
import { workspaceFor } from "@/lib/nav";
import { firebaseAuth } from "@/lib/firebase";
import { useSession } from "@/lib/session-context";
import { Button, Field, inputClass, Loading, Panel } from "@/components/ui";

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
      await refresh();
      router.push("/");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (!cfg) return <Loading label="Opening sign-in" />;
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
          <Field label="Password" error={error ? `Atrium could not sign you in: ${error}` : undefined}>
            <input className={inputClass} type="password" required autoComplete="current-password" aria-invalid={Boolean(error) || undefined}
              value={password} onChange={(e) => setPassword(e.target.value)} />
          </Field>
          <Button type="submit" busy={busy} className="w-full">Sign in</Button>
        </form>
      </Panel>
      <p className="mt-6 text-center text-sm text-ink-700">
        New here? <Link href="/" className="font-semibold text-green-600 hover:text-green-800 hover:underline">See what Atrium is</Link>.
      </p>
    </div>
  );
}
