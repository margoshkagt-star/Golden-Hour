// Shared CLI helpers for study-cards render scripts.
const fs = require('fs');
const path = require('path');

function parseArgs(argv) {
  const out = {};
  for (const a of argv.slice(2)) {
    if (!a.startsWith('--')) continue;
    const eq = a.indexOf('=');
    if (eq === -1) out[a.slice(2)] = true;
    else out[a.slice(2, eq)] = a.slice(eq + 1);
  }
  return out;
}

function ensureDir(dir) {
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
}

function resolveEdgeBin() {
  if (process.env.EDGE_BIN) return process.env.EDGE_BIN;
  if (process.platform === 'win32') {
    return 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
  }
  for (const candidate of ['/usr/bin/google-chrome', '/usr/bin/chromium', '/usr/bin/chromium-browser']) {
    if (fs.existsSync(candidate)) return candidate;
  }
  return 'google-chrome';
}

function parseThemes(args, fallback = ['light', 'dark']) {
  if (!args.themes) return fallback;
  return String(args.themes).split(',').map(t => t.trim()).filter(Boolean);
}

module.exports = { parseArgs, ensureDir, resolveEdgeBin, parseThemes };
