"""Make the Atrium demo film from the real app: narrate, record each scene, then assemble.

    uv run --project services/api python tools/video/make_video.py              # everything
    uv run --project services/api python tools/video/make_video.py --only call,rings
    uv run --project services/api python tools/video/make_video.py --compose-only

Voice-over: one Gemini-TTS clip per sentence (cached), silence trimmed so each sentence's start is exact. Recording:
scenes run in headless Chrome at 1440x810 CSS pixels, captured at 1920x1080 and 30 fps (tools/video/recorder.py).
Scenes that change data run against a local copy of the app, started here. Assembly: each scene gets its own audio,
then the scenes are joined with short cross-fades, the sound is levelled, and the film is written to
.superpowers/video/atrium-demo.mp4.
"""
import argparse
import asyncio
import json
import os
import re
import subprocess
import sys
import time
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
FPS = 30
PRE = 0.6       # seconds of picture before the first sentence of a scene
GAP = 0.35      # between sentences
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


def plan(scene: Scene) -> dict:
    """Each sentence's audio, start and end on the scene's clock."""
    clips, starts, ends, t = [], [], [], PRE
    for line in scene.lines:
        wav, _ = voice.render(line)
        clip, d = trimmed(wav)
        clips.append(clip)
        starts.append(round(t, 3))
        ends.append(round(t + d, 3))
        t += d + GAP
    return {"clips": clips, "starts": starts, "ends": ends}


def chunks(text: str, start: float, end: float, limit: int = 96) -> list[tuple[float, float, str]]:
    """A caption per readable piece: long sentences split at the comma or semicolon nearest their middle."""
    if len(text) <= limit:
        return [(start, end, text)]
    marks = [m.end() for m in re.finditer(r"[,;:] ", text)]
    if not marks:
        return [(start, end, text)]
    cut = min(marks, key=lambda i: abs(i - len(text) / 2))
    first, second = text[:cut].strip(), text[cut:].strip()
    mid = start + (end - start) * len(first) / len(text)
    return chunks(first, start, mid, limit) + chunks(second, mid, end, limit)


async def narrate(r: Recorder, scene: Scene, p: dict) -> None:
    pieces = [c for line, s, e in zip(scene.lines, p["starts"], p["ends"]) for c in chunks(line, s, e)]
    for i, (s, e, text) in enumerate(pieces):
        await r.until(s)
        await r.caption(text)
        nxt = pieces[i + 1][0] if i + 1 < len(pieces) else None
        await r.until(e + (0.25 if nxt is None else 0))
        if nxt is None or nxt - e > 0.6:
            await r.caption("")


async def label_for(r: Recorder, seconds: float) -> None:
    await r.until(seconds)
    await r.label("", "", "")


# -- the local copy --------------------------------------------------------------------------------------------

def http(method: str, url: str, user: str, body: dict | None = None):
    req = urllib.request.Request(url, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"X-Dev-User": user, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as resp:
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
        procs.append(subprocess.Popen(["uv", "run", "uvicorn", "app.main:app", "--port", "8000"], cwd=ROOT / "services" / "api",
                                      env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
    if not up(LOCAL):
        env = {**os.environ, "API_URL": LOCAL_API}
        procs.append(subprocess.Popen("pnpm dev", cwd=ROOT / "apps" / "web", env=env, shell=True,
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
    for _ in range(120):
        if up(f"{LOCAL_API}/health") and up(LOCAL):
            break
        time.sleep(2)
    for path in ("/operations/reconciliation", "/operations/approvals"):  # compile the pages before recording
        try:
            urllib.request.urlopen(LOCAL + path, timeout=120)
        except Exception:
            pass
    return procs


def proposals_waiting() -> None:
    """Mei's queue needs proposals: read the sample statement and find matches, unless some are waiting already."""
    if http("GET", f"{LOCAL_API}/ops/reconciliation", "mei@atrium.demo").get("proposals"):
        return
    http("POST", f"{LOCAL_API}/ops/statements/sample", "mei@atrium.demo", {"fmt": "csv"})
    http("POST", f"{LOCAL_API}/ops/reconcile", "mei@atrium.demo", {})


def pending_reversal() -> None:
    """Sam needs something to approve: Mei asks for one reversal, unless one is already waiting."""
    waiting = http("GET", f"{LOCAL_API}/ops/approvals?state=pending", "sam@atrium.demo")
    if waiting:
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

async def record(scene: Scene, p: dict, port: int) -> Path:
    out = WORK / "scenes" / f"{scene.key}.mp4"
    out.parent.mkdir(parents=True, exist_ok=True)
    async with Chrome(port=port) as c:
        r = Recorder(c, out, base=scene.base, fps=FPS)
        r.scene = scene
        await r.start()
        if scene.persona:
            await r.sign_in(scene.persona)
        await r.goto(scene.start, ready=scene.ready, settle=scene.settle)
        if not scene.cursor:
            await c.js("document.querySelector('#__atr .cur').style.display = 'none'")
        if scene.label:
            await r.label(*scene.label)
        tasks = [asyncio.create_task(narrate(r, scene, p))]
        if scene.label:
            tasks.append(asyncio.create_task(label_for(r, 3.8)))
        await r.resume()
        try:
            await scene.act(r, p["starts"])
            await r.until(max(r.clock, p["ends"][-1] + scene.tail))
        finally:
            for task in tasks:
                task.cancel()
            await r.stop()
    print(f"  {scene.key}: {r.clock:.1f} s of picture, narration ends at {p['ends'][-1]:.1f} s")
    return out


# -- assembly --------------------------------------------------------------------------------------------------

def scene_audio(scene: Scene, p: dict, length: float) -> Path:
    out = WORK / "scenes" / f"{scene.key}.wav"
    inputs, parts = [], []
    for i, (clip, start) in enumerate(zip(p["clips"], p["starts"])):
        inputs += ["-i", str(clip)]
        ms = int(start * 1000)
        parts.append(f"[{i}:a]adelay={ms}|{ms}[a{i}]")
    mix = "".join(f"[a{i}]" for i in range(len(p["clips"])))
    graph = ";".join(parts) + f";{mix}amix=inputs={len(p['clips'])}:normalize=0,apad,atrim=0:{length:.3f}[out]"
    run(["ffmpeg", "-loglevel", "error", "-y", *inputs, "-filter_complex", graph, "-map", "[out]", "-ar", "48000",
         "-ac", "2", str(out)])
    return out


def compose(keys: list[str]) -> Path:
    videos = [WORK / "scenes" / f"{k}.mp4" for k in keys]
    audios = [WORK / "scenes" / f"{k}.wav" for k in keys]
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
    out = WORK / "atrium-demo.mp4"
    run(["ffmpeg", "-loglevel", "error", "-y", *inputs, "-filter_complex", ";".join(vg + ag), "-map", "[vout]",
         "-map", "[aout]", "-c:v", "libx264", "-preset", "slow", "-crf", "19", "-r", str(FPS), "-c:a", "aac",
         "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", str(out)])
    print(f"film: {out} ({duration(out):.1f} s, {out.stat().st_size / 1e6:.1f} MB)")
    return out


async def main(only: list[str] | None, compose_only: bool) -> None:
    WORK.mkdir(parents=True, exist_ok=True)
    chosen = [s for s in SCENES if not only or s.key in only]
    plans = {s.key: plan(s) for s in SCENES}
    total_voice = sum(p["ends"][-1] - p["starts"][0] for p in plans.values())
    print(f"narration: {sum(len(s.lines) for s in SCENES)} sentences, {total_voice:.1f} s of speech")
    procs: list[subprocess.Popen] = []
    try:
        if not compose_only:
            if any(s.base == LOCAL for s in chosen):
                procs = start_local()
                proposals_waiting()
                pending_reversal()
            for n, scene in enumerate(chosen):
                if scene.key == "approve":
                    scene.extra["code"] = sam_code
                await record(scene, plans[scene.key], port=9731 + n)
        for scene in SCENES:
            video = WORK / "scenes" / f"{scene.key}.mp4"
            if video.exists():
                scene_audio(scene, plans[scene.key], duration(video))
        keys = [s.key for s in SCENES if (WORK / "scenes" / f"{s.key}.mp4").exists()]
        compose(keys)
    finally:
        for proc in procs:
            proc.terminate()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--compose-only", action="store_true")
    a = ap.parse_args()
    asyncio.run(main([k for k in a.only.split(",") if k], a.compose_only))
