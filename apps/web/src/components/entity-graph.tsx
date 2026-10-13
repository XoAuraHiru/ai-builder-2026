"use client";

import { motion, useReducedMotion } from "motion/react";
import { useId, type ReactNode } from "react";
import { drawOrder, layoutGraph, type GraphColumns, type GraphEdge, type GraphNode } from "@/lib/compliance";
import { EASE } from "@/components/motion";

// The graph assembles once, when it appears: its people and what they share fade in, then each link draws from one
// end to the other (strong links first), then each flagged node's coral ring pulses once. Nothing repeats.
const NODES_FADE = 0.3;
const LINKS_AT = 0.32;
const LINK_DRAW = 0.45;
const linkStep = (count: number) => Math.min(0.07, 0.7 / Math.max(1, count));

const WIDTH = 720;
const ROW = 84;
const RING_KINDS = new Set(["lead", "client", "device", "phone", "email", "ip", "document"]);

// Design system 0.2: people and clients in green, what they share in sand and ink, anything flagged in coral, and
// violet only for a link Gemini cites.
const C = {
  green100: "var(--color-green-100)", green500: "var(--color-green-500)", green600: "var(--color-green-600)",
  sand100: "var(--color-sand-100)", sand200: "var(--color-sand-200)", ink400: "var(--color-ink-400)",
  ink500: "var(--color-ink-500)", ink700: "var(--color-ink-700)", ink900: "var(--color-ink-900)",
  coral50: "var(--color-coral-50)", coral500: "var(--color-coral-500)", coral700: "var(--color-coral-700)",
  ai500: "var(--color-ai-500)", ai700: "var(--color-ai-700)", white: "var(--color-canvas)",
};

type MarkKind = GraphNode["kind"];

function Mark({ kind, flagged, x, y }: { kind: MarkKind; flagged: boolean; x: number; y: number }) {
  if (kind === "person") {
    return <circle cx={x} cy={y} r={8} fill={flagged ? C.coral500 : C.green100} stroke={flagged ? C.coral700 : C.green600} strokeWidth={1.5} />;
  }
  if (kind === "payer") {
    return <path d={`M ${x} ${y - 9} L ${x + 9} ${y} L ${x} ${y + 9} L ${x - 9} ${y} Z`} fill={flagged ? C.coral50 : C.white} stroke={flagged ? C.coral700 : C.green600} strokeWidth={1.5} />;
  }
  if (kind === "lead") return <circle cx={x} cy={y} r={7} fill={flagged ? C.coral500 : C.green500} />;
  if (kind === "client") {
    return (
      <g>
        <circle cx={x} cy={y} r={12} fill={C.white} stroke={flagged ? C.coral500 : C.green600} strokeWidth={1.5} />
        <circle cx={x} cy={y} r={7} fill={flagged ? C.coral500 : C.green500} />
      </g>
    );
  }
  // What people share: Atrium accounts, bank accounts, devices, documents, phones, emails and networks.
  const stroke = flagged ? C.coral700 : kind === "ip" ? C.ink400 : C.ink700;
  if (kind === "account") return <rect x={x - 8} y={y - 8} width={16} height={16} rx={3} fill={flagged ? C.coral50 : C.sand100} stroke={stroke} strokeWidth={1.5} />;
  if (kind === "bank") return <rect x={x - 9} y={y - 7} width={18} height={14} rx={2} fill={flagged ? C.coral50 : C.sand200} stroke={stroke} strokeWidth={1.5} />;
  return <rect x={x - 6} y={y - 6} width={12} height={12} rx={2} fill={flagged ? C.coral50 : C.sand100} stroke={stroke} strokeWidth={1.5} />;
}

/** Every link is ink-400; a weak one is dashed, and one Gemini cites is lit in violet. */
const stroke = (lit: boolean) => (lit ? C.ai500 : C.ink400);

/** A key entry: the mark as drawn in the graph, then what it means. */
export function KeyItem({ mark, children }: { mark: MarkKind | "flagged" | "strong" | "weak" | "cited"; children: ReactNode }) {
  const line = mark === "strong" || mark === "weak" || mark === "cited";
  // A client's mark is a ring 26px across, so its key draws it scaled down to the others' 18px instead of clipping it.
  const box = mark === "client" ? 26 : 18;
  return (
    <span className="inline-flex items-center gap-2">
      <svg width={line ? 22 : 18} height="18" viewBox={line ? "0 0 22 18" : `0 0 ${box} ${box}`} aria-hidden="true" className="shrink-0">
        {line
          ? <path d="M 1 9 L 21 9" stroke={mark === "cited" ? C.ai500 : C.ink400} strokeWidth={mark === "cited" ? 3 : 1.5} strokeDasharray={mark === "weak" ? "4 3" : undefined} />
          : <Mark kind={mark === "flagged" ? "person" : mark} flagged={mark === "flagged"} x={box / 2} y={box / 2} />}
      </svg>
      {children}
    </span>
  );
}

const ALERT_LEGEND = (
  <>
    <KeyItem mark="person">A person</KeyItem>
    <KeyItem mark="flagged">The alert&apos;s subject</KeyItem>
    <KeyItem mark="account">An Atrium account</KeyItem>
    <KeyItem mark="bank">A bank account, linked by a keyed hash, never the number</KeyItem>
    <KeyItem mark="payer">An outside payer</KeyItem>
  </>
);

/** The people an alert touches and what joins them: a shared bank account, a shared device, an outside payer.
 *  Ring graphs pass their own columns and legend; their weak links are dashed, and edges Gemini cites can be lit. */
export function EntityGraph({ nodes, edges, columns, highlight = [], legend = ALERT_LEGEND, title }:
  { nodes: GraphNode[]; edges: GraphEdge[]; columns?: GraphColumns; highlight?: string[]; legend?: ReactNode; title?: string }) {
  const { at, height } = layoutGraph(nodes, WIDTH, ROW, columns);
  const label = (id: string) => nodes.find((n) => n.id === id)?.label ?? id;
  const uid = useId().replace(/[^a-zA-Z0-9_-]/g, "");
  const reduce = useReducedMotion();
  const order = drawOrder(edges);
  const step = linkStep(edges.length);
  const drawAt = (key: string) => LINKS_AT + (order[key] ?? 0) * step;
  const pulseAt = LINKS_AT + Math.max(0, edges.length - 1) * step + LINK_DRAW;
  // With reduced motion the graph is simply there; a lit link still changes colour.
  const draw = (key: string) => (reduce ? {} : {
    initial: { pathLength: 0 }, animate: { pathLength: 1 }, transition: { duration: LINK_DRAW, delay: drawAt(key), ease: EASE },
  });
  const fade = (delay: number) => (reduce ? {} : {
    initial: { opacity: 0 }, animate: { opacity: 1 }, transition: { duration: NODES_FADE, delay, ease: EASE },
  });
  const lightUp = { transition: "stroke 250ms ease-out, stroke-width 250ms ease-out, fill 250ms ease-out" };
  return (
    <figure>
      {/* Below 600px the graph keeps its size and scrolls sideways, so its labels stay readable on a phone. */}
      <div className="-mx-1 overflow-x-auto px-1">
        <svg viewBox={`0 0 ${WIDTH} ${height}`} className="mx-auto h-auto w-full min-w-[600px] max-w-[760px]" role="img" aria-labelledby={`${uid}-title`}>
          <title id={`${uid}-title`}>{title ?? `Linked entities: ${nodes.length} people, accounts and payers joined by ${edges.length} links`}</title>
          {edges.map((e) => {
            const a = at[e.source];
            const b = at[e.target];
            if (!a || !b) return null;
            const key = `${e.source}-${e.target}`;
            const curve = a.x === b.x;
            const d = curve ? `M ${a.x} ${a.y} Q ${a.x + 140} ${(a.y + b.y) / 2} ${b.x} ${b.y}` : `M ${a.x} ${a.y} L ${b.x} ${b.y}`;
            // A ring's links fan into the few identifiers they share, so their ids sit near the member's end, where
            // the lines are still apart; an alert's labels sit midway.
            const along = e.strong === undefined ? 0.5 : 0.2;
            const mid = curve ? { x: a.x + 70, y: (a.y + b.y) / 2 } : { x: a.x + (b.x - a.x) * along, y: a.y + (b.y - a.y) * along };
            const lit = e.id !== undefined && highlight.includes(e.id);
            const dashed = e.strong === false;
            const mask = `${uid}-m${order[key] ?? 0}`;
            const line = { fill: "none", stroke: stroke(lit), strokeWidth: lit ? 3 : 1.25, strokeLinecap: "round" as const, style: lightUp };
            return (
              <g key={key}>
                {dashed ? (
                  // A dashed line cannot draw itself without losing its dashes, so a solid line drawing inside a mask
                  // reveals it from one end to the other.
                  <>
                    {!reduce && (
                      <mask id={mask} maskUnits="userSpaceOnUse">
                        <motion.path d={d} fill="none" stroke="white" strokeWidth={8} strokeLinecap="round" {...draw(key)} />
                      </mask>
                    )}
                    <path d={d} {...line} strokeDasharray="5 4" mask={reduce ? undefined : `url(#${mask})`} />
                  </>
                ) : <motion.path d={d} {...line} {...draw(key)} />}
                <motion.text x={mid.x} y={mid.y - 4} textAnchor="middle" fontSize={11} fill={lit ? C.ai700 : C.ink500}
                  fontFamily={e.id ? "var(--font-mono)" : undefined} style={lightUp}
                  fontWeight={lit ? 600 : undefined} stroke={C.white} strokeWidth={4} paintOrder="stroke"
                  {...fade(drawAt(key) + LINK_DRAW * 0.6)}>{e.label}</motion.text>
              </g>
            );
          })}
          {nodes.map((n, i) => {
            const p = at[n.id];
            const halo = RING_KINDS.has(n.kind) ? { stroke: C.white, strokeWidth: 4, paintOrder: "stroke" as const } : {};
            return (
              <motion.g key={n.id} {...fade(Math.min(i, 8) * 0.03)}>
                {/* A flagged node's ring pulses once, after the links have drawn: here is who the graph is about. */}
                {n.flagged && !reduce && (
                  <motion.circle cx={p.x} cy={p.y} fill="none" stroke={C.coral500} strokeWidth={2}
                    initial={{ r: 10, opacity: 0 }} animate={{ r: [10, 26], opacity: [0.7, 0] }}
                    transition={{ duration: 0.8, delay: pulseAt, ease: EASE }} />
                )}
                <Mark kind={n.kind} flagged={n.flagged} x={p.x} y={p.y} />
                <text x={p.x} y={p.y + 26} textAnchor="middle" fontSize={13} fontWeight={n.flagged ? 600 : 400}
                  fill={n.flagged ? C.coral700 : C.ink900} {...halo}>{n.label}</text>
              </motion.g>
            );
          })}
        </svg>
      </div>
      <figcaption className="mt-4 flex flex-wrap gap-x-5 gap-y-2 text-xs text-ink-500">
        <span className="w-full sm:hidden">Swipe sideways to see the whole graph.</span>
        {legend}
      </figcaption>
      <ul className="sr-only">
        {edges.map((e) => <li key={`${e.source}-${e.target}`}>{label(e.source)} {e.label} {label(e.target)}</li>)}
      </ul>
    </figure>
  );
}
