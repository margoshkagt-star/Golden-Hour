// render.js — рендерит cover + week-карточки в HTML и PNG (лайт и тёмная тема)
// Использование:
//   node render.js [--source=plan.json] [--output-dir=.] [--themes=light,dark] [--no-weeks]
// Зависимости: только Node.js + локальный Edge/Chrome (msedge --headless)
const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');
const { parseArgs, ensureDir, resolveEdgeBin, parseThemes } = require('./lib/cli');

const BASE = __dirname;
const args = parseArgs(process.argv);
const OUT_DIR = path.resolve(args['output-dir'] || BASE);
const SOURCE = path.resolve(args.source || path.join(BASE, 'plan.json'));
const themes = parseThemes(args);
const noWeeks = !!args['no-weeks'];

ensureDir(OUT_DIR);
const PLAN = JSON.parse(fs.readFileSync(SOURCE, 'utf8'));
if (noWeeks) PLAN.weeks = [];

// Палитры для каждой недели (лайт + тёмная)
const PALETTES = [
  // Week 1 — зелёная
  { light: { bg: '#E8F5E9', accent: '#2E7D32', title: '#1B5E20', subtitle: '#388E3C', numBg: '#C8E6C9', date: '#1B5E20' },
    dark:  { bg: '#0E1A12', accent: '#4CAF50', title: '#C8E6C9', subtitle: '#81C784', numBg: '#1B3320', cardBg: '#16241B', date: '#A5D6A7', text: '#E8F5E9', muted: '#90A4AE' } },
  // Week 2 — оранжевая
  { light: { bg: '#FFF3E0', accent: '#E65100', title: '#BF360C', subtitle: '#E65100', numBg: '#FFE0B2', date: '#BF360C' },
    dark:  { bg: '#1F140A', accent: '#FF9800', title: '#FFCC80', subtitle: '#FFB74D', numBg: '#3B2710', cardBg: '#2A1B0E', date: '#FFB74D', text: '#FFF3E0', muted: '#A1887F' } },
  // Week 3 — сиреневая
  { light: { bg: '#F3E5F5', accent: '#6A1B9A', title: '#4A148C', subtitle: '#6A1B9A', numBg: '#E1BEE7', date: '#4A148C' },
    dark:  { bg: '#170F1F', accent: '#BA68C8', title: '#E1BEE7', subtitle: '#CE93D8', numBg: '#2D1A3A', cardBg: '#1F1429', date: '#CE93D8', text: '#F3E5F5', muted: '#B39DDB' } },
  // Week 4 — синяя
  { light: { bg: '#E3F2FD', accent: '#1565C0', title: '#0D47A1', subtitle: '#1565C0', numBg: '#BBDEFB', date: '#0D47A1' },
    dark:  { bg: '#0E1626', accent: '#64B5F6', title: '#BBDEFB', subtitle: '#90CAF9', numBg: '#1A2B45', cardBg: '#15243B', date: '#90CAF9', text: '#E3F2FD', muted: '#90A4AE' } },
];

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

function weekHtml(week, palette, theme) {
  const p = palette[theme];
  const days = week.days.map(d => `
    <div class="day">
      <div class="date">${escapeHtml(d.date)}</div>
      <div class="weekday">${escapeHtml(d.weekday)}</div>
      <div class="num">${escapeHtml(d.task)}</div>
      <div class="topic">${escapeHtml(d.topic)}</div>
    </div>`).join('');

  return `<!DOCTYPE html>
<html lang="ru"><head><meta charset="UTF-8"><title>${escapeHtml(week.label)}</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  html, body { width: 1080px; height: 1440px; }
  body { font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; background: ${p.bg}; padding: 70px 60px; }
  .badge { display: inline-block; background: ${p.accent}; color: ${theme === 'dark' ? '#0E1116' : 'white'}; padding: 10px 22px; border-radius: 30px; font-size: 26px; font-weight: 700; letter-spacing: 2px; margin-bottom: 22px; }
  h1 { font-size: 70px; color: ${p.title}; font-weight: 800; margin-bottom: 14px; line-height: 1.05; }
  .subtitle { font-size: ${week.subtitle.length > 30 ? '30px' : '36px'}; color: ${p.subtitle}; font-weight: 600; margin-bottom: 50px; line-height: 1.2; }
  .day { background: ${theme === 'dark' ? p.cardBg : 'white'}; border-radius: 24px; padding: 24px 28px; margin-bottom: 18px; display: flex; align-items: center; box-shadow: ${theme === 'dark' ? '0 4px 14px rgba(0,0,0,0.4)' : '0 4px 14px rgba(0,0,0,0.07)'}; }
  .date { width: 140px; font-size: 32px; font-weight: 800; color: ${p.date}; }
  .weekday { width: 60px; font-size: 26px; color: ${theme === 'dark' ? p.muted : '#888'}; margin-right: 10px; font-weight: 600; }
  .num { background: ${p.numBg}; color: ${theme === 'dark' ? p.title : p.date}; padding: 10px 18px; border-radius: 14px; font-size: 28px; font-weight: 800; margin-right: 22px; min-width: 64px; text-align: center; }
  .topic { font-size: 28px; color: ${theme === 'dark' ? p.text : '#2C2C2C'}; flex: 1; font-weight: 500; }
  .footer { margin-top: 36px; text-align: center; font-size: 22px; color: ${p.subtitle}; font-weight: 600; }
</style></head>
<body>
<div class="badge">${escapeHtml(week.label)}</div>
<h1>${escapeHtml(week.title)}</h1>
<div class="subtitle">${escapeHtml(week.subtitle)}</div>
${days}
<div class="footer">${escapeHtml(week.footer)}</div>
</body></html>`;
}

function coverHtml(theme) {
  const c = PLAN.cover;
  // для обложки берём смешанную палитру — нейтральную, тёмную или светлую
  const isDark = theme === 'dark';
  const bg = isDark ? '#0E1116' : '#FAFAFA';
  const cardBg = isDark ? '#1A1F26' : 'white';
  const accent = isDark ? '#90CAF9' : '#1565C0';
  const title = isDark ? '#FFFFFF' : '#0D47A1';
  const subtitle = isDark ? '#B0BEC5' : '#37474F';
  const text = isDark ? '#ECEFF1' : '#263238';
  const muted = isDark ? '#78909C' : '#607D8B';
  const shadow = isDark ? '0 4px 18px rgba(0,0,0,0.5)' : '0 4px 18px rgba(0,0,0,0.08)';

  return `<!DOCTYPE html>
<html lang="ru"><head><meta charset="UTF-8"><title>Обложка</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  html, body { width: 1080px; height: 1440px; }
  body { font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; background: ${bg}; padding: 80px 70px; display: flex; flex-direction: column; }
  .top { margin-bottom: 60px; }
  .eyebrow { display: inline-block; background: ${accent}; color: ${isDark ? '#0E1116' : 'white'}; padding: 10px 22px; border-radius: 30px; font-size: 24px; font-weight: 700; letter-spacing: 3px; margin-bottom: 30px; }
  h1 { font-size: 92px; color: ${title}; font-weight: 900; line-height: 1.0; margin-bottom: 24px; }
  .subtitle { font-size: 44px; color: ${accent}; font-weight: 600; margin-bottom: 14px; }
  .target { font-size: 36px; color: ${subtitle}; font-weight: 500; }
  .dates { margin-top: 50px; font-size: 32px; color: ${text}; font-weight: 600; }
  .dates .arrow { color: ${accent}; margin: 0 14px; }
  .stats { display: flex; gap: 24px; margin-top: 60px; }
  .stat { flex: 1; background: ${cardBg}; border-radius: 28px; padding: 32px 28px; box-shadow: ${shadow}; }
  .stat .num { font-size: 64px; font-weight: 900; color: ${accent}; line-height: 1; margin-bottom: 10px; }
  .stat .lbl { font-size: 22px; color: ${muted}; font-weight: 600; }
  .deadline { margin-top: auto; text-align: center; padding: 28px; background: ${accent}; border-radius: 24px; }
  .deadline .d { font-size: 28px; font-weight: 700; color: ${isDark ? '#0E1116' : 'white'}; }
  .deadline .s { font-size: 22px; color: ${isDark ? '#0E1116' : 'white'}; opacity: 0.85; margin-top: 6px; }
  .footer { margin-top: 30px; text-align: center; font-size: 22px; color: ${muted}; font-weight: 500; }
</style></head>
<body>
<div class="top">
  <div class="eyebrow">ЕГЭ · 2026</div>
  <h1>${escapeHtml(c.title)}</h1>
  <div class="subtitle">${escapeHtml(c.subtitle)}</div>
  <div class="target">${escapeHtml(c.target)}</div>
  <div class="dates">${escapeHtml(c.date_from)}<span class="arrow">→</span>${escapeHtml(c.date_to)}</div>
</div>
<div class="stats">
  <div class="stat"><div class="num">${c.days_total}</div><div class="lbl">дней</div></div>
  <div class="stat"><div class="num">${c.hours_per_day}</div><div class="lbl">часа в день</div></div>
  <div class="stat"><div class="num">${c.hours_total}</div><div class="lbl">часов всего</div></div>
</div>
<div class="deadline">
  <div class="d">📅 ${escapeHtml(c.deadline)}</div>
  <div class="s">Дедлайн</div>
</div>
<div class="footer">${escapeHtml(c.footer)}</div>
</body></html>`;
}

// Рендер
function write(name, content) {
  const fp = path.join(OUT_DIR, name);
  fs.writeFileSync(fp, content, 'utf8');
  return fp;
}

// Скриншот через Edge/Chrome
function shoot(htmlFile, pngFile) {
  const edge = resolveEdgeBin();
  const udd = path.join(process.env.TEMP || '/tmp', 'edge_' + Date.now() + '_' + Math.random().toString(36).slice(2, 8));
  const url = 'file:///' + htmlFile.replace(/\\/g, '/');
  execSync(`"${edge}" --headless=new --disable-gpu --hide-scrollbars --no-first-run --no-default-browser-check --user-data-dir="${udd}" --force-device-scale-factor=1 --window-size=1080,1440 --screenshot="${pngFile}" "${url}"`, { stdio: 'ignore' });
}

const tasks = [];
const generated = [];

// Cover
themes.forEach(theme => {
  const html = write(`cover_${theme}.html`, coverHtml(theme));
  const png = path.join(OUT_DIR, `cover_${theme}.png`);
  tasks.push({ html, png });
  generated.push(png);
});

// Weeks
(PLAN.weeks || []).forEach((week, i) => {
  themes.forEach(theme => {
    const html = write(`week${i + 1}_${theme}.html`, weekHtml(week, PALETTES[i % PALETTES.length], theme));
    const png = path.join(OUT_DIR, `week${i + 1}_${theme}.png`);
    tasks.push({ html, png });
    generated.push(png);
  });
});

console.log(`Source: ${SOURCE}`);
console.log(`Output: ${OUT_DIR}`);
console.log(`Renders queued: ${tasks.length}`);
let done = 0;
for (const t of tasks) {
  try { shoot(t.html, t.png); done++; console.log(`OK ${path.basename(t.png)}`); }
  catch (e) { console.error(`FAIL ${path.basename(t.png)}: ${e.message}`); }
}
console.log(`Done: ${done}/${tasks.length}`);
console.log(JSON.stringify({ kind: 'plan', outputDir: OUT_DIR, files: generated.map(p => path.basename(p)) }));
