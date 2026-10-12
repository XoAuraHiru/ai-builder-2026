"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { signInWithEmailAndPassword } from "firebase/auth";
import { getConfig, type RuntimeConfig } from "@/lib/config";
import { firebaseAuth } from "@/lib/firebase";
import { useSession } from "@/lib/session-context";
import { Button, Field, inputClass, Loading, Notice } from "@/components/ui";

/** Email sign-in for deployments with real accounts. With persona sign-in, people are chosen on the front door. */
export default function LoginPage() {
  const router = useRouter();
  const { refresh } = useSession();
  const [cfg, setCfg] = useState<RuntimeConfig | null>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    getConfig().then((c) => {
      if (c.authMode === "dev") router.replace("/#journeys");
      else setCfg(c);
    });
  }, [router]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    try {
      await signInWithEmailAndPassword(firebaseAuth(cfg!), email, password);
      await refresh();
      router.push("/");
    } catch (err) {
      setError((err as Error).message);
    }
  }

  if (!cfg) return <Loading label="Opening sign-in" />;
  return (
    <div className="mx-auto max-w-sm">
      <h1 className="wide text-[30px] font-semibold tracking-[-0.015em]">Sign in</h1>
      <form onSubmit={submit} className="mt-6 space-y-4">
        <Field label="Email"><input className={inputClass} type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} /></Field>
        <Field label="Password"><input className={inputClass} type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} /></Field>
        {error && <Notice tone="error">{error}</Notice>}
        <Button type="submit">Sign in</Button>
      </form>
      <p className="mt-6 text-sm text-ink-2">New here? <Link href="/" className="font-semibold underline underline-offset-4">See what Atrium is</Link>.</p>
    </div>
  );
}
