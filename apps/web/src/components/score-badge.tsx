import { scoreTone, TRUST_LABEL, trustTone, type TrustBand } from "@/lib/leads";

const SCORE_STYLE = {
  high: "bg-emerald-100 text-emerald-800", medium: "bg-amber-100 text-amber-800",
  low: "bg-slate-200 text-slate-700", pending: "bg-slate-100 text-slate-500",
};
const TRUST_STYLE = {
  clear: "bg-emerald-100 text-emerald-800", review: "bg-amber-100 text-amber-800",
  high_risk: "bg-red-100 text-red-700", blocked: "bg-red-700 text-white", pending: "bg-slate-100 text-slate-500",
};

export function ScoreBadge({ score }: { score: number | null }) {
  return (
    <span className={`rounded px-2 py-0.5 text-xs font-semibold ${SCORE_STYLE[scoreTone(score)]}`}>
      Lead {score ?? "–"}
    </span>
  );
}

export function TrustBadge({ band, score }: { band: TrustBand | null; score: number | null }) {
  const tone = trustTone(band);
  return (
    <span className={`rounded px-2 py-0.5 text-xs font-semibold ${TRUST_STYLE[tone]}`}>
      Trust {score ?? "–"} · {TRUST_LABEL[tone]}
    </span>
  );
}
