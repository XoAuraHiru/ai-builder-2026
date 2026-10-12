import { BAND_COLOR } from "@/lib/invest";
import { BAND_LABEL } from "@/components/ui";

const BANDS = [1, 2, 3, 4, 5];

/** The five risk bands with the investor's profile (solid ring) and their portfolio (dashed ring) marked. */
export function RiskScale({ profile, portfolio }: { profile: number | null; portfolio: number }) {
  const said = profile
    ? `Risk scale from 1 to 5: your profile is band ${profile}, ${BAND_LABEL[profile]}; your portfolio behaves like band ${portfolio}, ${BAND_LABEL[portfolio]}`
    : `Risk scale from 1 to 5: your portfolio behaves like band ${portfolio}, ${BAND_LABEL[portfolio]}`;
  return (
    <div role="img" aria-label={said} className="space-y-2.5">
      <div className="grid grid-cols-5 gap-1.5" aria-hidden="true">
        {BANDS.map((b) => (
          <div key={b} className="h-3.5 rounded-[4px]"
            style={{
              background: BAND_COLOR[b], outlineOffset: 2,
              outline: b === profile ? "2px solid var(--color-ink)" : b === portfolio ? "2px dashed var(--color-loss)" : undefined,
            }} />
        ))}
      </div>
      <div className="grid grid-cols-5 gap-1.5 text-[12px] leading-snug text-muted sm:text-[13px]" aria-hidden="true">
        {BANDS.map((b) => (
          <span key={b} className={b === profile ? "font-semibold text-ink" : b === portfolio ? "font-semibold text-loss" : ""}>
            {b} {BAND_LABEL[b]}
            {b === profile && <span className="block">{b === portfolio ? "your profile and portfolio" : "your profile"}</span>}
            {b === portfolio && b !== profile && <span className="block">your portfolio now</span>}
          </span>
        ))}
      </div>
    </div>
  );
}
