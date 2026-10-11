"""Seitengeometrie – gemeinsam genutzt von Konverter und Vorschau."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .models import (
    FALLBACK_DPI,
    MARGIN_FRACTION,
    MM_TO_PT,
    PAGE_SIZES_MM,
    PDF_MAX_PT,
    FitMode,
    Orientation,
    PageFormat,
)


@dataclass(frozen=True)
class PageLayout:
    page_w: float   # pt
    page_h: float   # pt
    img_x: float    # pt, linke untere Ecke des gezeichneten Bildes
    img_y: float
    img_w: float
    img_h: float
    margin: float
    cropped: bool   # True, wenn das Bild über die Seite hinausragt (Seite füllen)

    @property
    def is_landscape(self) -> bool:
        return self.page_w > self.page_h


def page_size_pt(
    fmt: PageFormat,
    orientation: Orientation,
    img_w: int,
    img_h: int,
    dpi: Optional[float],
) -> tuple[float, float]:
    if fmt == PageFormat.ORIGINAL:
        d = dpi or FALLBACK_DPI
        w, h = img_w * 72.0 / d, img_h * 72.0 / d
        biggest = max(w, h)
        if biggest > PDF_MAX_PT:  # PDF-Grenze: proportional verkleinern
            f = PDF_MAX_PT / biggest
            w, h = w * f, h * f
        return w, h

    mm_w, mm_h = PAGE_SIZES_MM[fmt]
    w, h = mm_w * MM_TO_PT, mm_h * MM_TO_PT  # Hochformat
    if orientation == Orientation.AUTO:
        landscape = img_w > img_h
    else:
        landscape = orientation == Orientation.LANDSCAPE
    if landscape:
        w, h = h, w
    return w, h


def compute(
    fmt: PageFormat,
    orientation: Orientation,
    fit: FitMode,
    img_w: int,
    img_h: int,
    dpi: Optional[float],
) -> PageLayout:
    page_w, page_h = page_size_pt(fmt, orientation, img_w, img_h, dpi)

    if fmt == PageFormat.ORIGINAL:
        return PageLayout(page_w, page_h, 0.0, 0.0, page_w, page_h, 0.0, False)

    if fit == FitMode.FILL:
        margin = 0.0
        scale = max(page_w / img_w, page_h / img_h)
    else:
        margin = MARGIN_FRACTION * min(page_w, page_h)
        avail_w, avail_h = page_w - 2 * margin, page_h - 2 * margin
        scale = min(avail_w / img_w, avail_h / img_h)

    draw_w, draw_h = img_w * scale, img_h * scale
    x = (page_w - draw_w) / 2
    y = (page_h - draw_h) / 2
    cropped = draw_w > page_w + 0.01 or draw_h > page_h + 0.01
    return PageLayout(page_w, page_h, x, y, draw_w, draw_h, margin, cropped)
