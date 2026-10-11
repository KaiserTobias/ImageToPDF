"""Bildprüfung: Maße, DPI, Seiten, Animation, Größengrenze, Lesbarkeit."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PIL import Image, ImageOps

from .models import MAX_PIXELS, ImageInfo

# Eigene Grenze; die Pillow-Bombenwarnung soll nicht vorher greifen.
Image.MAX_IMAGE_PIXELS = None

EXIF_ORIENTATION_TAG = 0x0112


class ImageTooLarge(Exception):
    pass


class ImageUnreadable(Exception):
    pass


def _read_dpi(img: Image.Image) -> Optional[float]:
    dpi = img.info.get("dpi")
    if not dpi:
        return None
    try:
        x = float(dpi[0]) if isinstance(dpi, (tuple, list)) else float(dpi)
    except (TypeError, ValueError):
        return None
    if x < 1:
        return None
    return round(x, 2)


def _read_exif_orientation(img: Image.Image) -> int:
    try:
        exif = img.getexif()
        return int(exif.get(EXIF_ORIENTATION_TAG, 1)) or 1
    except Exception:
        return 1


def inspect(path: Path) -> ImageInfo:
    """Liest nur den Header. Wirft ImageTooLarge oder ImageUnreadable."""
    try:
        with Image.open(path) as img:
            width, height = img.size
            if width * height > MAX_PIXELS:
                raise ImageTooLarge(f"{width}x{height}")
            fmt = img.format or ""
            frames = 1
            animated = False
            if fmt == "GIF":
                animated = bool(getattr(img, "is_animated", False))
                frames = 1  # animierte GIFs: nur erstes Bild
            elif fmt == "TIFF":
                frames = int(getattr(img, "n_frames", 1))
            orientation = _read_exif_orientation(img) if fmt == "JPEG" else 1
            if orientation in (5, 6, 7, 8):
                width, height = height, width  # gedreht anzeigen
            return ImageInfo(
                width=width,
                height=height,
                dpi=_read_dpi(img),
                frames=frames,
                animated=animated,
                mode=img.mode,
                format=fmt,
                exif_orientation=orientation,
            )
    except ImageTooLarge:
        raise
    except Exception as exc:  # defekt, gesperrt, kein Bild
        raise ImageUnreadable(str(exc) or exc.__class__.__name__) from exc


def thumbnail(path: Path, size: int = 96) -> Image.Image:
    """Kleines RGB-Vorschaubild (erste Seite/erstes Einzelbild), EXIF-gedreht."""
    with Image.open(path) as img:
        img.draft("RGB", (size * 2, size * 2))
        frame = ImageOps.exif_transpose(img) or img
        frame = frame.convert("RGBA") if "A" in frame.getbands() or frame.mode == "P" else frame.convert("RGB")
        frame.thumbnail((size, size), Image.Resampling.LANCZOS)
        if frame.mode == "RGBA":
            bg = Image.new("RGB", frame.size, "white")
            bg.paste(frame, mask=frame.split()[3])
            frame = bg
        return frame.copy()
