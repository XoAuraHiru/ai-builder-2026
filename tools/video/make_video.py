"""Make the Atrium film from the real app: narrate, record each scene, then assemble.

    uv run --project services/api python tools/video/make_video.py              # everything
    uv run --project services/api python tools/video/make_video.py --only call,rings
    uv run --project services/api python tools/video/make_video.py --compose-only

Voice-over: one Gemini-TTS clip per sentence (cached), silence trimmed so each sentence's start is exact. Recording:
scenes run in headless Chrome at 1440x810 CSS pixels, captured at 1920x1080 and 30 fps (tools/video/recorder.py).
A scene is a list of beats (tools/video/scenes.py); each beat's sentence starts when the one before it and its action
are done, and the second it started is written next to the scene's video, so the sound is laid exactly where it was
said. Scenes that change data run against a local copy of the app, started here. Assembly: each scene gets its own
audio, the scenes are joined with short cross-fades, the sound is levelled, and the film is written to
.superpowers/video/atrium-film.mp4.
"""
import argparse
import asyncio
import hashlib
import importlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import traceback
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
from cdp import Chrome  # noqa: E402
from recorder import Recorder  # noqa: E402
from scenes import LOCAL, SCENES, Scene  # noqa: E402
import motion_clips  # noqa: E402
import sound  # noqa: E402
import voice  # noqa: E402

WORK = ROOT / ".superpowers" / "video"
SCENE_DIR = WORK / "film-scenes"
FPS = 30
PRE = 0.6       # seconds of picture before a scene's first sentence
XFADE = 0.45    # the cross-fade between scenes
LABEL_Y = 820   # where the motion label's band sits in the frame (above the captions)
KEEP = 0.5      # seconds a recorded scene runs on after its last action
RAMP = 1.9      # how much faster silent action plays when trimmed (--trim)
TRIM = False    # trim every recorded scene's ending, not only labelled ones (--trim)
SCORE_DB = -15  # the score, below the voice before ducking
FILM = "scenes"
LOCAL_API = "http://localhost:8000"


def run(args: list[str]) -> str:
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout


def duration(path: Path) -> float:
    return float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)]).strip())


# -- narration -------------------------------------------------------------------------------------------------

def trimmed(wav: Path) -> tuple[Path, float]:
    """The sentence without the silence the voice adds before and after it."""
    out = wav.with_name(wav.stem + ".trim.wav")
    if not out.exists():
        trim = "silenceremove=start_periods=1:start_threshold=-48dB:start_silence=0.05"
        run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(wav), "-af",
             f"{trim},areverse,{trim},areverse", "-ar", "48000", "-ac", "1", str(out)])
    return out, duration(out)


CAST: dict | None = None  # sentence -> the presenter's chosen take (tools/video/revoice.py), instead of Gemini-TTS


def narrator(scene: Scene) -> list[tuple[Path, float]]:
    return [trimmed(voice.render(beat.text)[0]) for beat in scene.beats]


def voices(scene: Scene) -> list[tuple[Path, float]]:
    if CAST is not None:
        return [(Path(CAST[b.text]["wav"]), CAST[b.text]["length"]) for b in scene.beats]
    return narrator(scene)


def chunks(text: str, start: float, end: float, limit: int = 96) -> list[tuple[float, float, str]]:
    """A caption per readable piece: long sentences split at the comma or semicolon nearest their middle."""
    if len(text) <= limit:
        return [(start, end, text)]
    marks = [m.end() for m in re.finditer(r"[,;:.] ", text)]
    if not marks:
        return [(start, end, text)]
    cut = min(marks, key=lambda i: abs(i - len(text) / 2))
    first, second = text[:cut].strip(), text[cut:].strip()
    mid = start + (end - start) * len(first) / len(text)
    return chunks(first, start, mid, limit) + chunks(second, mid, end, limit)


async def caption_beat(r: Recorder, text: str, start: float, end: float) -> None:
    for s, e, piece in chunks(text, start, end):
        await r.until(s)
        await r.caption(piece)
    await r.until(end + 0.2)
    await r.caption("")


async def label_for(r: Recorder, seconds: float) -> None:
    await r.until(seconds)
    await r.label("", "", "")


# -- the local copy --------------------------------------------------------------------------------------------

def http(method: str, url: str, user: str, body: dict | None = None):
    req = urllib.request.Request(url, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"X-Dev-User": user, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read() or b"null")


def up(url: str) -> bool:
    try:
        urllib.request.urlopen(url, timeout=5)
        return True
    except Exception:
        return False


def start_local() -> list[subprocess.Popen]:
    """The local API and web app, on a database of their own, unless they are already running."""
    procs = []
    if not up(f"{LOCAL_API}/health"):
        db = (ROOT / ".superpowers" / "video-local.db").as_posix()
        env = {**os.environ, "DATABASE_URL": f"sqlite+pysqlite:///{db}", "AUTO_SEED": "true",
               "CORS_ORIGINS": LOCAL, "PYTHONIOENCODING": "utf-8"}
        procs.append(subprocess.Popen(["uv", "run", "uvicorn", "app.main:app", "--port", "8000"],
                                      cwd=ROOT / "services" / "api", env=env,
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
    if not up(LOCAL):
        env = {**os.environ, "API_URL": LOCAL_API}
        procs.append(subprocess.Popen("pnpm dev", cwd=ROOT / "apps" / "web", env=env, shell=True,
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
    for _ in range(120):
        if up(f"{LOCAL_API}/health") and up(LOCAL):
            break
        time.sleep(2)
    for path in ("/operations/approvals",):  # compile the page before recording it
        try:
            urllib.request.urlopen(LOCAL + path, timeout=120)
        except Exception:
            pass
    return procs


def pending_reversal() -> None:
    """Sam needs something to approve: Mei asks for one reversal, unless one is already waiting."""
    if http("GET", f"{LOCAL_API}/ops/approvals?state=pending", "sam@atrium.demo"):
        return
    rows = http("GET", f"{LOCAL_API}/ops/blotter", "mei@atrium.demo")
    row = next(r for r in rows if r.get("posting_id") and not r.get("not_reversible_because"))
    http("POST", f"{LOCAL_API}/ops/reversals", "mei@atrium.demo",
         {"posting_id": row["posting_id"], "reason": "The client paid this into the wrong fund and asked for it back."})


async def sam_code() -> str:
    """Off the event loop, so the recording keeps its frames while the local API answers."""
    reply = await asyncio.to_thread(http, "GET", f"{LOCAL_API}/me/authenticator", "sam@atrium.demo")
    return reply["code"]


# -- recording -------------------------------------------------------------------------------------------------

async def record(scene: Scene, clips: list[tuple[Path, float]], port: int) -> None:
    SCENE_DIR.mkdir(parents=True, exist_ok=True)
    out = SCENE_DIR / f"{scene.key}.mp4"
    starts: list[float] = []
    async with Chrome(port=port) as c:
        r = Recorder(c, out, base=scene.base, fps=FPS)
        r.scene = scene
        await r.start()
        try:
            if scene.persona:
                await r.sign_in(scene.persona, device=scene.extra.get("device"))
            await r.goto(scene.start, ready=scene.ready, settle=scene.settle)
            if not scene.cursor:
                await c.js("document.querySelector('#__atr .cur').style.display = 'none'")
            if scene.label:
                await r.label(*scene.label)
                asyncio.create_task(label_for(r, 4.2))
            await r.resume()
            await r.hold(PRE)
            for beat, (_, length) in zip(scene.beats, clips):
                start = r.clock
                starts.append(round(start, 3))
                captions = asyncio.create_task(caption_beat(r, beat.text, start, start + length))
                action = asyncio.create_task(beat.act(r)) if beat.act else None
                await r.until(start + length)
                if action:
                    await action
                await captions
                await r.hold(beat.after)
            await r.hold(scene.tail)
        finally:
            await r.stop()
    (SCENE_DIR / f"{scene.key}.json").write_text(json.dumps({"starts": starts, "seconds": r.clock, "cues": r.cues}),
                                                 encoding="utf-8")
    speech = sum(length for _, length in clips)
    print(f"  {scene.key}: {r.clock:.1f} s of picture, {speech:.1f} s of narration")


# -- assembly --------------------------------------------------------------------------------------------------

def meta_of(scene: Scene, raw: bool = False) -> dict:
    """What the recording logged; for a finished scene (trimmed, ramped), where things now fall."""
    final = SCENE_DIR / f"{scene.key}.final.json"
    path = final if final.exists() and not raw else SCENE_DIR / f"{scene.key}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def starts_of(scene: Scene, raw: bool = False) -> list[float]:
    return meta_of(scene, raw)["starts"]


def placed(scene: Scene, clips: list[tuple[Path, float]]) -> list[tuple[Path, float]]:
    """Each sentence at the second the recording started it."""
    return [(clip, start) for (clip, _), start in zip(clips, starts_of(scene))]


def kept(scene: Scene, clips: list[tuple[Path, float]], source: Path) -> list[tuple[Path, float]]:
    """A scene that cannot be done again on the live app keeps footage recorded with another voice, and the captions
    burned into it. The new voice is laid under those captions: a sentence shown in pieces is cut between the words
    where its caption changes, and each piece starts as its caption appears."""
    for ext in (".mp4", ".json"):
        shutil.copyfile(source / f"{scene.key}{ext}", SCENE_DIR / f"{scene.key}{ext}")
    pieces = []
    for i, (beat, (clip, _), start, (_, before)) in enumerate(zip(scene.beats, clips, starts_of(scene),
                                                                  narrator(scene))):
        shown = chunks(beat.text, start, start + before)
        if len(shown) == 1:
            pieces.append((clip, start))
            continue
        said = [w for w in voice.transcribe(clip)["words"] if w["type"] == "word"]
        heard = [len(voice.spoken_words(w["text"])) for w in said]
        cuts, count, j = [0.0], 0, 0
        for _, _, piece in shown[:-1]:
            count += len(voice.spoken_words(piece))
            while j < len(said) and sum(heard[:j + 1]) < count:
                j += 1
            cuts.append((said[j]["end"] + said[j + 1]["start"]) / 2)
            j += 1
        cuts.append(duration(clip))
        for k, ((at, _, _), a, b) in enumerate(zip(shown, cuts, cuts[1:])):
            out = SCENE_DIR / f"{scene.key}-{i}-{k}.wav"
            run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(clip), "-af", f"atrim={a:.3f}:{b:.3f}",
                 "-ar", "48000", "-ac", "1", str(out)])
            pieces.append((out, at))
    return pieces


def words_of(wav: Path) -> list[tuple[str, float, float]]:
    """When each word of a cast take is said, from the transcript its casting made (scaled for a re-paced take)."""
    stem = wav.name.split(".")[0]
    trim = wav.with_name(f"{stem}.trim.wav")
    said = json.loads(wav.with_name(f"{stem}.trim.stt.json").read_text(encoding="utf-8"))
    scale = duration(wav) / duration(trim)
    return [(w["text"].strip(), w["start"] * scale, w["end"] * scale) for w in said["words"] if w.get("type") == "word"]


def motion_scene(scene: Scene, clips: list[tuple[Path, float]]) -> None:
    """A motion clip in place of a recording, timed from the voice: each sentence starts where it is laid, and the
    clip knows when every word is said and which caption is up."""
    template, data, starts = motion_data(scene, clips)
    motion_clips.render(f"{FILM}-{scene.key}", template, data, SCENE_DIR / f"{scene.key}.mp4")
    (SCENE_DIR / f"{scene.key}.json").write_text(json.dumps({"starts": starts, "seconds": data["T"], "cues": []}),
                                                 encoding="utf-8")
    print(f"  {scene.key}: motion clip, {data['T']:.1f} s")


def motion_data(scene: Scene, clips: list[tuple[Path, float]]) -> tuple[str, dict, list[float]]:
    beats, starts, t = [], [], PRE
    for beat, (wav, length) in zip(scene.beats, clips):
        beats.append({"start": round(t, 3), "end": round(t + length, 3), "text": beat.text,
                      "words": [[w, round(t + a, 3), round(t + b, 3)] for w, a, b in words_of(wav)],
                      "captions": [[round(a, 3), round(b + 0.2, 3), c] for a, b, c in chunks(beat.text, t, t + length)]})
        starts.append(round(t, 3))
        t += length + beat.after
    data = {"T": round(t + scene.tail, 3), "beats": beats}
    template = scene.clip
    if scene.clip.startswith("chapter"):
        n = int(scene.clip.removeprefix("chapter"))
        title, line, who = motion_clips.CHAPTERS[n]
        data.update(T=max(motion_clips.CHAPTER_SECONDS, data["T"] if beats else 0), n=n, of=len(motion_clips.CHAPTERS),
                    title=title, line=line, who=who)
        template = "chapter"
    return template, data, starts


def ramps(scene: Scene, end: float) -> list[tuple[float, float, float]]:
    """The scene in segments (from, to, speed): every sentence at normal speed, and the action between sentences, where
    no one speaks (the cursor travelling, a page loading), sped up by RAMP, as an editor ramps dead time."""
    spoken = [(max(0.0, s - 0.25), s + length + 0.35) for s, (_, length) in zip(starts_of(scene, raw=True), voices(scene))]
    segs, t = [], 0.0
    for a, b in spoken + [(end, end)]:
        a, b = min(a, end), min(b, end)
        if a - t >= 0.8:
            segs.append((t, a, RAMP))
        elif a > t:
            segs.append((t, a, 1.0))
        if b > max(a, t):
            segs.append((max(a, t), b, 1.0))
        t = max(t, b)
    merged: list[tuple[float, float, float]] = []
    for a, b, k in segs:
        if merged and merged[-1][2] == k and abs(merged[-1][1] - a) < 1e-6:
            merged[-1] = (merged[-1][0], b, k)
        else:
            merged.append((a, b, k))
    return merged


def warped(t: float, segs: list[tuple[float, float, float]]) -> float:
    return sum((min(t, b) - a) / k for a, b, k in segs if a < t)


def labelled(scene: Scene) -> Path:
    """The scene as it goes in the film: a recording ends half a second after its last action, not after the pauses
    it was recorded with, and carries its motion label (the feature, and the Google technology behind it). With
    --trim, the silent stretches are ramped too, and the scene's sentences and sound cues move with the picture."""
    video = SCENE_DIR / f"{scene.key}.mp4"
    if scene.clip:
        return video
    meta = json.loads((SCENE_DIR / f"{scene.key}.json").read_text(encoding="utf-8"))
    end = meta["seconds"] - scene.tail - (scene.beats[-1].after if scene.beats else 0) + KEEP
    end = min(end, duration(video))
    if not scene.lower and not TRIM:
        return video
    segs = ramps(scene, end) if TRIM else [(0.0, end, 1.0)]
    out = SCENE_DIR / f"{scene.key}.final.mp4"
    inputs = ["-i", str(video)]
    parts = [f"[0:v]split={len(segs)}" + "".join(f"[s{i}]" for i in range(len(segs)))] if len(segs) > 1 else []
    for i, (a, b, k) in enumerate(segs):
        src = f"[s{i}]" if len(segs) > 1 else "[0:v]"
        parts.append(f"{src}trim={a:.3f}:{b:.3f},setpts=(PTS-STARTPTS)/{k}[w{i}]")
    parts.append("".join(f"[w{i}]" for i in range(len(segs))) + f"concat=n={len(segs)}:v=1:a=0,fps={FPS}[base]")
    stale = [video]
    tail = "[base]"
    if scene.lower:
        title, sub = scene.lower
        slug = hashlib.sha256(f"{title}|{sub}".encode()).hexdigest()[:10]
        label = motion_clips.render(f"lower-{slug}", "lower", {"T": 4.8, "title": title, "sub": sub, "beats": []},
                                    WORK / "motion" / f"lower-{slug}.mov")
        inputs += ["-itsoffset", f"{PRE:.2f}", "-i", str(label)]
        parts.append(f"[base][1:v]overlay=0:{LABEL_Y}:eof_action=pass:format=auto[lab]")
        tail = "[lab]"
        stale.append(label)
    parts.append(f"{tail}format=yuv420p[v]")
    stamp = out.with_name(out.name + ".src")
    key = f"{segs}|{scene.lower}"
    if not out.exists() or out.stat().st_mtime < max(f.stat().st_mtime for f in stale) or \
            not stamp.exists() or stamp.read_text() != key:
        script = SCENE_DIR / f"{scene.key}.graph.txt"
        script.write_text(";".join(parts), encoding="utf-8")
        run(["ffmpeg", "-loglevel", "error", "-y", *inputs, "-/filter_complex", str(script), "-map", "[v]",
             "-c:v", "libx264", "-preset", "medium", "-crf", "16", "-r", str(FPS), str(out)])
        stamp.write_text(key)
    # where the scene's sentences and sound cues now fall
    (SCENE_DIR / f"{scene.key}.final.json").write_text(json.dumps({
        "starts": [round(warped(s, segs), 3) for s in meta["starts"]],
        "seconds": round(warped(end, segs), 3),
        "cues": [[n, round(warped(t, segs), 3)] for n, t in meta.get("cues", []) if t < end]}), encoding="utf-8")
    return out


def scene_audio(scene: Scene, pieces: list[tuple[Path, float]]) -> Path:
    length = duration(labelled(scene))
    out = SCENE_DIR / f"{scene.key}.wav"
    if not pieces:  # a chapter card without words: silence, for the sound design to fill
        run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-t",
             f"{length:.3f}", str(out)])
        return out
    inputs, parts = [], []
    for i, (clip, start) in enumerate(pieces):
        inputs += ["-i", str(clip)]
        ms = int(start * 1000)
        parts.append(f"[{i}:a]adelay={ms}|{ms}[a{i}]")
    mix = "".join(f"[a{i}]" for i in range(len(pieces)))
    graph = ";".join(parts) + f";{mix}amix=inputs={len(pieces)}:normalize=0,apad,atrim=0:{length:.3f}[out]"
    run(["ffmpeg", "-loglevel", "error", "-y", *inputs, "-filter_complex", graph, "-map", "[out]", "-ar", "48000",
         "-ac", "2", str(out)])
    return out


def compose(keys: list[str], name: str = "atrium-film.mp4") -> Path:
    by_key = {s.key: s for s in SCENES}
    videos = [labelled(by_key[k]) for k in keys]
    audios = [SCENE_DIR / f"{k}.wav" for k in keys]
    lengths = [duration(v) for v in videos]
    starts = [sum(lengths[:k]) - XFADE * k for k in range(len(keys))]
    (WORK / f"{Path(name).stem}.timeline.json").write_text(json.dumps(dict(zip(keys, starts))), encoding="utf-8")
    inputs = []
    for v, a in zip(videos, audios):
        inputs += ["-i", str(v), "-i", str(a)]
    vg, ag, offset = [], [], 0.0
    prev_v, prev_a = "[0:v]", "[1:a]"
    for k in range(1, len(keys)):
        offset += lengths[k - 1] - XFADE
        v_out, a_out = f"[v{k}]", f"[a{k}]"
        vg.append(f"{prev_v}[{2 * k}:v]xfade=transition=fade:duration={XFADE}:offset={offset:.3f}{v_out}")
        ag.append(f"{prev_a}[{2 * k + 1}:a]acrossfade=d={XFADE}:c1=tri:c2=tri{a_out}")
        prev_v, prev_a = v_out, a_out
    total = sum(lengths) - XFADE * (len(keys) - 1)
    vg.append(f"{prev_v}fade=t=in:st=0:d=0.5,fade=t=out:st={total - 0.8:.3f}:d=0.8,format=yuv420p[vout]")
    ag.append(f"{prev_a}afade=t=in:st=0:d=0.4,afade=t=out:st={total - 0.8:.3f}:d=0.8,"
              f"loudnorm=I=-16:TP=-1.5:LRA=11[aout]")
    out = WORK / name
    script = WORK / "film-graph.txt"  # a long filter graph is too long for a Windows command line
    script.write_text(";".join(vg + ag), encoding="utf-8")
    run(["ffmpeg", "-loglevel", "error", "-y", *inputs, "-/filter_complex", str(script), "-map", "[vout]",
         "-map", "[aout]", "-c:v", "libx264", "-preset", "slow", "-crf", "20", "-r", str(FPS), "-c:a", "aac",
         "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", str(out)])
    print(f"film: {out} ({duration(out):.1f} s, {out.stat().st_size / 1e6:.1f} MB)")
    return out


def finish(film: Path, keys: list[str]) -> Path:
    """The sound design under the voice: the score, ducked whenever the narrator speaks, a whoosh on each chapter
    card, a soft click under each click on screen, and a chime when the live inbox fires. Written beside the film as
    <name>-scored.mp4; the picture is copied, not encoded again."""
    try:
        assets = sound.ensure()
    except Exception as e:  # no key, no network: the film stands on the voice alone
        print(f"sound design skipped: {e}")
        return film
    timeline = json.loads((WORK / f"{film.stem}.timeline.json").read_text(encoding="utf-8"))
    by_key = {s.key: s for s in SCENES}
    cues: dict[str, list[float]] = {"whoosh": [], "click": [], "chime": []}
    for k in keys:
        at = timeline[k]
        if (by_key[k].clip or "").startswith("chapter"):
            cues["whoosh"].append(at + 0.05)
        for name, t in meta_of(by_key[k]).get("cues", []):
            cues.setdefault(name, []).append(at + t)
    total = duration(film)
    inputs = ["-i", str(film), "-stream_loop", "-1", "-i", str(assets["score"])]
    graph = [f"[1:a]atrim=0:{total:.3f},asetpts=PTS-STARTPTS,volume={SCORE_DB}dB,afade=t=in:st=0:d=2,"
             f"afade=t=out:st={total - 4:.3f}:d=4[score]",
             "[0:a]asplit=2[voice][key]",
             "[score][key]sidechaincompress=threshold=0.02:ratio=5:attack=40:release=650[bed]"]
    mixed = ["[voice]", "[bed]"]
    n = 2
    for name, times in cues.items():
        if not times:
            continue
        inputs += ["-i", str(assets[name])]
        labels = [f"[{name}{i}]" for i in range(len(times))]
        graph.append(f"[{n}:a]asplit={len(times)}" + "".join(labels) if len(times) > 1 else f"[{n}:a]anull{labels[0]}")
        for i, t in enumerate(times):
            ms = max(0, int(t * 1000))
            graph.append(f"{labels[i]}adelay={ms}|{ms}[{name}d{i}]")
            mixed.append(f"[{name}d{i}]")
        n += 1
    graph.append("".join(mixed) + f"amix=inputs={len(mixed)}:normalize=0,alimiter=limit=0.94,"
                 f"loudnorm=I=-16:TP=-1.5:LRA=11[aout]")
    script = WORK / "sound-graph.txt"
    script.write_text(";".join(graph), encoding="utf-8")
    out = film.with_name(f"{film.stem}-scored.mp4")
    run(["ffmpeg", "-loglevel", "error", "-y", *inputs, "-/filter_complex", str(script), "-map", "0:v", "-map",
         "[aout]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", str(out)])
    print(f"scored film: {out} ({sum(len(v) for v in cues.values())} sound cues)")
    return out


async def main(only: list[str] | None, compose_only: bool, reuse: list[str], name: str) -> None:
    WORK.mkdir(parents=True, exist_ok=True)
    SCENE_DIR.mkdir(parents=True, exist_ok=True)
    chosen = [s for s in SCENES if (not only or s.key in only) and s.key not in reuse and not s.clip]
    clips = {s.key: voices(s) for s in SCENES}
    speech = sum(length for cs in clips.values() for _, length in cs)
    print(f"narration: {sum(len(s.beats) for s in SCENES)} sentences, {speech:.1f} s of speech, {len(SCENES)} scenes")
    procs: list[subprocess.Popen] = []
    failed: list[str] = []
    try:
        if not compose_only:
            if any(s.base == LOCAL for s in chosen):
                procs = start_local()
                pending_reversal()
            for n, scene in enumerate(chosen):
                if scene.key == "approve":
                    scene.extra["code"] = sam_code
                try:
                    await record(scene, clips[scene.key], port=9761 + n)
                except Exception:
                    failed.append(scene.key)
                    print(f"  {scene.key}: FAILED\n{traceback.format_exc(limit=3)}")
        for scene in SCENES:
            if scene.clip and (not only or scene.key in only):
                try:
                    motion_scene(scene, clips[scene.key])
                except Exception:
                    failed.append(scene.key)
                    print(f"  {scene.key}: FAILED\n{traceback.format_exc(limit=3)}")
        kept_pieces = {s.key: kept(s, clips[s.key], WORK / "film-scenes") for s in SCENES if s.key in reuse}
        keys = [s.key for s in SCENES if (SCENE_DIR / f"{s.key}.json").exists() and s.key not in failed]
        for scene in SCENES:  # finish the picture first: trimming and ramps move where the sentences fall
            if scene.key in keys:
                labelled(scene)
        for scene in SCENES:
            if scene.key in keys:
                scene_audio(scene, kept_pieces.get(scene.key) or placed(scene, clips[scene.key]))
        if keys:
            finish(compose(keys, name), keys)
        if failed:
            print("failed scenes:", ",".join(failed))
    finally:
        for proc in procs:
            proc.terminate()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--compose-only", action="store_true")
    ap.add_argument("--voice", help="a cast of the presenter's takes, from tools/video/revoice.py")
    ap.add_argument("--scenes", default="film-scenes", help="the folder under .superpowers/video for scene footage")
    ap.add_argument("--name", default="atrium-film.mp4")
    ap.add_argument("--reuse", default="", help="scenes to keep from film-scenes rather than record again")
    ap.add_argument("--film", default="scenes", help="the module holding the film's SCENES (scenes, film_short)")
    ap.add_argument("--trim", action="store_true", help="end every recorded scene half a second after its last action")
    a = ap.parse_args()
    TRIM = a.trim
    SCENES = importlib.import_module(a.film).SCENES
    FILM = a.film
    if a.voice:
        CAST = json.loads(Path(a.voice).read_text(encoding="utf-8"))
    SCENE_DIR = WORK / a.scenes
    asyncio.run(main([k for k in a.only.split(",") if k], a.compose_only, [k for k in a.reuse.split(",") if k],
                     a.name))
