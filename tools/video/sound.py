"""The film's sound design, made once with ElevenLabs and kept: an instrumental score and three small effects.

    ELEVENLABS_API_KEY=... uv run --project services/api python tools/video/sound.py

The score sits under the voice and is ducked whenever the narrator speaks (make_video.finish); the whoosh marks a
chapter card, the click sits under each click on screen, and the chime rings when the live inbox fires. Every asset
is levelled here, so the mix only sets how far below the voice each one sits.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import voice  # noqa: E402

SOUND = HERE.parents[1] / ".superpowers" / "video" / "sound"  # gitignored
SCORE_PROMPT = ("Instrumental underscore for a polished fintech product film. Modern, warm and confident: a soft felt "
                "piano motif, gentle analog synth pads and a light plucked arpeggio over a subtle pulse at 100 BPM. "
                "Airy and spacious, a slow build through the middle, a calm resolve at the end. No vocals, no heavy "
                "drums, no risers; it sits under a voice-over.")
EFFECTS = {  # name: (prompt, seconds, loudness)
    "whoosh": ("a soft, airy whoosh for a clean motion-graphics transition, smooth, subtle, high fidelity", 1.0, -24),
    "click": ("a single soft, crisp mouse click, close, clean, very short, no room echo", 0.5, -30),
    "chime": ("a gentle two-note notification chime, warm and modern, clean, short tail", 1.4, -22),
}


def _level(src: Path, out: Path, loudness: float) -> Path:
    import subprocess
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(src), "-af",
                    f"loudnorm=I={loudness}:TP=-2:LRA=11", "-ar", "48000", "-ac", "2", str(out)], check=True)
    return out


def score(seconds: int = 300) -> Path:
    out = SOUND / "score.wav"
    if out.exists():
        return out
    SOUND.mkdir(parents=True, exist_ok=True)
    audio = voice._el("/music?output_format=mp3_44100_128", method="POST",
                      data=json.dumps({"prompt": SCORE_PROMPT, "music_length_ms": seconds * 1000,
                                       "model_id": "music_v1"}).encode(),
                      headers={"Content-Type": "application/json"})
    raw = SOUND / "score.mp3"
    raw.write_bytes(audio)
    return _level(raw, out, -16)  # levelled like the voice; the mix sets it well below


def effect(name: str) -> Path:
    out = SOUND / f"{name}.wav"
    if out.exists():
        return out
    SOUND.mkdir(parents=True, exist_ok=True)
    prompt, seconds, loudness = EFFECTS[name]
    audio = voice._el("/sound-generation?output_format=mp3_44100_128", method="POST",
                      data=json.dumps({"text": prompt, "duration_seconds": seconds, "prompt_influence": 0.6}).encode(),
                      headers={"Content-Type": "application/json"})
    raw = SOUND / f"{name}.mp3"
    raw.write_bytes(audio)
    return _level(raw, out, loudness)


def ensure() -> dict[str, Path]:
    return {"score": score(), **{name: effect(name) for name in EFFECTS}}


if __name__ == "__main__":
    for name, path in ensure().items():
        print(name, path)
