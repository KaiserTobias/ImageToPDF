"""Einstellungen: settings.json neben der .exe, Rückfall ins Benutzerprofil."""
from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

from .models import IMAGE_FORMATS, ConflictRule, FitMode, Orientation, PageFormat

SETTINGS_NAME = "settings.json"


@dataclass
class Settings:
    page_format: str = PageFormat.A4.value
    orientation: str = Orientation.AUTO.value
    fit: str = FitMode.FIT.value
    conflict_rule: str = ConflictRule.NUMBER.value
    formats: list[str] = field(default_factory=lambda: list(IMAGE_FORMATS.keys()))
    appearance: str = "system"      # "light" | "dark" | "system"
    open_target_after: bool = True

    # Typisierte Zugriffe
    @property
    def page_format_enum(self) -> PageFormat:
        return _enum_or(PageFormat, self.page_format, PageFormat.A4)

    @property
    def orientation_enum(self) -> Orientation:
        return _enum_or(Orientation, self.orientation, Orientation.AUTO)

    @property
    def fit_enum(self) -> FitMode:
        return _enum_or(FitMode, self.fit, FitMode.FIT)

    @property
    def conflict_rule_enum(self) -> ConflictRule:
        return _enum_or(ConflictRule, self.conflict_rule, ConflictRule.NUMBER)


def _enum_or(cls, value, default):
    try:
        return cls(value)
    except ValueError:
        return default


def app_dir() -> Path:
    """Ordner der .exe (gebaut) bzw. des Projekts (Entwicklung)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def user_dir() -> Path:
    base = os.environ.get("APPDATA") or os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "ImageToPDF"


class SettingsStore:
    def __init__(self, primary: Optional[Path] = None, fallback: Optional[Path] = None):
        self.primary = (primary or app_dir()) / SETTINGS_NAME
        self.fallback = (fallback or user_dir()) / SETTINGS_NAME
        self.path_in_use: Optional[Path] = None
        self.used_fallback = False

    def load(self) -> Settings:
        for p in (self.primary, self.fallback):
            if p.exists():
                try:
                    data = json.loads(p.read_text(encoding="utf-8"))
                    s = Settings(**{k: v for k, v in data.items() if k in Settings.__dataclass_fields__})
                    s.formats = [f for f in s.formats if f in IMAGE_FORMATS] or list(IMAGE_FORMATS)
                    self.path_in_use = p
                    return s
                except Exception:
                    continue
        return Settings()

    def save(self, settings: Settings) -> Path:
        payload = json.dumps(asdict(settings), indent=2, ensure_ascii=False)
        for i, p in enumerate((self.primary, self.fallback)):
            try:
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(payload, encoding="utf-8")
                self.path_in_use = p
                self.used_fallback = i == 1
                return p
            except OSError:
                continue
        raise OSError("Einstellungen konnten nicht gespeichert werden")
