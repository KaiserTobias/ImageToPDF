import sys
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


@pytest.fixture
def img_dir(tmp_path: Path) -> Path:
    return make_images(tmp_path)


def make_images(tmp_path: Path) -> Path:
    """Testordner mit allen Formaten und Sonderfällen."""
    d = tmp_path / "bilder"
    (d / "sub" / "tief").mkdir(parents=True)

    Image.new("RGB", (400, 300), (200, 30, 30)).save(d / "rot.jpg", quality=90)
    Image.new("RGB", (300, 400), (30, 200, 30)).save(d / "gruen.png")
    Image.new("RGB", (120, 80), (30, 30, 200)).save(d / "sub" / "blau.bmp")
    Image.new("L", (200, 200), 128).save(d / "sub" / "tief" / "grau.tif", dpi=(300, 300))

    # Transparentes PNG
    rgba = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
    rgba.paste((255, 0, 0, 255), (0, 0, 50, 50))
    rgba.save(d / "transparent.png")

    # Mehrseitiges TIFF: Hoch- und Querformat
    p1 = Image.new("RGB", (200, 300), (10, 10, 10))
    p2 = Image.new("RGB", (300, 200), (90, 90, 90))
    p1.save(d / "multi.tif", save_all=True, append_images=[p2])

    # Animiertes GIF
    f1 = Image.new("RGB", (60, 60), (255, 0, 0))
    f2 = Image.new("RGB", (60, 60), (0, 0, 255))
    f1.save(d / "anim.gif", save_all=True, append_images=[f2], duration=100, loop=0)
    # Statisches GIF
    Image.new("P", (60, 40), 2).save(d / "statisch.gif")

    # Namenskonflikt innerhalb eines Laufs
    Image.new("RGB", (50, 50)).save(d / "scan.png")
    Image.new("RGB", (50, 50)).save(d / "scan.jpg")

    # Defekte Datei
    (d / "kaputt.png").write_bytes(b"\x89PNG\r\n\x1a\nnonsense")

    # Nicht-Bild
    (d / "notiz.txt").write_text("hallo")
    return d
