import threading
from pathlib import Path

import pytest
from PIL import Image
from pypdf import PdfReader

from imagetopdf import converter, inspector, layout, planner, scanner
from imagetopdf.models import (
    FALLBACK_DPI,
    ConflictRule,
    FitMode,
    ImageItem,
    Orientation,
    PageFormat,
    Status,
)
from imagetopdf.settings import Settings, SettingsStore


def build_items(root: Path, formats=("png", "jpg", "tif", "bmp", "gif"), exclude=None):
    items = []
    for p in scanner.scan(root, formats, exclude):
        it = ImageItem(source=p, root=root)
        try:
            it.info = inspector.inspect(p)
        except inspector.ImageTooLarge:
            it.error = "too_large"
        except inspector.ImageUnreadable as e:
            it.error = str(e)
        items.append(it)
    return items


# ---------- Scanner ----------

def test_scan_finds_all_formats_recursively(img_dir):
    found = {p.relative_to(img_dir).as_posix() for p in scanner.scan(img_dir, ["png", "jpg", "tif", "bmp", "gif"])}
    assert "rot.jpg" in found
    assert "sub/blau.bmp" in found
    assert "sub/tief/grau.tif" in found
    assert "anim.gif" in found
    assert "notiz.txt" not in found


def test_scan_respects_format_selection(img_dir):
    found = {p.suffix for p in scanner.scan(img_dir, ["jpg"])}
    assert found == {".jpg"}


def test_scan_excludes_target_dir_inside_source(img_dir):
    target = img_dir / "sub"
    found = {p.relative_to(img_dir).as_posix() for p in scanner.scan(img_dir, ["bmp", "tif"], exclude_dir=target)}
    assert found == {"multi.tif"}  # bmp und grau.tif liegen nur unter sub/


def test_scan_ignores_exclude_outside_source(img_dir, tmp_path):
    outside = tmp_path / "anderswo"
    outside.mkdir()
    found = list(scanner.scan(img_dir, ["bmp"], exclude_dir=outside))
    assert len(found) == 1


# ---------- Inspector ----------

def test_inspect_basic_and_dpi(img_dir):
    info = inspector.inspect(img_dir / "rot.jpg")
    assert (info.width, info.height, info.format) == (400, 300, "JPEG")
    tif = inspector.inspect(img_dir / "sub" / "tief" / "grau.tif")
    assert tif.dpi == 300


def test_inspect_multipage_tiff_and_animated_gif(img_dir):
    assert inspector.inspect(img_dir / "multi.tif").frames == 2
    g = inspector.inspect(img_dir / "anim.gif")
    assert g.animated is True
    assert inspector.inspect(img_dir / "statisch.gif").animated is False


def test_inspect_rejects_too_large(tmp_path, monkeypatch):
    # Pillow-Header ohne echte Pixel: BMP-Header mit riesigen Maßen manuell nachbauen wäre
    # aufwendig, daher Grenze temporär senken.
    monkeypatch.setattr(inspector, "MAX_PIXELS", 10_000)
    p = tmp_path / "gross.png"
    Image.new("RGB", (200, 200)).save(p)
    with pytest.raises(inspector.ImageTooLarge):
        inspector.inspect(p)


def test_inspect_unreadable(img_dir):
    with pytest.raises(inspector.ImageUnreadable):
        inspector.inspect(img_dir / "kaputt.png")


def test_inspect_exif_rotation_swaps_dimensions(tmp_path):
    p = tmp_path / "gedreht.jpg"
    img = Image.new("RGB", (400, 200))
    exif = img.getexif()
    exif[0x0112] = 6  # 90° im Uhrzeigersinn
    img.save(p, exif=exif.tobytes())
    info = inspector.inspect(p)
    assert (info.width, info.height) == (200, 400)
    assert info.exif_orientation == 6


def test_thumbnail(img_dir):
    t = inspector.thumbnail(img_dir / "transparent.png", 64)
    assert t.mode == "RGB"
    assert max(t.size) <= 64
    assert t.getpixel((t.width - 1, t.height - 1)) == (255, 255, 255)  # transparent -> weiß


# ---------- Layout ----------

def test_layout_auto_orientation_and_margin():
    lay = layout.compute(PageFormat.A4, Orientation.AUTO, FitMode.FIT, 400, 300, None)
    assert lay.is_landscape
    assert lay.margin == pytest.approx(0.05 * min(lay.page_w, lay.page_h))
    assert lay.img_w <= lay.page_w - 2 * lay.margin + 0.01
    assert not lay.cropped


def test_layout_fixed_orientation():
    lay = layout.compute(PageFormat.A5, Orientation.PORTRAIT, FitMode.FIT, 400, 300, None)
    assert not lay.is_landscape


def test_layout_fill_crops():
    lay = layout.compute(PageFormat.A4, Orientation.PORTRAIT, FitMode.FILL, 400, 300, None)
    assert lay.cropped
    assert lay.margin == 0
    assert lay.img_h == pytest.approx(lay.page_h) or lay.img_w == pytest.approx(lay.page_w)


def test_layout_original_size_dpi_and_fallback():
    lay = layout.compute(PageFormat.ORIGINAL, Orientation.AUTO, FitMode.FIT, 300, 150, 300)
    assert (lay.page_w, lay.page_h) == pytest.approx((72, 36))
    lay2 = layout.compute(PageFormat.ORIGINAL, Orientation.AUTO, FitMode.FIT, 96, 96, None)
    assert lay2.page_w == pytest.approx(96 * 72 / FALLBACK_DPI)
    assert lay2.margin == 0


# ---------- Planner ----------

def test_planner_beside_image_and_structure(img_dir, tmp_path):
    items = build_items(img_dir)
    planner.plan(items, None)
    blau = next(i for i in items if i.name == "blau.bmp")
    assert blau.effective_target == img_dir / "sub" / "blau.pdf"

    target = tmp_path / "ziel"
    planner.plan(items, target)
    assert blau.effective_target == target / "sub" / "blau.pdf"
    grau = next(i for i in items if i.name == "grau.tif")
    assert grau.effective_target == target / "sub" / "tief" / "grau.pdf"


def test_planner_conflict_within_run_numbering(img_dir):
    items = build_items(img_dir)
    planner.plan(items, None)
    scans = [i for i in items if i.source.stem == "scan"]
    assert all(i.conflict for i in scans)
    targets = sorted(str(i.effective_target.name) for i in scans)
    assert targets == ["scan.pdf", "scan_1.pdf"]
    assert Status.CONFLICT in scans[0].statuses()


def test_planner_existing_file_rules(img_dir):
    items = build_items(img_dir, formats=("bmp",))
    blau = items[0]
    (img_dir / "sub" / "blau.pdf").write_bytes(b"%PDF")

    blau.conflict_rule = ConflictRule.NUMBER
    planner.plan(items, None)
    assert blau.conflict and blau.effective_target.name == "blau_1.pdf"

    blau.conflict_rule = ConflictRule.OVERWRITE
    planner.plan(items, None)
    assert blau.effective_target.name == "blau.pdf"

    blau.conflict_rule = ConflictRule.SKIP
    planner.plan(items, None)
    assert blau.effective_target is None


def test_planner_skips_disabled_and_unreadable(img_dir):
    items = build_items(img_dir)
    kaputt = next(i for i in items if i.name == "kaputt.png")
    assert not kaputt.is_convertible
    assert Status.ERROR in kaputt.statuses()
    rot = next(i for i in items if i.name == "rot.jpg")
    rot.enabled = False
    planner.plan(items, None)
    assert rot.effective_target is None and kaputt.effective_target is None


# ---------- Konverter ----------

def _convert_all(img_dir, target=None, **overrides):
    items = build_items(img_dir)
    for it in items:
        for k, v in overrides.items():
            setattr(it, k, v)
    planner.plan(items, target)
    summary = converter.run(items)
    return items, summary


def test_convert_all_formats(img_dir):
    items, summary = _convert_all(img_dir)
    assert summary.failed == 0
    assert summary.created == 10  # 11 Bilder, 1 defekt
    for it in items:
        if it.is_convertible:
            assert it.result == Status.DONE
            assert it.effective_target.exists()
            reader = PdfReader(str(it.effective_target))
            assert len(reader.pages) == it.info.frames
    # Originale unverändert
    assert (img_dir / "rot.jpg").exists() and (img_dir / "kaputt.png").exists()
    assert not list(img_dir.rglob("*.part"))


def test_convert_jpeg_embedded_raw(img_dir):
    items, _ = _convert_all(img_dir)
    rot = next(i for i in items if i.name == "rot.jpg")
    reader = PdfReader(str(rot.effective_target))
    xobj = reader.pages[0]["/Resources"]["/XObject"]
    img = list(xobj.values())[0].get_object()
    assert "/DCTDecode" in str(img.get("/Filter"))
    assert len(img.get_data()) == (img_dir / "rot.jpg").stat().st_size


def test_convert_page_sizes_and_orientation(img_dir):
    items, _ = _convert_all(img_dir, page_format=PageFormat.A4)
    rot = next(i for i in items if i.name == "rot.jpg")    # 400x300 -> quer
    gruen = next(i for i in items if i.name == "gruen.png")  # 300x400 -> hoch
    rb = PdfReader(str(rot.effective_target)).pages[0].mediabox
    gb = PdfReader(str(gruen.effective_target)).pages[0].mediabox
    assert float(rb.width) > float(rb.height)
    assert float(gb.width) < float(gb.height)
    assert float(gb.height) == pytest.approx(297 / 25.4 * 72, abs=0.5)


def test_convert_multipage_tiff_per_page_orientation(img_dir):
    items, _ = _convert_all(img_dir, page_format=PageFormat.A4)
    multi = next(i for i in items if i.name == "multi.tif")
    pages = PdfReader(str(multi.effective_target)).pages
    assert len(pages) == 2
    assert float(pages[0].mediabox.width) < float(pages[0].mediabox.height)
    assert float(pages[1].mediabox.width) > float(pages[1].mediabox.height)


def test_convert_original_size_uses_dpi(img_dir):
    items, _ = _convert_all(img_dir, page_format=PageFormat.ORIGINAL)
    grau = next(i for i in items if i.name == "grau.tif")  # 200 px @ 300 dpi = 48 pt
    box = PdfReader(str(grau.effective_target)).pages[0].mediabox
    assert float(box.width) == pytest.approx(48, abs=0.1)
    gruen = next(i for i in items if i.name == "gruen.png")  # 300 px @ 96 dpi = 225 pt
    box = PdfReader(str(gruen.effective_target)).pages[0].mediabox
    assert float(box.width) == pytest.approx(225, abs=0.1)


def test_convert_animated_gif_single_page(img_dir):
    items, _ = _convert_all(img_dir)
    anim = next(i for i in items if i.name == "anim.gif")
    assert len(PdfReader(str(anim.effective_target)).pages) == 1


def test_convert_conflict_numbering_and_skip(img_dir):
    items, summary = _convert_all(img_dir)
    assert (img_dir / "scan.pdf").exists() and (img_dir / "scan_1.pdf").exists()

    # zweiter Lauf: alle existieren jetzt -> nummerieren weiter, überspringen überspringt
    items2 = build_items(img_dir, formats=("jpg",))
    rot = next(i for i in items2 if i.name == "rot.jpg")
    rot.conflict_rule = ConflictRule.SKIP
    planner.plan(items2, None)
    s2 = converter.run(items2)
    assert rot.result == Status.SKIPPED and s2.skipped == 1
    scanjpg = next(i for i in items2 if i.name == "scan.jpg")
    assert scanjpg.effective_target.name == "scan_2.pdf"
    assert s2.created == 1


def test_convert_to_target_dir_rebuilds_structure(img_dir, tmp_path):
    target = tmp_path / "ziel"
    items, summary = _convert_all(img_dir, target=target)
    assert (target / "sub" / "tief" / "grau.pdf").exists()
    assert not list(img_dir.rglob("*.pdf"))  # Quelle unberührt


def test_convert_cancel(img_dir):
    items = build_items(img_dir)
    planner.plan(items, None)
    ev = threading.Event()
    ev.set()
    summary = converter.run(items, cancel=ev)
    assert summary.cancelled and summary.created == 0


def test_convert_16bit_and_cmyk(tmp_path):
    p16 = tmp_path / "16bit.tif"
    Image.new("I;16", (50, 50), 40000).save(p16)
    cmyk = tmp_path / "cmyk.jpg"
    Image.new("CMYK", (50, 50), (0, 100, 100, 0)).save(cmyk)
    items = build_items(tmp_path, formats=("tif", "jpg"))
    planner.plan(items, None)
    s = converter.run(items)
    assert s.failed == 0 and s.created == 2


# ---------- Settings ----------

def test_settings_roundtrip_and_fallback(tmp_path):
    store = SettingsStore(primary=tmp_path / "app", fallback=tmp_path / "user")
    s = store.load()
    assert s.page_format == "A4" and s.formats
    s.page_format = "A3"
    s.formats = ["png"]
    store.save(s)
    assert (tmp_path / "app" / "settings.json").exists()
    assert SettingsStore(primary=tmp_path / "app", fallback=tmp_path / "user").load().page_format == "A3"

    ro = tmp_path / "readonly.txt"
    ro.write_text("x")  # Datei statt Ordner -> Schreiben in "ro/settings.json" scheitert
    store2 = SettingsStore(primary=ro, fallback=tmp_path / "user")
    store2.save(Settings())
    assert store2.used_fallback
