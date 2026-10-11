"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError, type Me } from "@/lib/api";
import { formatUsd } from "@/lib/allocation";
import { groupByStage, STAGE_LABEL, STAGES, type Lead } from "@/lib/leads";
import { isSignedIn } from "@/lib/session";
import { ScoreBadge, TrustBadge } from "@/components/score-badge";

export default function AdvisorBoard() {
  const router = useRouter();
  const [leads, setLeads] = useState<Lead[] | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setLeads(await api<Lead[]>("/leads"));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    (async () => {
      if (!(await isSignedIn())) return router.push("/login");
      const me = await api<Me>("/me");
      if (!me.roles.includes("staff")) {
        setError("The advisor workspace is for Atrium staff. Switch to the Daniel persona.");
        return;
      }
      await load();
    })();
  }, [router, load]);

  async function scorePending() {
    setBusy(true);
    setError("");
    try {
      await api("/leads/score-pending", { method: "POST" });
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  if (error && !leads) return <p className="text-red-600">{error}</p>;
  if (!leads) return <p>Loading pipeline…</p>;
  const pending = leads.filter((l) => !l.scored_at).length;
  const groups = groupByStage(leads);
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-2xl font-semibold">Lead pipeline</h1>
          <p className="text-sm text-slate-500">Lead Score is fit and intent; Trust Score is identity and fraud risk.</p>
        </div>
        {pending > 0 && (
          <button onClick={scorePending} disabled={busy}
            className="rounded bg-[#0b5fff] px-4 py-2 text-sm font-medium text-white disabled:opacity-60">
            {busy ? "Scoring with Gemini…" : `Score ${pending} new lead${pending > 1 ? "s" : ""} with AI`}
          </button>
        )}
      </div>
      {error && <p className="text-sm text-red-600">{error}</p>}
      <div className="flex gap-3 overflow-x-auto pb-2">
        {STAGES.map((stage) => (
          <section key={stage} className="w-72 shrink-0 rounded-lg bg-slate-100 p-2">
            <h2 className="mb-2 px-1 text-sm font-semibold text-slate-600">
              {STAGE_LABEL[stage]} · {groups[stage].length}
            </h2>
            <div className="space-y-2">
              {groups[stage].map((l) => (
                <Link key={l.id} href={`/advisor/leads/${l.id}`}
                  className="block rounded-md border border-slate-200 bg-white p-3 hover:border-[#0b5fff]">
                  <div className="font-medium">{l.full_name}</div>
                  <div className="text-xs text-slate-500">{l.source} · {formatUsd(l.investable_usd)}</div>
                  <div className="mt-2 flex flex-wrap gap-1">
                    <ScoreBadge score={l.lead_score} />
                    <TrustBadge band={l.trust_band} score={l.trust_score} />
                  </div>
                  {l.next_best_action && <p className="mt-2 line-clamp-2 text-xs text-slate-600">{l.next_best_action}</p>}
                </Link>
              ))}
            </div>
          </section>
        ))}
      </div>
    </div>
  );
}
