# ImageToPDF – Anleitung

Wandelt Bilder (PNG, JPG, TIF, BMP, GIF) aus einem Ordner samt Unterordnern in je ein PDF um. Die Originalbilder werden nie verändert.

## Start

1. ZIP entpacken (an einen beliebigen Ort, auch USB-Stick).
2. `ImageToPDF.exe` doppelklicken. Keine Installation nötig.

**Hinweis Windows SmartScreen:** Beim ersten Start kann „Der Computer wurde durch Windows geschützt“ erscheinen, weil das Programm nicht signiert ist. Auf „Weitere Informationen“ und dann „Trotzdem ausführen“ klicken. Das ist nur einmal nötig.

## Bedienung

1. **Quellordner** über „Durchsuchen…“ wählen (oder einen Ordner in das Fenster ziehen).
2. **Bildformate** anhaken, die gesucht werden sollen.
3. **Ziel** wählen:
   - *PDF neben dem Bild ablegen* (Standard) – das PDF landet im selben Ordner wie das Bild.
   - *In Zielordner ablegen* – alle PDFs landen in einem Ordner; die Unterordnerstruktur der Quelle wird dort nachgebaut.
4. **Ordner durchsuchen** klicken. Die Tabelle füllt sich mit allen gefundenen Bildern, inklusive Vorschaubild, Auflösung, Dateigröße und geplantem Zielpfad.
5. **Feinabstimmung** (optional):
   - Zeilen markieren (Strg+A für alle, Strg/Umschalt+Klick für mehrere), in der Leiste darunter Seitenformat, Ausrichtung, Anpassung und Konfliktregel wählen und **Anwenden** klicken.
   - **Doppelklick** auf eine Zelle (Seitenformat, Ausrichtung, Anpassung, Bei Konflikt) schaltet den Wert dieser einen Zeile weiter.
   - Häkchen in der ersten Spalte anklicken, um ein Bild vom Lauf auszuschließen (Leertaste für alle markierten Zeilen).
   - Die **Vorschau** unten zeigt für die markierte Zeile, wie die PDF-Seite aussehen wird.
6. **Konvertieren** klicken. Fortschritt wird angezeigt, „Abbrechen“ stoppt nach der aktuellen Datei. Am Ende erscheint eine Zusammenfassung.

## Einstellungen

- **Seitenformat:** Originalgröße (nutzt die DPI-Angabe des Bildes, sonst 96 DPI), A2, A3, A4, A5.
- **Ausrichtung:** Automatisch (nach Bildform), Hochformat, Querformat. Bei Originalgröße ohne Bedeutung.
- **Anpassung:** *Einpassen* (ganzes Bild mit Rand, ca. 5 % der kürzeren Seitenkante) oder *Seite füllen* (Seite wird komplett ausgefüllt, überstehender Bildinhalt wird im PDF abgeschnitten – das Original bleibt unverändert).
- **Bei Konflikt:** Wenn das Ziel-PDF schon existiert oder zwei Bilder denselben PDF-Namen ergeben (z. B. `scan.png` und `scan.jpg`):
  *Nummerieren* (`scan_1.pdf`, Standard), *Überschreiben* oder *Überspringen*.
- **Als Standard speichern** merkt sich die Werte der Leiste als Vorgabe für alle künftigen Bilder. Gespeichert werden außerdem Formatauswahl, Hell/Dunkel und „Zielordner danach öffnen“ – in `settings.json` neben der EXE (oder im Benutzerprofil, falls der Programmordner schreibgeschützt ist). Quell- und Zielordner werden bewusst nicht gespeichert.

## Statusanzeige in der Tabelle

| Anzeige | Bedeutung |
|---|---|
| ✓ | Alles in Ordnung |
| ⚠ Konflikt | Ziel-PDF existiert bereits oder Name wird mehrfach vergeben; wird nach der Konfliktregel aufgelöst |
| ⚠ Animiert | Animiertes GIF: nur das erste Bild wird verwendet |
| ✖ Zu groß | Über 100 Megapixel, wird nicht verarbeitet |
| ✖ Pfad zu lang | Zielpfad länger als 260 Zeichen, wird übersprungen |
| ✖ Nicht lesbar | Datei defekt, gesperrt oder kein gültiges Bild, wird übersprungen |
| ✔ Erstellt / – Übersprungen / ✖ Fehlgeschlagen | Ergebnis des letzten Laufs |

## Technische Hinweise

- JPG-Bilder werden unverändert (1:1) in das PDF eingebettet, alle anderen Formate verlustfrei. Transparenz wird auf Weiß gelegt. 16-Bit- und CMYK-Bilder werden in 8-Bit-RGB bzw. Graustufen umgewandelt.
- Mehrseitige TIFFs ergeben ein PDF mit allen Seiten; bei Ausrichtung „Automatisch“ wird jede Seite einzeln ausgerichtet.
- Liegt der Zielordner innerhalb des Quellordners, wird er bei der Suche übersprungen.
- Nur 64-Bit-Windows 10/11.

## Portable Version selbst bauen (einmalig, nur für den Ersteller)

Voraussetzung: Windows-Rechner mit Python 3.10 oder neuer (python.org, beim Setup „Add python.exe to PATH“ aktivieren).

1. Projektordner entpacken.
2. `build.bat` doppelklicken. Das Skript legt eine virtuelle Umgebung an, installiert die Bibliotheken, führt die Tests aus und erzeugt `dist\ImageToPDF\`.
3. Den Ordner `dist\ImageToPDF` als ZIP weitergeben. Die Empfänger brauchen kein Python.

Zum Entwickeln ohne Build: `python run_imagetopdf.py` (nach `pip install -r requirements.txt`).
