"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { api, ApiError } from "@/lib/api";
import { formatDate } from "@/lib/format";
import {
  canFlagLeads, canOpenCase, flaggedMessage, KIND_LABEL, PATTERN_LABEL, RING_COLUMNS, ringHeadline, scoreTone, stageLabel,
  type NarrateResult, type Ring, type RingDetail, type RingList,
} from "@/lib/rings";
import { AiProse } from "@/components/ai-prose";
import { EntityGraph } from "@/components/entity-graph";
import { Badge, Button, ButtonLink, EmptyState, KeyMoment, Loading, Notice, PageHeader, Panel, Section, tableStyles as t } from "@/components/ui";

const msg = (e: unknown, fallback: string) => (e instanceof ApiError ? e.message : fallback);
const CHIP = "num inline-flex h-5 min-w-6 items-center justify-center rounded-[5px] bg-daylight-wash px-1 align-[2px] font-sans text-[11px] font-semibold text-daylight-ink hover:bg-daylight hover:text-ink";
const plural = (n: number, word: string, many = `${word}s`) => `${n} ${n === 1 ? word : many}`;

type Done = { kind: "case"; alertId: string; title: string } | { kind: "flagged"; text: string };

const RING_LEGEND = (
  <>
    <span>Discs are leads; a disc inside a ring is a client. Red ones are flagged.</span>
    <span>Squares are what they share: a device, phone, email, document or network. Red boxes are bank accounts.</span>
    <span>Solid lines are strong links. Dashed lines are a shared network: shown, but they never join anyone.</span>
    <span>L1, L2 and so on are the link ids Gemini cites.</span>
  </>
);

function RingFacts({ ring }: { ring: Ring }) {
  return (
    <div className="flex flex-wrap items-center gap-2 text-sm text-ink-2">
      <Badge tone={scoreTone(ring.score)}>Ring score {ring.score} of 100</Badge>
      <Badge>{stageLabel(ring.stages)}</Badge>
      <span>{plural(ring.members.length, "identity", "identities")}, {plural(ring.identifiers, "shared identifier")}, {plural(ring.links, "link")}</span>
    </div>
  );
}

function Reading({ result, onLight }: { result: NarrateResult; onLight: (ids: string[]) => void }) {
  const { narrative } = result;
  const problems = [
    result.dropped_citations ? `${plural(result.dropped_citations, "citation")} to links outside this ring ${result.dropped_citations === 1 ? "was" : "were"} removed` : "",
    result.unsupported_figures.length ? `${result.unsupported_figures.join(", ")} did not come from the ring` : "",
  ].filter(Boolean);
  return (
    <AiProse caption={`Written by ${result.model} from the ring's members and links. It explains what the graph found; you decide.`}
      warning={problems.length ? `Check before relying on this: ${problems.join("; ")}.` : undefined}>
      <p><span className="font-semibold">Resembles: {PATTERN_LABEL[narrative.pattern]}.</span> {narrative.summary}</p>
      {narrative.parts.map((part, i) => (
        <p key={i} className="mt-3" onMouseEnter={() => onLight(part.links)} onMouseLeave={() => onLight([])}>
          {part.text}{" "}
          {part.links.map((id) => (
            <button key={id} type="button" className={`${CHIP} ml-0.5`} aria-label={`Show link ${id} in the graph`}
              onFocus={() => onLight([id])} onBlur={() => onLight([])} onClick={() => onLight([id])}>{id}</button>
          ))}
        </p>
      ))}
      {narrative.next_checks.length > 0 && (
        <>
          <p className="mt-4 font-semibold">Checks worth making</p>
          <ul className="mt-1 list-disc space-y-1 pl-5">{narrative.next_checks.map((c, i) => <li key={i}>{c}</li>)}</ul>
        </>
      )}
    </AiProse>
  );
}

export default function RingsPage() {
  const [list, setList] = useState<RingList | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [detail, setDetail] = useState<RingDetail | null>(null);
  const [readings, setReadings] = useState<Record<string, NarrateResult>>({});
  const [lit, setLit] = useState<string[]>([]);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [changed, setChanged] = useState(false);
  const [done, setDone] = useState<Done | null>(null);

  const load = useCallback(async (want?: string | null) => {
    const rings = await api<RingList>("/compliance/rings");
    const id = rings.rings.find((r) => r.id === want)?.id ?? rings.strongest?.id ?? null;
    setList(rings);
    setSelected(id);
    setDetail(id ? await api<RingDetail>(`/compliance/rings/${id}`) : null);
  }, []);

  useEffect(() => {
    load().catch((e) => setError(msg(e, "Atrium could not load the rings. Try again.")));
  }, [load]);

  async function choose(id: string) {
    if (id === selected) return;
    setSelected(id);
    setDone(null);
    setError("");
    setChanged(false);
    setLit([]);
    try {
      setDetail(await api<RingDetail>(`/compliance/rings/${id}`));
    } catch (e) {
      setError(msg(e, "Atrium could not load this ring. Try again."));
    }
  }

  async function act(key: "narrate" | "case" | "flag-leads", ring: RingDetail) {
    setBusy(key);
    setError("");
    setChanged(false);
    setDone(null);
    const body = JSON.stringify({ members: ring.members.map((m) => m.id) });
    try {
      if (key === "narrate") {
        const out = await api<NarrateResult>(`/compliance/rings/${ring.id}/narrate`, { method: "POST", body });
        setReadings((r) => ({ ...r, [ring.id]: out }));
        return;
      }
      if (key === "case") {
        const out = await api<{ alert_id: string; title: string }>(`/compliance/rings/${ring.id}/case`, { method: "POST", body });
        setDone({ kind: "case", alertId: out.alert_id, title: out.title });
      } else {
        const out = await api<{ flagged: number }>(`/compliance/rings/${ring.id}/flag-leads`, { method: "POST", body });
        setDone({ kind: "flagged", text: flaggedMessage(out.flagged) });
      }
      await load(ring.id);
    } catch (e) {
      if (e instanceof ApiError && e.status === 409 && e.message.includes("changed")) setChanged(true);
      setError(msg(e, key === "narrate" ? "Gemini could not explain this ring right now." : "Atrium could not record that. Try again."));
    } finally {
      setBusy("");
    }
  }

  const header = (
    <PageHeader title="Fraud rings"
      description="One graph across leads, clients, devices, bank accounts and documents. The graph finds the rings; Gemini only explains them; you decide." />
  );
  if (!list) return <>{header}{error ? <Notice tone="error">{error}</Notice> : <Loading label="Loading the rings" />}</>;
  if (list.rings.length === 0) {
    return (
      <>
        {header}
        <EmptyState title="No rings right now">A ring appears when two or more leads or clients share a device, a bank account, an identity document, a phone number or an email address.</EmptyState>
      </>
    );
  }

  const ring = detail && detail.id === selected ? detail : null;
  const reading = ring ? readings[ring.id] : undefined;
  const allFlagged = ring ? ring.flagged_leads === ring.members.filter((m) => m.kind === "lead").length : false;
  return (
    <>
      {header}
      <div className="space-y-10">
        {ring ? (
          <KeyMoment tone="alert" label={ring.id === list.strongest?.id ? "The strongest ring" : "The ring you selected"} title={ringHeadline(ring)}
            actions={
              <>
                <Button variant="secondary" busy={busy === "narrate"} disabled={Boolean(busy)} onClick={() => act("narrate", ring)}>
                  {reading ? "Explain it again" : "Explain this ring"}
                </Button>
                {canOpenCase(ring) && (ring.case ? (
                  <ButtonLink href={`/compliance/alerts/${ring.case.id}`} variant="secondary">Open the case</ButtonLink>
                ) : (
                  <Button busy={busy === "case"} disabled={Boolean(busy)} onClick={() => act("case", ring)}>Open a case</Button>
                ))}
                {canFlagLeads(ring) && (
                  <Button variant="secondary" busy={busy === "flag-leads"} disabled={Boolean(busy) || allFlagged} onClick={() => act("flag-leads", ring)}>
                    {allFlagged ? "Leads flagged" : "Flag the leads"}
                  </Button>
                )}
              </>
            }>
            <RingFacts ring={ring} />
            {done?.kind === "case" && (
              <Notice tone="success" title="Case opened">
                <Link className="underline underline-offset-4" href={`/compliance/alerts/${done.alertId}`}>{done.title}</Link> is an open alert now; you decide it from the alert page as usual.
              </Notice>
            )}
            {done?.kind === "flagged" && <Notice tone="success" title="Leads flagged">{done.text}</Notice>}
            {ring.case && done?.kind !== "case" && (
              <p className="text-sm text-ink-2">A case is {ring.case.state} for this ring: <Link className="underline underline-offset-4" href={`/compliance/alerts/${ring.case.id}`}>{ring.case.title}</Link>.</p>
            )}
            {error && (
              <Notice tone="error" action={changed ? <Button size="sm" variant="secondary" onClick={() => { setError(""); setChanged(false); load(selected).catch(() => setError("Atrium could not reload the rings.")); }}>Reload</Button> : undefined}>
                {error}
              </Notice>
            )}
          </KeyMoment>
        ) : error ? <Notice tone="error">{error}</Notice> : <Loading label="Loading the ring" />}

        <div className="grid gap-10 2xl:grid-cols-[19rem_minmax(0,1fr)] 2xl:items-start">
          <Section title="Every ring" description="Strongest first. Choose one to see how it connects.">
            <ul className="space-y-2">
              {list.rings.map((r) => {
                const on = r.id === selected;
                return (
                  <li key={r.id}>
                    <button type="button" aria-pressed={on} onClick={() => choose(r.id)}
                      className={`w-full rounded-panel border px-4 py-3.5 text-left transition-colors ${on ? "border-ink bg-surface" : "border-line bg-surface hover:border-line-strong"}`}>
                      <span className="flex flex-wrap items-center gap-2">
                        <Badge tone={scoreTone(r.score)}>Score {r.score}</Badge>
                        <span className="font-semibold">{plural(r.members.length, "identity", "identities")}</span>
                        <span className="text-sm text-ink-2">{stageLabel(r.stages)}</span>
                      </span>
                      <span className="mt-1 block text-sm text-ink-2">Strongest link: {r.strongest}</span>
                      {(r.case || r.flagged_leads > 0) && (
                        <span className="mt-2 flex flex-wrap gap-1.5">
                          {r.case && <Badge tone="caution">Case {r.case.state}</Badge>}
                          {r.flagged_leads > 0 && <Badge>{plural(r.flagged_leads, "lead")} flagged</Badge>}
                        </span>
                      )}
                    </button>
                  </li>
                );
              })}
            </ul>
          </Section>

          {ring && (
            <div className="min-w-0 space-y-10">
              <Section title="How they connect" description="Each line is a link Atrium recorded: a lead's form, a client's account, a device that signed in.">
                <Panel className="p-5 sm:p-6">
                  <EntityGraph nodes={ring.graph.nodes} edges={ring.graph.edges} columns={RING_COLUMNS} highlight={lit} legend={RING_LEGEND}
                    title={`Ring of ${ring.members.length} identities joined through ${plural(ring.identifiers, "shared identifier")} by ${plural(ring.links, "link")}`} />
                </Panel>
              </Section>

              <Section title="Gemini's reading" description="What the ring resembles, each point citing the links it rests on. Point at a link id to find it in the graph.">
                <Panel className="p-6">
                  {reading ? <Reading result={reading} onLight={setLit} /> : (
                    <p className="text-sm text-ink-2">Explain this ring asks Gemini Flash to read the members and links above and say which pattern they resemble. It cites only this ring&apos;s links; it cannot add new ones.</p>
                  )}
                </Panel>
              </Section>

              <Section title="Members" description="Who is in the ring, and why each one is flagged, if they are.">
                <ul className="grid gap-3 sm:grid-cols-2">
                  {ring.members.map((m) => (
                    <li key={m.id} className="rounded-panel border border-line bg-surface px-4 py-3.5">
                      <div className="flex flex-wrap items-center gap-2">
                        <span aria-hidden="true" className={`h-2.5 w-2.5 rounded-full ${m.flagged ? "bg-loss" : "bg-ink"}`} />
                        <span className="font-medium">{m.label}</span>
                        <Badge>{m.kind === "lead" ? "Lead" : "Client"}</Badge>
                        {m.ring_flagged && <Badge tone="loss">Flagged in this ring</Badge>}
                      </div>
                      {m.flags.length > 0 ? (
                        <ul className="mt-2 flex flex-wrap gap-1.5">
                          {m.flags.map((f) => <li key={f}><Badge tone={f.startsWith("AML") ? "loss" : "caution"}>{f}</Badge></li>)}
                        </ul>
                      ) : <p className="mt-1 text-sm text-muted">No flags of their own.</p>}
                    </li>
                  ))}
                </ul>
              </Section>

              <div>
                <Section title="Links" description="Strong links join a ring; weak ones only describe it.">
                  <div className={`${t.wrap} rounded-panel border border-line bg-surface px-5`}>
                    <table className={t.table}>
                      <thead className={t.head}>
                        <tr><th className={t.th}>Link</th><th className={t.th}>Who</th><th className={t.th}>Shares</th></tr>
                      </thead>
                      <tbody>
                        {ring.link_rows.map((l) => (
                          <tr key={l.id} className={`${t.row} ${lit.includes(l.id) ? "bg-daylight-wash" : ""}`}>
                            <td className={`${t.td} num font-semibold`}>{l.id}</td>
                            <td className={t.td}>{l.member}<span className="block text-xs text-muted">{l.member_kind === "lead" ? "Lead" : "Client"}{l.seen_at ? `, ${formatDate(l.seen_at)}` : ""}</span></td>
                            <td className={t.td}>
                              <span className="whitespace-nowrap">{l.identifier}</span>
                              <span className="block text-xs text-muted">{KIND_LABEL[l.kind]}, {l.strength === "strong" ? "a strong link" : "a weak link"}</span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </Section>
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
