// render-stats.js — рендерит карточки статистики из state/tasks.yaml
// Использование: node render-stats.js [--source=PATH] [--output-dir=.] [--themes=light,dark]
// Зависимости: Node.js + Edge headless
const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');
const { parseArgs, ensureDir, resolveEdgeBin, parseThemes } = require('./lib/cli');
const { PALETTE } = require('./lib/palette');

const BASE = __dirname;
const args = parseArgs(process.argv);
const OUT_DIR = path.resolve(args['output-dir'] || BASE);
const SOURCE = path.resolve(
  args.source ? args.source : path.join(BASE, '..', 'state', 'tasks.yaml')
);
const themes = parseThemes(args);

ensureDir(OUT_DIR);

function parseValue(v) {
  if (v == null) return null;
  v = String(v).trim();
  if (v === '' || v === '~' || v === 'null' || v === 'NULL') return null;
  if (v === 'true') return true;
  if (v === 'false') return false;
  if (/^-?\d+$/.test(v)) return parseInt(v, 10);
  if (/^-?\d+\.\d+$/.test(v)) return parseFloat(v);
  if ((v.startsWith('"') && v.endsWith('"')) || (v.startsWith("'") && v.endsWith("'"))) {
    return v.slice(1, -1);
  }
  return v;
}

function loadTasks(srcPath) {
  const text = fs.readFileSync(srcPath, 'utf8');
  const tasks = [];
  const meta = {};
  let cur = null;
  let section = null;

  for (const raw of text.split('\n')) {
    if (!raw.trim() || raw.trim().startsWith('#')) continue;
    const trimmed = raw.trim();
    if (trimmed === 'tasks:') { section = 'tasks'; cur = null; continue; }
    if (trimmed === 'meta:') { section = 'meta'; cur = null; continue; }

    if (section === 'tasks' && /^\s*-\s/.test(raw)) {
      cur = {};
      tasks.push(cur);
      const rest = raw.replace(/^\s*-\s+/, '');
      const m = rest.match(/^(\S+):\s*(.*)$/);
      if (m) cur[m[1]] = parseValue(m[2]);
      continue;
    }

    if (cur && /^\s{2,}\S/.test(raw) && !raw.trim().startsWith('-')) {
      const m = raw.match(/^\s+(\S+):\s*(.*)$/);
      if (m) {
        const v = m[2].trim();
        cur[m[1]] = parseValue(v === '' ? null : v);
      }
      continue;
    }

    if (section === 'meta' && /^\s+\S/.test(raw) && !raw.trim().startsWith('-')) {
      const m = raw.match(/^\s+(\S+):\s*(.*)$/);
      if (m) meta[m[1]] = parseValue(m[2]);
    }
  }
  return { tasks, meta };
}

function escapeHtml(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

function fmtDate(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  if (isNaN(d)) return iso;
  const dd = String(d.getDate()).padStart(2, '0');
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  return `${dd}.${mm}.${d.getFullYear()}`;
}

function daysUntil(iso) {
  if (!iso) return null;
  const d = new Date(iso);
  const now = new Date();
  return Math.round((d - now) / (1000 * 60 * 60 * 24));
}


const PALETTE_STATS = {
  light: {
    bg: PALETTE.light.bg,
    cardBg: PALETTE.light.cardBg,
    accent: PALETTE.light.accent,
    title: PALETTE.light.title,
    subtitle: PALETTE.light.subtitle,
    text: PALETTE.light.text,
    muted: PALETTE.light.muted,
    good: PALETTE.light.good,
    warn: PALETTE.light.warn,
    bad: PALETTE.light.bad,
    shadow: PALETTE.light.shadow,
  },
  dark: {
    bg: PALETTE.dark.bg,
    cardBg: PALETTE.dark.cardBg,
    accent: PALETTE.dark.accent,
    title: PALETTE.dark.title,
    subtitle: PALETTE.dark.subtitle,
    text: PALETTE.dark.text,
    muted: PALETTE.dark.muted,
    good: PALETTE.dark.good,
    warn: PALETTE.dark.warn,
    bad: PALETTE.dark.bad,
    shadow: PALETTE.dark.shadow,
  },
};

function paletteFor(theme) {
  return PALETTE_STATS[theme] || PALETTE_STATS.dark;
}

function compute(tasks) {
  const total = tasks.length;
  const closed = tasks.filter(t => t.status === 'done').length;
  const active = tasks.filter(t => t.status === 'in_progress' || t.status === 'planned').length;
  const overdue = tasks.filter(t => t.status === 'overdue' || (t.deadline && new Date(t.deadline) < new Date() && t.status !== 'done')).length;
  const blocked = tasks.filter(t => t.status === 'blocked').length;

  const totalWeight = tasks.reduce((s, t) => s + (t.weight || 0), 0);
  const doneWeight = tasks.reduce((s, t) => s + (t.weight || 0) * (t.progress || 0) / 100, 0);
  const progressWeight = totalWeight ? Math.round(doneWeight / totalWeight * 100) : 0;

  const totalHours = tasks.reduce((s, t) => s + (t.actual_duration || 0), 0);
  const hoursLabel = totalHours >= 60 ? `${Math.floor(totalHours/60)} ч ${totalHours%60} мин` : `${totalHours} мин`;

  const cats = {};
  for (const t of tasks) {
    const c = t.category || 'Без категории';
    cats[c] = cats[c] || { count: 0, weight: 0, doneWeight: 0 };
    cats[c].count++;
    cats[c].weight += t.weight || 0;
    cats[c].doneWeight += (t.weight || 0) * (t.progress || 0) / 100;
  }
  for (const c of Object.keys(cats)) {
    cats[c].pct = cats[c].weight ? Math.round(cats[c].doneWeight / cats[c].weight * 100) : 0;
  }

  const longTasks = tasks.filter(t => t.task_type === 'long' || (t.deadline && daysUntil(t.deadline) > 7));
  const longAvg = longTasks.length ? Math.round(longTasks.reduce((s, t) => s + (t.progress || 0), 0) / longTasks.length) : null;

  const deadlines = tasks
    .filter(t => t.deadline && t.status !== 'done')
    .map(t => ({ ...t, days: daysUntil(t.deadline) }))
    .sort((a, b) => a.days - b.days)
    .slice(0, 6);

  return { total, closed, active, overdue, blocked, totalWeight, progressWeight, hoursLabel, cats, longTasks, longAvg, deadlines };
}

function bar(pct, color, width = 320) {
  const filled = Math.max(0, Math.min(width, Math.round(pct / 100 * width)));
  return `<div style="position:relative;width:${width}px;height:14px;background:rgba(127,127,127,0.18);border-radius:8px;overflow:hidden;"><div style="position:absolute;left:0;top:0;bottom:0;width:${filled}px;background:${color};border-radius:8px;"></div></div>`;
}

function coverHtml(s, theme) {
  const p = paletteFor(theme);
  const headline = s.total === 0 ? 'Трекер пуст 🗒️' :
                   s.progressWeight === 0 ? 'Старт дан 🚀' :
                   s.progressWeight < 30 ? 'Старт дан 🚀' :
                   s.progressWeight < 70 ? 'Хороший темп 📈' :
                   'Почти у цели 🏁';
  return `<!DOCTYPE html>
<html lang="ru"><head><meta charset="UTF-8"><title>Статистика</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  html, body { width: 1080px; height: 1440px; }
  body { font-family: 'Segoe UI', system-ui, sans-serif; background: ${p.bg}; padding: 80px 70px; display: flex; flex-direction: column; }
  .eyebrow { display: inline-block; background: ${p.accent}; color: ${theme === 'dark' ? '#0E1116' : 'white'}; padding: 10px 22px; border-radius: 30px; font-size: 24px; font-weight: 700; letter-spacing: 3px; margin-bottom: 28px; align-self: flex-start; }
  h1 { font-size: 76px; color: ${p.title}; font-weight: 900; line-height: 1.0; margin-bottom: 18px; }
  .sub { font-size: 32px; color: ${p.subtitle}; font-weight: 500; margin-bottom: 40px; }
  .big { font-size: 220px; font-weight: 900; color: ${p.accent}; line-height: 1; margin: 20px 0 6px 0; }
  .big-lbl { font-size: 28px; color: ${p.muted}; font-weight: 600; margin-bottom: 14px; }
  .headline { display: inline-block; background: ${p.cardBg}; padding: 18px 28px; border-radius: 22px; font-size: 30px; font-weight: 700; color: ${p.title}; box-shadow: ${p.shadow}; margin-bottom: 40px; align-self: flex-start; }
  .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; }
  .stat { background: ${p.cardBg}; border-radius: 24px; padding: 26px 24px; box-shadow: ${p.shadow}; }
  .stat .n { font-size: 60px; font-weight: 900; line-height: 1; margin-bottom: 8px; }
  .stat .l { font-size: 20px; color: ${p.muted}; font-weight: 600; }
  .n.good { color: ${p.good}; } .n.warn { color: ${p.warn}; } .n.bad { color: ${p.bad}; } .n.accent { color: ${p.accent}; }
  .footer { margin-top: auto; text-align: center; font-size: 22px; color: ${p.muted}; font-weight: 500; padding-top: 30px; }
</style></head>
<body>
<div class="eyebrow">СТАТИСТИКА</div>
<h1>Прогресс по трекеру</h1>
<div class="sub">${s.total} задач${s.totalWeight ? ' · ' + s.totalWeight + ' ед. веса' : ''}</div>

<div class="big">${s.progressWeight}<span style="font-size:90px;color:${p.muted};">%</span></div>
<div class="big-lbl">прогресс по весу</div>

<div class="headline">${headline}</div>

<div class="grid">
  <div class="stat"><div class="n good">${s.closed}</div><div class="l">✅ закрыто</div></div>
  <div class="stat"><div class="n accent">${s.active}</div><div class="l">⏳ активных</div></div>
  <div class="stat"><div class="n ${s.overdue ? 'bad' : 'good'}">${s.overdue}</div><div class="l">🔥 просрочено</div></div>
  <div class="stat"><div class="n accent">${s.hoursLabel}</div><div class="l">⏱ отработано</div></div>
</div>

<div class="footer">обновлено ${new Date().toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })} · ${path.basename(SOURCE)}</div>
</body></html>`;
}

function deadlinesHtml(s, theme) {
  const p = paletteFor(theme);
  const rows = s.deadlines.length === 0
    ? `<div style="background:${p.cardBg};border-radius:24px;padding:48px;text-align:center;font-size:34px;color:${p.muted};">Нет активных дедлайнов 🎉</div>`
    : s.deadlines.map(t => {
        const stColor = t.days < 0 ? p.bad : t.days <= 3 ? p.warn : p.good;
        const stLabel = t.days < 0 ? `🔥 просрочен · ${Math.abs(t.days)} дн` :
                        t.days === 0 ? '🔥 сегодня' :
                        t.days <= 3 ? `⚠️ ${t.days} дн` :
                        `🟢 ${t.days} дн`;
        return `
    <div style="background:${p.cardBg};border-radius:22px;padding:22px 26px;margin-bottom:14px;box-shadow:${p.shadow};display:flex;align-items:center;">
      <div style="width:150px;">
        <div style="font-size:30px;font-weight:800;color:${p.title};">${fmtDate(t.deadline)}</div>
        <div style="font-size:18px;color:${p.muted};font-weight:600;">${escapeHtml((t.task_type || 'short') === 'long' ? 'долгосрок' : 'short')}</div>
      </div>
      <div style="flex:1;padding:0 18px;">
        <div style="font-size:24px;font-weight:700;color:${p.text};">${escapeHtml(t.name)}</div>
        <div style="font-size:18px;color:${p.muted};margin-top:4px;">${escapeHtml(t.category || '')} · вес ${t.weight || 0}</div>
      </div>
      <div style="background:${stColor};color:${theme === 'dark' ? '#0E1116' : 'white'};padding:12px 18px;border-radius:16px;font-size:20px;font-weight:800;white-space:nowrap;">${stLabel}</div>
    </div>`;
      }).join('');

  return `<!DOCTYPE html>
<html lang="ru"><head><meta charset="UTF-8"><title>Дедлайны</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  html, body { width: 1080px; height: 1440px; }
  body { font-family: 'Segoe UI', system-ui, sans-serif; background: ${p.bg}; padding: 80px 70px; display: flex; flex-direction: column; }
  .eyebrow { display: inline-block; background: ${p.bad}; color: ${theme === 'dark' ? '#0E1116' : 'white'}; padding: 10px 22px; border-radius: 30px; font-size: 24px; font-weight: 700; letter-spacing: 3px; margin-bottom: 28px; align-self: flex-start; }
  h1 { font-size: 76px; color: ${p.title}; font-weight: 900; line-height: 1.0; margin-bottom: 12px; }
  .sub { font-size: 28px; color: ${p.subtitle}; font-weight: 500; margin-bottom: 36px; }
  .body { flex: 1; }
  .footer { margin-top: 30px; text-align: center; font-size: 22px; color: ${p.muted}; font-weight: 500; }
</style></head>
<body>
<div class="eyebrow">ДЕДЛАЙНЫ</div>
<h1>Ближайшие ${s.deadlines.length}</h1>
<div class="sub">${s.deadlines.length === 0 ? 'всё чисто' : 'по убыванию срочности'}</div>
<div class="body">${rows}</div>
<div class="footer">${new Date().toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })}</div>
</body></html>`;
}

function categoriesHtml(s, theme) {
  const p = paletteFor(theme);
  const cats = Object.entries(s.cats).sort((a, b) => b[1].weight - a[1].weight);
  const rows = cats.length === 0
    ? `<div style="background:${p.cardBg};border-radius:24px;padding:48px;text-align:center;font-size:34px;color:${p.muted};">Нет задач</div>`
    : cats.map(([name, c]) => `
    <div style="background:${p.cardBg};border-radius:22px;padding:24px 28px;margin-bottom:14px;box-shadow:${p.shadow};">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
        <div style="font-size:28px;font-weight:700;color:${p.title};">${escapeHtml(name)}</div>
        <div style="font-size:30px;font-weight:900;color:${p.accent};">${c.pct}<span style="font-size:18px;color:${p.muted};">%</span></div>
      </div>
      <div style="display:flex;align-items:center;gap:18px;">
        ${bar(c.pct, p.accent, 700)}
        <div style="font-size:20px;color:${p.muted};font-weight:600;white-space:nowrap;">${c.count} задач · вес ${c.weight}</div>
      </div>
    </div>`).join('');

  return `<!DOCTYPE html>
<html lang="ru"><head><meta charset="UTF-8"><title>Категории</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  html, body { width: 1080px; height: 1440px; }
  body { font-family: 'Segoe UI', system-ui, sans-serif; background: ${p.bg}; padding: 80px 70px; display: flex; flex-direction: column; }
  .eyebrow { display: inline-block; background: ${p.accent}; color: ${theme === 'dark' ? '#0E1116' : 'white'}; padding: 10px 22px; border-radius: 30px; font-size: 24px; font-weight: 700; letter-spacing: 3px; margin-bottom: 28px; align-self: flex-start; }
  h1 { font-size: 76px; color: ${p.title}; font-weight: 900; line-height: 1.0; margin-bottom: 36px; }
  .body { flex: 1; }
  .footer { margin-top: 30px; text-align: center; font-size: 22px; color: ${p.muted}; font-weight: 500; }
</style></head>
<body>
<div class="eyebrow">КАТЕГОРИИ</div>
<h1>По категориям</h1>
<div class="body">${rows}</div>
<div class="footer">${new Date().toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })}</div>
</body></html>`;
}

function write(name, content) {
  const fp = path.join(OUT_DIR, name);
  fs.writeFileSync(fp, content, 'utf8');
  return fp;
}

function shoot(htmlFile, pngFile) {
  const edge = resolveEdgeBin();
  const udd = path.join(process.env.TEMP || '/tmp', 'edge_' + Date.now() + '_' + Math.random().toString(36).slice(2, 8));
  const url = 'file:///' + htmlFile.replace(/\\/g, '/');
  execSync(`"${edge}" --headless=new --disable-gpu --hide-scrollbars --no-first-run --no-default-browser-check --user-data-dir="${udd}" --force-device-scale-factor=1 --window-size=1080,1440 --screenshot="${pngFile}" "${url}"`, { stdio: 'ignore' });
}

const { tasks, meta } = loadTasks(SOURCE);
const s = compute(tasks);
console.log(`Parsed ${tasks.length} tasks from ${SOURCE}`);
console.log(`Output: ${OUT_DIR}`);
if (tasks.length) console.log('First task:', tasks[0]);

const cards = [
  { name: 'stats_cover', html: coverHtml },
  { name: 'stats_deadlines', html: deadlinesHtml },
  { name: 'stats_cats', html: categoriesHtml },
];

const generated = [];
let done = 0;
for (const c of cards) {
  for (const theme of themes) {
    const htmlPath = write(`${c.name}_${theme}.html`, c.html(s, theme));
    const pngPath = path.join(OUT_DIR, `${c.name}_${theme}.png`);
    generated.push(pngPath);
    try { shoot(htmlPath, pngPath); console.log(`OK ${path.basename(pngPath)}`); done++; }
    catch (e) { console.error(`FAIL ${path.basename(pngPath)}: ${e.message}`); }
  }
}
console.log(`Done: ${done}/${cards.length * themes.length}`);
console.log(`Stats: total=${s.total} closed=${s.closed} active=${s.active} overdue=${s.overdue} progressWeight=${s.progressWeight}%`);
console.log(JSON.stringify({ kind: 'stats', outputDir: OUT_DIR, files: generated.map(p => path.basename(p)) }));
