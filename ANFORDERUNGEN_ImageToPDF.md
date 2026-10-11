# ImageToPDF – Anforderungsdokument

Stand: 10.10.2026 · Status: umgesetzt (Version 1.0.0, 11.10.2026)

## 1. Ziel

Portable Windows-Desktop-Anwendung, die Bilder aus einem Ordner (inkl. Unterordner) findet, dem Benutzer in einer Tabelle anzeigt und jedes Bild in ein eigenes PDF umwandelt. Der Benutzer bestimmt das Seitenformat global (Standard) und kann es pro Bild anpassen. Originalbilder werden nie verändert.

## 2. Rahmenbedingungen

| Punkt | Festlegung |
|---|---|
| Betriebssystem | Windows 10/11, nur 64-Bit |
| Installation | Keine. Auslieferung als portabler Ordner (ZIP entpacken, `ImageToPDF.exe` starten) |
| Sprache der Oberfläche | Deutsch; alle Texte in einer zentralen Texttabelle, damit Englisch später ohne Umbau möglich ist |
| Programmname | ImageToPDF |
| Design | Modern, Hell/Dunkel umschaltbar |
| Erwartete Datenmenge | Typisch bis ca. 100 Bilder; 1.000 sehr unwahrscheinlich |
| Technik | Python, customtkinter (Oberfläche), ttk.Treeview (Tabelle, im Design angepasst), Pillow (Bilder), PDF-Erzeugung mit verlustfreier Einbettung |
| Build | `build.bat` (PyInstaller), einmalig auf einem Windows-Rechner mit Python auszuführen; kein GitHub |
| Hinweis | SmartScreen meldet beim ersten Start "Unbekannter Herausgeber" (unsigniert, nicht vermeidbar) → gehört in die Anleitung |
| Architektur | Konvertierungslogik strikt von der Oberfläche getrennt (Logik automatisiert testbar, GUI wird vom Auftraggeber unter Windows geprüft) |

## 3. Ablauf

1. Quellordner wählen (Windows-Dialog "Durchsuchen"; zusätzlich Drag & Drop, falls technisch unproblematisch – kein Pflichtfeature, kein Pfad-Tippen nötig).
2. Bildformate auswählen (mehrere gleichzeitig): PNG, TIF/TIFF, JPG/JPEG, BMP, GIF. Kein EPS, kein HEIC, kein WebP.
3. Zielort wählen:
   - Standard (bei jedem Start vorausgewählt): PDF neben dem Bild im selben Ordner.
   - Optional: eigener Zielordner. Die Unterordnerstruktur der Quelle wird dort **immer** nachgebaut (keine Option).
   - Liegt der Zielordner innerhalb des Quellordners, wird er bei der Suche ausgelassen.
4. Suche durchläuft alle Unterordner; Ergebnisse erscheinen fortlaufend in der Tabelle (Vorschaubilder und Prüfungen laufen im Hintergrund).
5. Benutzer macht Feinabstimmung in der Tabelle (siehe 4 und 5).
6. Konvertieren mit Fortschrittsbalken und Abbrechen-Button (Abbruch je Datei).
7. Abschlussmeldung: Anzahl erstellt / übersprungen / Fehler, mit Fehlerliste. Optional "Zielordner danach öffnen".

## 4. Tabelle

Spalten: Häkchen (konvertieren ja/nein) · Vorschaubild · Name · Unterordner · Format · Auflösung (px) · Dateigröße · Seitenformat · Ausrichtung · Anpassung · Zielpfad · Status

Bedienung:
- Mehrfachauswahl von Zeilen; darunter eine **Bearbeitungsleiste**, mit der Seitenformat, Ausrichtung, Anpassung und Konfliktregel für alle markierten Zeilen gesetzt werden (Strg+A + setzen = "für alle setzen").
- Doppelklick auf eine Zelle für die Schnelländerung einer einzelnen Zeile.
- Alle Zeilen starten mit der gespeicherten Standardeinstellung.

Status-Symbole:
- ⚠ gelb: Namenskonflikt (Ziel-PDF existiert bereits oder zwei Bilder im Lauf ergeben denselben PDF-Namen, z. B. `scan.png` + `scan.jpg` → `scan.pdf`). Konfliktregel pro Zeile: **nummerieren** (Standard, `scan_1.pdf`), überschreiben, überspringen.
- ⚠ gelb: animiertes GIF → nur erstes Bild wird verwendet.
- ✖ rot: zu groß (über 100 Megapixel) → wird verweigert.
- ✖ rot: defekt, gesperrt, nicht lesbar oder Pfad länger als 260 Zeichen → wird übersprungen.

## 5. Vorschau

Unter der Tabelle ein Vorschaufeld für die markierte Zeile: zeigt Seite, Bildlage und Rand. Aktualisiert sich live bei Änderung von Format, Ausrichtung oder Anpassung. Bei "Seite füllen" Warnhinweis, dass Bildinhalt im PDF abgeschnitten wird.

## 6. PDF-Regeln

| Punkt | Festlegung |
|---|---|
| PDF-Name | Name des Bildes (`foto.jpg` → `foto.pdf`) |
| Seitenformate | Originalgröße, A2, A3, A4, A5 |
| Originalgröße | DPI aus der Bilddatei verwenden; fehlt die Angabe: 96 DPI. Ausrichtung und Anpassung sind hier ausgegraut, Rand 0 |
| Ausrichtung | Automatisch nach Bildform (Standard), pro Bild änderbar auf Hoch/Quer. EXIF-Drehung wird beachtet |
| Anpassung | "Einpassen" (Seitenverhältnis bleibt, Rand) oder "Seite füllen" (Bild wird komplett eingebettet, Seite schneidet ab = Clipping, verlustfrei). Kein Strecken |
| Rand | Automatisch, ca. 5 % der kürzeren Seitenkante; bei Originalgröße 0. Nicht einstellbar |
| Einbettung | JPG unverändert 1:1. PNG/BMP/GIF/TIF verlustfrei. Transparenz → weißer Hintergrund (verlustfrei). 16-Bit- oder CMYK-TIFF werden umgewandelt (Farbtiefe/Farbraum geht verloren, am Bildschirm nicht sichtbar) |
| Mehrseitige TIFFs | Alle Seiten in ein PDF. Bei "Automatisch" Ausrichtung pro Seite, bei fester Wahl für alle Seiten |
| Animierte GIFs | Nur erstes Bild, mit Warnhinweis in der Tabelle |
| Größengrenze | Über 100 Megapixel: verweigern (Pillow-Limit entsprechend setzen) |
| Originale | Werden in keiner Weise verändert oder gelöscht |

## 7. Einstellungen

Gespeichert in `settings.json` neben der `.exe` (portabel). Ist der Ordner schreibgeschützt: Rückfall ins Benutzerprofil (AppData) mit Hinweis.

Gespeichert werden: Seitenformat, Ausrichtung, Anpassung, Konfliktregel, Formatauswahl, Hell/Dunkel, "Zielordner danach öffnen".

**Nicht** gespeichert werden: Quellordner, Zielordner (ändern sich zu oft; Standard beim Start ist immer "PDF neben dem Bild").

## 8. Bewusst ausgeschlossen

- Gemeinsames PDF aus mehreren Bildern
- EPS, HEIC, WebP
- Einstellbarer Seitenrand, eigenes Seitenmaß, Letter/Legal, A6
- Voreinstellungen pro Bildformat
- Löschen der Originale
- Strecken des Bildes
- GitHub-Build, Code-Signatur
- 32-Bit-Windows

## 9. Lieferumfang

- Python-Projekt (`src/`, getrennt in Logik und GUI)
- `requirements.txt`, `build.bat`, Build-Anleitung
- Automatisierte Tests der Konvertierungslogik (alle Formate, Mehrseiten-TIFF, animiertes GIF, Transparenz, Konflikte, Größengrenze, DPI-Rückfall)
- Kurze Benutzeranleitung (inkl. SmartScreen-Hinweis)
