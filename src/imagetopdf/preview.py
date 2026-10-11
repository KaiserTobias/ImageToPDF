"""Vorschau einer PDF-Seite als PIL-Bild (für die Oberfläche)."""
from __future__ import annotations

from PIL import Image, ImageDraw

from . import layout
from .models import ImageItem, PageFormat


def render(item: ImageItem, box: int = 300, dark: bool = False) -> tuple[Image.Image, layout.PageLayout | None]:
    """Zeichnet Seite, Rand und Bildlage. Nutzt dieselbe Geometrie wie der Konverter."""
    bg = (43, 43, 43) if dark else (235, 235, 235)
    canvas_img = Image.new("RGB", (box, box), bg)
    if item.info is None or item.thumbnail is None:
        return canvas_img, None

    lay = layout.compute(
        item.page_format, item.orientation, item.fit,
        item.info.width, item.info.height, item.info.dpi,
    )
    # Seite in den Kasten einpassen
    pad = 14
    scale = min((box - 2 * pad) / lay.page_w, (box - 2 * pad) / lay.page_h)
    pw, ph = max(1, int(lay.page_w * scale)), max(1, int(lay.page_h * scale))
    px, py = (box - pw) // 2, (box - ph) // 2

    page = Image.new("RGB", (pw, ph), (255, 255, 255))

    # Bild skalieren (PDF-Koordinaten: y von unten; Bild: y von oben)
    iw, ih = max(1, int(round(lay.img_w * scale))), max(1, int(round(lay.img_h * scale)))
    ix = int(round(lay.img_x * scale))
    iy = ph - int(round((lay.img_y + lay.img_h) * scale))
    thumb = item.thumbnail.resize((iw, ih), Image.Resampling.BILINEAR)
    page.paste(thumb, (ix, iy))  # Überstand wird durch die Seitengrenze abgeschnitten

    draw = ImageDraw.Draw(page)
    if item.page_format != PageFormat.ORIGINAL and lay.margin > 0:
        m = int(round(lay.margin * scale))
        draw.rectangle([m, m, pw - 1 - m, ph - 1 - m], outline=(170, 190, 220))

    # Schatten und Seitenrahmen
    shadow = ImageDraw.Draw(canvas_img)
    shadow.rectangle([px + 3, py + 3, px + pw + 3, py + ph + 3], fill=(20, 20, 20) if dark else (190, 190, 190))
    canvas_img.paste(page, (px, py))
    shadow.rectangle([px - 1, py - 1, px + pw, py + ph], outline=(120, 120, 120))
    return canvas_img, lay
