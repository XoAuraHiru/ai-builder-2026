import { Badge } from "@/components/ui";
import { scoreTone, TRUST_LABEL, trustTone, type TrustBand } from "@/lib/leads";

const SCORE_TONE = { high: "gain", medium: "caution", low: "neutral", pending: "neutral" } as const;
const TRUST_TONE = { clear: "gain", review: "caution", high_risk: "loss", blocked: "strong", pending: "neutral" } as const;

export function ScoreBadge({ score }: { score: number | null }) {
  return <Badge tone={SCORE_TONE[scoreTone(score)]}><span className="num">{score === null ? "Lead not scored" : `Lead ${score}`}</span></Badge>;
}

export function TrustBadge({ band, score }: { band: TrustBand | null; score: number | null }) {
  const tone = trustTone(band);
  return (
    <Badge tone={TRUST_TONE[tone]}>
      <span className="num">{score === null ? "Trust not scored" : `Trust ${score}, ${TRUST_LABEL[tone]}`}</span>
    </Badge>
  );
}
