// Baut index.html aus src/ und vendor/ (Node.js): node build.js
const fs = require('fs'), path = require('path');
const r = f => fs.readFileSync(path.join(__dirname, f), 'utf8');
const safe = s => s.replace(/<\/script/gi, '<\\/script');
const out = r('src/template.html')
  .replace('/*{{CSS}}*/', () => r('src/style.css'))
  .replace('/*{{PAKO}}*/', () => safe(r('vendor/pako_inflate.min.js')))
  .replace('/*{{UTIF}}*/', () => safe(r('vendor/UTIF.js')))
  .replace('/*{{APP}}*/', () => safe(r('src/app.js')));
fs.writeFileSync(path.join(__dirname, 'index.html'), out);
console.log('index.html:', (out.length / 1024).toFixed(0), 'KB');
