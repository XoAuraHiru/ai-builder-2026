"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { signInWithEmailAndPassword } from "firebase/auth";
import { getConfig, type RuntimeConfig } from "@/lib/config";
import { firebaseAuth } from "@/lib/firebase";
import { setDevUser } from "@/lib/session";
import { useSession } from "@/lib/session-context";
import { Button, Field, inputClass, Loading, Notice } from "@/components/ui";

const PERSONAS = [
  { group: "Investors", email: "priya@atrium.demo", name: "Priya Raman", role: "Investor", home: "/investor",
    sees: "A balanced portfolio, the What-if Studio, the X-ray and the Copilot. Try buying 60 NVIDIA shares in Markets." },
  { group: "Investors", email: "lucas@atrium.demo", name: "Lucas Moreau", role: "Investor", home: "/investor",
    sees: "A growth and technology portfolio. Open the X-ray, then try buying more NVIDIA." },
  { group: "Investors", email: "tom@atrium.demo", name: "Tom Becker", role: "Investor", home: "/investor/trades",
    sees: "A large Tesla position. Selling it all from a new browser is held as a possible account takeover." },
  { group: "Investors", email: "hana@atrium.demo", name: "Hana Sato", role: "Investor", home: "/investor/trades",
    sees: "Sold PepsiCo at a loss recently. Buying it back raises the wash-sale warning." },
  { group: "Atrium staff", email: "daniel@atrium.demo", name: "Daniel Okafor", role: "Advisor", home: "/advisor",
    sees: "The lead pipeline with three fraud stories, AI replies and personalised proposals." },
  { group: "Atrium staff", email: "mei@atrium.demo", name: "Mei Tanaka", role: "Operations", home: "/operations",
    sees: "Reconciliation and approvals, arriving in the Operate release." },
  { group: "Atrium staff", email: "omar@atrium.demo", name: "Omar Haddad", role: "Compliance", home: "/compliance",
    sees: "Anti-money-laundering alerts and cases, arriving in the Operate release." },
];

export default function LoginPage() {
  const router = useRouter();
  const { refresh } = useSession();
  const [cfg, setCfg] = useState<RuntimeConfig | null>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [choosing, setChoosing] = useState("");

  useEffect(() => {
    getConfig().then(setCfg);
  }, []);

  async function choose(p: (typeof PERSONAS)[number]) {
    setChoosing(p.email);
    setDevUser(p.email);
    await refresh();
    router.push(p.home);
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
    <div className="grid gap-12 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.05fr)] lg:gap-16">
      <div className="max-w-xl">
        <h1 className="wide text-[38px] font-semibold leading-[1.08] tracking-[-0.02em] sm:text-[46px]">
          One platform for every client relationship, with every number explained.
        </h1>
        <p className="mt-5 text-[17px] leading-relaxed text-ink-2">
          Atrium acquires, serves and protects investors in one place. Leads are scored for fit and fraud from the first
          form, portfolios are simulated over real market history, and every answer the AI writes shows where it came from.
        </p>
        <ul className="mt-8 space-y-3 border-t border-line pt-6 text-sm text-ink-2">
          <li><span className="font-medium text-ink">Grounded AI.</span> Gemini writes the words; Atrium&apos;s engines own every figure, and each figure is checked.</li>
          <li><span className="font-medium text-ink">People decide.</span> Profiles, proposals and risky instructions wait for a person to confirm.</li>
          <li><span className="font-medium text-ink">Synthetic by design.</span> Every person, account and trade here is invented, and trading is on paper.</li>
        </ul>
      </div>
      <div>
        {!cfg ? <Loading label="Loading" /> : cfg.authMode === "dev" ? (
          <div className="space-y-8">
            {["Investors", "Atrium staff"].map((group) => (
              <section key={group}>
                <h2 className="text-sm font-medium text-muted">{group}</h2>
                <ul className="mt-2 divide-y divide-line border-y border-line">
                  {PERSONAS.filter((p) => p.group === group).map((p) => (
                    <li key={p.email}>
                      <button type="button" onClick={() => choose(p)} disabled={Boolean(choosing)}
                        className="group grid w-full grid-cols-[minmax(0,1fr)_auto] items-center gap-4 py-3.5 text-left disabled:opacity-60">
                        <span className="min-w-0">
                          <span className="font-medium group-hover:underline">{p.name}</span>
                          <span className="block text-sm text-ink-2">{p.sees}</span>
                        </span>
                        <span className="text-sm text-muted">{choosing === p.email ? "Opening…" : p.role}</span>
                      </button>
                    </li>
                  ))}
                </ul>
              </section>
            ))}
            <p className="text-xs text-muted">This demo uses persona sign-in. Choosing a persona signs you in as them.</p>
          </div>
        ) : (
          <form onSubmit={submit} className="max-w-sm space-y-4">
            <h2 className="text-lg font-semibold">Sign in</h2>
            <Field label="Email"><input className={inputClass} type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} /></Field>
            <Field label="Password"><input className={inputClass} type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} /></Field>
            {error && <Notice tone="error">{error}</Notice>}
            <Button type="submit">Sign in</Button>
          </form>
        )}
      </div>
    </div>
  );
}
