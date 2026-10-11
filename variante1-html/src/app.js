'use strict';
/* ImageToPDF – Webversion. Nachbau der Python-Anwendung (src/imagetopdf): gleiche Regeln für
   Seitengeometrie, Namenskonflikte, Einbettung (JPEG 1:1, sonst verlustfrei als Flate).
   Läuft komplett lokal im Browser. */

// ===================================================================== Konstanten
const APP_NAME = 'ImageToPDF';
const VERSION = '2.0.0';
const MAX_PIXELS = 100_000_000;
const FALLBACK_DPI = 96;
const MARGIN_FRACTION = 0.05;
const MM_TO_PT = 72 / 25.4;
const PDF_MAX_PT = 14400;
const THUMB = 96;

const PAGE_SIZES_MM = { A2: [420, 594], A3: [297, 420], A4: [210, 297], A5: [148, 210] };
const IMAGE_FORMATS = { png: ['.png'], jpg: ['.jpg', '.jpeg'], tif: ['.tif', '.tiff'], bmp: ['.bmp'], gif: ['.gif'] };

const LABELS = {
  page: { original: 'Originalgröße', A2: 'A2', A3: 'A3', A4: 'A4', A5: 'A5' },
  orient: { auto: 'Automatisch', portrait: 'Hochformat', landscape: 'Querformat' },
  fit: { fit: 'Einpassen', fill: 'Seite füllen' },
  conflict: { number: 'Nummerieren', overwrite: 'Überschreiben', skip: 'Überspringen' },
  status: {
    ok: '✓', conflict: '⚠ Konflikt', animated: '⚠ Animiert', too_large: '✖ Zu groß', error: '✖ Nicht lesbar',
    done: '✔ Erstellt', skipped: '– Übersprungen', failed: '✖ Fehlgeschlagen',
  },
};
const NOTES = {
  animated: 'Animiertes GIF: nur das erste Bild wird verwendet.',
  too_large: 'Bild größer als 100 Megapixel – wird nicht verarbeitet.',
  conflict: 'Ziel-PDF existiert bereits oder der Name wird mehrfach vergeben.',
};
const RED = new Set(['too_large', 'error', 'failed']);
const YELLOW = new Set(['conflict', 'animated']);
const CYCLE = { page: Object.keys(LABELS.page), orient: Object.keys(LABELS.orient), fit: Object.keys(LABELS.fit), conflict: Object.keys(LABELS.conflict) };
const CYCLE_FIELD = { page: 'pageFormat', orient: 'orientation', fit: 'fit', conflict: 'conflictRule' };

const $ = s => document.querySelector(s);
const esc = s => String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const sleep = ms => new Promise(r => setTimeout(r, ms));
const tick = () => new Promise(r => setTimeout(r, 0));
const stemOf = n => n.replace(/\.[^.]*$/, '');
const extOf = n => { const m = /\.[^.]*$/.exec(n); return m ? m[0].toLowerCase() : ''; };
const lowerCmp = (a, b) => { const x = a.toLowerCase(), y = b.toLowerCase(); return x < y ? -1 : x > y ? 1 : 0; };

function humanSize(n) {
  for (const u of ['B', 'KB', 'MB', 'GB']) {
    if (n < 1024 || u === 'GB') return u === 'B' ? `${n.toFixed(0)} B` : `${n.toFixed(1)} ${u}`;
    n /= 1024;
  }
}

// ===================================================================== Seitengeometrie (wie layout.py)
function pageSizePt(fmt, orient, w, h, dpi) {
  if (fmt === 'original') {
    const d = dpi || FALLBACK_DPI;
    let pw = w * 72 / d, ph = h * 72 / d;
    const big = Math.max(pw, ph);
    if (big > PDF_MAX_PT) { const f = PDF_MAX_PT / big; pw *= f; ph *= f; }
    return [pw, ph];
  }
  const [mw, mh] = PAGE_SIZES_MM[fmt];
  let pw = mw * MM_TO_PT, ph = mh * MM_TO_PT;
  const landscape = orient === 'auto' ? w > h : orient === 'landscape';
  if (landscape) [pw, ph] = [ph, pw];
  return [pw, ph];
}

function computeLayout(fmt, orient, fit, w, h, dpi) {
  const [pw, ph] = pageSizePt(fmt, orient, w, h, dpi);
  if (fmt === 'original') return { pw, ph, x: 0, y: 0, dw: pw, dh: ph, margin: 0, cropped: false };
  let margin, scale;
  if (fit === 'fill') { margin = 0; scale = Math.max(pw / w, ph / h); }
  else {
    margin = MARGIN_FRACTION * Math.min(pw, ph);
    scale = Math.min((pw - 2 * margin) / w, (ph - 2 * margin) / h);
  }
  const dw = w * scale, dh = h * scale;
  return { pw, ph, x: (pw - dw) / 2, y: (ph - dh) / 2, dw, dh, margin, cropped: dw > pw + 0.01 || dh > ph + 0.01 };
}

// ===================================================================== Bildkopf lesen (wie inspector.py)
async function getFile(it) { return it.file || await it.handle.getFile(); }

function sniff(dv) {
  if (dv.byteLength < 4) return '';
  const a = dv.getUint32(0);
  if ((a >>> 16) === 0xFFD8) return 'jpeg';
  if (a === 0x89504E47) return 'png';
  if (a === 0x47494638) return 'gif';
  if ((a >>> 16) === 0x424D) return 'bmp';
  if (a === 0x49492A00 || a === 0x4D4D002A) return 'tiff';
  return '';
}

// TIFF-IFD (für EXIF in JPEG): liefert Tags Orientierung, Auflösung
function readExifTiff(dv, base) {
  const le = dv.getUint16(base) === 0x4949;
  const u16 = o => dv.getUint16(base + o, le), u32 = o => dv.getUint32(base + o, le);
  if (u16(2) !== 42) return {};
  const off = u32(4), n = u16(off), out = {};
  for (let i = 0; i < n; i++) {
    const e = off + 2 + i * 12, tag = u16(e), type = u16(e + 2);
    if (tag === 0x0112 && type === 3) out.orientation = u16(e + 8);
    else if (tag === 0x0128 && type === 3) out.unit = u16(e + 8);
    else if (tag === 0x011A && type === 5) { const o = u32(e + 8); out.xres = u32(o) / (u32(o + 4) || 1); }
  }
  return out;
}

function parseJpeg(dv) {
  let p = 2, jfif = null, exif = {}, adobe = false;
  while (p + 4 <= dv.byteLength) {
    if (dv.getUint8(p) !== 0xFF) { p++; continue; }
    const m = dv.getUint8(p + 1);
    if (m === 0xFF) { p++; continue; }
    if (m === 0xD8 || m === 0x01 || (m >= 0xD0 && m <= 0xD7)) { p += 2; continue; }
    const len = dv.getUint16(p + 2);
    if (m === 0xE0 && len >= 16 && dv.getUint32(p + 4) === 0x4A464946) { // JFIF
      const units = dv.getUint8(p + 11), xd = dv.getUint16(p + 12);
      if (xd > 0) jfif = units === 1 ? xd : units === 2 ? xd * 2.54 : null;
    } else if (m === 0xE1 && len >= 14 && dv.getUint32(p + 4) === 0x45786966) { // Exif
      try { exif = readExifTiff(dv, p + 10); } catch { /* defektes EXIF ignorieren */ }
    } else if (m === 0xEE && len >= 14 && dv.getUint32(p + 4) === 0x41646F62) adobe = true;
    if (m >= 0xC0 && m <= 0xCF && m !== 0xC4 && m !== 0xC8 && m !== 0xCC) {
      const precision = dv.getUint8(p + 4), h = dv.getUint16(p + 5), w = dv.getUint16(p + 7), comps = dv.getUint8(p + 9);
      let dpi = jfif;
      if (!dpi && exif.xres > 0) dpi = exif.unit === 3 ? exif.xres * 2.54 : exif.unit === 1 ? null : exif.xres;
      return { w, h, comps, precision, sof: m, dpi, orientation: exif.orientation || 1, adobe };
    }
    p += 2 + len;
  }
  throw new Error('Kein gültiges JPEG');
}

function parsePng(dv) {
  const w = dv.getUint32(16), h = dv.getUint32(20), bitDepth = dv.getUint8(24), colorType = dv.getUint8(25);
  let dpi = null, p = 8;
  while (p + 8 <= dv.byteLength) {
    const len = dv.getUint32(p), type = dv.getUint32(p + 4);
    if (type === 0x70485973 && len >= 9) { // pHYs
      const ppu = dv.getUint32(p + 8), unit = dv.getUint8(p + 16);
      if (unit === 1 && ppu > 0) dpi = ppu * 0.0254;
    }
    if (type === 0x49444154) break; // IDAT
    p += 12 + len;
  }
  return { w, h, bitDepth, colorType, dpi };
}

function parseGif(dv) {
  const w = dv.getUint16(6, true), h = dv.getUint16(8, true), flags = dv.getUint8(10);
  let p = 13;
  if (flags & 0x80) p += 3 * (1 << ((flags & 7) + 1));
  let frames = 0;
  const skipSub = () => { while (p < dv.byteLength) { const n = dv.getUint8(p++); if (!n) break; p += n; } };
  while (p < dv.byteLength) {
    const b = dv.getUint8(p++);
    if (b === 0x3B) break;
    if (b === 0x21) { p++; skipSub(); }
    else if (b === 0x2C) {
      frames++;
      const f = dv.getUint8(p + 8); p += 9;
      if (f & 0x80) p += 3 * (1 << ((f & 7) + 1));
      p++; skipSub();
      if (frames > 1) break;
    } else break;
  }
  return { w, h, frames };
}

function parseBmp(dv) {
  const size = dv.getUint32(14, true);
  let w, h, dpi = null;
  if (size === 12) { w = dv.getUint16(18, true); h = dv.getUint16(20, true); }
  else {
    w = dv.getInt32(18, true); h = Math.abs(dv.getInt32(22, true));
    const ppm = dv.getInt32(38, true);
    if (ppm > 0) dpi = ppm * 0.0254;
  }
  return { w: Math.abs(w), h, dpi };
}

function tiffDpi(ifd) {
  const x = ifd.t282 && ifd.t282[0];
  const unit = ifd.t296 ? ifd.t296[0] : 2;
  if (!x || x <= 0 || unit === 1) return null;
  return unit === 3 ? x * 2.54 : x;
}

const round2 = d => (d && d >= 1 ? Math.round(d * 100) / 100 : null);

// Liest nur den Header. Wirft Error('too_large') oder Error(<Meldung>).
async function inspectFile(file) {
  const headBuf = await file.slice(0, 1 << 20).arrayBuffer();
  let dv = new DataView(headBuf);
  const kind = sniff(dv);
  let info;
  if (kind === 'jpeg') {
    let j;
    try { j = parseJpeg(dv); } catch (e) {
      if (file.size > headBuf.byteLength) j = parseJpeg(new DataView(await file.arrayBuffer())); else throw e;
    }
    const swap = j.orientation >= 5 && j.orientation <= 8;
    info = { format: 'JPEG', kind, width: swap ? j.h : j.w, height: swap ? j.w : j.h, dpi: round2(j.dpi), frames: 1, animated: false,
             exif: j.orientation, comps: j.comps, rawOk: [0xC0, 0xC1, 0xC2].includes(j.sof) && j.precision === 8 && (j.comps === 1 || j.comps === 3), gray: j.comps === 1 };
  } else if (kind === 'png') {
    const p = parsePng(dv);
    info = { format: 'PNG', kind, width: p.w, height: p.h, dpi: round2(p.dpi), frames: 1, animated: false, exif: 1, gray: p.colorType === 0 || p.colorType === 4 };
  } else if (kind === 'gif') {
    dv = new DataView(await file.arrayBuffer());
    const g = parseGif(dv);
    info = { format: 'GIF', kind, width: g.w, height: g.h, dpi: null, frames: 1, animated: g.frames > 1, exif: 1, gray: false };
  } else if (kind === 'bmp') {
    const b = parseBmp(dv);
    info = { format: 'BMP', kind, width: b.w, height: b.h, dpi: round2(b.dpi), frames: 1, animated: false, exif: 1, gray: false };
  } else if (kind === 'tiff') {
    const buf = await file.arrayBuffer();
    const ifds = UTIF.decode(buf);
    if (!ifds.length || !ifds[0].t256) throw new Error('Kein gültiges TIFF');
    const f = ifds[0], o = f.t274 ? f.t274[0] : 1, swap = o >= 5 && o <= 8;
    const w = f.t256[0], h = f.t257[0];
    info = { format: 'TIFF', kind, width: swap ? h : w, height: swap ? w : h, dpi: round2(tiffDpi(f)), frames: ifds.length, animated: false, exif: o, gray: false };
  } else throw new Error('Kein unterstütztes Bildformat');
  if (!(info.width > 0 && info.height > 0)) throw new Error('Ungültige Bildmaße');
  if (info.width * info.height > MAX_PIXELS) throw new Error('too_large');
  return info;
}

// ===================================================================== Bild → PDF-Seiten (wie converter.py)
// EXIF-Orientierung als Transformation Quellbild → Anzeige:  X = p·u + q·v + r,  Y = s·u + t·v + w
// (u, v: Einheitsquadrat des Bildes, v nach oben; X, Y: Anzeige, Y nach oben)
const ORIENT_UNIT = {
  1: [1, 0, 0, 0, 1, 0], 2: [-1, 0, 1, 0, 1, 0], 3: [-1, 0, 1, 0, -1, 1], 4: [1, 0, 0, 0, -1, 1],
  5: [0, -1, 1, -1, 0, 1], 6: [0, 1, 0, -1, 0, 1], 7: [0, 1, 0, 1, 0, 0], 8: [0, -1, 1, 1, 0, 0],
};
// Canvas-Transformation (a,b,c,d,e,f) Quellpixel → Zielpixel für Breite w, Höhe h der Quelle
function canvasOrient(o, w, h) {
  return { 1: [1, 0, 0, 1, 0, 0], 2: [-1, 0, 0, 1, w, 0], 3: [-1, 0, 0, -1, w, h], 4: [1, 0, 0, -1, 0, h],
           5: [0, 1, 1, 0, 0, 0], 6: [0, 1, -1, 0, h, 0], 7: [0, -1, -1, 0, h, w], 8: [0, -1, 1, 0, 0, w] }[o] || [1, 0, 0, 1, 0, 0];
}

function newCanvas(w, h) {
  const c = document.createElement('canvas'); c.width = w; c.height = h; return c;
}

// Quelle (Bitmap oder Canvas) mit Orientierung auf weißen Hintergrund zeichnen
function flattenToCanvas(src, sw, sh, orient) {
  const swap = orient >= 5 && orient <= 8;
  const c = newCanvas(swap ? sh : sw, swap ? sw : sh);
  const g = c.getContext('2d', { willReadFrequently: true });
  g.fillStyle = '#fff'; g.fillRect(0, 0, c.width, c.height);
  g.setTransform(...canvasOrient(orient, sw, sh));
  g.drawImage(src, 0, 0);
  return c;
}

async function deflate(bytes) {
  const stream = new Blob([bytes]).stream().pipeThrough(new CompressionStream('deflate'));
  return new Uint8Array(await new Response(stream).arrayBuffer());
}

// Pixel aus Canvas → Flate-Daten (RGB oder Graustufen), verlustfrei
async function canvasToFlate(c, gray) {
  const { width: w, height: h } = c;
  const data = c.getContext('2d').getImageData(0, 0, w, h).data;
  let out;
  if (gray) { out = new Uint8Array(w * h); for (let i = 0, j = 0; j < out.length; i += 4, j++) out[j] = data[i]; }
  else { out = new Uint8Array(w * h * 3); for (let i = 0, j = 0; i < data.length; i += 4, j += 3) { out[j] = data[i]; out[j + 1] = data[i + 1]; out[j + 2] = data[i + 2]; } }
  return { kind: 'flate', w, h, gray, bytes: await deflate(out) };
}

// Alle Seiten eines Elements als einbettbare Bilder: {kind:'dct'|'flate', w, h, ...}
async function framesOf(it, cancelled) {
  const file = await getFile(it), info = it.info;
  // JPEG (RGB/Graustufen) unverändert einbetten; EXIF-Drehung wird über die Seitenmatrix erledigt
  if (info.kind === 'jpeg' && info.rawOk) {
    const bytes = new Uint8Array(await file.arrayBuffer());
    return [{ kind: 'dct', w: info.width, h: info.height, comps: info.comps, orient: info.exif, bytes }];
  }
  if (info.kind === 'tiff') {
    const buf = await file.arrayBuffer(), ifds = UTIF.decode(buf), out = [];
    for (const ifd of ifds) {
      if (cancelled()) throw new CancelledError();
      UTIF.decodeImage(buf, ifd);
      const w = ifd.width, h = ifd.height;
      const rgba = new Uint8ClampedArray(UTIF.toRGBA8(ifd));
      const src = newCanvas(w, h);
      src.getContext('2d').putImageData(new ImageData(rgba, w, h), 0, 0);
      const o = ifd.t274 ? ifd.t274[0] : 1;
      const pmi = ifd.t262 ? ifd.t262[0] : 2, spp = ifd.t277 ? ifd.t277[0] : 1;
      const gray = (pmi === 0 || pmi === 1) && spp === 1;
      out.push(await canvasToFlate(flattenToCanvas(src, w, h, o), gray));
    }
    return out;
  }
  // PNG, BMP, GIF (erstes Einzelbild), nicht rohbettbares JPEG (z. B. CMYK): vom Browser dekodieren
  const bmp = await createImageBitmap(file, { imageOrientation: 'from-image', colorSpaceConversion: 'none' });
  try {
    const c = flattenToCanvas(bmp, bmp.width, bmp.height, 1);
    return [await canvasToFlate(c, info.gray && info.kind !== 'jpeg')];
  } finally { bmp.close(); }
}

class CancelledError extends Error {}

// ===================================================================== PDF schreiben
function pdfHexString(s) {
  let h = 'FEFF';
  for (let i = 0; i < s.length; i++) h += s.charCodeAt(i).toString(16).padStart(4, '0');
  return `<${h}>`;
}

function buildPdf(frames, it) {
  const enc = new TextEncoder(), parts = [], offsets = []; let len = 0;
  const push = x => { const b = typeof x === 'string' ? enc.encode(x) : x; parts.push(b); len += b.length; };
  const obj = (head, stream) => {
    offsets.push(len); push(`${offsets.length} 0 obj\n${head}\n`);
    if (stream) { push('stream\n'); push(stream); push('\nendstream\n'); }
    push('endobj\n');
  };
  const f2 = n => n.toFixed(2);
  push('%PDF-1.4\n%\xE2\xE3\xCF\xD3\n');
  obj('<< /Type /Catalog /Pages 2 0 R >>');
  obj(`<< /Type /Pages /Kids [${frames.map((_, i) => `${4 + i * 3} 0 R`).join(' ')}] /Count ${frames.length} >>`);
  obj(`<< /Title ${pdfHexString(stemOf(it.name))} /Creator (${APP_NAME}) /Producer (${APP_NAME} ${VERSION}) >>`);
  frames.forEach((fr, i) => {
    const lay = computeLayout(it.pageFormat, it.orientation, it.fit, fr.w, fr.h, it.info.dpi);
    const id = 4 + i * 3;
    obj(`<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ${f2(lay.pw)} ${f2(lay.ph)}] /Contents ${id + 1} 0 R /Resources << /XObject << /Im0 ${id + 2} 0 R >> >> >>`);
    let a = lay.dw, b = 0, c = 0, d = lay.dh, e = lay.x, f = lay.y;
    if (fr.kind === 'dct' && fr.orient > 1) {
      const [p, q, r, s, t, w] = ORIENT_UNIT[fr.orient];
      a = lay.dw * p; c = lay.dw * q; e = lay.x + lay.dw * r;
      b = lay.dh * s; d = lay.dh * t; f = lay.y + lay.dh * w;
    }
    const content = `q 0 0 ${f2(lay.pw)} ${f2(lay.ph)} re W n ${f2(a)} ${f2(b)} ${f2(c)} ${f2(d)} ${f2(e)} ${f2(f)} cm /Im0 Do Q`;
    obj(`<< /Length ${content.length} >>`, enc.encode(content));
    const gray = fr.kind === 'dct' ? fr.comps === 1 : fr.gray;
    const sw = fr.kind === 'dct' ? (fr.orient >= 5 ? fr.h : fr.w) : fr.w, sh = fr.kind === 'dct' ? (fr.orient >= 5 ? fr.w : fr.h) : fr.h;
    obj(`<< /Type /XObject /Subtype /Image /Width ${sw} /Height ${sh} /ColorSpace ${gray ? '/DeviceGray' : '/DeviceRGB'} /BitsPerComponent 8 /Filter /${fr.kind === 'dct' ? 'DCTDecode' : 'FlateDecode'} /Length ${fr.bytes.length} >>`, fr.bytes);
  });
  const xref = len;
  push(`xref\n0 ${offsets.length + 1}\n0000000000 65535 f \n`);
  offsets.forEach(o => push(String(o).padStart(10, '0') + ' 00000 n \n'));
  push(`trailer\n<< /Size ${offsets.length + 1} /Root 1 0 R /Info 3 0 R >>\nstartxref\n${xref}\n%%EOF\n`);
  return new Blob(parts, { type: 'application/pdf' });
}

// ===================================================================== ZIP (ohne Kompression), für Browser ohne Ordner-Schreibzugriff
const CRC_TABLE = (() => { const t = new Uint32Array(256); for (let n = 0; n < 256; n++) { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xEDB88320 ^ (c >>> 1) : c >>> 1; t[n] = c >>> 0; } return t; })();
function crc32(bytes) { let c = 0xFFFFFFFF; for (let i = 0; i < bytes.length; i++) c = CRC_TABLE[(c ^ bytes[i]) & 0xFF] ^ (c >>> 8); return (c ^ 0xFFFFFFFF) >>> 0; }

class ZipWriter {
  constructor() { this.parts = []; this.central = []; this.offset = 0; }
  add(path, bytes) {
    const name = new TextEncoder().encode(path), crc = crc32(bytes), now = new Date();
    const time = (now.getHours() << 11) | (now.getMinutes() << 5) | (now.getSeconds() >> 1);
    const date = ((now.getFullYear() - 1980) << 9) | ((now.getMonth() + 1) << 5) | now.getDate();
    const lh = new DataView(new ArrayBuffer(30));
    lh.setUint32(0, 0x04034B50, true); lh.setUint16(4, 20, true); lh.setUint16(6, 0x0800, true); lh.setUint16(8, 0, true);
    lh.setUint16(10, time, true); lh.setUint16(12, date, true); lh.setUint32(14, crc, true);
    lh.setUint32(18, bytes.length, true); lh.setUint32(22, bytes.length, true); lh.setUint16(26, name.length, true); lh.setUint16(28, 0, true);
    const ch = new DataView(new ArrayBuffer(46));
    ch.setUint32(0, 0x02014B50, true); ch.setUint16(4, 20, true); ch.setUint16(6, 20, true); ch.setUint16(8, 0x0800, true); ch.setUint16(10, 0, true);
    ch.setUint16(12, time, true); ch.setUint16(14, date, true); ch.setUint32(16, crc, true);
    ch.setUint32(20, bytes.length, true); ch.setUint32(24, bytes.length, true); ch.setUint16(28, name.length, true); ch.setUint32(42, this.offset, true);
    this.parts.push(lh, name, bytes); this.central.push(ch, name);
    this.offset += 30 + name.length + bytes.length;
    this.count = (this.count || 0) + 1;
  }
  finish() {
    const csize = this.central.reduce((n, p) => n + (p.byteLength ?? p.length), 0);
    const end = new DataView(new ArrayBuffer(22));
    end.setUint32(0, 0x06054B50, true); end.setUint16(8, this.count || 0, true); end.setUint16(10, this.count || 0, true);
    end.setUint32(12, csize, true); end.setUint32(16, this.offset, true);
    return new Blob([...this.parts, ...this.central, end], { type: 'application/zip' });
  }
}

// ===================================================================== Einstellungen (wie settings.py, im Browser gespeichert)
const DEFAULTS = { pageFormat: 'A4', orientation: 'auto', fit: 'fit', conflictRule: 'number', formats: Object.keys(IMAGE_FORMATS), appearance: 'system' };
function loadSettings() {
  try {
    const d = JSON.parse(localStorage.getItem('imagetopdf.settings') || '{}');
    const s = { ...DEFAULTS };
    if (d.pageFormat in LABELS.page) s.pageFormat = d.pageFormat;
    if (d.orientation in LABELS.orient) s.orientation = d.orientation;
    if (d.fit in LABELS.fit) s.fit = d.fit;
    if (d.conflictRule in LABELS.conflict) s.conflictRule = d.conflictRule;
    if (Array.isArray(d.formats)) { const f = d.formats.filter(x => x in IMAGE_FORMATS); if (f.length) s.formats = f; }
    if (['light', 'dark', 'system'].includes(d.appearance)) s.appearance = d.appearance;
    return s;
  } catch { return { ...DEFAULTS }; }
}
function saveSettings() {
  try { localStorage.setItem('imagetopdf.settings', JSON.stringify(settings)); return true; } catch { return false; }
}
const settings = loadSettings();

// ===================================================================== Zustand
const HAS_FS = typeof window.showDirectoryPicker === 'function';
const state = {
  items: [], selected: new Set(), anchor: null, nextId: 1,
  src: null,   // {name, handle|null, files|null}
  dst: null,   // {name, handle}
  busy: false, cancel: false, planSeq: 0,
};
const byId = id => state.items.find(i => i.id === id);

function newItem(name, dirParts, fileOrHandle) {
  return {
    id: state.nextId++, name, dirParts,
    file: fileOrHandle instanceof File ? fileOrHandle : null,
    handle: fileOrHandle instanceof File ? null : fileOrHandle,
    size: fileOrHandle instanceof File ? fileOrHandle.size : 0,
    info: null, error: null, enabled: true,
    pageFormat: settings.pageFormat, orientation: settings.orientation, fit: settings.fit, conflictRule: settings.conflictRule,
    target: null, eff: null, conflict: false, result: null, resultMsg: '', thumb: null, thumbUrl: null,
  };
}
const convertible = it => it.info !== null && !it.error;

// ===================================================================== Ordnerzugriff
async function getDir(root, parts, create) {
  let d = root;
  for (const p of parts) d = await d.getDirectoryHandle(p, { create });
  return d;
}
const nameCache = new Map();
async function existingNames(rootKey, root, parts) {
  const key = rootKey + '/' + parts.join('/');
  if (nameCache.has(key)) return nameCache.get(key);
  const names = new Set();
  try { for await (const [n] of (await getDir(root, parts, false)).entries()) names.add(n.toLowerCase()); } catch { /* Ordner existiert noch nicht */ }
  nameCache.set(key, names);
  return names;
}

// Ausgabewurzel: Handle mit Schreibrecht oder null (→ ZIP-Download)
function outputRoot() {
  if (document.querySelector('input[name=tmode]:checked').value === 'dir') return state.dst ? { key: 'dst', handle: state.dst.handle, name: state.dst.name } : null;
  return state.src && state.src.handle ? { key: 'src', handle: state.src.handle, name: state.src.name } : null;
}
const targetMode = () => document.querySelector('input[name=tmode]:checked').value;

// ===================================================================== Suche (wie scanner.py)
async function scanHandle(root, exts, excludePath, onItem) {
  async function walk(dir, parts) {
    const files = [], dirs = [];
    for await (const [name, h] of dir.entries()) (h.kind === 'file' ? files : dirs).push([name, h]);
    files.sort((a, b) => lowerCmp(a[0], b[0])); dirs.sort((a, b) => lowerCmp(a[0], b[0]));
    for (const [name, h] of files) if (exts.has(extOf(name))) await onItem(newItem(name, parts, h));
    for (const [name, h] of dirs) {
      const sub = [...parts, name];
      if (excludePath && sub.join('/') === excludePath) continue;
      await walk(h, sub);
    }
  }
  await walk(root, []);
}

// Ohne Ordner-Handles (Firefox/Safari, oder Drop): flache Dateiliste mit relativen Pfaden
async function scanFiles(files, exts, onItem) {
  const tree = { files: [], dirs: new Map() };
  for (const f of files) {
    const rel = (f.webkitRelativePath || f._relPath || f.name).split('/');
    rel.shift(); // Wurzelordner
    const name = rel.pop(); let n = tree;
    for (const d of rel) { if (!n.dirs.has(d)) n.dirs.set(d, { files: [], dirs: new Map() }); n = n.dirs.get(d); }
    n.files.push([name, f]);
  }
  async function walk(node, parts) {
    node.files.sort((a, b) => lowerCmp(a[0], b[0]));
    for (const [name, f] of node.files) if (exts.has(extOf(name))) await onItem(newItem(name, parts, f));
    for (const d of [...node.dirs.keys()].sort(lowerCmp)) await walk(node.dirs.get(d), [...parts, d]);
  }
  await walk(tree, []);
}

async function readEntries(entry, rel, out) { // webkitGetAsEntry-Rekursion (Drop in Browsern ohne Handles)
  if (entry.isFile) { const f = await new Promise((res, rej) => entry.file(res, rej)); f._relPath = rel + entry.name; out.push(f); return; }
  const reader = entry.createReader();
  for (;;) {
    const batch = await new Promise((res, rej) => reader.readEntries(res, rej));
    if (!batch.length) break;
    for (const e of batch) await readEntries(e, rel + entry.name + '/', out);
  }
}

// ===================================================================== Namenskonflikte (wie planner.py)
const tkey = t => t.dir.join('/').toLowerCase() + '/' + t.name.toLowerCase();

async function replan() {
  const seq = ++state.planSeq;
  const root = outputRoot();
  const items = state.items;
  for (const it of items) { it.target = { dir: it.dirParts, name: stemOf(it.name) + '.pdf' }; it.eff = null; it.conflict = false; }
  const exists = async t => {
    if (!root || !root.handle) return false;
    return (await existingNames(root.key, root.handle, t.dir)).has(t.name.toLowerCase());
  };
  const active = items.filter(it => it.enabled && convertible(it));
  const counts = new Map();
  for (const it of active) counts.set(tkey(it.target), (counts.get(tkey(it.target)) || 0) + 1);
  const reserved = new Set();
  const numbered = async t => {
    for (let n = 1; ; n++) {
      const cand = { dir: t.dir, name: `${stemOf(t.name)}_${n}.pdf` };
      if (!reserved.has(tkey(cand)) && !(await exists(cand))) return cand;
    }
  };
  for (const it of active) {
    const k = tkey(it.target), ex = await exists(it.target);
    it.conflict = ex || counts.get(k) > 1;
    if (!it.conflict) { it.eff = it.target; reserved.add(k); continue; }
    if (it.conflictRule === 'skip') it.eff = null;
    else if (it.conflictRule === 'overwrite') it.eff = reserved.has(k) ? await numbered(it.target) : it.target;
    else it.eff = (!ex && !reserved.has(k)) ? it.target : await numbered(it.target);
    if (it.eff) reserved.add(tkey(it.eff));
  }
  for (const it of items) if (!active.includes(it)) it.conflict = await exists(it.target);
  if (seq !== state.planSeq) return; // neuere Planung läuft
  scheduleRender();
}

// ===================================================================== Status (wie models.py)
function statuses(it) {
  if (it.result) return [it.result];
  const out = [];
  if (it.error) out.push(it.error === 'too_large' ? 'too_large' : 'error');
  if (it.conflict) out.push('conflict');
  if (it.info && it.info.animated) out.push('animated');
  return out.length ? out : ['ok'];
}
function level(it) {
  const st = statuses(it);
  if (st.some(s => RED.has(s))) return 'red';
  if (st.some(s => YELLOW.has(s))) return 'yellow';
  if (st.includes('done')) return 'green';
  return 'ok';
}

// ===================================================================== Vorschaubilder (im Hintergrund)
async function makeThumb(it) {
  const file = await getFile(it);
  let src, sw, sh, close = () => {};
  if (it.info.kind === 'tiff') {
    const buf = await file.arrayBuffer(), ifds = UTIF.decode(buf), ifd = ifds[0];
    UTIF.decodeImage(buf, ifd);
    const c = newCanvas(ifd.width, ifd.height);
    c.getContext('2d').putImageData(new ImageData(new Uint8ClampedArray(UTIF.toRGBA8(ifd)), ifd.width, ifd.height), 0, 0);
    src = flattenToCanvas(c, ifd.width, ifd.height, ifd.t274 ? ifd.t274[0] : 1); sw = src.width; sh = src.height;
  } else {
    src = await createImageBitmap(file, { imageOrientation: 'from-image', colorSpaceConversion: 'none' });
    sw = src.width; sh = src.height; close = () => src.close();
  }
  const s = Math.min(1, THUMB / Math.max(sw, sh));
  const c = newCanvas(Math.max(1, Math.round(sw * s)), Math.max(1, Math.round(sh * s)));
  const g = c.getContext('2d');
  g.fillStyle = '#fff'; g.fillRect(0, 0, c.width, c.height);
  g.imageSmoothingQuality = 'high'; g.drawImage(src, 0, 0, c.width, c.height);
  close();
  it.thumb = c; it.thumbUrl = c.toDataURL('image/png');
}

// ===================================================================== Oberfläche
function setStatus(t) { $('#status').textContent = t; }
function showDialog(title, text) {
  $('#dlg-title').textContent = title; $('#dlg-text').textContent = text;
  const d = $('#dlg'); if (!d.open) d.showModal();
}
$('#dlg-ok').onclick = () => $('#dlg').close();

let renderQueued = false;
function scheduleRender() { if (renderQueued) return; renderQueued = true; requestAnimationFrame(() => { renderQueued = false; render(); }); }

function targetText(it) {
  if (!convertible(it)) return '';
  if (!it.enabled) return '';
  if (!it.eff) return '(wird übersprungen)';
  const root = outputRoot();
  return [root ? root.name : 'ZIP', ...it.eff.dir, it.eff.name].join('/');
}

const rowHtml = new Map(); // id → zuletzt gerenderter HTML-Text (nur geänderte Zeilen werden ersetzt)
function renderRow(it) {
  const lv = level(it), st = statuses(it);
  const cls = [state.selected.has(it.id) ? 'sel' : '', !it.enabled ? 'off' : `lvl-${lv}`].join(' ');
  const orig = it.pageFormat === 'original';
  const cyc = (col, text) => `<td class="c cyc" data-cyc="${col}">${esc(text)}</td>`;
  const res = it.info ? `${it.info.width} × ${it.info.height}${it.info.frames > 1 ? ` · ${it.info.frames} S.` : ''}` : '';
  const tip = it.resultMsg || (it.error && it.error !== 'too_large' ? it.error : '');
  return `<tr data-id="${it.id}" class="${cls}">
    <td class="c"><input type="checkbox" data-chk ${it.enabled ? 'checked' : ''}></td>
    <td>${it.thumbUrl ? `<img src="${it.thumbUrl}" alt="">` : '<div class="ph"></div>'}</td>
    <td class="name" title="${esc(it.name)}">${esc(it.name)}</td>
    <td>${esc(it.dirParts.join('/'))}</td>
    <td class="c">${esc(it.info ? it.info.format : '')}</td>
    <td class="c">${esc(res)}</td>
    <td class="r">${it.size ? humanSize(it.size) : ''}</td>
    ${cyc('page', LABELS.page[it.pageFormat])}${cyc('orient', orig ? '–' : LABELS.orient[it.orientation])}${cyc('fit', orig ? '–' : LABELS.fit[it.fit])}${cyc('conflict', LABELS.conflict[it.conflictRule])}
    <td class="wrap">${esc(targetText(it))}</td>
    <td title="${esc(tip)}">${st.map(s => esc(LABELS.status[s])).join(' ')}</td>
  </tr>`;
}

function render() {
  const tb = $('#rows'), items = state.items;
  const htmls = items.map(renderRow);
  const trs = tb.children;
  const same = trs.length === items.length && items.every((it, i) => +trs[i].dataset.id === it.id);
  if (!same) {
    tb.innerHTML = htmls.join('');
    rowHtml.clear(); items.forEach((it, i) => rowHtml.set(it.id, htmls[i]));
  } else {
    items.forEach((it, i) => {
      if (rowHtml.get(it.id) === htmls[i]) return;
      const t = document.createElement('tbody'); t.innerHTML = htmls[i];
      trs[i].replaceWith(t.firstElementChild); rowHtml.set(it.id, htmls[i]);
    });
  }
  $('#empty').style.display = items.length ? 'none' : 'flex';
  updatePreview();
  updateModeNote();
}

function updateModeNote() {
  let t = '';
  if (!HAS_FS) t = 'Hinweis: Dieser Browser darf nicht direkt in Ordner schreiben. Das Ergebnis wird als ZIP-Datei heruntergeladen (Ordnerstruktur bleibt erhalten). Für direktes Speichern Chrome oder Edge verwenden.';
  else if (state.src && !state.src.handle && targetMode() === 'beside') t = 'Hinweis: Der Ordner wurde ohne Schreibzugriff geöffnet. Das Ergebnis wird als ZIP-Datei heruntergeladen. Für direktes Speichern „Durchsuchen…“ statt Drag & Drop verwenden.';
  $('#mode-note').textContent = t;
}

// ---- Auswahl
function selectedItems() { return state.items.filter(i => state.selected.has(i.id)); }
function rowClick(id, e) {
  const idx = state.items.findIndex(i => i.id === id);
  if (e.shiftKey && state.anchor !== null) {
    const a = Math.min(state.anchor, idx), b = Math.max(state.anchor, idx);
    if (!(e.ctrlKey || e.metaKey)) state.selected.clear();
    for (let i = a; i <= b; i++) state.selected.add(state.items[i].id);
  } else if (e.ctrlKey || e.metaKey) {
    if (state.selected.has(id)) state.selected.delete(id); else state.selected.add(id);
    state.anchor = idx;
  } else { state.selected = new Set([id]); state.anchor = idx; }
  render();
}
$('#rows').addEventListener('click', e => {
  const tr = e.target.closest('tr'); if (!tr) return;
  const id = +tr.dataset.id;
  if (e.target.matches('[data-chk]')) { const it = byId(id); it.enabled = e.target.checked; replan(); scheduleRender(); return; }
  rowClick(id, e);
});
$('#rows').addEventListener('dblclick', e => {
  const td = e.target.closest('td[data-cyc]'); if (!td) return;
  const it = byId(+td.parentElement.dataset.id), col = td.dataset.cyc;
  if ((col === 'orient' || col === 'fit') && it.pageFormat === 'original') return;
  const list = CYCLE[col], f = CYCLE_FIELD[col];
  it[f] = list[(list.indexOf(it[f]) + 1) % list.length];
  if (col === 'conflict') replan(); else render();
});
function selectAll() { state.selected = new Set(state.items.map(i => i.id)); render(); }
function setEnabled(v, items) { for (const it of items) it.enabled = v; replan(); scheduleRender(); }
$('#tablewrap').addEventListener('keydown', e => {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'a') { e.preventDefault(); selectAll(); }
  else if (e.key === ' ') { e.preventDefault(); const s = selectedItems(); if (s.length) setEnabled(!s.every(i => i.enabled), s); }
  else if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
    e.preventDefault(); if (!state.items.length) return;
    const cur = state.anchor === null ? -1 : state.anchor, nx = Math.max(0, Math.min(state.items.length - 1, cur + (e.key === 'ArrowDown' ? 1 : -1)));
    state.selected = new Set([state.items[nx].id]); state.anchor = nx; render();
    document.querySelector(`tr[data-id="${state.items[nx].id}"]`)?.scrollIntoView({ block: 'nearest' });
  }
});

// ---- Bearbeitungsleiste
function fillSelect(sel, labels, value) {
  sel.innerHTML = Object.entries(labels).map(([k, v]) => `<option value="${k}">${esc(v)}</option>`).join('');
  sel.value = value;
}
function onBarPage() { const o = $('#bar-page').value === 'original'; $('#bar-orient').disabled = o; $('#bar-fit').disabled = o; }
$('#bar-page').onchange = onBarPage;
$('#btn-apply').onclick = () => {
  for (const it of selectedItems()) {
    it.pageFormat = $('#bar-page').value; it.orientation = $('#bar-orient').value; it.fit = $('#bar-fit').value; it.conflictRule = $('#bar-conflict').value;
  }
  replan(); render();
};
$('#btn-all').onclick = selectAll;
$('#btn-on').onclick = () => setEnabled(true, selectedItems());
$('#btn-off').onclick = () => setEnabled(false, selectedItems());
$('#btn-save').onclick = () => {
  settings.pageFormat = $('#bar-page').value; settings.orientation = $('#bar-orient').value; settings.fit = $('#bar-fit').value; settings.conflictRule = $('#bar-conflict').value;
  settings.formats = [...document.querySelectorAll('#formats input:checked')].map(i => i.value) || DEFAULTS.formats;
  if (!settings.formats.length) settings.formats = [...DEFAULTS.formats];
  setStatus(saveSettings() ? 'Standardeinstellung gespeichert.' : 'Einstellungen konnten nicht gespeichert werden.');
};

// ---- Vorschau (wie preview.py)
function updatePreview() {
  const cv = $('#pvc'), dpr = window.devicePixelRatio || 1, box = 220;
  cv.width = box * dpr; cv.height = box * dpr;
  const g = cv.getContext('2d'); g.scale(dpr, dpr);
  const dark = document.documentElement.dataset.theme === 'dark';
  g.fillStyle = dark ? '#2b2b2b' : '#ebebeb'; g.fillRect(0, 0, box, box);
  const sel = selectedItems(), it = sel[0];
  const info = $('#pinfo'), warn = $('#pwarn'), notes = $('#pnotes');
  if (!it) { info.textContent = 'Zeile markieren, um die Seite zu sehen.'; warn.textContent = ''; notes.textContent = ''; return; }
  const noteLines = [];
  for (const s of statuses(it)) { if (NOTES[s]) noteLines.push(NOTES[s]); }
  if (it.error && it.error !== 'too_large') noteLines.push(`Datei nicht lesbar: ${it.error}`);
  if (it.resultMsg) noteLines.push(it.resultMsg);
  notes.textContent = noteLines.join('\n');
  if (!it.info) { info.textContent = it.name; warn.textContent = ''; return; }
  const lay = computeLayout(it.pageFormat, it.orientation, it.fit, it.info.width, it.info.height, it.info.dpi);
  if (it.pageFormat === 'original') {
    info.textContent = `Originalgröße bei ${it.info.dpi || 96} DPI${it.info.dpi ? '' : ' (keine DPI-Angabe, 96 angenommen)'}`;
  } else {
    info.textContent = `${LABELS.page[it.pageFormat]} · ${(lay.pw / MM_TO_PT).toFixed(0)} × ${(lay.ph / MM_TO_PT).toFixed(0)} mm · Rand ${(lay.margin / MM_TO_PT).toFixed(1)} mm`;
  }
  if (it.info.frames > 1) info.textContent += ` · ${it.info.frames} Seiten`;
  warn.textContent = lay.cropped ? 'Seite füllen: Bildinhalt wird im PDF abgeschnitten.' : '';
  if (!it.thumb) return;
  const pad = 14, scale = Math.min((box - 2 * pad) / lay.pw, (box - 2 * pad) / lay.ph);
  const pw = Math.max(1, Math.round(lay.pw * scale)), ph = Math.max(1, Math.round(lay.ph * scale));
  const px = Math.round((box - pw) / 2), py = Math.round((box - ph) / 2);
  g.fillStyle = dark ? '#141414' : '#bebebe'; g.fillRect(px + 3, py + 3, pw, ph);
  g.save(); g.beginPath(); g.rect(px, py, pw, ph); g.clip();
  g.fillStyle = '#fff'; g.fillRect(px, py, pw, ph);
  g.drawImage(it.thumb, px + lay.x * scale, py + ph - (lay.y + lay.dh) * scale, lay.dw * scale, lay.dh * scale);
  if (it.pageFormat !== 'original' && lay.margin > 0) {
    g.strokeStyle = '#aabedc'; g.lineWidth = 1;
    const m = Math.round(lay.margin * scale); g.strokeRect(px + m + .5, py + m + .5, pw - 2 * m - 1, ph - 2 * m - 1);
  }
  g.restore();
  g.strokeStyle = '#787878'; g.lineWidth = 1; g.strokeRect(px - .5, py - .5, pw + 1, ph + 1);
}

// ---- Quelle / Ziel
function setSource(src) {
  state.src = src;
  $('#srcfield').textContent = src.name; $('#srcfield').classList.remove('empty');
  updateModeNote();
}
function setTarget(dst) {
  state.dst = dst;
  $('#dstfield').textContent = dst.name; $('#dstfield').classList.remove('empty');
  document.querySelector('input[name=tmode][value=dir]').checked = true;
  nameCache.clear(); replan(); updateModeNote();
}
$('#btn-src').onclick = async () => {
  if (state.busy) return;
  if (!HAS_FS) { $('#fin').click(); return; }
  try { const h = await showDirectoryPicker({ id: 'itp-src', mode: 'readwrite' }); setSource({ name: h.name, handle: h }); }
  catch (e) { if (e.name !== 'AbortError') showDialog('Fehler', e.message); }
};
$('#fin').onchange = e => {
  const files = [...e.target.files]; if (!files.length) return;
  setSource({ name: files[0].webkitRelativePath.split('/')[0], files }); e.target.value = '';
};
$('#btn-dst').onclick = async () => {
  if (state.busy) return;
  if (!HAS_FS) { showDialog('Zielordner', 'Dieser Browser kann nicht direkt in Ordner schreiben. Das Ergebnis wird als ZIP-Datei heruntergeladen.'); return; }
  try { const h = await showDirectoryPicker({ id: 'itp-dst', mode: 'readwrite' }); setTarget({ name: h.name, handle: h }); }
  catch (e) { if (e.name !== 'AbortError') showDialog('Fehler', e.message); }
};
document.querySelectorAll('input[name=tmode]').forEach(r => r.onchange = () => { nameCache.clear(); replan(); updateModeNote(); });
$('#dstfield').textContent = 'Zielordner wählen …'; $('#dstfield').classList.add('empty');

// ---- Suchen
async function startScan() {
  if (state.busy) return;
  if (!state.src) { showDialog('Fehler', 'Bitte zuerst einen Quellordner wählen.'); return; }
  const fmts = [...document.querySelectorAll('#formats input:checked')].map(i => i.value);
  if (!fmts.length) { showDialog('Fehler', 'Bitte mindestens ein Bildformat auswählen.'); return; }
  if (targetMode() === 'dir' && !state.dst && HAS_FS) { showDialog('Fehler', 'Bitte einen Zielordner wählen oder „PDF neben dem Bild ablegen“ aktivieren.'); return; }
  const exts = new Set(fmts.flatMap(f => IMAGE_FORMATS[f]));
  const scanId = state.scanId = (state.scanId || 0) + 1;
  setBusy(true);
  state.items = []; state.selected.clear(); state.anchor = null; nameCache.clear(); render();
  let n = 0;
  const onItem = async it => { state.items.push(it); if (++n % 15 === 0) { setStatus(`Durchsuche … ${n} Bilder gefunden`); scheduleRender(); await tick(); } };
  try {
    if (state.src.handle) {
      let exclude = null;
      if (state.dst && targetMode() === 'dir') { const rel = await state.src.handle.resolve(state.dst.handle); if (rel) exclude = rel.join('/'); }
      await scanHandle(state.src.handle, exts, exclude, onItem);
    } else await scanFiles(state.src.files, exts, onItem);
  } catch (e) { showDialog('Fehler', 'Ordner konnte nicht gelesen werden: ' + e.message); }
  if (!n) { setStatus('Keine Bilder mit den gewählten Formaten gefunden.'); setBusy(false); render(); return; }
  let last = 0;
  for (const [i, it] of state.items.entries()) {
    if (scanId !== state.scanId) return;
    try { const f = await getFile(it); it.size = f.size; it.info = await inspectFile(f); }
    catch (e) { it.error = e.message === 'too_large' ? 'too_large' : (e.message || 'Fehler'); }
    if (Date.now() - last > 120) { last = Date.now(); setStatus(`Prüfe Bilder … ${i + 1} / ${n}`); scheduleRender(); await tick(); }
  }
  await replan(); render();
  setStatus(`${n} Bilder gefunden`);
  setBusy(false);
  for (const it of state.items) { // Vorschaubilder im Hintergrund
    if (scanId !== state.scanId) return;
    if (!it.info) continue;
    try { await makeThumb(it); } catch { /* ohne Vorschau weiter */ }
    scheduleRender(); await tick();
  }
}
$('#btn-scan').onclick = startScan;

function setBusy(b) {
  state.busy = b;
  for (const id of ['#btn-scan', '#btn-src', '#btn-dst']) $(id).disabled = b;
  $('#btn-conv').disabled = b;
}

// ---- Konvertieren (wie converter.run)
async function writePdf(rootHandle, t, blob) {
  const d = await getDir(rootHandle, t.dir, true);
  const fh = await d.getFileHandle(t.name, { create: true });
  const w = await fh.createWritable(); // schreibt in Zwischendatei, Übernahme erst bei close()
  try { await w.write(blob); await w.close(); } catch (e) { try { await w.abort(); } catch { /* egal */ } throw e; }
}

async function startConvert() {
  if (state.busy) return;
  const todo = state.items.filter(i => i.enabled && convertible(i));
  if (!todo.length) { showDialog('Hinweis', 'Keine aktivierten, konvertierbaren Bilder in der Liste.'); return; }
  const root = outputRoot();
  let useZip = !(root && root.handle), zipReason = '';
  if (!useZip) {
    try { if (await root.handle.requestPermission({ mode: 'readwrite' }) !== 'granted') { useZip = true; zipReason = 'Schreibzugriff auf den Ordner wurde nicht erlaubt – Ergebnis als ZIP.'; } }
    catch { useZip = true; }
  }
  const zip = useZip ? new ZipWriter() : null;
  setBusy(true); state.cancel = false; $('#btn-cancel').disabled = false;
  for (const it of state.items) { it.result = null; it.resultMsg = ''; }
  const sum = { created: 0, skipped: 0, failed: 0, cancelled: false, errors: [] };
  $('#prog').max = todo.length; $('#prog').value = 0;
  for (const [i, it] of todo.entries()) {
    if (state.cancel) { sum.cancelled = true; break; }
    setStatus(`${i + 1} / ${todo.length}: ${it.name}`);
    await tick();
    if (!it.eff) { it.result = 'skipped'; it.resultMsg = 'Konfliktregel: überspringen'; sum.skipped++; }
    else {
      try {
        const frames = await framesOf(it, () => state.cancel);
        const blob = buildPdf(frames, it);
        if (useZip) zip.add([...it.eff.dir, it.eff.name].join('/'), new Uint8Array(await blob.arrayBuffer()));
        else await writePdf(root.handle, it.eff, blob);
        it.result = 'done'; it.resultMsg = [...it.eff.dir, it.eff.name].join('/'); sum.created++;
      } catch (e) {
        if (e instanceof CancelledError) { sum.cancelled = true; break; }
        it.result = 'failed'; it.resultMsg = e.message || e.name || 'Fehler'; sum.failed++; sum.errors.push(`${[...it.dirParts, it.name].join('/')}: ${it.resultMsg}`);
      }
    }
    $('#prog').value = i + 1; scheduleRender();
  }
  if (zip && zip.count) {
    const a = document.createElement('a'); a.href = URL.createObjectURL(zip.finish()); a.download = `${APP_NAME}.zip`; a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 30000);
  }
  nameCache.clear();
  $('#btn-cancel').disabled = true; setBusy(false); setStatus('Fertig.'); render();
  let text = `Erstellt: ${sum.created}\nÜbersprungen: ${sum.skipped}\nFehler: ${sum.failed}`;
  if (useZip && sum.created) text += `\n\nDie PDFs wurden als „${APP_NAME}.zip“ heruntergeladen.${zipReason ? '\n' + zipReason : ''}`;
  if (sum.cancelled) text += '\n\nAbgebrochen.';
  if (sum.errors.length) text += `\n\nFehlerliste:\n${sum.errors.join('\n')}`;
  showDialog('Fertig', text);
}
$('#btn-conv').onclick = startConvert;
$('#btn-cancel').onclick = () => { state.cancel = true; };

// ---- Drag & Drop eines Ordners
const veil = $('#dropveil');
let dragDepth = 0;
window.addEventListener('dragenter', e => { if ([...(e.dataTransfer?.types || [])].includes('Files')) { dragDepth++; veil.classList.add('on'); } });
window.addEventListener('dragleave', () => { if (--dragDepth <= 0) { dragDepth = 0; veil.classList.remove('on'); } });
window.addEventListener('dragover', e => e.preventDefault());
window.addEventListener('drop', async e => {
  e.preventDefault(); dragDepth = 0; veil.classList.remove('on');
  if (state.busy) return;
  const its = [...e.dataTransfer.items].filter(i => i.kind === 'file');
  const handles = its.map(i => i.getAsFileSystemHandle ? i.getAsFileSystemHandle() : null);
  const entries = its.map(i => i.webkitGetAsEntry ? i.webkitGetAsEntry() : null);
  for (const hp of handles) {
    const h = await hp;
    if (h && h.kind === 'directory') { setSource({ name: h.name, handle: h }); startScan(); return; }
  }
  const dir = entries.find(en => en && en.isDirectory);
  if (dir) {
    const files = []; await readEntries(dir, '', files);
    setSource({ name: dir.name, files }); startScan();
  }
});

// ---- Design (Hell/Dunkel)
const mq = window.matchMedia('(prefers-color-scheme: dark)');
function applyTheme() {
  const dark = settings.appearance === 'dark' || (settings.appearance === 'system' && mq.matches);
  document.documentElement.dataset.theme = dark ? 'dark' : 'light';
  $('#dark').checked = dark;
  updatePreview();
}
$('#dark').onchange = e => { settings.appearance = e.target.checked ? 'dark' : 'light'; saveSettings(); applyTheme(); };
mq.addEventListener?.('change', () => { if (settings.appearance === 'system') applyTheme(); });

// ---- Start
$('#formats').innerHTML = Object.keys(IMAGE_FORMATS).map(f => `<label class="chk"><input type="checkbox" value="${f}" ${settings.formats.includes(f) ? 'checked' : ''}> ${f.toUpperCase()}</label>`).join('');
fillSelect($('#bar-page'), LABELS.page, settings.pageFormat);
fillSelect($('#bar-orient'), LABELS.orient, settings.orientation);
fillSelect($('#bar-fit'), LABELS.fit, settings.fit);
fillSelect($('#bar-conflict'), LABELS.conflict, settings.conflictRule);
onBarPage(); applyTheme(); render();
if (!HAS_FS) document.querySelector('input[name=tmode][value=dir]').closest('label').style.display = 'none', $('#btn-dst').style.display = 'none', $('#dstfield').style.display = 'none';
window.__itp = { state, settings, setSource, setTarget, startScan, startConvert, replan, inspectFile, framesOf, buildPdf };
