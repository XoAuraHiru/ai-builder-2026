import { layoutGraph, type GraphEdge, type GraphNode } from "@/lib/compliance";

const WIDTH = 720;
const ROW = 84;

function Mark({ node, x, y }: { node: GraphNode; x: number; y: number }) {
  const fill = node.flagged ? "var(--color-ink)" : "var(--color-surface)";
  if (node.kind === "person") return <circle cx={x} cy={y} r={8} fill={fill} stroke="var(--color-ink)" strokeWidth={1.5} />;
  if (node.kind === "account") return <rect x={x - 8} y={y - 8} width={16} height={16} rx={3} fill={fill} stroke="var(--color-ink)" strokeWidth={1.5} />;
  if (node.kind === "bank") return <rect x={x - 9} y={y - 7} width={18} height={14} fill="var(--color-surface)" stroke="var(--color-loss)" strokeWidth={1.5} />;
  return <path d={`M ${x} ${y - 9} L ${x + 9} ${y} L ${x} ${y + 9} L ${x - 9} ${y} Z`} fill="var(--color-surface)" stroke="var(--color-caution)" strokeWidth={1.5} />;
}

/** The people an alert touches and what joins them: a shared bank account, a shared device, an outside payer. */
export function EntityGraph({ nodes, edges }: { nodes: GraphNode[]; edges: GraphEdge[] }) {
  const { at, height } = layoutGraph(nodes, WIDTH, ROW);
  const label = (id: string) => nodes.find((n) => n.id === id)?.label ?? id;
  return (
    <figure>
      {/* Below 600px the graph keeps its size and scrolls sideways, so its labels stay readable on a phone. */}
      <div className="overflow-x-auto">
        <svg viewBox={`0 0 ${WIDTH} ${height}`} className="h-auto w-full min-w-[600px]" role="img" aria-labelledby="entity-graph-title">
          <title id="entity-graph-title">Linked entities: {nodes.length} people, accounts and payers joined by {edges.length} links</title>
          {edges.map((e) => {
            const a = at[e.source];
            const b = at[e.target];
            if (!a || !b) return null;
            const curve = a.x === b.x;
            const mid = curve ? { x: a.x + 70, y: (a.y + b.y) / 2 } : { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
            return (
              <g key={`${e.source}-${e.target}`}>
                <path d={curve ? `M ${a.x} ${a.y} Q ${a.x + 140} ${(a.y + b.y) / 2} ${b.x} ${b.y}` : `M ${a.x} ${a.y} L ${b.x} ${b.y}`}
                  fill="none" stroke={e.label === "shares a device" ? "var(--color-caution)" : "var(--color-line-strong)"} strokeWidth={1.25} />
                <text x={mid.x} y={mid.y - 4} textAnchor="middle" fontSize={11} fill="var(--color-muted)" stroke="var(--color-ground)" strokeWidth={4} paintOrder="stroke">{e.label}</text>
              </g>
            );
          })}
          {nodes.map((n) => {
            const p = at[n.id];
            return (
              <g key={n.id}>
                <Mark node={n} x={p.x} y={p.y} />
                <text x={p.x} y={p.y + 26} textAnchor="middle" fontSize={13} fontWeight={n.flagged ? 600 : 400} fill="var(--color-ink)">{n.label}</text>
              </g>
            );
          })}
        </svg>
      </div>
      <figcaption className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-xs text-muted">
        <span className="sm:hidden">Scroll sideways to see the whole graph.</span>
        <span>Circles are people; the filled one is the alert&apos;s subject.</span>
        <span>Squares are Atrium accounts.</span>
        <span>Red boxes are bank accounts, linked by a keyed hash, never the number.</span>
        <span>Diamonds are outside payers.</span>
      </figcaption>
      <ul className="sr-only">
        {edges.map((e) => <li key={`${e.source}-${e.target}`}>{label(e.source)} {e.label} {label(e.target)}</li>)}
      </ul>
    </figure>
  );
}
