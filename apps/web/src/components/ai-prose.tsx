import type { ReactNode } from "react";
import { figureSpans } from "@/lib/ai-figures";
import { Sparkle } from "@/components/ui";

export type Narrative = {
  headline: string;
  paragraphs: string[];
  cautions: string[];
  unsupported_figures: string[];
  verified: boolean;
  model: string;
};

/** Words written by Gemini: a violet panel, the text in Newsreader, captioned with who wrote it and what was checked.
 *  Violet marks provenance only; the person's decision stays in the page's own buttons. */
export function AiProse({ children, caption, warning, model, actions }:
  { children: ReactNode; caption: string; warning?: string; model?: string; actions?: ReactNode }) {
  return (
    <figure className="flex max-w-[860px] flex-col gap-4 rounded-[16px] bg-ai-50 px-6 py-[22px]">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <span className="inline-flex items-center gap-2 text-[13px] font-semibold text-ai-700"><Sparkle />Written by Gemini</span>
        {model && <span className="code text-[11px] text-ai-700">{model}</span>}
      </div>
      <div className="font-serif text-[17px] leading-[26px] text-ink-900 sm:text-[19px] sm:leading-[29px]">{children}</div>
      {warning && (
        <p className="self-start rounded-[6px] bg-amber-50 px-2 py-1 text-[13px] font-medium text-amber-800">{warning}</p>
      )}
      <figcaption className="flex flex-wrap items-center justify-between gap-3 border-t border-ai-100 pt-3.5 text-xs text-ink-700">
        <span>{caption}</span>
        {actions && <span className="flex gap-2">{actions}</span>}
      </figcaption>
    </figure>
  );
}

/** Gemini's text with every dollar and percentage marked: dotted green when an engine produced it, amber when not. */
export function CheckedText({ text, unsupported }: { text: string; unsupported: string[] }) {
  return (
    <>
      {figureSpans(text, unsupported).map((s, i) =>
        s.kind === "text" ? <span key={i}>{s.text}</span>
          : s.kind === "checked" ? <span key={i} className="border-b-[1.5px] border-dotted border-green-500">{s.text}</span>
          : <span key={i} title="Not produced by an engine" className="rounded-[4px] border-b-[1.5px] border-amber-400 bg-amber-50 px-1 text-amber-800">{s.text}</span>)}
    </>
  );
}

export function FigureLegend({ unchecked }: { unchecked: boolean }) {
  return (
    <span className="flex flex-wrap gap-4">
      <span className="inline-flex items-center gap-1.5"><span aria-hidden="true" className="w-3.5 border-b-[1.5px] border-dotted border-green-500" />Checked against the engine</span>
      {unchecked && (
        <span className="inline-flex items-center gap-1.5"><span aria-hidden="true" className="h-2.5 w-3.5 rounded-[3px] border-b-[1.5px] border-amber-400 bg-amber-50" />Not produced by an engine</span>
      )}
    </span>
  );
}

export function NarrativeView({ narrative }: { narrative: Narrative }) {
  const bad = narrative.unsupported_figures;
  return (
    <AiProse model={narrative.model}
      caption={`From the figures on this page. Every dollar and percentage figure is checked against the engine.`}
      warning={narrative.verified ? undefined
        : `Check before relying on this: ${bad.join(", ")} did not come from the engine.`}
      actions={<FigureLegend unchecked={bad.length > 0} />}>
      <p className="text-[20px] font-medium leading-snug sm:text-[22px]"><CheckedText text={narrative.headline} unsupported={bad} /></p>
      {narrative.paragraphs.map((p, i) => <p key={i} className="mt-3"><CheckedText text={p} unsupported={bad} /></p>)}
      {narrative.cautions.length > 0 && (
        <ul className="mt-3 list-disc space-y-1 pl-5 font-sans text-[15px] leading-[22px] text-ink-700">
          {narrative.cautions.map((c, i) => <li key={i}>{c}</li>)}
        </ul>
      )}
    </AiProse>
  );
}
