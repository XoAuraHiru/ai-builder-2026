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
STYLE = ("You are narrating a product film for a financial technology company. Speak in a calm, confident, warm "
         "voice at an unhurried, measured pace, with clear diction and natural pauses at commas. Sound like a "
         "seasoned documentary narrator, not an advertisement.")
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


# -- the presenter's own voice, from ElevenLabs ------------------------------------------------------------------

EL_CACHE = ROOT / ".superpowers" / "video" / "voice-el"  # gitignored
EL_API = "https://api.elevenlabs.io/v1"
# v3, because with the presenter's clone v2 opened most takes with an "uh"; v3 takes no previous/next text
EL_MODEL = "eleven_v3"
EL_SETTINGS = {"stability": 0.5, "similarity_boost": 0.8, "style": 0.0, "use_speaker_boost": True}


def _el(path: str, **kwargs):
    """A call to ElevenLabs. The API key is read from ELEVENLABS_API_KEY and never written anywhere."""
    import os
    import urllib.request

    headers = {"xi-api-key": os.environ["ELEVENLABS_API_KEY"], **kwargs.pop("headers", {})}
    with urllib.request.urlopen(urllib.request.Request(f"{EL_API}{path}", headers=headers, **kwargs),
                                timeout=180) as resp:
        return resp.read()


def render_el(text: str, voice_id: str, previous_text: str = "", next_text: str = "", seed: int = 1,
              speed: float = 1.0) -> tuple[Path, float]:
    """One take of the sentence in the presenter's cloned voice. The neighbouring sentences are sent as context, so
    the delivery flows across a scene; another seed is another take, and speed paces it."""
    EL_CACHE.mkdir(parents=True, exist_ok=True)
    settings = {**EL_SETTINGS, "speed": round(speed, 2)}
    key = hashlib.sha256(json.dumps([text, voice_id, EL_MODEL, settings, previous_text, next_text, seed])
                         .encode()).hexdigest()[:16]
    wav = EL_CACHE / f"{key}.wav"
    if wav.exists():
        return wav, duration_s(wav)
    body = {"text": text, "model_id": EL_MODEL, "voice_settings": settings, "seed": seed}
    if previous_text and EL_MODEL != "eleven_v3":
        body["previous_text"] = previous_text
    if next_text and EL_MODEL != "eleven_v3":
        body["next_text"] = next_text
    audio = _el(f"/text-to-speech/{voice_id}?output_format=mp3_44100_128", data=json.dumps(body).encode(),
                method="POST", headers={"Content-Type": "application/json", "Accept": "audio/mpeg"})
    mp3 = EL_CACHE / f"{key}.mp3"
    mp3.write_bytes(audio)
    to_wav(mp3, wav)
    mp3.unlink(missing_ok=True)
    return wav, duration_s(wav)


ONES = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen " \
       "seventeen eighteen nineteen".split()
TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()


def _number(n: int) -> str:
    if n < 20:
        return ONES[n]
    if n < 100:
        return TENS[n // 10] + ("" if n % 10 == 0 else " " + ONES[n % 10])
    if 2000 <= n < 2100:
        return "two thousand" + ("" if n == 2000 else " " + _number(n - 2000))
    if n < 1000:
        return ONES[n // 100] + " hundred" + ("" if n % 100 == 0 else " " + _number(n % 100))
    return _number(n // 1000) + " thousand" + ("" if n % 1000 == 0 else " " + _number(n % 1000))


def spoken_words(text: str) -> list[str]:
    """The words as they are said, so a transcript's "10,000" and the script's "ten-thousand" compare equal."""
    import re

    text = text.lower().replace("%", " percent").replace("’", "'")
    text = re.sub(r"(?<=\d),(?=\d{3})", "", text)
    text = re.sub(r"\d+", lambda m: " " + _number(int(m.group())) + " ", text)
    text = re.sub(r"[^a-z ]+", " ", text.replace("-", " ").replace("'", ""))  # its and it's sound the same
    return text.split()


def transcribe(wav: Path) -> dict:
    """What a take actually says, word by word with timings, so a take that stumbles or adds a word is caught."""
    out = wav.with_suffix(".stt.json")
    if out.exists():
        return json.loads(out.read_text(encoding="utf-8"))
    boundary = "atrium" + hashlib.sha256(wav.name.encode()).hexdigest()[:12]
    body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"model_id\"\r\n\r\nscribe_v1\r\n"
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{wav.name}\"\r\n"
            f"Content-Type: audio/wav\r\n\r\n").encode() + wav.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
    reply = json.loads(_el("/speech-to-text", data=body, method="POST",
                           headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}))
    out.write_text(json.dumps(reply), encoding="utf-8")
    return reply
