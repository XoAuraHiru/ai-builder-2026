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
import voice  # noqa: E402

WORK = ROOT / ".superpowers" / "video"
SCENE_DIR = WORK / "film-scenes"
FPS = 30
PRE = 0.6       # seconds of picture before a scene's first sentence
XFADE = 0.45    # the cross-fade between scenes
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
    (SCENE_DIR / f"{scene.key}.json").write_text(json.dumps({"starts": starts, "seconds": r.clock}), encoding="utf-8")
    speech = sum(length for _, length in clips)
    print(f"  {scene.key}: {r.clock:.1f} s of picture, {speech:.1f} s of narration")


# -- assembly --------------------------------------------------------------------------------------------------

def starts_of(scene: Scene) -> list[float]:
    return json.loads((SCENE_DIR / f"{scene.key}.json").read_text(encoding="utf-8"))["starts"]


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


def scene_audio(scene: Scene, pieces: list[tuple[Path, float]]) -> Path:
    video = SCENE_DIR / f"{scene.key}.mp4"
    length = duration(video)
    out = SCENE_DIR / f"{scene.key}.wav"
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
    videos = [SCENE_DIR / f"{k}.mp4" for k in keys]
    audios = [SCENE_DIR / f"{k}.wav" for k in keys]
    lengths = [duration(v) for v in videos]
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


async def main(only: list[str] | None, compose_only: bool, reuse: list[str], name: str) -> None:
    WORK.mkdir(parents=True, exist_ok=True)
    SCENE_DIR.mkdir(parents=True, exist_ok=True)
    chosen = [s for s in SCENES if (not only or s.key in only) and s.key not in reuse]
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
        kept_pieces = {s.key: kept(s, clips[s.key], WORK / "film-scenes") for s in SCENES if s.key in reuse}
        keys = [s.key for s in SCENES if (SCENE_DIR / f"{s.key}.json").exists() and s.key not in failed]
        for scene in SCENES:
            if scene.key in keys:
                scene_audio(scene, kept_pieces.get(scene.key) or placed(scene, clips[scene.key]))
        if keys:
            compose(keys, name)
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
    a = ap.parse_args()
    if a.voice:
        CAST = json.loads(Path(a.voice).read_text(encoding="utf-8"))
    SCENE_DIR = WORK / a.scenes
    asyncio.run(main([k for k in a.only.split(",") if k], a.compose_only, [k for k in a.reuse.split(",") if k],
                     a.name))
