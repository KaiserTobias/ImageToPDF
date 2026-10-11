# ImageToPDF – Webversion

Nachbau der Python-Anwendung als einzelne Datei: **`index.html` im Browser öffnen** (Doppelklick), keine Installation, nichts wird hochgeladen.

Bedienung wie in der Python-Anwendung (siehe [`../ANLEITUNG.md`](../ANLEITUNG.md)):
Quellordner wählen (oder Ordner ins Fenster ziehen) → Formate anhaken → Ziel wählen → „Ordner durchsuchen“ → in der Tabelle Seitenformat, Ausrichtung, Anpassung und Konfliktregel feinabstimmen (Bearbeitungsleiste oder Doppelklick auf eine Zelle) → „Konvertieren“. Jedes Bild ergibt ein eigenes PDF; JPGs werden unverändert eingebettet, alles andere verlustfrei.

## Browser
- **Chrome / Edge (empfohlen):** PDFs werden direkt in den Ordner geschrieben (neben das Bild oder in den Zielordner, Unterordnerstruktur wird nachgebaut). Beim Konvertieren fragt der Browser einmal nach Schreibzugriff.
- **Firefox / Safari:** Ordner kann gelesen, aber nicht beschrieben werden. Das Ergebnis wird als `ImageToPDF.zip` (mit Ordnerstruktur) heruntergeladen.

## Unterschiede zur Python-Anwendung
- Einstellungen („Als Standard speichern“, Hell/Dunkel) liegen im Browser (`localStorage`), nicht in `settings.json`.
- Kein „Zielordner danach öffnen“ und keine Prüfung auf Pfadlänge > 260 Zeichen (der Browser kennt den vollen Pfad nicht).
- Es wird der Ordnername statt des vollen Pfads angezeigt.

## Entwicklung
`index.html` wird aus `src/` (Oberfläche, Logik) und `vendor/` (UTIF.js für TIFF und pako; MIT-Lizenzen, siehe `vendor/LICENSES.txt`) gebaut:

```
node build.js
```
