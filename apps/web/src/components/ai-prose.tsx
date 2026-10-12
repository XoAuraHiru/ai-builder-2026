import type { ReactNode } from "react";

export type Narrative = {
  headline: string;
  paragraphs: string[];
  cautions: string[];
  unsupported_figures: string[];
  verified: boolean;
  model: string;
};

/** Words written by Gemini. They are always set in the serif, beside a daylight rule, with who wrote them. */
export function AiProse({ children, caption, warning }: { children: ReactNode; caption: string; warning?: string }) {
  return (
    <figure className="border-l-2 border-daylight pl-5">
      <div className="max-w-[68ch] font-serif text-[17px] leading-[1.65] text-ink">{children}</div>
      <figcaption className="mt-3 text-xs text-daylight-ink">{caption}</figcaption>
      {warning && <p className="mt-2 text-xs font-medium text-caution">{warning}</p>}
    </figure>
  );
}

export function NarrativeView({ narrative }: { narrative: Narrative }) {
  return (
    <AiProse
      caption={`Written by ${narrative.model} from the figures on this page. Every dollar and percentage figure is checked against the engine.`}
      warning={narrative.verified ? undefined
        : `Check before relying on this: ${narrative.unsupported_figures.join(", ")} did not come from the engine.`}>
      <p className="text-[20px] font-semibold leading-snug">{narrative.headline}</p>
      {narrative.paragraphs.map((p, i) => <p key={i} className="mt-3">{p}</p>)}
      {narrative.cautions.length > 0 && (
        <ul className="mt-3 list-disc space-y-1 pl-5 text-[15px] text-ink-2">
          {narrative.cautions.map((c, i) => <li key={i}>{c}</li>)}
        </ul>
      )}
    </AiProse>
  );
}
