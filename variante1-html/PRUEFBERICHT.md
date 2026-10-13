# Prüfbericht: Ist die Webversion sicher für einen Anwender?

Stand: 13.10.2026 · Geprüft: `variante1-html/` auf Branch `claude/funny-pasteur-x7et1x`, Commit `650a851` · Maßstab laut Rückfragen: keine Datenverluste, nichts verlässt den Rechner, stabil im Alltag, Schutz vor Angriffen; Start per Doppelklick (file://); Chrome/Edge und Firefox (ZIP reicht); Bilder auf lokaler Platte, NAS, OneDrive/SharePoint, USB; Anwender: du selbst und später Kollegen ohne IT-Kenntnisse.

## 1. Urteil in drei Sätzen

**Im jetzigen Stand nicht für Kollegen freigeben.** Es gibt drei bestätigte Wege, auf denen die Webversion vorhandene PDF-Dateien ohne Hinweis überschreibt (Originalbilder sind nie betroffen), und mehrere TIFF-Varianten, die als „✔ Erstellt“ gemeldet werden, obwohl das PDF schwarz, farbfalsch oder Müll ist. Datenschutz und Injektionsschutz sind dagegen in Ordnung: Es wurde keine einzige Netzwerkanfrage beobachtet, die eingebetteten Bibliotheken sind byteidentisch mit den Originalen, und feindliche Dateinamen führen nicht zu Code-Ausführung.

Die kritischen Punkte haben eine gemeinsame Ursache (die Planung wird vor dem Lauf nicht erneuert und die Oberfläche ist während des Laufs nicht gesperrt) und sind mit überschaubarem Aufwand behebbar (Abschnitt 8).

## 2. Wie geprüft wurde

- 8 unabhängige Prüfperspektiven (Datensicherheit, Datenschutz, Robustheit, Injection, Browser-Umgebung, PDF-Treue gegenüber dem Python-Vorbild, Logikfehler, Anwendersicht), jede mit echten Tests in Chromium (Playwright, headless) gegen ein Sandbox-Dateisystem, sowie Vergleichsläufe mit der Python-Anwendung aus `src/imagetopdf`.
- 65 Rohbefunde → 62 nach Zusammenlegung → jeder Befund von zwei weiteren Prüfern gegengeprüft (ein Skeptiker, der widerlegen sollte, und ein Reproduzierer, der die Folge selbst beobachten musste). Ergebnis: 53 bestätigt, 8 noch in Nachprüfung (Abschnitt 7), 1 unsicher, 0 verworfen. Ein Vollständigkeitskritiker fand drei weitere belegte Befunde und benennt, was nicht prüfbar war (Abschnitt 9).
- Nicht prüfbar in dieser Umgebung: echtes Windows mit Chrome/Edge und echtem Ordnerdialog, echtes Firefox/Safari (nur simuliert), Netzlaufwerke, OneDrive, USB. Diese Punkte stehen in Abschnitt 9 mit konkreter Prüfanleitung.

Alle Nachweise (Skripte, Logs, Screenshots, erzeugte PDFs) liegen unter `scratchpad/audit/` der Sitzung; die wichtigsten Dateinamen sind je Befund genannt.

## 3. Was in Ordnung ist (positiv belegt)

| Aussage | Nachweis |
|---|---|
| Nichts verlässt den Rechner | Vollständiges Request-Protokoll (Playwright + CDP + route-Interception) während Suche und Konvertierung: nur `index.html` und `favicon.ico` vom eigenen Server, sonst ausschließlich `data:`-URLs der Vorschaubilder. Keine Cookies, kein IndexedDB, kein Service Worker, kein Cache. `audit/datenschutz/net-result.json` |
| Keine fremden oder veränderten Bibliotheken | `vendor/UTIF.js` und `vendor/pako_inflate.min.js` byteidentisch mit den npm-Paketen `utif@3.1.0`/`pako@2.1.0`; `index.html` entspricht einem frischen Build aus `src/`. Kein `fetch`, `XMLHttpRequest`, `eval`, `import()`, kein externes `src=`/`href=`. |
| Originalbilder werden nie verändert oder gelöscht | Alle Schreibpfade (`writePdf`, `ZipWriter`) erzeugen ausschließlich `.pdf`-Dateien mit neuem Namen; Bilddateien werden nur gelesen. In keinem der ~130 Testläufe wurde eine Bilddatei verändert. |
| Keine Code-Ausführung über Dateinamen | Dateien/Ordner mit `<img onerror=…>`, `" onmouseover=…`, `&amp;`, 200 Zeichen, Leerzeichen/Punkte: keine Ausführung (`window.__pwned` blieb undefined), Anzeige über `textContent` korrekt, erzeugte Dateinamen und PDFs korrekt. |
| Seitengeometrie identisch zum Vorbild | 3 240 Kombinationen (Format × Ausrichtung × Anpassung × Bildmaß × DPI) numerisch verglichen: 0 Abweichungen (`audit/pdf-treue/layout_cmp.py`). |
| Konfliktplanung identisch zum Vorbild | 21 Dateien mit Duplikaten, vorhandenen PDFs, deaktivierten und defekten Zeilen in drei Zielmodi: nur Abweichung, welche von zwei Dateien, die sich ausschließlich in Groß-/Kleinschreibung unterscheiden (`Scan.JPG`/`scan.jpg`), den Suffix `_1` bekommt (hängt von der Aufzählreihenfolge des Dateisystems ab, in beiden Versionen). |
| EXIF-Drehung 1–8, A4/A5/Original, Mehrseiten-TIFF, Alpha, Palette, 1-Bit, Graustufen, CMYK-JPEG, progressives JPEG | Pixelvergleich der gerenderten PDFs gegen Pillow/Vorbild: Mittelwert ≤ 1 (Rundung), keine Strukturabweichung. |

## 4. Kritisch – vorhandene Dateien werden ohne Hinweis überschrieben

Alle drei Punkte betreffen nur **PDF-Dateien** (eigene oder fremde), nie Bilder. Alle drei sind reproduziert, in jedem Fall meldete der Abschlussdialog „Erstellt: N, Fehler: 0“.

### K1 – „Konvertieren“ plant nicht neu (`app.js:825–858`)
`startConvert()` übernimmt die Zielnamen aus der letzten Suche ungeprüft. Jedes PDF, das **nach** der Suche entstanden ist, wird trotz Regel „Nummerieren“ überschrieben – auch die PDFs des vorherigen Laufs derselben Sitzung. Der Normalfall „Einstellung ändern, nochmal konvertieren“ ersetzt also stillschweigend den ersten Lauf (das Vorbild erzeugt `name_1.pdf`). Ebenso wird ein PDF ersetzt, das zwischenzeitlich jemand anderes dort abgelegt hat. Nachweis: `audit/repro-0/r0_repro.log` (fremdes `b.pdf` mit 50 Byte wurde durch 1 322 Byte ersetzt; Vorbild liefert `b_1.pdf`).
**Behebung:** Zu Beginn von `startConvert()` `nameCache.clear(); await replan();` (wie `app.py:475`), und in `writePdf()` vor dem Anlegen prüfen, ob die Datei existiert.

### K2 – Anderen Quellordner wählen ohne neue Suche (`app.js:741`)
`setSource()` leert weder Tabelle noch Plan. Wählt man nach einem Lauf über Ordner A den Ordner B und klickt direkt „Konvertieren“, werden die PDFs der A-Bilder in B geschrieben (mit A-Unterordnerstruktur) und gleichnamige PDFs in B überschrieben; die Zielpfad-Spalte zeigt dabei weiter „ordnerA/…“. Nachweis: `audit/repro-1/`.
**Behebung:** In `setSource()` Tabelle und Plan zurücksetzen und „Konvertieren“ erst nach einer Suche freigeben, oder je Zeile das Wurzel-Handle speichern.

### K3 – Oberfläche während des Laufs nicht gesperrt (`app.js:768, 653, 656, 684, 811`)
`setBusy()` sperrt nur vier Buttons. Zielmodus-Radios, Zeilen-Checkboxen, Doppelklick auf Zellen, „Anwenden“, „Aktivieren/Deaktivieren“ und die Leertaste lösen während des Laufs `replan()` aus, und die Schreibschleife liest die Ziele live. Bestätigte Folgen eines einzigen Klicks:
- Radio „In Zielordner“/„neben dem Bild“ umschalten → vorhandenes PDF wird trotz „Nummerieren“ überschrieben (zwei Varianten, `audit/repro-2/`, `audit/repro-3/`), oder Zeilen enden als „Übersprungen“/„Fehlgeschlagen: Cannot read properties of null“, PDFs fehlen (6 von 8 Läufen betroffen, `audit/repro-4/`).
- Checkbox einer bereits geschriebenen Zeile abwählen → das Duplikat bekommt denselben Namen und überschreibt das gerade erzeugte PDF (`audit/repro-5/`, `audit/repro-15/`).
- Doppelklick auf „Bei Konflikt“ einer noch nicht verarbeiteten Zeile → Regel wird mitten im Lauf zu „Überschreiben“.
**Behebung:** Plan zu Laufbeginn einfrieren (`const jobs = todo.map(it => ({it, eff: it.eff}))`), in `setBusy()` Tabelle, Bearbeitungsleiste und Radios sperren, in den Handlern `if (state.busy) return;`, und nach jedem erfolgreichen Schreiben den Namen in den `nameCache` eintragen.

## 5. Hoch – falsches PDF mit „✔ Erstellt“, Absturz, Datenverlust im ZIP-Weg

| Nr. | Befund | Stelle | Nachweis |
|---|---|---|---|
| H1 | **TIFF mit zyklischem IFD-Zeiger**: `UTIF.decode` läuft endlos, Seite friert ein, Speicher wächst auf 4 GB, Tab stürzt nach ca. 30 s ab; die ganze Tabelle ist weg, ohne Hinweis auf die Datei. Pillow liest dieselbe Datei problemlos. | `app.js:220`, `vendor/UTIF.js:93` | `audit/repro-6/`, `audit/repro-11/` |
| H2 | **Bildkante > 65 535 px** (bei ≤ 100 MP erlaubt, z. B. Panorama 70 000×1 400): Chrome liefert ein leeres Canvas, das PDF ist komplett schwarz, Status „✔ Erstellt“. Gleiches für **Mehrseiten-TIFF**, bei dem nur Seite 1 gegen die 100-MP-Grenze geprüft wird (Seite 2 mit 289 MP → schwarze Seite). | `app.js:227, 221–227, 283–294` | `audit/repro-7/`, `audit/kritik/tA_tiff_seite2_gross.js` |
| H3 | **TIFF-Varianten, die UTIF nicht kann, ergeben stillschweigend falsche Bilder**: Kompression 32946/LZMA/ZSTD/WebP → schwarz; CIELab → weiß; abgeschnittene Pixeldaten → schwarze Fläche; JPEG-komprimiertes TIFF mit Photometric=RGB (Standard bei Pillow/GIMP) → **Farben vertauscht**; planar, Graustufen+Alpha, 4 Bit → Müllbild. Immer Status „✔ Erstellt“, nur `console.log` in den Entwicklerwerkzeugen. Das Vorbild konvertiert alle korrekt oder meldet einen Fehler. | `app.js:286–288` | `audit/repro-8/`, `-9/`, `-13/`, `-14/` |
| H4 | **Bild zwischen Suche und Konvertieren ersetzt/gedreht** (Windows-Fotos „Drehen“, Kamera-Import): `framesOf` bettet die neuen Bytes ein, nimmt Breite/Höhe/EXIF aber aus der alten Suche → PDF mit Streifen/Müll, „✔ Erstellt“. | `app.js:276–280, 341` | `audit/kritik/tG_*.js` |
| H5 | **Unlesbarer Unterordner bricht die ganze Suche ab**: `System Volume Information`, `$RECYCLE.BIN` auf externen Platten, ACL-geschützte oder OneDrive-Platzhalterordner werfen in `dir.entries()`; alle danach kommenden Ordner fehlen in der Tabelle, Statuszeile sagt trotzdem „N Bilder gefunden“, Dialog englisch und irreführend („write to a file“). | `app.js:452, 790` | `audit/repro-28/` |
| H6 | **ZIP-Weg (Firefox, Drag & Drop, verweigertes Schreibrecht)**: alle PDFs bleiben bis zum Ende im Speicher (8,7 GB RSS bei 60 Bildern à 25 MP, Tab-Absturz auf 8-GB-Rechnern = alles verloren); ab 4 GB Gesamtgröße entsteht wegen fehlendem ZIP64 ein **defektes Archiv** bei Dialog „Erstellt: 44, Fehler: 0“. | `app.js:355–380, 849, 860` | `audit/repro-10/`, `audit/repro-50/` |

## 6. Mittel – irreführende Anzeige, stiller Rückfall, Abweichung mit Folgen

| Nr. | Befund | Stelle |
|---|---|---|
| M1 | Doppelklick auf „Konvertieren“, während Chromes Rechte-Abfrage offen ist, startet **zwei Schreibschleifen** parallel (`busy` wird erst nach dem `await` gesetzt). | `app.js:832–836` |
| M2 | Schreibfehler (Platte voll, USB abgezogen, Virenschutz) hinterlässt eine **0-Byte-„PDF“**, weil die Datei vor `createWritable` angelegt wird. | `app.js:820` |
| M3 | Nach einem Lauf bleibt „✔ Erstellt“ stehen, auch wenn Regel/Format geändert wurden; ein neuer Konflikt wird nicht angezeigt. | `app.js:656–689` |
| M4 | Unter **file://** teilen sich alle lokal geöffneten HTML-Dateien denselben `localStorage`; eine andere lokale HTML-Datei kann den Standard auf „Überschreiben“ setzen, die App übernimmt ihn ohne Hinweis (reproduziert mit `audit/datenschutz/fremd.html`). | `app.js:386` |
| M5 | **Abgeschnittenes JPEG** (fehlender EOI-Marker) wird 1:1 eingebettet: halbes Bild, „✔ Erstellt“ (Vorbild: Fehler). | `app.js:279` |
| M6 | Konvertierung blockiert den Hauptthread 10–12 s je 100-MP-Bild: Oberfläche und „Abbrechen“ reagieren nicht. | `app.js:267` |
| M7 | Drag & Drop von „Downloads“, „Desktop“, „Dokumente“ oder dem Benutzerordner: Chrome lehnt ab (Blockliste), App reagiert **gar nicht** (unbehandelte Ablehnung). | `app.js:887` |
| M8 | Quellordner wird mit `mode:'readwrite'` geöffnet → Chrome fragt schon beim Auswählen „Website darf Dateien bearbeiten?“, auch im Zielordner-Modus; „Nicht zulassen“ bricht stumm ab, Feld bleibt leer. | `app.js:755` |
| M9 | Ordnerdialog durch Firmenrichtlinie oder Website-Einstellung blockiert: englische Fehlermeldung, kein Rückfall auf Dateidialog + ZIP. | `app.js:756` |
| M10 | Auswahl von Einzeldateien statt Ordner (Mobilgeräte, alte Browser): Suche stürzt mit „Cannot read properties of undefined“ ab. | `app.js:760, 468` |
| M11 | Browser ohne `CompressionStream` (Firefox ≤ 112, Safari ≤ 16.3) bzw. ohne `imageOrientation:'from-image'` (Chrome/Edge ≤ 111, Firefox ≤ 110): Vorschau fehlt stumm, alle Nicht-JPEGs „✖ Fehlgeschlagen“ mit JS-Meldung; keine Startprüfung, keine Mindestversionen in der README. | `app.js:260, 299` |
| M12 | Nach **verweigertem Schreibrecht** wird still auf ZIP umgeschaltet, aber Zielpfad-Spalte und Status zeigen weiter „Ordner/foto.pdf ✔ Erstellt“. | `app.js:584, 832` |
| M13 | ZIP-Modus erkennt vorhandene PDFs im Quellordner nicht als Konflikt, obwohl sie in der Dateiliste stehen (beim Entpacken wird überschrieben). | `app.js:500` |
| M14 | Zielmodus „In Zielordner“ ohne gewählten Ordner: „Konvertieren“ lädt stillschweigend ein ZIP herunter statt zu warnen (die Suche warnt in derselben Lage). | `app.js:829` |
| M15 | „Ordner durchsuchen“ ist **nicht abbrechbar** (Vorbild: ja) – bei Netzlaufwerk mit tausenden TIFFs nur Tab schließen. | `app.js:811` |
| M16 | Layout: bei 1366×768 mit 125 % Windows-Zoom oder Fensterhöhe ≤ 700 px überdeckt die Tabelle die Bearbeitungsleiste; ein Klick auf „Anwenden“ trifft eine Zelle. | `style.css:42` |
| M17 | 16-Bit-Graustufen: Web nimmt das obere Byte, Vorbild spreizt auf Min/Max → sichtbar andere Helligkeit. | `app.js:288` |
| M18 | JPEG mit ungültigem EXIF-Orientierungswert (z. B. 9): „✖ Fehlgeschlagen – undefined is not iterable“ (Vorbild konvertiert). | `app.js:334` |
| M19 | Seite über **http:// im Intranet** (unsicherer Kontext): Hinweis „Chrome oder Edge verwenden“ erscheint auch in Chrome, Zielordner-Option verschwindet; README nennt die Voraussetzung file:// bzw. https:// nicht. | `app.js:403, 631, 915` |

## 7. Niedrig – Komfort und Kleinigkeiten

N1 Datei, die nur „.png“ heißt, wird als namenlose, versteckte „.pdf“ geschrieben (Vorbild ignoriert sie). · N2 JPEG-Metadaten (GPS, Seriennummer, Autor) wandern 1:1 ins PDF (Vorbild entfernt sie; relevant beim Weitergeben). · N3 1 500 Bilder: Vorschauphase 133 s, jede Bedienaktion 1–2 s, weil `render()` alle Zeilen samt Data-URLs neu aufbaut. · N4 `inspectFile` liest TIFF und GIF vollständig in den Speicher (1,1 GB Datei → 2,4 GB RSS). · N5 Nicht dekodierbare Bilder stehen nach der Suche als „✓“, Fehler erst beim Konvertieren, Meldung englisch. · N6 Bidi-Steuerzeichen (U+202E) im Dateinamen drehen Name/Zielpfad/Status in der Anzeige um. · N7 Interne Meldung „Offset is outside the bounds of the DataView“ bei abgeschnittenen Dateien. · N8 Unterordner-Spalte ohne Breitenbegrenzung schiebt Status aus dem Sichtbereich. · N9 Firefox zeigt beim Ordnerwählen „N Dateien hochladen?“ – die App erklärt das nirgends (widerspricht „nichts wird hochgeladen“). · N10 CMYK-TIFF: letzter Pixel weiß. · N11 DPI-Randfälle (EXIF ohne Einheit, TIFF ohne Auflösung) weichen vom Vorbild ab → andere Seitengröße bei „Originalgröße“. · N12 Nach Klick auf ein Häkchen geht der Tastaturfokus verloren (Strg+A markiert den Seitentext).

**Noch in Nachprüfung (zweiter Durchlauf, Ergebnis wird ergänzt):** kein `beforeunload`-Schutz (F5/Tab schließen im ZIP-Modus verwirft alles ohne Warnung); Ordnerdialog abgebrochen/Recht verweigert ohne jede Rückmeldung; Abschlussdialog meldet „Fehler: 0“, obwohl rote Zeilen (nicht lesbar, zu groß) gar nicht konvertiert wurden; Vorschautext bei „Originalgröße“ ohne mm-Angabe; Leertaste auf fokussierter Checkbox schaltet andere Zeilen; Drop einer Einzeldatei ohne Rückmeldung; Formatauswahl geht beim Neuladen verloren.

**Unsicher (nicht abschließend geklärt):** Ob Firefox beim ZIP-Download Metadaten (Hash, Dateiname) an den Safe-Browsing-Dienst sendet. Für Chrome/Chromium ist belegt, dass für dieses ZIP **kein** Ping gesendet wird.

## 8. Empfehlung – was vor einer Weitergabe behoben sein muss

**Stufe 1 (Pflicht, Datenverlust; ca. 60–100 Zeilen in `app.js`):** K1, K2, K3, M1, M2, M3, M12, M14 – alles Varianten derselben Ursache: Plan vor dem Lauf erneuern und einfrieren, Oberfläche während des Laufs sperren, Quelle wechseln = Tabelle leeren, Existenz vor dem Schreiben prüfen, Status bei Änderungen zurücksetzen.

**Stufe 2 (Pflicht, falsches PDF ohne Hinweis):** H1–H5 – IFD-Schleifenschutz; Kantenlänge/Fläche je Seite gegen Browsergrenzen prüfen; TIFF-Tags prüfen und nicht unterstützte Varianten als „Nicht lesbar“ ablehnen (Kompression, Photometric, Planar, SamplesPerPixel, Streifen innerhalb der Datei); nach dem Flatten einen Pixel gegenprüfen, damit nie Nullbytes als Bild eingebettet werden; Bildmaße beim Konvertieren neu lesen; Ordnerfehler je Unterordner abfangen und am Ende nennen. Für den JPEG-in-TIFF-Farbfehler entweder den Dekoder korrigieren oder die Variante ablehnen.

**Stufe 3 (vor Weitergabe an Kollegen):** H6 (ZIP-Grenze prüfen und sauber abbrechen, Download je Datei oder in Teilen), M4 („Überschreiben“ nicht als Standard speichern), M5, M7–M11, M15, M16, M18, N9, sowie die Punkte aus der Nachprüfung; dazu README/Anleitung mit Mindest-Browserversionen, Erklärung der Chrome-Dialoge und der Firefox-„Hochladen“-Rückfrage.

**Stufe 4 (optional):** M6/N3/N4 (Web Worker, Streaming), M13, M17, N1, N2, N5–N8, N10–N12.

## 9. Was nicht geprüft werden konnte – bitte selbst prüfen

1. **Echtes Windows 10/11 mit Chrome/Edge, Doppelklick auf `index.html`**: echter Ordnerdialog, NTFS. Chrome lässt beim Auflisten Namen aus, die es für unsicher hält (`CON.png`, `LPT1.jpg`); Desktop/Dokumente/Downloads direkt als Quelle wählen; Ziel-PDF in Acrobat offen halten und mit „Überschreiben“ konvertieren (bleibt `.crswap` liegen?).
2. **OneDrive/SharePoint mit „Dateien bei Bedarf“**: Die App liest jede Datei dreimal (Kopf, Vorschau, Konvertierung; TIFF jeweils vollständig) → jede Platzhalterdatei wird komplett heruntergeladen. Bei 1 000 Fotos mehrere GB; bei Netzabbruch englische Fehlermeldungen. Test: Ordner mit „Speicherplatz freigeben“, Netz trennen, durchsuchen.
3. **Netzlaufwerk/NAS (UNC/SMB)**: Dauer der Suche (500 TIFFs), Netzlast, Verhalten bei Verbindungsabbruch (H5!).
4. **USB-Stick**: während „Konvertieren“ abziehen → 0-Byte-Dateien (M2), Status; schreibgeschützter Stick als Ziel.
5. **Safe Browsing / SmartScreen beim Schreiben**: Chrome/Edge prüfen jede per File-System-Access-API geschriebene Datei (`PerformAfterWriteChecks`), können sie blockieren und markieren sie als „aus dem Internet“ (Mark of the Web → Acrobat „Geschützte Ansicht“). In PowerShell prüfen: `Get-Content x.pdf -Stream Zone.Identifier`.
6. **Echtes Firefox/Safari**: eigene Bilddekoder (ICC-Profile, Gamma bei PNG), „Hochladen?“-Dialog, Speicher im ZIP-Weg, Entpacken von Umlaut-Namen im Explorer/7-Zip.
7. **Verknüpfungen/Junctions im Quellbaum** (`mklink /J loop .`): keine Schleifenerkennung in `scanHandle` → vermutlich Endlosrekursion.
8. **PDF-Anzeige in Acrobat Reader, Windows-Vorschau, Drucker**: geprüft wurde mit poppler und Chromes PDFium; Acrobat ist strenger (EXIF-Drehung über Seitenmatrix, 14 400-pt-Seiten bei „Originalgröße“, Binärmarker in Zeile 2 ist UTF-8-kodiert).
9. **Unbelegte Zusagen in der README**: „alles andere verlustfrei“ stimmt nicht für 16 Bit, CMYK, ICC-Profile und halbtransparente Pixel (Vorbild-Anleitung sagt das ehrlich); „fragt einmal nach Schreibzugriff“ gilt nur bis alle Tabs geschlossen sind.
