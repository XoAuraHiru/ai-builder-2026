"use client";

import { motion } from "motion/react";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError, apiDownload, apiUpload } from "@/lib/api";
import {
  callMarks, clock, demoName, droppedNote, FIELD_LABEL, figuresWarning, FLAG_LABEL, flagsHeadline, highFlags, ROLE_LABEL, SEVERITY_LABEL,
  sortFlags, sweepDelay, updateLine, type CallFlag, type DemoCall, type LeadCall, type UpdateField,
} from "@/lib/calls";
import { formatDate } from "@/lib/format";
import { AiProse } from "@/components/ai-prose";
import { AiThinking } from "@/components/ai-thinking";
import { CardSection } from "@/components/card-section";
import { ConfirmedLine } from "@/components/form-feedback";
import { EASE, GrowBar } from "@/components/motion";
import { BlockSkeleton } from "@/components/skeleton";
import { Badge, Button, Notice, Sparkle } from "@/components/ui";

const ACCEPT = "audio/mpeg,audio/wav,audio/x-wav,audio/mp4,audio/x-m4a,audio/ogg,.mp3,.wav,.m4a,.ogg";
// One Gemini call listens, transcribes, flags and proposes; then every quote is checked against the transcript.
const LISTENING_STEPS = [
  "Gemini is listening to the recording",
  "Gemini is writing the transcript, speaker by speaker",
  "Gemini is looking for promises, pressure and a third party directing the client",
  "Gemini is noting what the client asked to change",
  "Checking every quote against the transcript",
];
// The reading lands as a sweep along the call: the timeline fills in this long, and each flag arrives as it is passed.
const SWEEP = 0.6;
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
  const [paused, setPaused] = useState<string | null>(null);  // the breaker's message while call analysis is paused
  const [audio, setAudio] = useState<Record<string, string>>({});  // a demo name or an uploaded call's id -> object URL
  const urls = useRef<string[]>([]);

  const loadCalls = useCallback(async () => {
    try {
      const [list, status] = await Promise.all([
        api<LeadCall[]>(`/leads/${leadId}/calls`),
        api<{ paused: string | null }>(`/leads/${leadId}/calls/status`).catch(() => ({ paused: null })),
      ]);
      setCalls(list);
      setPaused(status.paused);
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
    <CardSection id="calls" title="Calls"
      description="Gemini listens to a recorded call and proposes; you decide. A flag or update whose words are not in the transcript is dropped. The audio is never stored, only the reading.">
      <div className="flex flex-wrap items-center gap-2.5">
        {demoCall && (
          <Button variant="ai" disabled={Boolean(busy) || Boolean(paused)} onClick={() => runDemo(demoCall)}>
            <Sparkle />{`Analyse the ${demoCall} call`}
          </Button>
        )}
        <label className={`inline-flex min-h-11 cursor-pointer items-center justify-center gap-2 whitespace-nowrap rounded-full border border-sand-200 bg-white px-5 text-sm font-medium text-ink-900 hover:bg-fill focus-within:shadow-[0_0_0_3px_var(--color-green-200)] ${busy || paused ? "pointer-events-none text-ink-400" : ""}`} aria-disabled={Boolean(busy) || Boolean(paused) || undefined}>
          Upload a recording
          <input type="file" accept={ACCEPT} className="sr-only" disabled={Boolean(busy) || Boolean(paused)}
            onChange={(e) => { upload(e.target.files?.[0]); e.target.value = ""; }} />
        </label>
      </div>
      <p className="mt-2 text-xs text-ink-500">
        MP3, WAV, M4A or OGG, up to 20 MB.{demoCall && ` The ${demoCall} call is a demo recorded for this lead: synthetic voices reading a script.`}
      </p>
      {paused && (
        <div className="mt-4">
          <Notice tone="caution" title="Call analysis is paused">
            {paused} Earlier readings below stay available; the Model Risk Office resets the model once it passes its checks again.
          </Notice>
        </div>
      )}
      {error && <div className="mt-4"><Notice tone="error" title="The call could not be analysed">{error}</Notice></div>}
      {busy && <div className="mt-6"><AiThinking steps={LISTENING_STEPS} usually="about 17 s" /></div>}
      {calls === null ? <div className="mt-6"><BlockSkeleton label="Loading the calls" shape="lines" /></div>
        : current ? (
          <div className="mt-6">
            <CallView key={current.id} call={current} leadId={leadId} audioUrl={audioUrl}
              onApplied={async (call) => {
                setCalls((prev) => (prev ?? []).map((c) => (c.id === call.id ? call : c)));
                await onChange();
              }} />
          </div>
        ) : !busy && <p className="mt-6 text-sm text-ink-500">No calls analysed for this lead yet.</p>}
      {earlier.length > 0 && (
        <div className="mt-8">
          <h3 className="text-sm font-semibold">Earlier calls</h3>
          <ul className="mt-2 divide-y divide-sand-100 border-y border-sand-100">
            {earlier.map((c) => (
              <li key={c.id} className="flex flex-wrap items-center justify-between gap-3 py-2.5 text-sm">
                <span className="min-w-0">
                  <span className="font-medium">{c.filename}</span>{" "}
                  <span className="text-ink-500">
                    {formatDate(c.created_at)}, {c.reading.flags.length === 1 ? "1 flag" : `${c.reading.flags.length} flags`}
                  </span>
                </span>
                <Button size="sm" variant="secondary" onClick={() => setSelected(c.id)}>Show this call</Button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </CardSection>
  );
}

function TimeButton({ at, onPlay }: { at: number; onPlay?: (at: number) => void }) {
  if (!onPlay) return <span className="num inline-flex min-h-8 shrink-0 items-center self-start text-xs font-semibold text-ink-500">{clock(at)}</span>;
  return (
    <button type="button" onClick={() => onPlay(at)} aria-label={`Play from ${clock(at)}`}
      className="num inline-flex h-8 shrink-0 items-center gap-1.5 self-start rounded-full border border-sand-200 bg-white px-2.5 text-xs font-semibold text-ink-900 hover:bg-fill">
      <svg width="8" height="9" viewBox="0 0 8 9" aria-hidden="true" className="text-green-600"><path d="M0 0l8 4.5L0 9z" fill="currentColor" /></svg>
      {clock(at)}
    </button>
  );
}

const SEVERITY_TONE = { high: "loss", medium: "caution", low: "neutral" } as const;
const MARK_FILL = { high: "bg-coral-500", medium: "bg-amber-400", low: "bg-ink-400" } as const;

/** The call as a line from its start to its end, with a mark at each flag (coral high, amber medium). When the reading
 *  lands, the line fills from the start and each mark appears as the fill passes it: the flags in the order they were
 *  said. With the recording at hand, a mark plays the call from that second. */
function CallTimeline({ flags, duration, onPlay }: { flags: CallFlag[]; duration: number; onPlay?: (at: number) => void }) {
  const marks = callMarks(flags, duration);
  const end = duration > 0 ? duration : Math.max(...flags.map((f) => f.start_s));
  return (
    <div className="mt-4 max-w-xl" role={onPlay ? "group" : undefined} aria-label={onPlay ? "Flags along the call" : undefined} aria-hidden={onPlay ? undefined : true}>
      <div className="relative h-6">
        <span aria-hidden="true" className="absolute inset-x-0 top-1/2 h-1.5 -translate-y-1/2 overflow-hidden rounded-full bg-sand-100">
          <GrowBar pct={100} className="bg-sand-300" />
        </span>
        <div className="absolute inset-x-1.5 inset-y-0">
          {marks.map(({ flag, share }, i) => {
            const dot = (
              <motion.span aria-hidden="true" className={`block h-3 w-3 rounded-full ring-2 ring-fill ${MARK_FILL[flag.severity]}`}
                initial={{ opacity: 0, scale: 0.6 }} animate={{ opacity: 1, scale: 1 }}
                transition={{ duration: 0.2, delay: share * SWEEP, ease: EASE }} />
            );
            const place = "absolute top-1/2 flex h-6 w-6 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full";
            return onPlay ? (
              <button key={`${flag.kind}-${flag.start_s}-${i}`} type="button" style={{ left: `${share * 100}%` }} onClick={() => onPlay(flag.start_s)}
                aria-label={`Play from ${clock(flag.start_s)}: ${SEVERITY_LABEL[flag.severity]}, ${FLAG_LABEL[flag.kind]}`}
                className={`${place} hover:bg-white focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-green-200`}>{dot}</button>
            ) : <span key={`${flag.kind}-${flag.start_s}-${i}`} style={{ left: `${share * 100}%` }} className={place}>{dot}</span>;
          })}
        </div>
      </div>
      <div aria-hidden="true" className="num mt-0.5 flex justify-between text-xs text-ink-500"><span>0:00</span><span>{clock(end)}</span></div>
    </div>
  );
}

/** Each flag as a status chip (coral for high, amber for medium) at the second it was said, the words quoted, and why.
 *  Listed by severity, they arrive in the order they were said, each as the timeline's fill reaches it. */
function FlagList({ flags, duration, onPlay }: { flags: CallFlag[]; duration: number; onPlay?: (at: number) => void }) {
  const last = Math.max(0, ...flags.map((f) => f.start_s));
  return (
    <ul>
      {flags.map((f, i) => (
        <motion.li key={`${f.kind}-${f.start_s}-${i}`} className="border-t border-sand-100 py-4 first:border-t-0 first:pt-0 last:pb-0"
          initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.28, delay: 0.05 + sweepDelay(f.start_s, duration, SWEEP, last), ease: EASE }}>
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={SEVERITY_TONE[f.severity]}>{SEVERITY_LABEL[f.severity]} · {FLAG_LABEL[f.kind]}</Badge>
            <TimeButton at={f.start_s} onPlay={onPlay} />
          </div>
          <p className="mt-2.5 text-[15px] leading-[22px] text-ink-900">&ldquo;{f.quote}&rdquo;</p>
          <p className="mt-1 text-sm leading-[21px] text-ink-700">{f.why} <span className="text-ink-500">Touches {f.rule}.</span></p>
          {f.source === "gemini" ? (
            <p className="mt-2 flex items-center gap-1.5 text-xs font-medium text-ai-700"><Sparkle size={12} />Flagged by Gemini</p>
          ) : <p className="mt-2 text-xs text-ink-500">Flagged by the promise rules that also check advisors&rsquo; drafts</p>}
        </motion.li>
      ))}
    </ul>
  );
}

function CallView({ call, leadId, audioUrl, onApplied }:
  { call: LeadCall; leadId: string; audioUrl?: string; onApplied: (call: LeadCall) => Promise<void> }) {
  const player = useRef<HTMLAudioElement>(null);
  const [ticked, setTicked] = useState<Set<UpdateField>>(new Set());
  const [justApplied, setJustApplied] = useState<Set<UpdateField>>(new Set());  // confirmed with a drawn check
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
      setJustApplied(new Set(out.applied));
      await onApplied(out.call);
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="rounded-control bg-fill px-4 py-3.5">
        <p className="code text-[13px] text-ink-900">{call.filename}</p>
        <p className="mt-0.5 text-[13px] text-ink-500">
          {call.source === "demo" ? "Demo call" : "Uploaded recording"}, {clock(call.duration_s)}. Analysed by {call.created_by} on {formatDate(call.created_at)}.
        </p>
        {audioUrl ? <audio ref={player} controls preload="metadata" src={audioUrl} className="mt-3 w-full max-w-xl" />
          : <p className="mt-2 text-sm text-ink-700">{call.source === "demo" ? "Loading the recording…" : "The recording is not kept, so only its reading can be shown."}</p>}
        {flags.length > 0 && <CallTimeline flags={flags} duration={call.duration_s} onPlay={onPlay} />}
      </div>

      {flags.length > 0 ? (
        <section aria-label="Conduct flags" className="space-y-4">
          <div className="flex flex-col items-start gap-3">
            <Badge tone={high.length > 0 ? "loss" : "caution"}>
              {flags.length === 1 ? "1 conduct flag" : `${flags.length} conduct flags`}
            </Badge>
            {high.length > 0 && <h3 className="max-w-[620px] text-[20px] font-semibold leading-7 tracking-[-0.01em]">{flagsHeadline(flags)}</h3>}
          </div>
          <FlagList flags={flags} duration={call.duration_s} onPlay={onPlay} />
        </section>
      ) : (
        <Notice tone="success" title="No conduct flags">Neither Gemini nor the promise rules found anything to flag on this call.</Notice>
      )}

      <AiProse caption="Gemini's reading of the call. Listen to the moments that matter before you act on it."
        warning={figuresWarning(reading.unsupported_figures)}>
        <p>{reading.summary}</p>
        {reading.action_items.length > 0 && (
          <ul className="mt-3 list-disc space-y-1 pl-5 text-[16px] leading-6">
            {reading.action_items.map((a, i) => <li key={i}>{a}</li>)}
          </ul>
        )}
      </AiProse>

      {reading.updates.length > 0 && (
        <section aria-labelledby={`updates-${call.id}`} className="space-y-3">
          <div>
            <h3 id={`updates-${call.id}`} className="text-[15px] font-semibold">Proposed updates</h3>
            <p className="mt-1 flex items-start gap-1.5 text-xs font-medium text-ai-700">
              <span className="mt-0.5 shrink-0"><Sparkle size={12} /></span>
              Proposed by Gemini from the client&rsquo;s own words, each checked against the transcript and the form&rsquo;s limits.
            </p>
            <p className="mt-1.5 text-[13px] text-ink-500">Tick the ones the client stated. Nothing changes on the lead until you apply them.</p>
          </div>
          <ul className="space-y-2">
            {reading.updates.map((u) => {
              const done = applied.get(u.field);
              const id = `call-${call.id}-${u.field}`;
              const on = Boolean(done) || ticked.has(u.field);
              return (
                <li key={u.field} className={`flex gap-3 rounded-control px-4 py-3.5 transition-colors ${on && !done ? "bg-green-50" : "bg-fill"}`}>
                  <input id={id} type="checkbox" className="mt-0.5 h-[18px] w-[18px] shrink-0 accent-[var(--color-green-500)]" checked={on}
                    disabled={Boolean(done) || busy} onChange={() => toggle(u.field)} />
                  <div className="min-w-0 text-sm">
                    <label htmlFor={id} className="font-medium text-ink-900">{updateLine(u)}</label>
                    <div className="mt-1.5 flex flex-wrap items-center gap-2 text-ink-700">
                      <span>&ldquo;{u.quote}&rdquo;</span>
                      <TimeButton at={u.start_s} onPlay={onPlay} />
                    </div>
                    {done && (justApplied.has(u.field)
                      ? <ConfirmedLine className="mt-1.5">Applied by {done.by} on {formatDate(done.at)}.</ConfirmedLine>
                      : <p className="mt-1.5 text-xs font-medium text-green-700">Applied by {done.by} on {formatDate(done.at)}.</p>)}
                  </div>
                </li>
              );
            })}
          </ul>
          <div className="flex flex-wrap items-center gap-3 pt-1">
            <Button variant="tonal" busy={busy} disabled={ticked.size === 0} onClick={apply}>{busy ? "Applying" : "Apply selected"}</Button>
            {ticked.size > 0 && <span className="text-[13px] text-ink-500">{[...ticked].map((f) => FIELD_LABEL[f]).join(", ")}</span>}
          </div>
          {error && <Notice tone="error">{error}</Notice>}
        </section>
      )}

      {note && <Notice tone="caution">{note}</Notice>}

      <details className="group rounded-control border border-sand-200 bg-white">
        <summary className="flex min-h-11 cursor-pointer list-none flex-wrap items-center justify-between gap-2 px-4 py-2.5 text-sm hover:bg-fill">
          <span className="font-semibold">Transcript</span>
          <span className="text-ink-500">{reading.transcript.length} turns, {clock(reading.duration_s)}. <span className="font-semibold text-green-600 group-open:hidden">Show</span><span className="hidden font-semibold text-green-600 group-open:inline">Hide</span></span>
        </summary>
        <ol className="border-t border-sand-100">
          {reading.transcript.map((s, i) => (
            <li key={i} className="flex gap-3 border-t border-sand-100 px-4 py-2.5 text-sm first:border-t-0">
              <TimeButton at={s.start_s} onPlay={onPlay} />
              <div className="min-w-0">
                <p className="text-xs font-semibold text-ink-500">{ROLE_LABEL[s.role]}, {s.speaker}</p>
                <p className="mt-0.5 text-ink-900">{s.text}</p>
              </div>
            </li>
          ))}
        </ol>
        <p className="flex items-start gap-1.5 border-t border-sand-100 px-4 py-2.5 text-xs font-medium text-ai-700">
          <span className="mt-0.5 shrink-0"><Sparkle size={12} /></span>
          Transcribed by Gemini. Speaker roles are its judgement; the recording is the record.
        </p>
      </details>
    </div>
  );
}
