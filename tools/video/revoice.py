"""Cast the film's narration in the presenter's own voice, one checked take per sentence.

    ELEVENLABS_API_KEY=... uv run --project services/api python tools/video/revoice.py VOICE_ID
    uv run --project services/api python tools/video/make_video.py --voice .superpowers/video/voice-cast.json \
        --scenes film-scenes-cast --name atrium-film-cast.mp4 --reuse score,proposal,held

A cloned voice is less even than a studio narrator: a take can start with an "uh", stall mid-sentence, or rush. So
every take is transcribed and judged before it is used. It must say the sentence's words and no filler, without a
long stall, at an even pace (PACE words a minute, within TOLERANCE). A take that rushes or drags is spoken again at
an adjusted speed, a take that stumbles is spoken again with another seed, and the best take of each sentence is
written to CAST for make_video.py --voice to record the film with.
"""
import argparse
import difflib
import importlib
import json
import re
import statistics
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import make_video as mv  # noqa: E402
import voice  # noqa: E402

CAST = mv.WORK / "voice-cast.json"
PACE = 150  # words a minute, measured over the whole script's letters so long words take longer
TOLERANCE = (0.9, 1.12)  # a take's length against the length that pace gives it
FILLERS = {"uh", "um", "er", "ah", "hmm", "mm", "erm"}
TAKES = 6
LEVEL = -19.0  # LUFS for every take before the film is levelled as a whole

words = voice.spoken_words
LETTERS_PER_SECOND = 0.0  # set from the whole script in main()


def letters(text: str) -> int:
    return sum(len(w) for w in words(text))


def judge(text: str, length: float, stt: dict) -> dict:
    said = [w for w in stt.get("words", []) if w.get("type") == "word"]
    heard = words(" ".join(w["text"] for w in said))
    meant = words(text)
    match = difflib.SequenceMatcher(a=meant, b=heard).ratio()
    fillers = [w for w in heard if w in FILLERS and w not in meant]
    stall = max((b["start"] - a["end"] for a, b in zip(said, said[1:])
                 if not re.search(r"[.,;:?!]$", a["text"].strip())), default=0.0)
    pause = max((b["start"] - a["end"] for a, b in zip(said, said[1:])), default=0.0)
    events = [w["text"] for w in stt.get("words", []) if w.get("type") == "audio_event"
              and "breath" not in w["text"].lower()]
    pace = length / (letters(text) / LETTERS_PER_SECOND)
    problems = []
    if match < 0.9:
        problems.append(f"says {' '.join(heard)!r}")
    if fillers:
        problems.append(f"filler {fillers}")
    if stall > 0.6 or pause > 1.0:
        problems.append(f"stalls {max(stall, pause):.1f} s")
    if events:
        problems.append(f"noise {events}")
    if not TOLERANCE[0] <= pace <= TOLERANCE[1]:
        problems.append(f"pace {pace:.2f}")
    return {"ok": not problems, "words_ok": not problems or all(p.startswith("pace") for p in problems),
            "pace": pace, "match": match, "problems": problems}


def paced(clip: Path, pace: float) -> tuple[Path, float]:
    """A take a little off the pace, brought to the nearest edge of the tolerance; atempo keeps the pitch, and a
    change of under a tenth is not heard."""
    target = min(max(pace, TOLERANCE[0]), TOLERANCE[1])
    out = clip.with_name(f"{clip.stem}.pace{target:.2f}.wav")
    if not out.exists():
        mv.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(clip), "-af", f"atempo={pace / target:.4f}",
                "-ar", "48000", "-ac", "1", str(out)])
    return out, mv.duration(out)


def levelled(clip: Path) -> Path:
    """The take at the same loudness as every other: takes come back up to 9 dB apart."""
    out = clip.with_name(f"{clip.stem}.lvl.wav")
    if not out.exists():
        meter = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(clip), "-af", "ebur128", "-f", "null", "-"],
                               capture_output=True, text=True).stderr
        loudness = float(re.findall(r"I:\s+(-?[\d.]+) LUFS", meter)[-1])
        mv.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(clip), "-af",
                f"volume={LEVEL - loudness:.2f}dB,alimiter=limit=0.89:level=false", "-ar", "48000", "-ac", "1",
                str(out)])
    return out


def cast_sentence(voice_id: str, text: str, previous: str, following: str) -> dict:
    takes = []
    for seed in range(1, TAKES + 1):
        wav, _ = voice.render_el(text, voice_id, previous_text=previous, next_text=following, seed=seed)
        clip, length = mv.trimmed(wav)
        verdict = judge(text, length, voice.transcribe(clip))
        takes.append({"wav": str(clip), "length": length, "seed": seed, **verdict})
        if verdict["ok"]:
            break
    best = min(takes, key=lambda t: (not t["ok"], not t["words_ok"], abs(t["pace"] - 1)))
    if best["words_ok"] and not best["ok"] and 0.8 <= best["pace"] <= 1.25:
        clip, length = paced(Path(best["wav"]), best["pace"])
        best = {**best, "wav": str(clip), "length": length, "ok": True, "retimed": round(best["pace"], 2),
                "pace": min(max(best["pace"], TOLERANCE[0]), TOLERANCE[1]), "problems": []}
    return {"text": text, **best, "tries": len(takes),
            "rejected": [f"seed {t['seed']}: {'; '.join(t['problems'])}" for t in takes if t["seed"] != best["seed"]]}


def main(voice_id: str, film: str, recast: bool) -> None:
    global LETTERS_PER_SECOND
    cast = json.loads(CAST.read_text(encoding="utf-8")) if CAST.exists() else {}
    sentences = []
    for scene in importlib.import_module(film).SCENES:
        texts = [b.text for b in scene.beats]
        for i, text in enumerate(texts):
            sentences.append((scene.key, text, " ".join(texts[:i])[-600:], " ".join(texts[i + 1:])[:600]))
    all_text = " ".join(s[1] for s in sentences)
    LETTERS_PER_SECOND = letters(all_text) / (len(words(all_text)) / (PACE / 60))
    if not recast:  # a sentence already cast keeps its take, including one chosen by hand
        sentences = [s for s in sentences if s[1] not in cast]
    if not sentences:
        print("every sentence is already cast")
        return
    with ThreadPoolExecutor(4) as pool:
        picks = list(pool.map(lambda s: cast_sentence(voice_id, *s[1:]), sentences))
    for (key, *_), pick in zip(sentences, picks):
        mark = "ok " if pick["ok"] else "!! "
        retimed = f" retimed from {pick['retimed']}" if pick.get("retimed") else ""
        print(f"{mark}{key:11} pace {pick['pace']:.2f}{retimed} seed {pick['seed']} ({pick['tries']} tries) "
              f"{'; '.join(pick['problems'])}")
    paces = [p["pace"] for p in picks]
    print(f"{sum(p['ok'] for p in picks)}/{len(picks)} sentences clean; pace {min(paces):.2f}-{max(paces):.2f}, "
          f"median {statistics.median(paces):.2f}; {sum(p['length'] for p in picks):.0f} s of speech")
    for pick in picks:
        pick["wav"] = str(levelled(Path(pick["wav"])))
    cast.update({p["text"]: {"wav": p["wav"], "length": p["length"]} for p in picks})
    CAST.write_text(json.dumps(cast, indent=1), encoding="utf-8")
    CAST.with_name(CAST.stem + "-report.json").write_text(json.dumps(picks, indent=1), encoding="utf-8")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("voice_id")
    ap.add_argument("--film", default="scenes", help="the module holding the film's SCENES (scenes, film_short)")
    ap.add_argument("--recast", action="store_true", help="cast again sentences that already have a take")
    ap.add_argument("--cast", help="the cast file to write (default .superpowers/video/voice-cast.json)")
    a = ap.parse_args()
    if a.cast:
        CAST = Path(a.cast)
    main(a.voice_id, a.film, a.recast)
