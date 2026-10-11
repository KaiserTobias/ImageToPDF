"""Ordnersuche nach Bilddateien."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, Iterator, Optional

from .models import IMAGE_FORMATS


def extensions_for(formats: Iterable[str]) -> set[str]:
    exts: set[str] = set()
    for f in formats:
        exts.update(IMAGE_FORMATS.get(f.lower(), ()))
    return exts


def _is_within(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except (ValueError, OSError):
        return False


def scan(root: Path, formats: Iterable[str], exclude_dir: Optional[Path] = None) -> Iterator[Path]:
    """Liefert alle Bilddateien unter root (inkl. Unterordner), sortiert je Ordner.

    exclude_dir (z. B. der Zielordner) wird samt Unterordnern ausgelassen,
    sofern er innerhalb von root liegt.
    """
    exts = extensions_for(formats)
    if not exts:
        return
    root = Path(root)
    excl = exclude_dir.resolve() if exclude_dir and _is_within(exclude_dir, root) else None

    for dirpath, dirnames, filenames in os.walk(root):
        current = Path(dirpath)
        if excl is not None:
            dirnames[:] = [
                d for d in dirnames
                if (current / d).resolve() != excl
            ]
        dirnames.sort(key=str.lower)
        for name in sorted(filenames, key=str.lower):
            if Path(name).suffix.lower() in exts:
                yield current / name
