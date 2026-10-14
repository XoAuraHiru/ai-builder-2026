"""The voice-over: each sentence rendered once with a Gemini-TTS voice and cached by its text, as a WAV of exact
length, so captions and actions can be timed to the second each sentence starts.

The token is the gcloud CLI's own (`gcloud auth print-access-token`), as in tools/make_demo_calls.py; Application
Default Credentials are never used.
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from make_demo_calls import Refused, access_token, duration_s, request_body, synthesize, to_wav  # noqa: E402

CACHE = ROOT / ".superpowers" / "video" / "voice"  # gitignored
VOICE = "Charon"
STYLE = ("You are narrating a short product film for a financial technology company. Speak in a calm, confident, warm "
         "voice at a natural, brisk pace, neither slow nor rushed, with clear diction and short pauses at commas. "
         "Sound like a seasoned documentary narrator, not an advertisement.")
MODELS: tuple[str | None, ...] = ("gemini-2.5-pro-tts", "gemini-3.1-flash-tts-preview", "gemini-2.5-flash-tts", None)


def _key(text: str, model: str | None) -> str:
    return hashlib.sha256(json.dumps([text, VOICE, STYLE, model]).encode()).hexdigest()[:16]


def render(text: str, token: str | None = None) -> tuple[Path, float]:
    """The sentence as a WAV and its length in seconds, from the cache when it was rendered before."""
    CACHE.mkdir(parents=True, exist_ok=True)
    for model in MODELS:
        wav = CACHE / f"{_key(text, model)}.wav"
        if wav.exists():
            return wav, duration_s(wav)
    token = token or access_token()
    last: Exception | None = None
    for model in MODELS:
        voice = VOICE if model else f"en-US-Chirp3-HD-{VOICE}"
        try:
            audio = synthesize(request_body(text, voice=voice, model=model, style=STYLE), token)
        except Refused as e:  # this model or voice is not available: try the next
            last = e
            continue
        mp3 = CACHE / f"{_key(text, model)}.mp3"
        wav = CACHE / f"{_key(text, model)}.wav"
        mp3.write_bytes(audio)
        to_wav(mp3, wav)
        mp3.unlink(missing_ok=True)
        return wav, duration_s(wav)
    raise RuntimeError(f"no TTS model accepted the narration: {last}")
