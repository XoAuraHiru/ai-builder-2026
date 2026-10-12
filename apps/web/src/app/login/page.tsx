"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { signInWithEmailAndPassword } from "firebase/auth";
import { getConfig, type RuntimeConfig } from "@/lib/config";
import { firebaseAuth } from "@/lib/firebase";
import { setDevUser } from "@/lib/session";
import { useSession } from "@/lib/session-context";

const PERSONAS = [
  { email: "priya@atrium.demo", label: "Priya Raman", role: "Investor", home: "/investor" },
  { email: "lucas@atrium.demo", label: "Lucas Moreau", role: "Investor", home: "/investor" },
  { email: "daniel@atrium.demo", label: "Daniel Okafor", role: "Advisor", home: "/advisor" },
  { email: "mei@atrium.demo", label: "Mei Tanaka", role: "Operations", home: "/operations" },
  { email: "omar@atrium.demo", label: "Omar Haddad", role: "Compliance", home: "/compliance" },
];

export default function LoginPage() {
  const router = useRouter();
  const { refresh } = useSession();
  const [cfg, setCfg] = useState<RuntimeConfig | null>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    getConfig().then(setCfg);
  }, []);

  if (!cfg) return <p>Loading…</p>;

  if (cfg.authMode === "dev") {
    return (
      <div className="mx-auto max-w-md space-y-3">
        <h1 className="text-xl font-semibold">Choose a demo persona</h1>
        <p className="text-sm text-slate-600">Every persona and number here is synthetic.</p>
        {PERSONAS.map((p) => (
          <button
            key={p.email}
            type="button"
            onClick={async () => {
              setDevUser(p.email);
              await refresh();
              router.push(p.home);
            }}
            className="flex w-full items-center justify-between rounded-lg border border-slate-200 bg-white px-4 py-3 text-left hover:border-[#0b5fff]"
          >
            <span className="font-medium">{p.label}</span>
            <span className="text-sm text-slate-500">{p.role}</span>
          </button>
        ))}
      </div>
    );
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    try {
      await signInWithEmailAndPassword(firebaseAuth(cfg!), email, password);
      await refresh();
      router.push("/investor");
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <form onSubmit={submit} className="mx-auto max-w-md space-y-3">
      <h1 className="text-xl font-semibold">Sign in</h1>
      <label className="block text-sm">
        Email
        <input
          className="mt-1 w-full rounded border border-slate-300 px-3 py-2"
          type="email"
          autoComplete="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
      </label>
      <label className="block text-sm">
        Password
        <input
          className="mt-1 w-full rounded border border-slate-300 px-3 py-2"
          type="password"
          autoComplete="current-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
      </label>
      {error && <p className="text-sm text-red-600">{error}</p>}
      <button type="submit" className="rounded bg-[#0b5fff] px-4 py-2 text-white">
        Sign in
      </button>
    </form>
  );
}
