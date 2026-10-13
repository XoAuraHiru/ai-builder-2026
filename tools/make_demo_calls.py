"""Render the synthetic demo calls once with Gemini-TTS voices, through the Cloud Text-to-Speech REST API.

  uv run --project services/api python tools/make_demo_calls.py [discovery pressure attack]

Each script line is synthesised in its speaker's voice, decoded to WAV so its length is exact, joined with 400 ms of
silence by ffmpeg's concat demuxer, and encoded once as a mono MP3 under services/api/app/seed/calls/. The second
each line starts is written back into its script as "start_s". The token is the gcloud CLI's own
(`gcloud auth print-access-token`); Application Default Credentials are never used. Every person is fictional.
"""
import base64
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CALLS = ROOT / "services" / "api" / "app" / "seed" / "calls"
CACHE = ROOT / ".superpowers" / "tts-cache"  # gitignored
ENDPOINT = "https://texttospeech.googleapis.com/v1/text:synthesize"
PROJECT = "atrium-cup-2026"
GAP_S = 0.4
SAMPLE_RATE = 24000
# Tried in order: the spec's TTS model, its fallback, then Chirp 3 HD voices of the same names (no model, no style).
MODELS: tuple[str | None, ...] = ("gemini-3.1-flash-tts-preview", "gemini-2.5-flash-tts", None)
LOG: list[dict] = []  # one entry per TTS request, for the task report


def request_body(text: str, *, voice: str, model: str | None, style: str | None = None) -> dict:
    """The text:synthesize body: a Gemini-TTS voice with its model and style prompt, or a Chirp 3 HD voice alone."""
    body: dict = {"input": {"text": text}, "voice": {"languageCode": "en-US", "name": voice},
                  "audioConfig": {"audioEncoding": "MP3"}}
    if model:
        body["voice"]["modelName"] = model
        if style:
            body["input"]["prompt"] = style
    return body


def start_times(durations: list[float], *, gap: float = GAP_S) -> list[float]:
    """The second each part starts when the parts are joined with `gap` seconds of silence between them."""
    out, t = [], 0.0
    for d in durations:
        out.append(round(t, 2))
        t += d + gap
    return out


def voice_name(voice: str, model: str | None) -> str:
    return voice if model else f"en-US-Chirp3-HD-{voice}"


def _gcloud() -> str:
    found = shutil.which("gcloud.cmd") or shutil.which("gcloud")
    if not found:
        sys.exit("gcloud is not installed")
    return found


def access_token() -> str:
    out = subprocess.run([_gcloud(), "auth", "print-access-token"], capture_output=True, text=True, check=True)
    return out.stdout.strip()


class Refused(Exception):
    """The API refused this model or voice (not a transient error), so the next model is tried."""


class Forbidden(Exception):
    """The API is disabled or the account may not call it; trying other models would not help."""


def synthesize(body: dict, token: str) -> bytes:
    """One line's MP3. Rendered parts are cached by request, so a rerun after a failure asks only for what is missing."""
    key = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()[:24]
    cached = CACHE / f"{key}.mp3"
    if cached.exists():
        return cached.read_bytes()
    request = urllib.request.Request(ENDPOINT, data=json.dumps(body).encode(), method="POST", headers={
        "Authorization": f"Bearer {token}", "x-goog-user-project": PROJECT, "Content-Type": "application/json"})
    for attempt in range(5):
        entry = {"voice": body["voice"]["name"], "model": body["voice"].get("modelName"), "status": None}
        LOG.append(entry)
        try:
            with urllib.request.urlopen(request, timeout=120) as resp:
                entry["status"] = resp.status
                audio = base64.b64decode(json.loads(resp.read())["audioContent"])
                CACHE.mkdir(parents=True, exist_ok=True)
                cached.write_bytes(audio)
                return audio
        except urllib.error.HTTPError as e:
            entry["status"] = e.code
            detail = e.read().decode(errors="replace")[:600]
            disabled = "SERVICE_DISABLED" in detail or "has not been used" in detail
            if disabled and attempt < 4 and any(x["status"] == 200 for x in LOG):
                time.sleep(30)  # a freshly enabled API answers unevenly while the change propagates
                continue
            if e.code in (429, 500, 502, 503, 504) and attempt < 4:
                time.sleep(2 * (attempt + 1) ** 2)
                continue
            if e.code == 401 or disabled:
                raise Forbidden(f"{e.code}: {detail}") from e
            raise Refused(f"{e.code}: {detail}") from e
    raise Refused("gave up after retries")


def _run(args: list[str]) -> str:
    return subprocess.run(args, capture_output=True, text=True, check=True).stdout


def to_wav(mp3: Path, wav: Path) -> None:
    _run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp3), "-ar", str(SAMPLE_RATE), "-ac", "1",
          "-c:a", "pcm_s16le", str(wav)])


def duration_s(path: Path) -> float:
    return float(_run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                       "default=noprint_wrappers=1:nokey=1", str(path)]).strip())


def render_lines(name: str, script: dict, work: Path, token: str, model: str | None) -> list[Path]:
    parts: list[Path] = []
    for i, line in enumerate(script["lines"]):
        speaker = script["speakers"][line["speaker"]]
        body = request_body(line["text"], voice=voice_name(speaker["voice"], model), model=model,
                            style=speaker.get("style"))
        mp3, wav = work / f"part{i:02d}.mp3", work / f"part{i:02d}.wav"
        mp3.write_bytes(synthesize(body, token))
        to_wav(mp3, wav)
        parts.append(wav)
        print(f"  {name} line {i + 1}/{len(script['lines'])} ({line['speaker']})", flush=True)
    return parts


def render(name: str, token: str, model_index: list[int]) -> dict:
    """Render one script in one model throughout; model_index is shared so a refused model is not asked again."""
    path = CALLS / f"{name}.json"
    script = json.loads(path.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        silence = work / "silence.wav"
        _run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
              f"anullsrc=r={SAMPLE_RATE}:cl=mono", "-t", str(GAP_S), "-c:a", "pcm_s16le", str(silence)])
        while True:
            model = MODELS[model_index[0]]
            try:
                parts = render_lines(name, script, work, token, model)
                break
            except Refused as e:
                if model_index[0] + 1 >= len(MODELS):
                    raise
                print(f"  {model or 'Chirp 3 HD'} refused ({e}); falling back", flush=True)
                model_index[0] += 1
        durations = [duration_s(p) for p in parts]
        listing = work / "list.txt"
        entries: list[str] = []
        for i, p in enumerate(parts):
            if i:
                entries.append(f"file '{silence.as_posix()}'")
            entries.append(f"file '{p.as_posix()}'")
        listing.write_text("\n".join(entries) + "\n", encoding="utf-8")
        out = CALLS / f"{name}.mp3"
        _run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(listing),
              "-c:a", "libmp3lame", "-b:a", "64k", "-ar", str(SAMPLE_RATE), "-ac", "1", str(out)])
    starts = start_times(durations)
    for line, start in zip(script["lines"], starts):
        line["start_s"] = start
    expected = round(sum(durations) + GAP_S * (len(durations) - 1), 2)
    script["duration_s"] = expected
    script["rendered_with"] = {"model": MODELS[model_index[0]] or "chirp3-hd",
                               "voices": {k: voice_name(v["voice"], MODELS[model_index[0]])
                                          for k, v in script["speakers"].items()}}
    path.write_text(json.dumps(script, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    measured = duration_s(out)
    return {"name": name, "lines": len(durations), "sum_of_parts_s": expected, "mp3_s": round(measured, 2),
            "bytes": out.stat().st_size}


def main(names: list[str]) -> None:
    token = access_token()
    model_index = [0]
    try:
        reports = [render(n, token, model_index) for n in names]
    except Forbidden as e:
        print(json.dumps({"tts_requests": len(LOG), "log": LOG}))
        sys.exit(f"Cloud Text-to-Speech refused the project or account: {e}")
    for r in reports:
        print(json.dumps(r))
    voices = sorted({e["voice"] for e in LOG if e["status"] == 200})
    print(json.dumps({"tts_requests": len(LOG), "succeeded": sum(e["status"] == 200 for e in LOG),
                      "refused": [e for e in LOG if e["status"] != 200], "voices": voices}))


if __name__ == "__main__":
    main(sys.argv[1:] or ["discovery", "pressure", "attack"])
