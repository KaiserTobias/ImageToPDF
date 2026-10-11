# ImageToPDF

Bilder in PDF umwandeln. Es gibt drei Wege:

| Ordner | Variante | Benutzung |
|---|---|---|
| [`src/`](src), `run_imagetopdf.py`, `build.bat` | **Python-Desktop-Anwendung** (Windows) | Siehe [`ANLEITUNG.md`](ANLEITUNG.md) und [`ANFORDERUNGEN_ImageToPDF.md`](ANFORDERUNGEN_ImageToPDF.md). |
| [`variante1-html`](variante1-html) | **Webseite als einzelne HTML-Datei** (Nachbau der Python-Anwendung) | `index.html` im Browser öffnen. Ordner wählen, Bilder prüfen, konvertieren; jedes Bild ergibt ein eigenes PDF. Chrome/Edge schreiben direkt in Ordner, andere Browser liefern ein ZIP. Alles läuft lokal. Siehe [README](variante1-html/README.md). |
| [`variante3-exe`](variante3-exe) | **Go-Kommandozeilenprogramm** (eine Datei, keine Abhängigkeiten) | Fertige Programme in `fertig/`. Aufruf: `imagetopdf -o out.pdf a.jpg b.png` oder Bilder auf die `.exe` ziehen. Baut mit `./build.sh`. |

Optionen der Go-Variante: `-o datei.pdf` (Ausgabe), `-fit` (Seitengröße = Bildgröße statt A4). Die Go-Variante erzeugt ein gemeinsames PDF aus allen Bildern.
