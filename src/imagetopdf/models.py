"""Datenmodelle und Konstanten – keine GUI-Abhängigkeiten."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional


class PageFormat(str, Enum):
    ORIGINAL = "original"
    A2 = "A2"
    A3 = "A3"
    A4 = "A4"
    A5 = "A5"


class Orientation(str, Enum):
    AUTO = "auto"
    PORTRAIT = "portrait"
    LANDSCAPE = "landscape"


class FitMode(str, Enum):
    FIT = "fit"      # Einpassen mit Rand
    FILL = "fill"    # Seite füllen, Überstand wird abgeschnitten


class ConflictRule(str, Enum):
    NUMBER = "number"
    OVERWRITE = "overwrite"
    SKIP = "skip"


class Status(str, Enum):
    OK = "ok"
    CONFLICT = "conflict"        # gelb
    ANIMATED = "animated"        # gelb
    TOO_LARGE = "too_large"      # rot
    PATH_TOO_LONG = "path_too_long"  # rot
    ERROR = "error"              # rot
    DONE = "done"                # nach Konvertierung
    SKIPPED = "skipped"          # nach Konvertierung (Regel: überspringen)
    FAILED = "failed"            # Konvertierung fehlgeschlagen


# Seitenmaße in mm (Hochformat)
PAGE_SIZES_MM: dict[PageFormat, tuple[float, float]] = {
    PageFormat.A2: (420.0, 594.0),
    PageFormat.A3: (297.0, 420.0),
    PageFormat.A4: (210.0, 297.0),
    PageFormat.A5: (148.0, 210.0),
}

# Unterstützte Formate: Schlüssel = Auswahl in der Oberfläche, Werte = Endungen
IMAGE_FORMATS: dict[str, tuple[str, ...]] = {
    "png": (".png",),
    "jpg": (".jpg", ".jpeg"),
    "tif": (".tif", ".tiff"),
    "bmp": (".bmp",),
    "gif": (".gif",),
}

MAX_PIXELS = 100_000_000          # über 100 Megapixel wird verweigert
MAX_PATH_LENGTH = 259             # Windows-Grenze ohne Long-Path-Unterstützung
FALLBACK_DPI = 96.0
MARGIN_FRACTION = 0.05            # Rand: 5 % der kürzeren Seitenkante
MM_TO_PT = 72.0 / 25.4
PDF_MAX_PT = 14400.0              # Maximale Seitenkante laut PDF-Spezifikation

RED_STATUSES = {Status.TOO_LARGE, Status.PATH_TOO_LONG, Status.ERROR, Status.FAILED}
YELLOW_STATUSES = {Status.CONFLICT, Status.ANIMATED}


@dataclass
class ImageInfo:
    width: int
    height: int
    dpi: Optional[float]          # None = keine Angabe in der Datei
    frames: int = 1               # Seiten (TIFF) bzw. Einzelbilder (GIF)
    animated: bool = False        # animiertes GIF
    mode: str = "RGB"
    format: str = ""              # Pillow-Formatname, z. B. "JPEG"
    exif_orientation: int = 1


@dataclass(eq=False)
class ImageItem:
    source: Path
    root: Path
    info: Optional[ImageInfo] = None
    error: Optional[str] = None
    enabled: bool = True
    page_format: PageFormat = PageFormat.A4
    orientation: Orientation = Orientation.AUTO
    fit: FitMode = FitMode.FIT
    conflict_rule: ConflictRule = ConflictRule.NUMBER
    target: Optional[Path] = None            # nominelles Ziel (name.pdf)
    effective_target: Optional[Path] = None  # tatsächliches Ziel nach Konfliktregel
    conflict: bool = False
    result: Optional[Status] = None          # DONE / SKIPPED / FAILED nach Lauf
    result_message: str = ""
    thumbnail: object = None                 # PIL-Bild, wird von der GUI befüllt

    @property
    def name(self) -> str:
        return self.source.name

    @property
    def relative_dir(self) -> Path:
        try:
            return self.source.parent.relative_to(self.root)
        except ValueError:
            return Path()

    @property
    def size_bytes(self) -> int:
        try:
            return self.source.stat().st_size
        except OSError:
            return 0

    @property
    def is_convertible(self) -> bool:
        return self.info is not None and self.error is None and not self.path_too_long

    @property
    def path_too_long(self) -> bool:
        t = self.effective_target or self.target
        return t is not None and len(str(t)) > MAX_PATH_LENGTH

    def statuses(self) -> list[Status]:
        """Alle zutreffenden Status in Anzeigereihenfolge (rot vor gelb)."""
        if self.result is not None:
            return [self.result]
        out: list[Status] = []
        if self.error:
            out.append(Status.ERROR if self.error != "too_large" else Status.TOO_LARGE)
        if self.path_too_long:
            out.append(Status.PATH_TOO_LONG)
        if self.conflict:
            out.append(Status.CONFLICT)
        if self.info and self.info.animated:
            out.append(Status.ANIMATED)
        return out or [Status.OK]

    def worst_level(self) -> str:
        """'red', 'yellow' oder 'ok' – für die Zeilenfärbung."""
        st = self.statuses()
        if any(s in RED_STATUSES for s in st):
            return "red"
        if any(s in YELLOW_STATUSES for s in st):
            return "yellow"
        if Status.DONE in st:
            return "green"
        return "ok"


@dataclass
class RunSummary:
    created: int = 0
    skipped: int = 0
    failed: int = 0
    cancelled: bool = False
    errors: list[tuple[Path, str]] = field(default_factory=list)
