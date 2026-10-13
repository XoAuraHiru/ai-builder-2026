"use client";

import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { formatDate, formatPct, formatUsd } from "@/lib/format";
import { ASSET_COLOR, CATEGORY, findingCards, sectorRows, type Finding, type Narrative, type XRay } from "@/lib/invest";
import { useMe } from "@/lib/session-context";
import { AllocationBar } from "@/components/allocation-bar";
import { NarrativeView } from "@/components/ai-prose";
import { TickerTile } from "@/components/market-bits";
import { WhyPanel } from "@/components/why-panel";
import { Badge, Button, ButtonLink, EmptyState, Figure, Loading, Notice, PageHeader, Panel, Section, Sparkle,
  tableStyles } from "@/components/ui";

const COMPANIES_SHOWN = 5;
const VIA_SHOWN = 3;

/** An ETF named as a chip: outlined, in Geist Mono. */
function EtfChip({ ticker }: { ticker: string }) {
  return <span className="code rounded-full border border-sand-200 px-2 py-[3px] text-[11px] leading-4 text-ink-900">{ticker}</span>;
}

/** X2: one card per finding — the figure large, a status chip, and what it names as chips. */
function FindingCard({ f }: { f: Finding }) {
  const chips = f.chips.length > 0 && (
    <span className="flex flex-wrap gap-1.5">
      {f.chips.map((c) => c.mono ? <EtfChip key={c.text} ticker={c.text} />
        : <span key={c.text} className="whitespace-nowrap rounded-full bg-fill px-2.5 py-1 text-xs font-medium text-ink-900">{c.text}</span>)}
    </span>
  );
  return (
    <Panel className="flex flex-col gap-3.5 p-6">
      <div className="flex items-start justify-between gap-3">
        <h3 className="min-w-0 pt-1 text-[15px] font-semibold leading-5">{f.title}</h3>
        <Badge tone={f.tone === "look" ? "caution" : "neutral"}>{f.tone === "look" ? "Worth a look" : "Note"}</Badge>
      </div>
      {f.figure && <p className="num text-[40px] font-medium leading-[44px] tracking-[-0.03em] sm:text-[44px] sm:leading-[46px]">{f.figure}</p>}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm leading-[21px] text-ink-700">{f.sentence}</p>
        {chips}
      </div>
    </Panel>
  );
}

/** X3/X4: the largest companies underneath, each with a small green bar so it reads like the sector list. */
function Companies({ xray }: { xray: XRay }) {
  const [all, setAll] = useState(false);
  const rows = all ? xray.companies : xray.companies.slice(0, COMPANIES_SHOWN);
  const widest = Math.max(...xray.companies.map((c) => c.pct), 0.01);
  const cols = "grid grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)] gap-x-4 sm:grid-cols-[minmax(0,1.4fr)_minmax(0,1.2fr)_170px]";
  return (
    <Panel className="flex min-w-0 flex-col gap-3.5 p-6">
      <div className="flex flex-col gap-1">
        <h2 className="text-base font-semibold">Largest companies you own</h2>
        <p className="text-[13px] leading-5 text-ink-500">From each ETF&apos;s ten largest holdings, which cover {formatPct(xray.coverage_pct)} of your stock exposure.</p>
      </div>
      {xray.companies.length === 0 ? <p className="text-sm text-ink-500">None of your money is in stocks.</p> : (
        <div role="table" aria-label="Largest companies you own">
          <div role="row" className={`${cols} border-b border-sand-100 py-2.5 text-xs font-medium text-ink-500`}>
            <span role="columnheader">Company</span>
            <span role="columnheader">Share of your money</span>
            <span role="columnheader" className="hidden sm:block">Held through</span>
          </div>
          {rows.map((c) => (
            <div role="row" key={c.symbol} className={`${cols} items-center gap-y-2 border-b border-sand-100 py-3 last:border-b-0`}>
              <span role="cell" className="flex min-w-0 items-center gap-2.5">
                <TickerTile size="sm" symbol={c.symbol} />
                <span className="truncate text-sm font-medium" title={c.name}>{c.name}</span>
              </span>
              <span role="cell" className="flex items-center gap-2.5">
                <span aria-hidden="true" className="h-1.5 flex-1 rounded-[3px] bg-sand-100">
                  <span className="block h-1.5 rounded-[3px] bg-green-400" style={{ width: `${(c.pct / widest) * 100}%` }} />
                </span>
                <span className="num w-11 text-right text-[13px]">{formatPct(c.pct)}</span>
              </span>
              <span role="cell" className="col-span-2 flex flex-wrap gap-1 sm:col-span-1">
                <span className="sr-only">Held through {c.via.join(", ")}</span>
                <span aria-hidden="true" className="contents" title={c.via.join(", ")}>
                  {c.via.slice(0, VIA_SHOWN).map((v) => <EtfChip key={v} ticker={v} />)}
                  {c.via.length > VIA_SHOWN && (
                    <span title={c.via.slice(VIA_SHOWN).join(", ")} className="rounded-full px-1.5 py-[3px] text-[11px] font-medium leading-4 text-ink-500">
                      +{c.via.length - VIA_SHOWN}
                    </span>
                  )}
                </span>
              </span>
            </div>
          ))}
        </div>
      )}
      {xray.companies.length > COMPANIES_SHOWN && (
        <div>
          <Button variant="quiet" size="sm" className="-ml-3" aria-expanded={all} onClick={() => setAll(!all)}>
            {all ? `Show the largest ${COMPANIES_SHOWN}` : `Show all ${xray.companies.length}`}
          </Button>
        </div>
      )}
    </Panel>
  );
}

function Sectors({ xray }: { xray: XRay }) {
  return (
    <Panel className="flex flex-col gap-4 p-6">
      <h2 className="text-base font-semibold">Sectors</h2>
      <ul className="flex flex-col gap-3.5">
        {sectorRows(xray.sectors).map((s) => (
          <li key={s.name} className="flex flex-col gap-1.5">
            <span className={`flex justify-between gap-3 text-[13px] ${s.other ? "text-ink-500" : ""}`}>
              <span className="min-w-0 truncate">{s.name}</span><span className="num">{formatPct(s.pct)}</span>
            </span>
            <span aria-hidden="true" className="h-2 rounded-[4px] bg-sand-100">
              <span className={`block h-2 rounded-[4px] ${s.other ? "bg-green-300" : "bg-green-400"}`} style={{ width: `${s.width}%` }} />
            </span>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

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

  const regions = xray.regions.map((r, i) => ({ key: r.name, label: r.name, value: r.value_usd, color: CATEGORY[i % CATEGORY.length] }));
  const assets = xray.asset_classes.map((r, i) => ({ key: r.name, label: r.name, value: r.value_usd, color: ASSET_COLOR[r.name] ?? CATEGORY[i % CATEGORY.length] }));
  const findings = findingCards(xray);
  return (
    <>
      {header}
      <div className="space-y-12">
        <div className="space-y-6">
          {findings.length > 0 && (
            <section aria-labelledby="findings" className="flex flex-col gap-3">
              <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 px-1 sm:px-2">
                <h2 id="findings" className="text-base font-semibold">Things to look at</h2>
                <p className="text-[13px] text-ink-500">Fixed rules applied to what you own underneath. None of them is an instruction to sell.</p>
              </div>
              <div className={`grid gap-4 md:grid-cols-2 ${findings.length >= 3 ? "xl:grid-cols-3" : ""}`}>
                {findings.map((f) => <FindingCard key={f.key} f={f} />)}
              </div>
            </section>
          )}
          <div className="grid gap-4 xl:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
            <Companies xray={xray} />
            <Sectors xray={xray} />
          </div>
        </div>

        <Section title="Regions and asset classes">
          <div className="grid gap-4 lg:grid-cols-2">
            <Panel className="min-w-0 p-6"><AllocationBar title="By region" slices={regions} total={xray.total_value_usd} /></Panel>
            <Panel className="min-w-0 p-6"><AllocationBar title="By asset class" slices={assets} total={xray.total_value_usd} /></Panel>
          </div>
        </Section>

        {xray.overlaps.length > 0 && (
          <Section title="Overlap between your funds" description="Money in two funds that own the same ETFs or companies is less spread out than it looks.">
            <Panel className="px-6 py-2">
              <ul className="divide-y divide-sand-100 text-sm">
                {xray.overlaps.map((o) => (
                  <li key={o.funds.join("-")} className="py-3.5">
                    <p className="font-medium">{o.names[0]} and {o.names[1]}</p>
                    <p className="text-ink-700">
                      {[o.shared_etfs_pct > 0 ? `${formatPct(o.shared_etfs_pct)} in the same ETFs` : "",
                        o.shared_companies_pct > 0 ? `${formatPct(o.shared_companies_pct)} in the same companies` : ""].filter(Boolean).join(" and ")}
                      {o.top_shared.length > 0 ? `, including ${o.top_shared.join(", ")}` : ""}.
                    </p>
                  </li>
                ))}
              </ul>
            </Panel>
          </Section>
        )}

        <Section title="What you pay">
          <Panel className="p-6">
            <div className="grid gap-6 sm:grid-cols-3">
              <Figure label="Every year" value={formatUsd(xray.fees.total_annual_usd)} detail={`${formatPct(xray.fees.total_pct, 2)} of your portfolio`} />
              <Figure label="Atrium fees" value={formatUsd(xray.fees.atrium_annual_usd)} detail="One yearly fee per fund" />
              <Figure label="ETF costs" value={formatUsd(xray.fees.etf_annual_usd)} detail="Already inside the ETF prices" />
            </div>
            <p className="mt-5 border-t border-sand-100 pt-4 text-sm text-ink-700">Over ten years at today&apos;s value, that comes to about {formatUsd(xray.fees.ten_year_usd, 0)}.</p>
          </Panel>
        </Section>

        <Section title="ETFs underneath">
          <Panel className="px-6 py-2">
            <div className={tableStyles.wrap}>
              <table className={`${tableStyles.table} min-w-[520px]`}>
                <thead className={tableStyles.head}>
                  <tr><th className={tableStyles.th}>ETF</th><th className={tableStyles.th}>Holds</th><th className={`${tableStyles.th} text-right`}>Value</th>
                    <th className={`${tableStyles.th} text-right`}>Share</th><th className={`${tableStyles.th} text-right`}>Expense ratio</th></tr>
                </thead>
                <tbody>
                  {xray.etfs.map((e) => (
                    <tr key={e.ticker} className={tableStyles.row}>
                      <td className={tableStyles.td}><span className="flex items-center gap-2.5"><TickerTile size="sm" tone="etf" symbol={e.ticker} /><span className="sr-only">{e.ticker}</span></span></td>
                      <td className={`${tableStyles.td} text-ink-700`}>{e.asset_class === "equity" ? "Stocks" : e.asset_class === "bond" ? "Bonds" : "T-bills"}</td>
                      <td className={`${tableStyles.td} num text-right`}>{formatUsd(e.value_usd)}</td>
                      <td className={`${tableStyles.td} num text-right`}>{formatPct(e.pct)}</td>
                      <td className={`${tableStyles.td} num text-right`}>{e.expense_ratio_pct === null ? "n/a" : formatPct(e.expense_ratio_pct, 2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>
        </Section>

        <Section title="What this means for you" description="Gemini reads the X-ray and explains it. It cannot change the figures.">
          {narrative ? <NarrativeView narrative={narrative} /> : (
            <Button variant="ai" busy={busy} onClick={explain}>{!busy && <Sparkle />}{busy ? "Gemini is reading your X-ray" : "Explain my X-ray"}</Button>
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
