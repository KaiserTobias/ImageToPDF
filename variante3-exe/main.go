// ImageToPDF: wandelt Bilder (JPG, PNG, GIF) in ein PDF um. Nur Go-Standardbibliothek.
package main

import (
	"bufio"
	"bytes"
	"compress/zlib"
	"flag"
	"fmt"
	"image"
	"image/color"
	"image/draw"
	_ "image/gif"
	_ "image/jpeg"
	_ "image/png"
	"os"
	"path/filepath"
	"strings"
	"time"
)

const version = "v3"

const (
	a4W    = 595.28 // Punkte
	a4H    = 841.89
	margin = 42.52 // 15 mm
)

type pdfImage struct {
	w, h   int
	gray   bool
	filter string // "DCTDecode" oder "FlateDecode"
	data   []byte
}

func load(path string) (*pdfImage, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	cfg, format, err := image.DecodeConfig(bytes.NewReader(raw))
	if err != nil {
		return nil, fmt.Errorf("%s: kein unterstütztes Bild (%v)", path, err)
	}
	// JPEG unverändert einbetten (verlustfrei, klein), sofern Gray oder YCbCr.
	if format == "jpeg" && (cfg.ColorModel == color.GrayModel || cfg.ColorModel == color.YCbCrModel) {
		return &pdfImage{w: cfg.Width, h: cfg.Height, gray: cfg.ColorModel == color.GrayModel, filter: "DCTDecode", data: raw}, nil
	}
	img, _, err := image.Decode(bytes.NewReader(raw))
	if err != nil {
		return nil, fmt.Errorf("%s: %v", path, err)
	}
	b := img.Bounds()
	// Auf weißen Hintergrund setzen (Transparenz) und als RGB speichern.
	rgba := image.NewRGBA(b)
	draw.Draw(rgba, b, image.NewUniform(color.White), image.Point{}, draw.Src)
	draw.Draw(rgba, b, img, b.Min, draw.Over)
	rgb := make([]byte, 0, b.Dx()*b.Dy()*3)
	for y := b.Min.Y; y < b.Max.Y; y++ {
		for x := b.Min.X; x < b.Max.X; x++ {
			i := rgba.PixOffset(x, y)
			rgb = append(rgb, rgba.Pix[i], rgba.Pix[i+1], rgba.Pix[i+2])
		}
	}
	var z bytes.Buffer
	zw := zlib.NewWriter(&z)
	zw.Write(rgb)
	zw.Close()
	return &pdfImage{w: b.Dx(), h: b.Dy(), filter: "FlateDecode", data: z.Bytes()}, nil
}

func writePDF(out string, imgs []*pdfImage, fit bool) error {
	var buf bytes.Buffer
	var offsets []int
	obj := func(body string) {
		offsets = append(offsets, buf.Len())
		fmt.Fprintf(&buf, "%d 0 obj\n%s\nendobj\n", len(offsets), body)
	}
	buf.WriteString("%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")

	n := len(imgs)
	// Objekte: 1 Catalog, 2 Pages, danach je Bild: Page, Content, Image
	kids := ""
	for i := 0; i < n; i++ {
		kids += fmt.Sprintf("%d 0 R ", 3+i*3)
	}
	obj("<< /Type /Catalog /Pages 2 0 R >>")
	obj(fmt.Sprintf("<< /Type /Pages /Kids [%s] /Count %d >>", kids, n))

	for i, im := range imgs {
		pw, ph := a4W, a4H
		var dw, dh, x, y float64
		if fit { // Seite = Bildgröße (96 dpi → Punkte)
			dw, dh = float64(im.w)*0.75, float64(im.h)*0.75
			pw, ph = dw, dh
		} else {
			aw, ah := a4W-2*margin, a4H-2*margin
			s := aw / float64(im.w)
			if t := ah / float64(im.h); t < s {
				s = t
			}
			dw, dh = float64(im.w)*s, float64(im.h)*s
			x, y = (a4W-dw)/2, (a4H-dh)/2
		}
		pageID := 3 + i*3
		obj(fmt.Sprintf("<< /Type /Page /Parent 2 0 R /MediaBox [0 0 %.2f %.2f] /Contents %d 0 R /Resources << /XObject << /Im0 %d 0 R >> >> >>", pw, ph, pageID+1, pageID+2))
		content := fmt.Sprintf("q %.2f 0 0 %.2f %.2f %.2f cm /Im0 Do Q", dw, dh, x, y)
		obj(fmt.Sprintf("<< /Length %d >>\nstream\n%s\nendstream", len(content), content))
		cs := "/DeviceRGB"
		if im.gray {
			cs = "/DeviceGray"
		}
		hdr := fmt.Sprintf("<< /Type /XObject /Subtype /Image /Width %d /Height %d /ColorSpace %s /BitsPerComponent 8 /Filter /%s /Length %d >>\nstream\n", im.w, im.h, cs, im.filter, len(im.data))
		obj(hdr + string(im.data) + "\nendstream")
	}

	xref := buf.Len()
	fmt.Fprintf(&buf, "xref\n0 %d\n0000000000 65535 f \n", len(offsets)+1)
	for _, o := range offsets {
		fmt.Fprintf(&buf, "%010d 00000 n \n", o)
	}
	fmt.Fprintf(&buf, "trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n", len(offsets)+1, xref)
	return os.WriteFile(out, buf.Bytes(), 0o644)
}

// pause hält das Fenster offen (wichtig bei Doppelklick/Drag & Drop unter Windows).
func pause() {
	fmt.Print("\nEnter drücken zum Beenden …")
	if _, err := bufio.NewReader(os.Stdin).ReadString('\n'); err != nil {
		// Eingabe nicht verfügbar: Fenster trotzdem lange genug offen halten.
		time.Sleep(60 * time.Second)
	}
}

// splitPaths zerlegt eine Eingabezeile in Pfade; Pfade mit Leerzeichen stehen in "…".
func splitPaths(line string) []string {
	var out []string
	var cur strings.Builder
	quoted := false
	flush := func() {
		if cur.Len() > 0 {
			out = append(out, cur.String())
			cur.Reset()
		}
	}
	for _, r := range line {
		switch {
		case r == '"':
			quoted = !quoted
			if !quoted {
				flush()
			}
		case (r == ' ' || r == '\t' || r == '\r' || r == '\n') && !quoted:
			flush()
		default:
			cur.WriteRune(r)
		}
	}
	flush()
	return out
}

func main() {
	defer func() {
		if r := recover(); r != nil {
			fmt.Fprintln(os.Stderr, "Unerwarteter Fehler:", r)
			pause()
			os.Exit(1)
		}
	}()
	interactive := false
	outFlag := flag.String("o", "", "Ausgabedatei (Standard: <erstes Bild>.pdf)")
	fit := flag.Bool("fit", false, "Seitengröße an Bild anpassen statt A4")
	flag.Usage = func() {
		fmt.Fprintln(os.Stderr, "Aufruf: imagetopdf [-o ausgabe.pdf] [-fit] bild1.jpg bild2.png ...")
		fmt.Fprintln(os.Stderr, "Tipp (Windows): Bilder per Drag & Drop auf die .exe ziehen.")
		flag.PrintDefaults()
	}
	flag.Parse()
	files := flag.Args()
	if len(files) == 0 { // Doppelklick: nach Bildern fragen
		interactive = true
		fmt.Println("ImageToPDF " + version + " – Bilder in ein PDF umwandeln")
		fmt.Println("Ziehe die Bilddateien in dieses Fenster und drücke Enter:")
		line, _ := bufio.NewReader(os.Stdin).ReadString('\n')
		files = splitPaths(line)
		if len(files) == 0 {
			fmt.Println("Keine Bilder angegeben.")
			pause()
			os.Exit(2)
		}
	}
	fail := func(err error) {
		fmt.Fprintln(os.Stderr, "Fehler:", err)
		if interactive || *outFlag == "" {
			pause()
		}
		os.Exit(1)
	}
	var imgs []*pdfImage
	for _, p := range files {
		im, err := load(p)
		if err != nil {
			fail(err)
		}
		imgs = append(imgs, im)
	}
	out := *outFlag
	if out == "" {
		first := files[0]
		out = first[:len(first)-len(filepath.Ext(first))] + ".pdf"
	}
	if err := writePDF(out, imgs, *fit); err != nil {
		fail(err)
	}
	fmt.Printf("%d Bild(er) → %s\n", len(imgs), out)
	if interactive || *outFlag == "" {
		pause()
	}
}
