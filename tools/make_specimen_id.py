"""Generate clearly marked SPECIMEN identity cards for demos. They imitate no real issuer's design.

  uv run --project services/api python tools/make_specimen_id.py
"""
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parents[1] / "apps" / "web" / "public" / "demo"


def _font(size: int):
    for name in ("arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def make_specimen(name: str, dob: str, number: str, expiry: str) -> bytes:
    img = Image.new("RGB", (900, 560), (236, 241, 247))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 900, 90], fill=(11, 95, 255))
    d.text((30, 26), "ATRIUM DEMO IDENTITY CARD", font=_font(36), fill="white")
    d.rectangle([40, 130, 300, 450], fill=(200, 205, 214))
    d.text((120, 280), "PHOTO", font=_font(28), fill=(110, 115, 125))
    for i, (label, value) in enumerate([("NAME", name), ("DATE OF BIRTH", dob), ("DOCUMENT NO.", number),
                                        ("EXPIRES", expiry)]):
        d.text((340, 130 + i * 80), label, font=_font(20), fill=(90, 100, 115))
        d.text((340, 156 + i * 80), value, font=_font(32), fill=(20, 28, 40))
    d.rectangle([0, 480, 900, 560], fill=(200, 30, 45))
    d.text((60, 500), "SPECIMEN - NOT A REAL DOCUMENT", font=_font(34), fill="white")
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "specimen-match.png").write_bytes(make_specimen("Emma Walsh", "1984-05-12", "AT-1029384", "2030-08-31"))
    (OUT / "specimen-mismatch.png").write_bytes(
        make_specimen("Emily Walters", "1979-11-03", "AT-5550192", "2024-02-29"))
    print(f"wrote specimens to {OUT}")


if __name__ == "__main__":
    main()
