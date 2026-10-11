"use client";

import { useState } from "react";

export type Evidence = { label: string; detail: string };

/** The explain-everything primitive: every AI or computed number on screen opens one of these. */
export function WhyPanel({
  title,
  evidence,
  confidence,
  model,
}: {
  title: string;
  evidence: Evidence[];
  confidence?: number;
  model?: string;
}) {
  const [open, setOpen] = useState(false);
  return (
    <div className="rounded-lg border border-slate-200 bg-white text-sm">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen(!open)}
        className="flex w-full items-center justify-between px-3 py-2 text-left font-medium"
      >
        <span>Why: {title}</span>
        <span className="text-xs text-slate-500">
          {confidence !== undefined && `confidence ${Math.round(confidence * 100)}% `}
          {open ? "Hide" : "Show"}
        </span>
      </button>
      {open && (
        <div className="border-t border-slate-100 px-3 py-2">
          <ul className="list-disc space-y-1 pl-5">
            {evidence.map((e) => (
              <li key={e.label}>
                <span className="font-medium">{e.label}:</span> {e.detail}
              </li>
            ))}
          </ul>
          {model && <p className="mt-2 text-xs text-slate-500">Source: {model}. Illustrative, not advice.</p>}
        </div>
      )}
    </div>
  );
}
