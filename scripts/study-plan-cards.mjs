#!/usr/bin/env node
// study-plan-cards.mjs — build CardPlan from plan.md + render via study-cards orchestrator.
//
// Usage:
//   node scripts/study-plan-cards.mjs --user <user_key> [--dry-run]

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
import { parsePlanTopics, parsePlanMeta } from "./lib/plan-parse.mjs";
import { CARD_THEME, RENDER_ORCHESTRATOR } from "./lib/card-render.mjs";

const WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"];
const DAY_FLOW = ["теория", "практика", "задачи", "разбор", "закрепление", "повтор", "отдых"];

function purposeLabel(profile) {
  const p = profile.purpose || "study";
  if (p === "exam") return `экзамен — ${profile.exam_subject || "предмет"}`;
  if (p === "olympiad") return `олимпиада — ${profile.olympiad_subject || "предмет"}`;
  return profile.study_topic || "тема";
}

function weekRangeLabel(weeks) {
  if (!weeks) return "—";
  if (weeks.start === weeks.end) return `Нед. ${weeks.start}`;
  return `Нед. ${weeks.start}–${weeks.end}`;
}

function buildWeekDays(topic) {
  return DAY_FLOW.map((step, i) => ({
    date: "—",
    weekday: WEEKDAYS[i],
    task: String(i + 1),
    topic: `${topic.title}: ${step}`,
  }));
}

function buildCardPlan(profile, planText) {
  const meta = parsePlanMeta(planText);
  const topics = parsePlanTopics(planText);
  if (!topics.length) die("no topics in plan.md");

  const name = profile.name || "Ученик";
  const hpw = profile.hours_per_week || meta.hoursPerWeek || 8;
  const totalWeeks =
    meta.totalWeeks || topics.reduce((m, t) => Math.max(m, t.weeks?.end || 0), 0);
  const totalHours = topics.reduce((s, t) => s + (t.hours || 0), 0);
  const hoursPerDay = Math.max(1, Math.round((hpw / 7) * 10) / 10);

  const cover = {
    eyebrow: purposeLabel(profile).toUpperCase(),
    title: `План — ${name}`,
    subtitle: purposeLabel(profile),
    target: profile.deadline ? `Дедлайн ${profile.deadline}` : "Подготовка",
    date_from: meta.created || "старт",
    date_to: meta.deadline || `${totalWeeks} нед.`,
    deadline: profile.deadline || "—",
    days_total: totalWeeks * 7,
    hours_per_day: hoursPerDay,
    hours_total: totalHours || hpw * totalWeeks,
    footer: "Листай → карточки по темам",
  };

  const weeks = topics.map((t, i) => ({
    label: t.title.toUpperCase().includes("ФИНАЛ") ? `ФИНАЛ` : `ТЕМА ${i + 1}`,
    title: weekRangeLabel(t.weeks),
    subtitle: t.title,
    footer: `⏱ ~${t.hours || "—"} ч · ${t.level || "уровень"}`,
    days: buildWeekDays(t),
  }));

  return { cover, weeks };
}

const { opts } = parseArgs(process.argv);
const userKey = requireUser(opts);
const dir = userDir(userKey);
const planPath = path.join(dir, "plan.md");
const cardsDir = path.join(dir, "cards");
const planJsonPath = path.join(cardsDir, "plan.json");

const { exists, profile } = loadProfile(dir, (p) => readText(p));
if (!exists) die("profile not found");
if (getSetupStatus(profile) !== "complete") {
  die("setup_status not complete", { setup_status: getSetupStatus(profile) });
}

const planText = readText(planPath);
if (!planText) {
  die("plan.md not found — run study-plan first", { path: relWorkspacePath(planPath) });
}

const cardPlan = buildCardPlan(profile, planText);
const pngCount = 1 + cardPlan.weeks.length;

if (isDryRun(opts)) {
  out({
    ok: true,
    user_key: userKey,
    dry_run: true,
    card_plan: cardPlan,
    output_dir: relWorkspacePath(cardsDir),
    card_theme: CARD_THEME,
    png_estimate: pngCount,
    summary: `Карточки: обложка + ${cardPlan.weeks.length} тем (~${pngCount} PNG, ${CARD_THEME}).`,
  });
  process.exit(0);
}

if (!fs.existsSync(cardsDir)) fs.mkdirSync(cardsDir, { recursive: true });
writeText(planJsonPath, JSON.stringify(cardPlan, null, 2) + "\n");

try {
  execSync(
    `node "${RENDER_ORCHESTRATOR}" --mode=from-plan-file --source="${planJsonPath}" --output-dir="${cardsDir}" --themes=${CARD_THEME}`,
    { stdio: "pipe", encoding: "utf8" }
  );
} catch (e) {
  die("render failed — нужен Edge/Chrome на хосте", {
    detail: String(e.stderr || e.message || e).slice(0, 300),
  });
}

const suffix = `_${CARD_THEME}.png`;
const pngs = fs
  .readdirSync(cardsDir)
  .filter((f) => f.endsWith(suffix))
  .sort()
  .map((f) => relWorkspacePath(path.join(cardsDir, f)));

out({
  ok: true,
  user_key: userKey,
  output_dir: relWorkspacePath(cardsDir),
  plan_json: relWorkspacePath(planJsonPath),
  card_theme: CARD_THEME,
  png_files: pngs,
  summary: `Готово: ${pngs.length} карточек (${CARD_THEME}). Отправь альбомом в Telegram.`,
});
