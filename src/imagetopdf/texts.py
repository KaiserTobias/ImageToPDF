"""Alle Oberflächentexte an einer Stelle (Deutsch). Für Englisch: zweites Wörterbuch ergänzen."""
from __future__ import annotations

from .models import ConflictRule, FitMode, Orientation, PageFormat, Status

DE = {
    "app_title": "ImageToPDF",
    # Quelle / Ziel
    "source": "Quellordner",
    "browse": "Durchsuchen…",
    "drop_hint": "Ordner hierher ziehen oder „Durchsuchen“ wählen",
    "formats": "Bildformate",
    "target_beside": "PDF neben dem Bild ablegen",
    "target_dir": "In Zielordner ablegen (Unterordnerstruktur wird nachgebaut)",
    "scan": "Ordner durchsuchen",
    "scanning": "Durchsuche … {n} Bilder gefunden",
    "scan_done": "{n} Bilder gefunden",
    "scan_none": "Keine Bilder mit den gewählten Formaten gefunden.",
    "no_source": "Bitte zuerst einen Quellordner wählen.",
    "no_target": "Bitte einen Zielordner wählen oder „PDF neben dem Bild ablegen“ aktivieren.",
    "no_formats": "Bitte mindestens ein Bildformat auswählen.",
    # Tabelle
    "col_check": "",
    "col_thumb": "Vorschau",
    "col_name": "Name",
    "col_subdir": "Unterordner",
    "col_format": "Format",
    "col_resolution": "Auflösung",
    "col_filesize": "Größe",
    "col_page": "Seitenformat",
    "col_orientation": "Ausrichtung",
    "col_fit": "Anpassung",
    "col_conflict": "Bei Konflikt",
    "col_target": "Zielpfad",
    "col_status": "Status",
    # Bearbeitungsleiste
    "edit_bar": "Für markierte Zeilen",
    "apply": "Anwenden",
    "select_all": "Alle markieren",
    "enable_rows": "Aktivieren",
    "disable_rows": "Deaktivieren",
    "save_default": "Als Standard speichern",
    "default_saved": "Standardeinstellung gespeichert.",
    "default_saved_fallback": "Standardeinstellung gespeichert (im Benutzerprofil, da der Programmordner schreibgeschützt ist).",
    "hint_doubleclick": "Doppelklick auf eine Zelle schaltet den Wert dieser Zeile weiter.",
    # Vorschau
    "preview": "Vorschau",
    "preview_none": "Zeile markieren, um die Seite zu sehen.",
    "preview_crop_warning": "Seite füllen: Bildinhalt wird im PDF abgeschnitten.",
    "preview_info": "{fmt} · {w} × {h} mm · Rand {m} mm",
    "preview_pages": " · {n} Seiten",
    "preview_original": "Originalgröße bei {dpi} DPI",
    "preview_dpi_fallback": " (keine DPI-Angabe, 96 angenommen)",
    # Konvertierung
    "convert": "Konvertieren",
    "cancel": "Abbrechen",
    "open_after": "Zielordner danach öffnen",
    "progress": "{i} / {n}: {name}",
    "nothing_to_convert": "Keine aktivierten, konvertierbaren Bilder in der Liste.",
    "summary_title": "Fertig",
    "summary": "Erstellt: {created}\nÜbersprungen: {skipped}\nFehler: {failed}",
    "summary_cancelled": "\n\nAbgebrochen.",
    "summary_errors": "\n\nFehlerliste:\n{errors}",
    # Sonstiges
    "appearance": "Dunkel",
    "ready": "Bereit.",
    "error_title": "Fehler",
    "settings_save_failed": "Einstellungen konnten nicht gespeichert werden.",
    "animated_note": "Animiertes GIF: nur das erste Bild wird verwendet.",
    "too_large_note": "Bild größer als 100 Megapixel – wird nicht verarbeitet.",
    "path_too_long_note": "Zielpfad länger als 260 Zeichen – wird übersprungen.",
    "conflict_note": "Ziel-PDF existiert bereits oder der Name wird mehrfach vergeben.",
    "error_note": "Datei nicht lesbar: {msg}",
}

PAGE_FORMAT_LABELS = {
    PageFormat.ORIGINAL: "Originalgröße",
    PageFormat.A2: "A2",
    PageFormat.A3: "A3",
    PageFormat.A4: "A4",
    PageFormat.A5: "A5",
}
ORIENTATION_LABELS = {
    Orientation.AUTO: "Automatisch",
    Orientation.PORTRAIT: "Hochformat",
    Orientation.LANDSCAPE: "Querformat",
}
FIT_LABELS = {
    FitMode.FIT: "Einpassen",
    FitMode.FILL: "Seite füllen",
}
CONFLICT_LABELS = {
    ConflictRule.NUMBER: "Nummerieren",
    ConflictRule.OVERWRITE: "Überschreiben",
    ConflictRule.SKIP: "Überspringen",
}
STATUS_LABELS = {
    Status.OK: "✓",
    Status.CONFLICT: "⚠ Konflikt",
    Status.ANIMATED: "⚠ Animiert",
    Status.TOO_LARGE: "✖ Zu groß",
    Status.PATH_TOO_LONG: "✖ Pfad zu lang",
    Status.ERROR: "✖ Nicht lesbar",
    Status.DONE: "✔ Erstellt",
    Status.SKIPPED: "– Übersprungen",
    Status.FAILED: "✖ Fehlgeschlagen",
}

T = DE


def label_to_enum(labels: dict, label: str):
    for k, v in labels.items():
        if v == label:
            return k
    raise KeyError(label)
