"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { formatUsd } from "@/lib/format";
import { groupByStage, STAGE_LABEL, STAGES, type Lead } from "@/lib/leads";
import { useMe } from "@/lib/session-context";
import { ScoreBadge, TrustBadge } from "@/components/score-badge";
import { Button, Loading, Notice, PageHeader } from "@/components/ui";

export default function AdvisorBoard() {
  const me = useMe();
  const [leads, setLeads] = useState<Lead[] | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState("");
  const staff = me.roles.includes("staff");

  const load = useCallback(async () => {
    try {
      setLeads(await api<Lead[]>("/leads"));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    if (staff) load();
  }, [staff, load]);

  async function scorePending() {
    setBusy(true);
    setError("");
    setProgress("");
    try {
      // The API scores a small batch per request; keep going until nothing is left, showing progress as we go.
      for (let round = 0; round < 20; round++) {
        const r = await api<{ scored: number; remaining: number }>("/leads/score-pending", { method: "POST" });
        await load();
        if (r.remaining === 0 || r.scored === 0) break;
        setProgress(`${r.remaining} still to score`);
      }
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(false);
      setProgress("");
      await load(); // some leads may have been scored before an error; show them either way
    }
  }

  if (!staff) return <Notice tone="caution" title="The advisor workspace is for Atrium staff">Switch to the Daniel persona.</Notice>;
  if (error && !leads) return <Notice tone="error" title="Could not load the pipeline">{error}</Notice>;
  if (!leads) return <Loading label="Loading the pipeline" />;
  const pending = leads.filter((l) => !l.scored_at).length;
  const groups = groupByStage(leads);
  return (
    <>
      <PageHeader title="Lead pipeline"
        description="Lead Score is fit and intent; Trust Score is identity and fraud risk. Open a lead to see why."
        actions={pending > 0 ? (
          <Button busy={busy} onClick={scorePending}>
            {busy ? `Scoring with Gemini${progress ? `, ${progress}` : ""}` : `Score ${pending} new lead${pending > 1 ? "s" : ""} with AI`}
          </Button>
        ) : undefined} />
      {error && <div className="mb-4"><Notice tone="error">{error}</Notice></div>}
      <div className="-mx-4 flex gap-4 overflow-x-auto px-4 pb-4 sm:-mx-8 sm:px-8">
        {STAGES.map((stage) => (
          <section key={stage} className="w-72 shrink-0">
            <h2 className="flex items-baseline justify-between border-b border-line pb-2 text-sm font-semibold">
              {STAGE_LABEL[stage]} <span className="num text-xs font-normal text-muted">{groups[stage].length}</span>
            </h2>
            <ul className="mt-3 space-y-2">
              {groups[stage].map((l) => (
                <li key={l.id}>
                  <Link href={`/advisor/leads/${l.id}`} className="block rounded-panel border border-line bg-surface p-3 transition-colors hover:border-ink">
                    <span className="block font-medium">{l.full_name}</span>
                    <span className="block text-xs text-muted">Came via {l.source}, {formatUsd(l.investable_usd, 0)} to invest</span>
                    <span className="mt-2 flex flex-wrap gap-1"><ScoreBadge score={l.lead_score} /><TrustBadge band={l.trust_band} score={l.trust_score} /></span>
                    {l.next_best_action && <span className="mt-2 line-clamp-2 block font-serif text-[13.5px] text-ink-2">{l.next_best_action}</span>}
                  </Link>
                </li>
              ))}
              {groups[stage].length === 0 && <li className="rounded-panel border border-dashed border-line px-3 py-6 text-center text-xs text-muted">No leads</li>}
            </ul>
          </section>
        ))}
      </div>
    </>
  );
}
