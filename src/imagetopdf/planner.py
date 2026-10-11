"""Zielpfade bestimmen und Namenskonflikte auflösen."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional

from .models import ConflictRule, ImageItem


def nominal_target(item: ImageItem, target_dir: Optional[Path]) -> Path:
    """name.pdf neben dem Bild oder im Zielordner mit nachgebauter Struktur."""
    pdf_name = item.source.stem + ".pdf"
    if target_dir is None:
        return item.source.parent / pdf_name
    return Path(target_dir) / item.relative_dir / pdf_name


def _key(p: Path) -> str:
    # Windows: Groß-/Kleinschreibung ignorieren, damit Scan.png und scan.jpg kollidieren
    return str(p).lower()


def _numbered(target: Path, taken: set[str]) -> Path:
    stem, parent = target.stem, target.parent
    n = 1
    while True:
        cand = parent / f"{stem}_{n}.pdf"
        if _key(cand) not in taken and not cand.exists():
            return cand
        n += 1


def plan(items: Iterable[ImageItem], target_dir: Optional[Path]) -> None:
    """Setzt target, effective_target und conflict für alle aktivierten Elemente.

    Ein Konflikt liegt vor, wenn das Ziel bereits existiert oder ein anderes
    Element im selben Lauf dasselbe nominelle Ziel hat. Die Auflösung folgt der
    Konfliktregel des Elements; "nummerieren" vergibt den ersten freien Namen
    unter Berücksichtigung der in diesem Lauf bereits vergebenen Ziele.
    """
    items = list(items)
    for it in items:
        it.target = nominal_target(it, target_dir)
        it.effective_target = None
        it.conflict = False

    active = [it for it in items if it.enabled and it.is_convertible]

    # Nominelle Ziele zählen (nur aktive, konvertierbare Elemente)
    counts: dict[str, int] = {}
    for it in active:
        counts[_key(it.target)] = counts.get(_key(it.target), 0) + 1

    reserved: set[str] = set()
    for it in active:
        k = _key(it.target)
        exists = it.target.exists()
        dup_in_run = counts[k] > 1
        it.conflict = exists or dup_in_run

        if not it.conflict:
            it.effective_target = it.target
            reserved.add(k)
            continue

        rule = it.conflict_rule
        if rule == ConflictRule.SKIP:
            it.effective_target = None
        elif rule == ConflictRule.OVERWRITE:
            # Überschreiben: nur das erste Element im Lauf bekommt das Ziel,
            # weitere mit gleichem Ziel werden nummeriert, damit nichts verloren geht.
            if k in reserved:
                it.effective_target = _numbered(it.target, reserved)
            else:
                it.effective_target = it.target
            reserved.add(_key(it.effective_target))
        else:  # NUMBER
            if not exists and k not in reserved:
                it.effective_target = it.target  # erster Treffer behält den Namen
            else:
                it.effective_target = _numbered(it.target, reserved)
            reserved.add(_key(it.effective_target))

    # Nicht aktive Elemente: nur nominelles Ziel anzeigen, Konflikt mit bestehender Datei markieren
    for it in items:
        if it not in active and it.target is not None:
            it.conflict = it.target.exists()
