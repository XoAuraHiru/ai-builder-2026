"use client";

import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { formatUsd, type AllocationPoint } from "@/lib/allocation";

const COLORS = ["#0b5fff", "#5b8def", "#9fbcff", "#1f8a70", "#59b89c", "#f2a93b", "#d95d39"];

export function AllocationChart({ title, data }: { title: string; data: AllocationPoint[] }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-3">
      <h3 className="mb-1 text-sm font-semibold">{title}</h3>
      {data.length === 0 ? (
        <p className="py-8 text-center text-sm text-slate-500">No holdings yet</p>
      ) : (
        <div className="h-52">
          <ResponsiveContainer>
            <PieChart>
              <Pie data={data} dataKey="value" nameKey="name" innerRadius={50} outerRadius={80} paddingAngle={2}>
                {data.map((d, i) => (
                  <Cell key={d.name} fill={COLORS[i % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip formatter={(v) => formatUsd(Number(v))} />
            </PieChart>
          </ResponsiveContainer>
        </div>
      )}
      <ul className="mt-1 grid grid-cols-2 gap-x-3 text-xs text-slate-600">
        {data.map((d, i) => (
          <li key={d.name} className="flex items-center gap-1">
            <span className="inline-block h-2 w-2 rounded-full" style={{ background: COLORS[i % COLORS.length] }} />
            {d.name} {d.pct}%
          </li>
        ))}
      </ul>
    </div>
  );
}
