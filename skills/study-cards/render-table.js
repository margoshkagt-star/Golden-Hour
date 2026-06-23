// render-table.js — markdown table JSON → PNG (study-cards dark theme)
// Usage: node render-table.js --source=table.json --output-dir=./ --name=table.png
const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');
const { parseArgs, ensureDir, resolveEdgeBin } = require('./lib/cli');
const { PALETTE, DEFAULT_THEME } = require('./lib/palette');

const args = parseArgs(process.argv);
const sourcePath = path.resolve(args.source || '');
const outputDir = path.resolve(args['output-dir'] || path.dirname(sourcePath));
const outName = args.name || 'table.png';
const theme = DEFAULT_THEME;
const p = PALETTE[theme];

if (!sourcePath || !fs.existsSync(sourcePath)) {
  console.error('Missing --source table.json');
  process.exit(1);
}

ensureDir(outputDir);

const data = JSON.parse(fs.readFileSync(sourcePath, 'utf8'));
const { title = 'Таблица', subtitle = '', headers = [], rows = [] } = data;

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

const colCount = Math.max(headers.length, ...rows.map((r) => r.length), 1);
const fontSize = colCount > 6 ? 20 : colCount > 4 ? 24 : 28;
const headerSize = colCount > 6 ? 22 : colCount > 4 ? 26 : 24;
const rowH = colCount > 6 ? 48 : 56;
const headerH = 64;
const padTop = 48;
const titleBlock = subtitle ? 150 : 120;
const height = Math.min(2400, Math.max(500, padTop + titleBlock + headerH + Math.ceil(rows.length * rowH * 1.4) + 80));

const totalWidth = 1080 - 80;
let colWidths;
if (colCount === 4) {
  const side = [100, 110, 160];
  const main = totalWidth - side[0] - side[1] - side[2];
  colWidths = [side[0], main, side[1], side[2]];
} else {
  colWidths = new Array(colCount).fill(Math.floor(totalWidth / colCount));
}

const headerCells = headers
  .map((h, c) => {
    const wrap = c >= 2 ? `<center>${escapeHtml(h)}</center>` : escapeHtml(h);
    return `<th style="width:${colWidths[c]}px">${wrap}</th>`;
  })
  .join('');

const bodyRows = rows
  .map((row, ri) => {
    const cells = [];
    for (let c = 0; c < colCount; c++) {
      const wrap = c >= 2 ? `<center>${escapeHtml(row[c] ?? '')}</center>` : escapeHtml(row[c] ?? '');
      cells.push(`<td>${wrap}</td>`);
    }
    const bgRow = ri % 2 === 1 ? p.zebra : p.cardBg;
    return `<tr style="background:${bgRow}">${cells.join('')}</tr>`;
  })
  .join('');

const html = `<!DOCTYPE html>
<html lang="ru"><head><meta charset="UTF-8"><title>${escapeHtml(title)}</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  html, body { width: 1080px; height: ${height}px; }
  body { font-family: 'Segoe UI', system-ui, sans-serif; background: ${p.bg}; padding: ${padTop}px 40px 40px; color: ${p.text}; }
  .badge { display: inline-block; background: ${p.accent}; color: #0E1116; padding: 8px 18px; border-radius: 24px; font-size: 20px; font-weight: 700; margin-bottom: 16px; }
  h1 { font-size: 42px; color: ${p.title}; font-weight: 800; margin-bottom: 8px; line-height: 1.1; }
  .sub { font-size: 26px; color: ${p.muted}; margin-bottom: 24px; }
  .wrap { background: ${p.cardBg}; border-radius: 20px; overflow: hidden; box-shadow: ${p.shadow}; }
  table { width: 100%; border-collapse: collapse; table-layout: fixed; }
  th { background: ${p.headerBg}; color: ${p.title}; font-size: ${headerSize}px; font-weight: 700; padding: 14px 16px; text-align: left; border-bottom: 2px solid ${p.accent}; border-right: 1px solid ${p.border}; word-wrap: break-word; white-space: nowrap; }
  th:last-child, td:last-child { border-right: none; }
  td { font-size: ${fontSize}px; padding: 12px 16px; border-bottom: 1px solid ${p.border}; border-right: 1px solid ${p.border}; vertical-align: top; word-wrap: break-word; line-height: 1.25; text-align: left; }
  center { display: block; text-align: center; }
  tr:last-child td { border-bottom: none; }
</style></head>
<body>
  <div class="badge">🌅 Золотой час</div>
  <h1>${escapeHtml(title)}</h1>
  ${subtitle ? `<div class="sub">${escapeHtml(subtitle)}</div>` : ''}
  <div class="wrap">
    <table><thead><tr>${headerCells}</tr></thead><tbody>${bodyRows}</tbody></table>
  </div>
</body></html>`;

const base = outName.replace(/\.png$/i, '');
const htmlFile = path.join(outputDir, `${base}.html`);
const pngFile = path.join(outputDir, outName);
fs.writeFileSync(htmlFile, html, 'utf8');

const edge = resolveEdgeBin();
const udd = path.join(process.env.TEMP || '/tmp', 'edge_tbl_' + Date.now());
const url = 'file:///' + htmlFile.replace(/\\/g, '/');
execSync(
  `"${edge}" --headless=new --disable-gpu --hide-scrollbars --no-first-run --no-default-browser-check --user-data-dir="${udd}" --force-device-scale-factor=1 --window-size=1080,${height} --screenshot="${pngFile}" "${url}"`,
  { stdio: 'ignore' }
);
console.log(pngFile);
console.log(JSON.stringify({ kind: 'table', theme, outputDir, files: [path.basename(pngFile)] }));
