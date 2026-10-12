"use client";

import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { formatDate, formatPct, formatUsd } from "@/lib/format";
import { CATEGORY, type Narrative, type XRay } from "@/lib/invest";
import { useMe } from "@/lib/session-context";
import { AllocationBar } from "@/components/allocation-bar";
import { NarrativeView } from "@/components/ai-prose";
import { WhyPanel } from "@/components/why-panel";
import { Badge, Button, ButtonLink, EmptyState, Figure, Loading, Notice, PageHeader, Section, tableStyles } from "@/components/ui";

export default function XRayPage() {
  const me = useMe();
  const account = me.accounts[0];
  const [xray, setXray] = useState<XRay | null>(null);
  const [empty, setEmpty] = useState("");
  const [error, setError] = useState("");
  const [narrative, setNarrative] = useState<Narrative | null>(null);
  const [busy, setBusy] = useState(false);
  const [explainError, setExplainError] = useState("");

  useEffect(() => {
    if (!account) return;
    api<XRay>(`/accounts/${account.id}/xray`).then(setXray).catch((e) => {
      if (e instanceof ApiError && e.status === 409) setEmpty(e.message);
      else setError(e instanceof ApiError ? e.message : "Atrium could not load your X-ray.");
    });
  }, [account]);

  async function explain() {
    setBusy(true);
    setExplainError("");
    try {
      setNarrative((await api<{ narrative: Narrative }>(`/accounts/${account!.id}/xray/explain`, { method: "POST" })).narrative);
    } catch (e) {
      setExplainError(e instanceof ApiError ? e.message : "The explanation is unavailable right now.");
    } finally {
      setBusy(false);
    }
  }

  const header = <PageHeader title="Portfolio X-ray" description="Your funds hold ETFs, and the ETFs hold companies. This is what you own underneath." />;
  if (!account || empty) return <>{header}<EmptyState title="Nothing to look through yet" action={<ButtonLink href="/investor/orders">Make your first investment</ButtonLink>}>{empty || "Choose an investor persona to see an X-ray."}</EmptyState></>;
  if (error) return <>{header}<Notice tone="error" title="Could not load your X-ray">{error}</Notice></>;
  if (!xray) return <>{header}<Loading label="Looking through your funds" /></>;

  const widest = Math.max(...xray.sectors.map((s) => s.pct), 1);
  const toSlices = (rows: XRay["regions"]) => rows.map((r, i) => ({ key: r.name, label: r.name, value: r.value_usd, color: CATEGORY[i % CATEGORY.length] }));
  return (
    <>
      {header}
      <div className="space-y-12">
        {xray.warnings.length > 0 && (
          <Section title="Things to look at" description="Fixed rules applied to what you own underneath. None of them is an instruction to sell.">
            <ul className="divide-y divide-line border-y border-line">
              {xray.warnings.map((w) => (
                <li key={w.code + w.message} className="grid gap-x-4 gap-y-0.5 py-3 sm:grid-cols-[14rem_minmax(0,1fr)]">
                  <span className="flex items-center gap-2 text-sm font-medium">
                    <span aria-hidden="true" className={`h-1.5 w-1.5 shrink-0 rounded-full ${w.severity === "caution" ? "bg-caution" : "bg-ink-2"}`} />{w.title}
                  </span>
                  <span className="text-sm text-ink-2">{w.message}</span>
                </li>
              ))}
            </ul>
          </Section>
        )}
        <div className="grid gap-12 lg:grid-cols-2">
          <div>
          <Section title="Largest companies you own" description={`From each ETF's ten largest holdings, which cover ${formatPct(xray.coverage_pct)} of your stock exposure.`}>
            <table className={tableStyles.table}>
              <thead className={tableStyles.head}>
                <tr><th className={tableStyles.th}>Company</th><th className={`${tableStyles.th} text-right`}>Share</th><th className={tableStyles.th}>Held through</th></tr>
              </thead>
              <tbody>
                {xray.companies.map((c) => (
                  <tr key={c.symbol} className={tableStyles.row}>
                    <td className={tableStyles.td}>{c.name}</td>
                    <td className={`${tableStyles.td} num text-right`}>{formatPct(c.pct, 2)}</td>
                    <td className={tableStyles.td}><span className="flex flex-wrap gap-1">{c.via.map((v) => <Badge key={v}>{v}</Badge>)}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Section>
          </div>
          <div>
          <Section title="Sectors">
            <ul className="space-y-2.5">
              {xray.sectors.map((s) => (
                <li key={s.name} className="grid grid-cols-[minmax(0,10rem)_1fr_3.5rem] items-center gap-3 text-sm">
                  <span className="truncate">{s.name}</span>
                  <span className="h-2 rounded-full bg-line"><span className="block h-2 rounded-full bg-ink" style={{ width: `${(s.pct / widest) * 100}%` }} /></span>
                  <span className="num text-right text-ink-2">{formatPct(s.pct)}</span>
                </li>
              ))}
            </ul>
          </Section>
          </div>
        </div>
        <Section title="Regions and asset classes">
          <div className="grid gap-8 md:grid-cols-2">
            <AllocationBar title="By region" slices={toSlices(xray.regions)} total={xray.total_value_usd} />
            <AllocationBar title="By asset class" slices={toSlices(xray.asset_classes)} total={xray.total_value_usd} />
          </div>
        </Section>
        {xray.overlaps.length > 0 && (
          <Section title="Overlap between your funds" description="Money in two funds that own the same ETFs or companies is less spread out than it looks.">
            <ul className="divide-y divide-line border-y border-line text-sm">
              {xray.overlaps.map((o) => (
                <li key={o.funds.join("-")} className="py-3">
                  <p className="font-medium">{o.names[0]} and {o.names[1]}</p>
                  <p className="text-ink-2">
                    {[o.shared_etfs_pct > 0 ? `${formatPct(o.shared_etfs_pct)} in the same ETFs` : "",
                      o.shared_companies_pct > 0 ? `${formatPct(o.shared_companies_pct)} in the same companies` : ""].filter(Boolean).join(" and ")}
                    {o.top_shared.length > 0 ? `, including ${o.top_shared.join(", ")}` : ""}.
                  </p>
                </li>
              ))}
            </ul>
          </Section>
        )}
        <Section title="What you pay">
          <div className="grid gap-6 sm:grid-cols-3">
            <Figure label="Every year" value={formatUsd(xray.fees.total_annual_usd)} detail={`${formatPct(xray.fees.total_pct, 2)} of your portfolio`} />
            <Figure label="Atrium fees" value={formatUsd(xray.fees.atrium_annual_usd)} detail="One yearly fee per fund" />
            <Figure label="ETF costs" value={formatUsd(xray.fees.etf_annual_usd)} detail="Already inside the ETF prices" />
          </div>
          <p className="mt-4 text-sm text-ink-2">Over ten years at today&apos;s value, that comes to about {formatUsd(xray.fees.ten_year_usd, 0)}.</p>
        </Section>
        <Section title="ETFs underneath">
          <div className={tableStyles.wrap}>
            <table className={tableStyles.table}>
              <thead className={tableStyles.head}>
                <tr><th className={tableStyles.th}>ETF</th><th className={tableStyles.th}>Holds</th><th className={`${tableStyles.th} text-right`}>Value</th>
                  <th className={`${tableStyles.th} text-right`}>Share</th><th className={`${tableStyles.th} text-right`}>Expense ratio</th></tr>
              </thead>
              <tbody>
                {xray.etfs.map((e) => (
                  <tr key={e.ticker} className={tableStyles.row}>
                    <td className={`${tableStyles.td} font-medium`}>{e.ticker}</td>
                    <td className={`${tableStyles.td} text-ink-2`}>{e.asset_class === "equity" ? "Stocks" : e.asset_class === "bond" ? "Bonds" : "T-bills"}</td>
                    <td className={`${tableStyles.td} num text-right`}>{formatUsd(e.value_usd)}</td>
                    <td className={`${tableStyles.td} num text-right`}>{formatPct(e.pct)}</td>
                    <td className={`${tableStyles.td} num text-right`}>{e.expense_ratio_pct === null ? "n/a" : formatPct(e.expense_ratio_pct, 2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Section>
        <Section title="What this means for you" description="Gemini reads the X-ray and explains it. It cannot change the figures.">
          {narrative ? <NarrativeView narrative={narrative} /> : (
            <Button variant="secondary" busy={busy} onClick={explain}>{busy ? "Gemini is reading your X-ray" : "Explain my X-ray"}</Button>
          )}
          {explainError && <div className="mt-3"><Notice tone="caution">{explainError}</Notice></div>}
        </Section>
        <WhyPanel title="how the X-ray works" model="look-through engine (no AI in the figures)"
          evidence={[
            { label: "Funds to ETFs", detail: "Each house fund holds ETFs in fixed weights, so your money in each ETF is exact." },
            { label: "ETFs to companies and sectors", detail: `From each ETF's published top-ten holdings and sector weights (Yahoo Finance, ${formatDate(xray.profiles_as_of)}). Company shares are a lower bound.` },
            { label: "Warnings", detail: "Fixed rules: one company above 5%, one sector above 35%, one fund above 60%, more than 90% in the US, or two funds sharing a quarter of their ETFs or 15% of their companies." },
            { label: "Fees", detail: "The Atrium fee for each fund plus each ETF's expense ratio, at today's value." },
          ]} />
      </div>
    </>
  );
}
