"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError, apiDownload, apiUpload } from "@/lib/api";
import {
  clock, demoName, droppedNote, FIELD_LABEL, figuresWarning, FLAG_LABEL, flagsHeadline, highFlags, ROLE_LABEL, SEVERITY_LABEL, sortFlags,
  updateLine, type CallFlag, type DemoCall, type LeadCall, type UpdateField,
} from "@/lib/calls";
import { formatDate } from "@/lib/format";
import { AiProse } from "@/components/ai-prose";
import { Badge, Button, KeyMoment, Notice, Panel, Section } from "@/components/ui";

const ACCEPT = "audio/mpeg,audio/wav,audio/x-wav,audio/mp4,audio/x-m4a,audio/ogg,.mp3,.wav,.m4a,.ogg";
const LISTENING = "Gemini is listening…";
const message = (e: unknown) => (e instanceof ApiError ? e.message : String(e));
type Busy = "" | DemoCall | "upload";

/** The Calls section of a lead: analyse a recording, see the conduct flags at the second they were said, apply the
 * updates the client stated, and read the transcript. Gemini proposes; the advisor decides. */
export function CallsSection({ leadId, demoCall, onChange }:
  { leadId: string; demoCall: DemoCall | null; onChange: () => Promise<void> }) {
  const [calls, setCalls] = useState<LeadCall[] | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [busy, setBusy] = useState<Busy>("");
  const [error, setError] = useState("");
  const [audio, setAudio] = useState<Record<string, string>>({});  // a demo name or an uploaded call's id -> object URL
  const urls = useRef<string[]>([]);

  const loadCalls = useCallback(async () => {
    try {
      setCalls(await api<LeadCall[]>(`/leads/${leadId}/calls`));
    } catch (e) {
      setError(`Could not load the calls: ${message(e)}`);
      setCalls([]);
    }
  }, [leadId]);

  useEffect(() => {
    loadCalls();
  }, [loadCalls]);

  useEffect(() => () => urls.current.forEach((u) => URL.revokeObjectURL(u)), []);

  const remember = useCallback((key: string, blob: Blob) => {
    const url = URL.createObjectURL(blob);
    urls.current.push(url);
    setAudio((prev) => ({ ...prev, [key]: url }));
  }, []);

  const current = calls?.find((c) => c.id === selected) ?? calls?.[0] ?? null;
  const demo = current ? demoName(current) : null;

  useEffect(() => {
    // The audio element cannot send the sign-in header, so the demo recording is fetched and played from a blob.
    if (!demo || audio[demo]) return;
    apiDownload(`/demo/calls/${demo}.mp3`).then((blob) => remember(demo, blob)).catch(() => {});
  }, [demo, audio, remember]);

  async function analyse(kind: Busy, request: () => Promise<LeadCall>, file?: File) {
    setBusy(kind);
    setError("");
    try {
      const call = await request();
      if (file) remember(call.id, file);
      setCalls((prev) => [call, ...(prev ?? []).filter((c) => c.id !== call.id)]);
      setSelected(call.id);
      await onChange();
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy("");
    }
  }

  const runDemo = (name: DemoCall) => analyse(name, () =>
    api<LeadCall>(`/leads/${leadId}/calls/demo`, { method: "POST", body: JSON.stringify({ name }) }));

  function upload(file: File | undefined) {
    if (!file) return;
    const form = new FormData();
    form.append("file", file);
    analyse("upload", () => apiUpload<LeadCall>(`/leads/${leadId}/calls`, form), file);
  }

  const earlier = (calls ?? []).filter((c) => c.id !== current?.id);
  const audioUrl = current ? (demo ? audio[demo] : audio[current.id]) : undefined;

  return (
    <Section id="calls" title="Calls"
      description="Gemini listens to a recorded call and proposes; you decide. A flag or update whose words are not in the transcript is dropped. The audio is never stored, only the reading.">
      <div className="flex flex-wrap items-center gap-2.5">
        {demoCall && (
          <Button busy={busy === demoCall} disabled={Boolean(busy)} onClick={() => runDemo(demoCall)}>
            {busy === demoCall ? LISTENING : `Analyse the ${demoCall} call`}
          </Button>
        )}
        <label className={`inline-flex min-h-11 cursor-pointer items-center justify-center gap-2 rounded-full px-5 text-sm font-semibold ${demoCall ? "border border-line-strong bg-surface text-ink hover:border-ink focus-within:border-ink" : "bg-ink text-white hover:bg-[#26343f]"} ${busy ? "pointer-events-none opacity-60" : ""}`}>
          {busy === "upload" ? LISTENING : "Upload a recording"}
          <input type="file" accept={ACCEPT} className="sr-only" disabled={Boolean(busy)}
            onChange={(e) => { upload(e.target.files?.[0]); e.target.value = ""; }} />
        </label>
      </div>
      <p className="mt-2 text-xs text-muted">
        MP3, WAV, M4A or OGG, up to 20 MB.{demoCall && ` The ${demoCall} call is a demo recorded for this lead: synthetic voices reading a script.`}
      </p>
      {busy && <p role="status" className="mt-3 text-sm text-daylight-ink">{LISTENING} A three-minute call takes about half a minute.</p>}
      {error && <div className="mt-4"><Notice tone="error" title="The call could not be analysed">{error}</Notice></div>}
      {calls === null ? <p role="status" className="mt-6 text-sm text-muted">Loading the calls…</p>
        : current ? (
          <div className="mt-6">
            <CallView key={current.id} call={current} leadId={leadId} audioUrl={audioUrl}
              onApplied={async (call) => {
                setCalls((prev) => (prev ?? []).map((c) => (c.id === call.id ? call : c)));
                await onChange();
              }} />
          </div>
        ) : <p className="mt-6 text-sm text-muted">No calls analysed for this lead yet.</p>}
      {earlier.length > 0 && (
        <div className="mt-8">
          <h3 className="text-sm font-semibold">Earlier calls</h3>
          <ul className="mt-2 divide-y divide-line border-y border-line">
            {earlier.map((c) => (
              <li key={c.id} className="flex flex-wrap items-center justify-between gap-3 py-2.5 text-sm">
                <span className="min-w-0">
                  <span className="font-medium">{c.filename}</span>{" "}
                  <span className="text-muted">
                    {formatDate(c.created_at)}, {c.reading.flags.length === 1 ? "1 flag" : `${c.reading.flags.length} flags`}
                  </span>
                </span>
                <Button size="sm" variant="secondary" onClick={() => setSelected(c.id)}>Show this call</Button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </Section>
  );
}

function TimeButton({ at, onPlay }: { at: number; onPlay?: (at: number) => void }) {
  if (!onPlay) return <span className="num inline-flex min-h-8 shrink-0 items-center self-start text-xs font-semibold text-muted">{clock(at)}</span>;
  return (
    <button type="button" onClick={() => onPlay(at)} aria-label={`Play from ${clock(at)}`}
      className="num inline-flex h-8 shrink-0 items-center gap-1.5 self-start rounded-full border border-line-strong bg-surface px-2.5 text-xs font-semibold text-ink hover:border-ink">
      <svg width="8" height="9" viewBox="0 0 8 9" aria-hidden="true"><path d="M0 0l8 4.5L0 9z" fill="currentColor" /></svg>
      {clock(at)}
    </button>
  );
}

const SEVERITY_TONE = { high: "loss", medium: "caution", low: "neutral" } as const;

function FlagList({ flags, onPlay }: { flags: CallFlag[]; onPlay?: (at: number) => void }) {
  return (
    <ul className="divide-y divide-line">
      {flags.map((f, i) => (
        <li key={`${f.kind}-${f.start_s}-${i}`} className="py-3.5 first:pt-0 last:pb-0">
          <div className="flex flex-wrap items-center gap-2">
            <TimeButton at={f.start_s} onPlay={onPlay} />
            <span className="font-semibold">{FLAG_LABEL[f.kind]}</span>
            <Badge tone={SEVERITY_TONE[f.severity]}>{SEVERITY_LABEL[f.severity]} severity</Badge>
          </div>
          <p className="mt-2 text-[15px] text-ink">&ldquo;{f.quote}&rdquo;</p>
          <p className="mt-1 text-sm text-ink-2">{f.why} <span className="text-muted">Touches {f.rule}.</span></p>
          {f.source === "gemini" ? (
            <p className="mt-1.5 flex items-center gap-1.5 text-xs text-daylight-ink">
              <span aria-hidden="true" className="h-2 w-2 shrink-0 rounded-[1px] bg-daylight" />Flagged by Gemini
            </p>
          ) : <p className="mt-1.5 text-xs text-muted">Flagged by the promise rules that also check advisors&rsquo; drafts</p>}
        </li>
      ))}
    </ul>
  );
}

function CallView({ call, leadId, audioUrl, onApplied }:
  { call: LeadCall; leadId: string; audioUrl?: string; onApplied: (call: LeadCall) => Promise<void> }) {
  const player = useRef<HTMLAudioElement>(null);
  const [ticked, setTicked] = useState<Set<UpdateField>>(new Set());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const { reading } = call;
  const flags = sortFlags(reading.flags);
  const high = highFlags(flags);
  const applied = new Map(call.applied.map((a) => [a.field, a]));
  const note = droppedNote(call.dropped);
  const onPlay = audioUrl ? (at: number) => {
    const el = player.current;
    if (!el) return;
    el.currentTime = at;
    el.play().catch(() => {});
  } : undefined;

  function toggle(field: UpdateField) {
    setTicked((prev) => {
      const next = new Set(prev);
      if (next.has(field)) next.delete(field);
      else next.add(field);
      return next;
    });
  }

  async function apply() {
    setBusy(true);
    setError("");
    try {
      const out = await api<{ call: LeadCall; applied: UpdateField[] }>(`/leads/${leadId}/calls/${call.id}/apply`,
        { method: "POST", body: JSON.stringify({ fields: [...ticked] }) });
      setTicked(new Set());
      await onApplied(out.call);
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <p className="font-semibold">{call.filename}</p>
        <p className="text-sm text-muted">
          {call.source === "demo" ? "Demo call" : "Uploaded recording"}, {clock(call.duration_s)}. Analysed by {call.created_by} on {formatDate(call.created_at)}.
        </p>
        {audioUrl ? <audio ref={player} controls preload="metadata" src={audioUrl} className="mt-3 w-full max-w-xl" />
          : <p className="mt-2 text-sm text-ink-2">{call.source === "demo" ? "Loading the recording…" : "The recording is not kept, so only its reading can be shown."}</p>}
      </div>

      {high.length > 0 ? (
        <KeyMoment tone="alert" label="Conduct flags" title={flagsHeadline(flags)}>
          <FlagList flags={flags} onPlay={onPlay} />
        </KeyMoment>
      ) : flags.length > 0 ? (
        <Panel className="p-5">
          <h3 className="mb-3 text-sm font-semibold">Conduct flags</h3>
          <FlagList flags={flags} onPlay={onPlay} />
        </Panel>
      ) : (
        <Notice tone="success" title="No conduct flags">Neither Gemini nor the promise rules found anything to flag on this call.</Notice>
      )}

      <AiProse caption="Gemini's reading of the call. Listen to the moments that matter before you act on it."
        warning={figuresWarning(reading.unsupported_figures)}>
        <p>{reading.summary}</p>
        {reading.action_items.length > 0 && (
          <ul className="mt-3 list-disc space-y-1 pl-5 text-[16px]">
            {reading.action_items.map((a, i) => <li key={i}>{a}</li>)}
          </ul>
        )}
      </AiProse>

      {reading.updates.length > 0 && (
        <Panel className="p-5">
          <h3 className="text-sm font-semibold">Proposed updates</h3>
          <p className="mt-1 flex items-start gap-2 text-xs text-daylight-ink">
            <span aria-hidden="true" className="mt-1 h-2 w-2 shrink-0 rounded-[1px] bg-daylight" />
            Proposed by Gemini from the client&rsquo;s own words, each checked against the transcript and the form&rsquo;s limits.
          </p>
          <p className="mt-2 text-sm text-muted">Tick the ones the client stated. Nothing changes on the lead until you apply them.</p>
          <ul className="mt-3 divide-y divide-line border-y border-line">
            {reading.updates.map((u) => {
              const done = applied.get(u.field);
              const id = `call-${call.id}-${u.field}`;
              return (
                <li key={u.field} className="flex gap-3 py-3">
                  <input id={id} type="checkbox" className="mt-1 h-4 w-4 shrink-0 accent-ink" checked={Boolean(done) || ticked.has(u.field)}
                    disabled={Boolean(done) || busy} onChange={() => toggle(u.field)} />
                  <div className="min-w-0 text-sm">
                    <label htmlFor={id} className="font-medium text-ink">{updateLine(u)}</label>
                    <div className="mt-1 flex flex-wrap items-center gap-2 text-ink-2">
                      <span>&ldquo;{u.quote}&rdquo;</span>
                      <TimeButton at={u.start_s} onPlay={onPlay} />
                    </div>
                    {done && <p className="mt-1 text-xs text-gain">Applied by {done.by} on {formatDate(done.at)}.</p>}
                  </div>
                </li>
              );
            })}
          </ul>
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <Button busy={busy} disabled={ticked.size === 0} onClick={apply}>Apply selected</Button>
            {ticked.size > 0 && <span className="text-sm text-muted">{[...ticked].map((f) => FIELD_LABEL[f]).join(", ")}</span>}
          </div>
          {error && <div className="mt-3"><Notice tone="error">{error}</Notice></div>}
        </Panel>
      )}

      {note && <p className="text-sm text-caution">{note}</p>}

      <details className="group rounded-panel border border-line bg-surface">
        <summary className="flex cursor-pointer list-none flex-wrap items-center justify-between gap-2 px-4 py-3 text-sm">
          <span className="font-semibold">Transcript</span>
          <span className="text-muted">{reading.transcript.length} turns, {clock(reading.duration_s)}. <span className="group-open:hidden">Show</span><span className="hidden group-open:inline">Hide</span></span>
        </summary>
        <ol className="divide-y divide-line border-t border-line">
          {reading.transcript.map((s, i) => (
            <li key={i} className="flex gap-3 px-4 py-2.5 text-sm">
              <TimeButton at={s.start_s} onPlay={onPlay} />
              <div className="min-w-0">
                <p className="text-xs font-semibold text-muted">{ROLE_LABEL[s.role]}, {s.speaker}</p>
                <p className="mt-0.5 text-ink">{s.text}</p>
              </div>
            </li>
          ))}
        </ol>
        <p className="flex items-start gap-2 border-t border-line px-4 py-2.5 text-xs text-daylight-ink">
          <span aria-hidden="true" className="mt-1 h-2 w-2 shrink-0 rounded-[1px] bg-daylight" />
          Transcribed by Gemini. Speaker roles are its judgement; the recording is the record.
        </p>
      </details>
    </div>
  );
}
