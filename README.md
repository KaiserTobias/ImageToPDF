# ImageToPDF

Bilder (JPG, PNG, GIF, …) in ein PDF umwandeln – ohne Python und ohne Installation.

| Ordner | Variante | Benutzung |
|---|---|---|
| [`variante1-html`](variante1-html) | Einzelne HTML-Datei | `index.html` im Browser öffnen. Bilder hineinziehen/auswählen/einfügen (Strg+V), per Drag & Drop oder ↑/↓ sortieren, drehen, Seitengröße (A4/Letter/Bildgröße), Ausrichtung, Rand, JPEG-Qualität und Dateiname wählen, „PDF erstellen“. Alles läuft lokal im Browser. |
| [`variante3-exe`](variante3-exe) | Go-Programm (eine Datei, keine Abhängigkeiten) | `./build.sh` baut Programme für Windows, macOS und Linux nach `fertig/` (fertige Programme liegen bereits dort). Aufruf: `imagetopdf -o out.pdf a.jpg b.png` oder Bilder auf die `.exe` ziehen. |

Optionen der Go-Variante: `-o datei.pdf` (Ausgabe), `-fit` (Seitengröße = Bildgröße statt A4).
