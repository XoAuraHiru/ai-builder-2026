import importlib.util
from io import BytesIO
from pathlib import Path

from PIL import Image

TOOL = Path(__file__).resolve().parents[3] / "tools" / "make_specimen_id.py"


def test_specimen_is_a_marked_png():
    spec = importlib.util.spec_from_file_location("make_specimen_id", TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    png = module.make_specimen("Emma Walsh", "1984-05-12", "AT-1029384", "2030-08-31")
    image = Image.open(BytesIO(png))
    assert image.format == "PNG" and image.size == (900, 560)
