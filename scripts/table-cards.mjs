#!/usr/bin/env node
// table-cards.mjs — render markdown tables as PNG via study-cards (dark theme).
//
// Usage:
//   node scripts/table-cards.mjs --user <key> --title "..." --text "markdown..."
//   node scripts/table-cards.mjs --user <key> --title "..." --file path.md
//   echo "..." | node scripts/table-cards.mjs --user <key> --title "..." --stdin

import fs from "node:fs";
import path from "node:path";
import { execSync } from "node:child_process";
import {
  parseArgs,
  requireUser,
  userDir,
  readText,
  writeText,
  isDryRun,
  out,
  die,
  relWorkspacePath,
} from "./lib/cli.mjs";
import { loadProfile, getSetupStatus } from "./lib/profile.mjs";
import {
  extractMarkdownTables,
  chunkTable,
} from "./lib/markdown-table.mjs";
import { CARD_THEME, RENDER_TABLE_JS } from "./lib/card-render.mjs";

function readInput(opts) {
  if (opts.stdin === "true") {
    return fs.readFileSync(0, "utf8");
  }
  if (opts.file) {
    const p = path.isAbsolute(opts.file)
      ? opts.file
      : path.join(process.cwd(), opts.file);
    if (!fs.existsSync(p)) die("file not found", { path: opts.file });
    return readText(p);
  }
  if (opts.text != null) return String(opts.text);
  die("provide --text, --file, or --stdin");
}

function renderOne(table, meta, outDir, index) {
  const chunks = chunkTable(table);
  const pngs = [];
  for (let ci = 0; ci < chunks.length; ci++) {
    const ch = chunks[ci];
    const subtitle =
      ch.pages > 1
        ? `${meta.subtitle || ""} · стр. ${ch.page}/${ch.pages}`.trim()
        : meta.subtitle || "";
    const jsonPath = path.join(outDir, `table-${index}-${ci}.json`);
    writeText(
      jsonPath,
      JSON.stringify(
        {
          title: meta.title,
          subtitle,
          headers: ch.headers,
          rows: ch.rows,
        },
        null,
        2
      ) + "\n"
    );
    const pngName = `table-${index}-${ci}.png`;
    try {
      execSync(
        `node "${RENDER_TABLE_JS}" --source="${jsonPath}" --output-dir="${outDir}" --name="${pngName}"`,
        { stdio: "pipe", encoding: "utf8" }
      );
      pngs.push(path.join(outDir, pngName));
    } catch (e) {
      die("table render failed — нужен Edge на хосте", {
        detail: String(e.stderr || e.message || e).slice(0, 300),
      });
    }
  }
  return pngs;
}

const { opts } = parseArgs(process.argv);
const userKey = requireUser(opts);
const dir = userDir(userKey);
const title = opts.title || "Сводка";
const subtitle = opts.subtitle || "";

const { exists, profile } = loadProfile(dir, (p) => readText(p));
if (!exists) die("profile not found");
if (getSetupStatus(profile) !== "complete") {
  die("setup_status not complete", { setup_status: getSetupStatus(profile) });
}

const text = readInput(opts);
const tables = extractMarkdownTables(text);
if (!tables.length) {
  out({
    ok: true,
    user_key: userKey,
    tables_found: 0,
    png_files: [],
    summary: "Таблиц в тексте нет — отправляй обычным текстом или списком.",
  });
  process.exit(0);
}

const stamp = new Date().toISOString().replace(/[:.]/g, "").slice(0, 15);
const outDir = path.join(dir, "cards", "tables", stamp);
const relOut = relWorkspacePath(outDir);

if (isDryRun(opts)) {
  out({
    ok: true,
    user_key: userKey,
    dry_run: true,
    tables_found: tables.length,
    output_dir: relOut,
    card_theme: CARD_THEME,
    summary: `Найдено таблиц: ${tables.length}. Будут PNG (${CARD_THEME}) в ${relOut}.`,
  });
  process.exit(0);
}

if (!fs.existsSync(outDir)) fs.mkdirSync(outDir, { recursive: true });

const allPngs = [];
tables.forEach((table, i) => {
  const tableTitle = tables.length > 1 ? `${title} (${i + 1}/${tables.length})` : title;
  allPngs.push(...renderOne(table, { title: tableTitle, subtitle }, outDir, i));
});

out({
  ok: true,
  user_key: userKey,
  tables_found: tables.length,
  output_dir: relOut,
  card_theme: CARD_THEME,
  png_files: allPngs.map((p) => relWorkspacePath(p)),
  summary: `Готово: ${allPngs.length} PNG. Отправь картинками в Telegram, не markdown-таблицей.`,
});
