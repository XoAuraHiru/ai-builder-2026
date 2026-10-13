import type { ReactNode } from "react";
import { Badge } from "@/components/ui";
import {
  scoreTone, signedWeight, TRUST_LABEL, TRUST_SEGMENTS, trustMeter, trustTone, type MeterTone, type TrustBand, type TrustSignal,
} from "@/lib/leads";
import { initials } from "@/lib/personas";

const TRUST_TONE = { clear: "gain", review: "caution", high_risk: "loss", blocked: "strong", pending: "neutral" } as const;
const FIT_LABEL = { high: "High fit", medium: "Medium fit", low: "Low fit", pending: "Not scored" } as const;
const METER_FILL: Record<MeterTone, string> = { coral: "bg-coral-500", amber: "bg-amber-400", green: "bg-green-500", none: "bg-sand-100" };

/** The Trust Score's band as a status chip (with its dot); the score itself sits beside it, never inside the colour. */
export function TrustBadge({ band, score, showScore = false }: { band: TrustBand | null; score: number | null; showScore?: boolean }) {
  const tone = trustTone(band);
  return (
    <Badge tone={TRUST_TONE[tone]}>
      <span className="num">{showScore && score !== null ? `Trust ${score}, ${TRUST_LABEL[tone]}` : TRUST_LABEL[tone]}</span>
    </Badge>
  );
}

/** The Lead Score's fit level as a quiet chip: green when it is worth a call first, sand otherwise (amber means caution). */
export function ScoreBadge({ score }: { score: number | null }) {
  const tone = scoreTone(score);
  return <Badge tone={tone === "high" ? "gain" : "neutral"}>{FIT_LABEL[tone]}</Badge>;
}

/** The Trust Score as 20 segments: coral for high risk and blocked, amber for review, green for clear. */
export function TrustMeter({ score, band, size = "md" }: { score: number | null; band: TrustBand | null; size?: "md" | "sm" }) {
  const { filled, tone } = trustMeter(score, band);
  const label = score === null ? "Trust Score not scored yet" : `Trust Score ${score} of 100, ${TRUST_LABEL[trustTone(band)]}`;
  return (
    <span role="img" aria-label={label} className={`flex w-full ${size === "md" ? "gap-[3px]" : "gap-[2px]"}`}>
      {Array.from({ length: TRUST_SEGMENTS }, (_, i) => (
        <span key={i} aria-hidden="true"
          className={`flex-1 ${size === "md" ? "h-4 rounded-[4px]" : "h-2 rounded-[2px]"} ${i < filled ? METER_FILL[tone] : "bg-sand-100"}`} />
      ))}
    </span>
  );
}

/** A trust signal and its signed weight: coral when it takes points away, green when it adds them. */
/** A signal as the lead and the order checks both send it; only a lead's signals can block. */
export type SignalLike = Pick<TrustSignal, "code" | "label" | "weight" | "evidence"> & { blocking?: boolean };

export function SignalRow({ signal, evidence = false }: { signal: SignalLike; evidence?: boolean }) {
  return (
    <li className="flex justify-between gap-3 border-t border-sand-100 py-2.5 text-[13px] leading-[18px]">
      <span className="min-w-0">
        <span className="text-ink-900">{signal.label}</span>
        {evidence && signal.evidence && (
          <span className="mt-0.5 block text-xs leading-4 text-ink-500">
            {signal.evidence}{signal.blocking ? " A person must decide." : ""}
          </span>
        )}
      </span>
      <span className={`num shrink-0 font-semibold ${signal.weight < 0 ? "text-coral-700" : signal.weight > 0 ? "text-green-700" : "text-ink-500"}`}>
        {signedWeight(signal.weight)}
      </span>
    </li>
  );
}

/** The design's Trust Score card: who (or a title), the band chip, the score out of 100 with the fit beside it, the meter,
 *  and the signals with their signed weights. */
export function TrustScoreCard({ score, band, signals, fit, person, title = "Trust Score", evidence = false, limit, footer, className = "" }: {
  score: number | null; band: TrustBand | null; signals: SignalLike[] | null; fit?: number | null;
  person?: { name: string; meta: string }; title?: string; evidence?: boolean; limit?: number; footer?: ReactNode; className?: string;
}) {
  const shown = limit === undefined ? signals ?? [] : (signals ?? []).slice(0, limit);
  const hidden = (signals?.length ?? 0) - shown.length;
  return (
    <div className={`flex flex-col gap-[18px] rounded-panel border border-sand-200 bg-white p-5 sm:p-6 ${className}`}>
      <div className="flex items-start justify-between gap-3">
        {person ? (
          <div className="flex min-w-0 items-center gap-3">
            <span aria-hidden="true" className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-sand-100 text-[13px] font-semibold">
              {initials(person.name)}
            </span>
            <span className="flex min-w-0 flex-col gap-0.5">
              <span className="truncate text-[15px] font-semibold leading-5">{person.name}</span>
              <span className="truncate text-xs text-ink-500">{person.meta}</span>
            </span>
          </div>
        ) : <h3 className="text-[15px] font-semibold leading-6">{title}</h3>}
        <TrustBadge band={band} score={score} />
      </div>
      <div className="flex flex-col gap-2">
        <div className="flex items-baseline gap-1.5">
          <span className="num text-[32px] font-medium leading-9 tracking-[-0.02em]">{score ?? "–"}</span>
          <span className="num text-[13px] text-ink-500">/ 100{fit !== undefined && fit !== null ? ` · fit ${fit}` : ""}</span>
        </div>
        <TrustMeter score={score} band={band} />
      </div>
      {signals && (shown.length > 0 ? (
        <ul>
          {shown.map((s, i) => <SignalRow key={`${s.code}-${i}`} signal={s} evidence={evidence} />)}
          {hidden > 0 && <li className="border-t border-sand-100 pt-2.5 text-xs text-ink-500">and {hidden} more signal{hidden === 1 ? "" : "s"}</li>}
        </ul>
      ) : (
        <p className="border-t border-sand-100 pt-2.5 text-[13px] text-ink-700">No risk signals: nothing in the form, the history or the documents raised a flag.</p>
      ))}
      {footer}
    </div>
  );
}

/** The Lead Score as a stat card: the figure large, out of 100, with how likely the lead is to become a client. */
export function LeadScoreStat({ score, probability, children }: { score: number | null; probability?: number | null; children?: ReactNode }) {
  return (
    <div className="flex flex-col gap-[18px] rounded-panel border border-sand-200 bg-white p-5 sm:p-6">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          <span aria-hidden="true" className="flex h-7 w-7 items-center justify-center rounded-tile bg-green-50 text-green-600">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M3 3v18h18" /><path d="m19 9-5 5-4-4-3 3" />
            </svg>
          </span>
          <h3 className="text-[15px] font-semibold leading-6">Lead Score</h3>
        </div>
        <ScoreBadge score={score} />
      </div>
      <div className="flex flex-col gap-2">
        <div className="flex items-baseline gap-1.5">
          <span className="num text-[32px] font-medium leading-9 tracking-[-0.02em]">{score ?? "–"}</span>
          <span className="num text-[13px] text-ink-500">/ 100</span>
        </div>
        <span className="text-xs text-ink-500">
          {probability !== undefined && probability !== null
            ? `${Math.round(probability * 100)}% likely to become a client`
            : "How likely this lead is to become a client"}
        </span>
      </div>
      {children}
    </div>
  );
}
