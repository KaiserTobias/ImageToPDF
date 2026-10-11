"""PDF-Erzeugung mit reportlab.

Einbettung:
- JPEG (RGB/Graustufen, ohne EXIF-Drehung): Rohdaten 1:1 (DCTDecode), kein Neukodieren.
- Alles andere: verlustfrei als Flate; Transparenz auf Weiß, 16-Bit/CMYK/1-Bit
  werden in RGB bzw. Graustufen umgewandelt.
- "Seite füllen": Bild wird komplett gezeichnet, die Seite schneidet ab (Clipping).
"""
from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Callable, Iterable, Iterator, Optional

from PIL import Image, ImageOps, ImageSequence
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from . import layout
from .models import FitMode, ImageItem, Orientation, PageFormat, RunSummary, Status


class Cancelled(Exception):
    pass


def _flatten(frame: Image.Image) -> Image.Image:
    """In RGB oder L umwandeln; Transparenz auf Weiß."""
    mode = frame.mode
    if mode in ("RGB", "L"):
        return frame
    if mode == "P":
        frame = frame.convert("RGBA" if "transparency" in frame.info else "RGB")
        mode = frame.mode
    if mode in ("RGBA", "LA", "PA"):
        rgba = frame.convert("RGBA")
        bg = Image.new("RGB", rgba.size, (255, 255, 255))
        bg.paste(rgba, mask=rgba.getchannel("A"))
        return bg
    if mode == "1":
        return frame.convert("L")
    if mode.startswith("I;16") or mode == "I":
        # 16-Bit-Graustufen auf 8 Bit skalieren (lineare Punktfunktion, von Pillow für Modus I erlaubt)
        img_i = frame.convert("I")
        lo, hi = img_i.getextrema()
        if hi > 255 or lo < 0:
            scale = 255.0 / max(hi - lo, 1)
            return img_i.point(lambda v: (v - lo) * scale).convert("L")
        return img_i.convert("L")
    if mode == "F":
        return frame.convert("L")
    return frame.convert("RGB")  # CMYK, YCbCr, LAB, HSV, RGBX, ...


def _can_embed_raw_jpeg(item: ImageItem) -> bool:
    info = item.info
    return (
        info is not None
        and info.format == "JPEG"
        and info.mode in ("RGB", "L")
        and info.exif_orientation == 1
    )


def _frames(item: ImageItem) -> Iterator[Image.Image]:
    """Liefert die einzubettenden Seiten als PIL-Bilder (bereits gedreht, geplättet)."""
    with Image.open(item.source) as img:
        if img.format == "TIFF":
            for frame in ImageSequence.Iterator(img):
                f = frame.copy()
                f = ImageOps.exif_transpose(f) or f
                yield _flatten(f)
        else:
            img.seek(0)  # animiertes GIF: nur erstes Einzelbild
            f = img.copy()
            f = ImageOps.exif_transpose(f) or f
            yield _flatten(f)


def _frame_sizes(item: ImageItem) -> list[tuple[int, int]]:
    sizes: list[tuple[int, int]] = []
    with Image.open(item.source) as img:
        if img.format == "TIFF":
            for frame in ImageSequence.Iterator(img):
                sizes.append(frame.size)
        else:
            w, h = img.size
            if item.info and item.info.exif_orientation in (5, 6, 7, 8):
                w, h = h, w
            sizes.append((w, h))
    return sizes


def convert_item(item: ImageItem, cancel: Optional[threading.Event] = None) -> Path:
    """Erzeugt das PDF für ein Element. Schreibt erst in eine Temporärdatei
    und benennt am Ende um, damit kein halbes PDF liegen bleibt."""
    if item.effective_target is None:
        raise ValueError("Kein Ziel")
    target = item.effective_target
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + ".part")

    dpi = item.info.dpi if item.info else None
    raw_jpeg = _can_embed_raw_jpeg(item)

    c: Optional[canvas.Canvas] = None
    try:
        first = True
        if raw_jpeg:
            frames: Iterable[object] = [ImageReader(str(item.source))]
            sizes = _frame_sizes(item)
        else:
            frames = _frames(item)
            sizes = None

        for idx, frame in enumerate(frames):
            if cancel is not None and cancel.is_set():
                raise Cancelled()
            if sizes is not None:
                fw, fh = sizes[idx]
                reader = frame
            else:
                fw, fh = frame.size  # type: ignore[attr-defined]
                reader = ImageReader(frame)  # type: ignore[arg-type]

            lay = layout.compute(item.page_format, item.orientation, item.fit, fw, fh, dpi)
            if first:
                c = canvas.Canvas(str(tmp), pagesize=(lay.page_w, lay.page_h))
                c.setTitle(item.source.stem)
                c.setCreator("ImageToPDF")
                first = False
            else:
                c.setPageSize((lay.page_w, lay.page_h))

            c.saveState()
            p = c.beginPath()
            p.rect(0, 0, lay.page_w, lay.page_h)
            c.clipPath(p, stroke=0, fill=0)
            c.drawImage(reader, lay.img_x, lay.img_y, lay.img_w, lay.img_h)
            c.restoreState()
            c.showPage()

        if c is None:
            raise ValueError("Keine Bilddaten")
        c.save()
        c = None
        os.replace(tmp, target)
        return target
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


ProgressCallback = Callable[[int, int, ImageItem], None]


def run(
    items: Iterable[ImageItem],
    cancel: Optional[threading.Event] = None,
    progress: Optional[ProgressCallback] = None,
) -> RunSummary:
    """Konvertiert alle aktivierten, konvertierbaren Elemente. Fehler je Datei
    werden gesammelt, der Lauf geht weiter. Abbruch wirkt je Datei."""
    todo = [it for it in items if it.enabled and it.is_convertible]
    summary = RunSummary()
    total = len(todo)
    for i, it in enumerate(todo, 1):
        if cancel is not None and cancel.is_set():
            summary.cancelled = True
            break
        if progress:
            progress(i, total, it)
        if it.effective_target is None:
            it.result = Status.SKIPPED
            it.result_message = "Konfliktregel: überspringen"
            summary.skipped += 1
            continue
        try:
            convert_item(it, cancel)
            it.result = Status.DONE
            it.result_message = str(it.effective_target)
            summary.created += 1
        except Cancelled:
            summary.cancelled = True
            break
        except Exception as exc:
            it.result = Status.FAILED
            it.result_message = str(exc) or exc.__class__.__name__
            summary.failed += 1
            summary.errors.append((it.source, it.result_message))
    return summary
