import type { ReactNode } from "react";
import { layoutGraph, type GraphColumns, type GraphEdge, type GraphNode } from "@/lib/compliance";

const WIDTH = 720;
const ROW = 84;
const RING_KINDS = new Set(["lead", "client", "device", "phone", "email", "ip", "document"]);

function Mark({ node, x, y }: { node: GraphNode; x: number; y: number }) {
  const fill = node.flagged ? "var(--color-ink)" : "var(--color-surface)";
  if (node.kind === "person") return <circle cx={x} cy={y} r={8} fill={fill} stroke="var(--color-ink)" strokeWidth={1.5} />;
  if (node.kind === "account") return <rect x={x - 8} y={y - 8} width={16} height={16} rx={3} fill={fill} stroke="var(--color-ink)" strokeWidth={1.5} />;
  if (node.kind === "bank") return <rect x={x - 9} y={y - 7} width={18} height={14} fill="var(--color-surface)" stroke="var(--color-loss)" strokeWidth={1.5} />;
  if (node.kind === "payer") return <path d={`M ${x} ${y - 9} L ${x + 9} ${y} L ${x} ${y + 9} L ${x - 9} ${y} Z`} fill="var(--color-surface)" stroke="var(--color-caution)" strokeWidth={1.5} />;
  // Ring graphs: leads and clients are filled discs (a client has an outer ring), flagged ones in the loss tone; what
  // they share is a small square.
  const tone = node.flagged ? "var(--color-loss)" : "var(--color-ink)";
  if (node.kind === "lead") return <circle cx={x} cy={y} r={7} fill={tone} />;
  if (node.kind === "client") {
    return (
      <g>
        <circle cx={x} cy={y} r={12} fill="var(--color-surface)" stroke={tone} strokeWidth={1.5} />
        <circle cx={x} cy={y} r={7} fill={tone} />
      </g>
    );
  }
  return <rect x={x - 6} y={y - 6} width={12} height={12} rx={2} fill="var(--color-surface)" stroke={node.kind === "ip" ? "var(--color-muted)" : "var(--color-ink-2)"} strokeWidth={1.5} />;
}

function stroke(e: GraphEdge, lit: boolean): string {
  if (lit) return "var(--color-daylight)";
  if (e.strong !== undefined) return "var(--color-muted)";
  return e.label === "shares a device" ? "var(--color-caution)" : "var(--color-line-strong)";
}

const ALERT_LEGEND = (
  <>
    <span>Circles are people; the filled one is the alert&apos;s subject.</span>
    <span>Squares are Atrium accounts.</span>
    <span>Red boxes are bank accounts, linked by a keyed hash, never the number.</span>
    <span>Diamonds are outside payers.</span>
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
      <div className="overflow-x-auto">
        <svg viewBox={`0 0 ${WIDTH} ${height}`} className="h-auto w-full min-w-[600px]" role="img" aria-labelledby="entity-graph-title">
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
                  fill="none" stroke={stroke(e, lit)} strokeWidth={lit ? 3 : 1.25}
                  strokeDasharray={e.strong === false ? "5 4" : undefined} />
                <text x={mid.x} y={mid.y - 4} textAnchor="middle" fontSize={11} fill={lit ? "var(--color-daylight-ink)" : "var(--color-muted)"}
                  fontWeight={lit ? 600 : undefined} stroke="var(--color-ground)" strokeWidth={4} paintOrder="stroke">{e.label}</text>
              </g>
            );
          })}
          {nodes.map((n) => {
            const p = at[n.id];
            const halo = RING_KINDS.has(n.kind) ? { stroke: "var(--color-surface)", strokeWidth: 4, paintOrder: "stroke" as const } : {};
            return (
              <g key={n.id}>
                <Mark node={n} x={p.x} y={p.y} />
                <text x={p.x} y={p.y + 26} textAnchor="middle" fontSize={13} fontWeight={n.flagged ? 600 : 400} fill="var(--color-ink)" {...halo}>{n.label}</text>
              </g>
            );
          })}
        </svg>
      </div>
      <figcaption className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-xs text-muted">
        <span className="sm:hidden">Scroll sideways to see the whole graph.</span>
        {legend}
      </figcaption>
      <ul className="sr-only">
        {edges.map((e) => <li key={`${e.source}-${e.target}`}>{label(e.source)} {e.label} {label(e.target)}</li>)}
      </ul>
    </figure>
  );
}
