import type { ReactNode } from "react";
import { layoutGraph, type GraphColumns, type GraphEdge, type GraphNode } from "@/lib/compliance";

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
  ai500: "var(--color-ai-500)", ai700: "var(--color-ai-700)", white: "#ffffff",
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
  return (
    <span className="inline-flex items-center gap-2">
      <svg width={line ? 22 : 18} height="18" viewBox={line ? "0 0 22 18" : "0 0 18 18"} aria-hidden="true" className="shrink-0">
        {line
          ? <path d="M 1 9 L 21 9" stroke={mark === "cited" ? C.ai500 : C.ink400} strokeWidth={mark === "cited" ? 3 : 1.5} strokeDasharray={mark === "weak" ? "4 3" : undefined} />
          : <Mark kind={mark === "flagged" ? "person" : mark} flagged={mark === "flagged"} x={9} y={9} />}
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
  return (
    <figure>
      {/* Below 600px the graph keeps its size and scrolls sideways, so its labels stay readable on a phone. */}
      <div className="-mx-1 overflow-x-auto px-1">
        <svg viewBox={`0 0 ${WIDTH} ${height}`} className="mx-auto h-auto w-full min-w-[600px] max-w-[760px]" role="img" aria-labelledby="entity-graph-title">
          <title id="entity-graph-title">{title ?? `Linked entities: ${nodes.length} people, accounts and payers joined by ${edges.length} links`}</title>
          {edges.map((e) => {
            const a = at[e.source];
            const b = at[e.target];
            if (!a || !b) return null;
            const curve = a.x === b.x;
            // A ring's links fan into the few identifiers they share, so their ids sit near the member's end, where
            // the lines are still apart; an alert's labels sit midway.
            const along = e.strong === undefined ? 0.5 : 0.2;
            const mid = curve ? { x: a.x + 70, y: (a.y + b.y) / 2 } : { x: a.x + (b.x - a.x) * along, y: a.y + (b.y - a.y) * along };
            const lit = e.id !== undefined && highlight.includes(e.id);
            return (
              <g key={`${e.source}-${e.target}`}>
                <path d={curve ? `M ${a.x} ${a.y} Q ${a.x + 140} ${(a.y + b.y) / 2} ${b.x} ${b.y}` : `M ${a.x} ${a.y} L ${b.x} ${b.y}`}
                  fill="none" stroke={stroke(lit)} strokeWidth={lit ? 3 : 1.25} strokeLinecap="round"
                  strokeDasharray={e.strong === false ? "5 4" : undefined} />
                <text x={mid.x} y={mid.y - 4} textAnchor="middle" fontSize={11} fill={lit ? C.ai700 : C.ink500}
                  fontFamily={e.id ? "var(--font-mono)" : undefined}
                  fontWeight={lit ? 600 : undefined} stroke={C.white} strokeWidth={4} paintOrder="stroke">{e.label}</text>
              </g>
            );
          })}
          {nodes.map((n) => {
            const p = at[n.id];
            const halo = RING_KINDS.has(n.kind) ? { stroke: C.white, strokeWidth: 4, paintOrder: "stroke" as const } : {};
            return (
              <g key={n.id}>
                <Mark kind={n.kind} flagged={n.flagged} x={p.x} y={p.y} />
                <text x={p.x} y={p.y + 26} textAnchor="middle" fontSize={13} fontWeight={n.flagged ? 600 : 400}
                  fill={n.flagged ? C.coral700 : C.ink900} {...halo}>{n.label}</text>
              </g>
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
