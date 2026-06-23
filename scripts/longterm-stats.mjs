#!/usr/bin/env node
// longterm-stats.mjs — aggregate stats from tasks.yaml and daily plans.
//
// Usage:
//   node scripts/longterm-stats.mjs --user <user_key> [--period week|month|year|all]

import path from "node:path";
import fs from "node:fs";
import {
  parseArgs,
  requireUser,
  userDir,
  readText,
  readJson,
  out,
  die,
} from "./lib/cli.mjs";
import { loadProfile, getSetupStatus } from "./lib/profile.mjs";
import { resolveToday, daysBetween } from "./lib/dates.mjs";
import { kgPeriodStats } from "./lib/temporal-kg-core.mjs";

const PERIOD_DAYS = { week: 7, month: 30, year: 365, all: null };

function parseTasksYaml(text) {
  if (!text) return [];
  const tasks = [];
  const blocks = text.split(/\n\s*-\s+id:/);
  for (const block of blocks.slice(1)) {
    const chunk = "id:" + block;
    const id = chunk.match(/id:\s*(\d+)/)?.[1];
    const name = chunk.match(/name:\s*(.+)/)?.[1]?.trim();
    const weight = Number(chunk.match(/weight:\s*(\d+)/)?.[1] || 3);
    const progress = Number(chunk.match(/progress:\s*(\d+)/)?.[1] || 0);
    const status = chunk.match(/status:\s*(\w+)/)?.[1] || "planned";
    const task_type = chunk.match(/task_type:\s*(\w+)/)?.[1] || "short";
    const actual = Number(chunk.match(/actual_duration:\s*(\d+)/)?.[1] || 0);
    const estimated = Number(chunk.match(/estimated_duration:\s*(\d+)/)?.[1] || 0);
    const closed_at = chunk.match(/closed_at:\s*(\S+)/)?.[1] || null;
    const deadline = chunk.match(/deadline:\s*(\S+)/)?.[1] || null;
    tasks.push({
      id: id ? +id : tasks.length + 1,
      name,
      weight,
      progress,
      status,
      task_type,
      actual_duration: actual,
      estimated_duration: estimated,
      closed_at,
      deadline,
    });
  }
  return tasks;
}

function aggregatePlans(plansDir, since) {
  let minutes = 0;
  let done = 0;
  let planned = 0;
  if (!fs.existsSync(plansDir)) return { minutes, done, planned };

  for (const f of fs.readdirSync(plansDir)) {
    if (!/^\d{4}-\d{2}-\d{2}\.json$/.test(f)) continue;
    const date = f.replace(".json", "");
    if (since && date < since) continue;
    const plan = readJson(path.join(plansDir, f));
    if (!plan?.tasks) continue;
    for (const t of plan.tasks) {
      planned++;
      if (t.status === "done") {
        done++;
        minutes += t.est_minutes || 0;
      }
    }
  }
  return { minutes, done, planned };
}

function weightProgress(tasks) {
  const active = tasks.filter((t) => t.status !== "done");
  const all = tasks.length ? tasks : [{ weight: 1, progress: 0 }];
  const sumW = all.reduce((s, t) => s + (t.weight || 1), 0);
  const sumWP = all.reduce((s, t) => s + (t.weight || 1) * (t.progress || 0), 0);
  return sumW ? Math.round(sumWP / sumW) : 0;
}

const { opts } = parseArgs(process.argv);
const userKey = requireUser(opts);
const period = opts.period || "week";
const today = resolveToday(opts);
const dir = userDir(userKey);

const { exists, profile } = loadProfile(dir, (p) => readText(p));
if (!exists) die("profile not found");
if (getSetupStatus(profile) !== "complete") die("setup_status not complete");

const days = PERIOD_DAYS[period] ?? 7;
const since = days ? (() => {
  const d = new Date(today + "T12:00:00Z");
  d.setUTCDate(d.getUTCDate() - days + 1);
  return d.toISOString().slice(0, 10);
})() : null;

const tasksYaml = readText(path.join(dir, "tasks.yaml"), "");
const tasks = parseTasksYaml(tasksYaml);
const longTasks = tasks.filter(
  (t) =>
    t.task_type === "long" ||
    (t.deadline && daysBetween(today, t.deadline) > 7)
);

const planStats = aggregatePlans(path.join(dir, "plans"), since);
const pomodoroStats = readJson(path.join(dir, "pomodoro", "stats.json"), null);
let pomodoroMinutes = 0;
if (pomodoroStats?.total_work_minutes_by_date) {
  for (const [date, min] of Object.entries(pomodoroStats.total_work_minutes_by_date)) {
    if (!since || date >= since) pomodoroMinutes += min;
  }
}
const focusDir = path.join(dir, "focus");
let focusMinutes = 0;
if (fs.existsSync(focusDir)) {
  for (const f of fs.readdirSync(focusDir)) {
    if (!f.endsWith(".json")) continue;
    const s = readJson(path.join(focusDir, f));
    if (s?.total_minutes) focusMinutes += s.total_minutes;
  }
}

const hoursActual = Math.round((planStats.minutes + focusMinutes + pomodoroMinutes) / 60 * 10) / 10;
const kgStats = kgPeriodStats(path.join(dir, "temporal-kg"), since, today);
const weightPct = weightProgress(tasks);

const kgPart =
  kgStats.event_count > 0
    ? `, ${kgStats.event_count} событий в графе (${kgStats.topics_active_in_period} тем)`
    : "";

out({
  user_key: userKey,
  period,
  since,
  today,
  tasks: {
    total: tasks.length,
    long_term: longTasks.length,
    weight_progress_pct: weightPct,
  },
  plans: planStats,
  focus_minutes: focusMinutes,
  pomodoro_minutes: pomodoroMinutes,
  temporal_kg: kgStats,
  hours_actual: hoursActual,
  summary: `За ${period}: закрыто ${planStats.done}/${planStats.planned} слотов плана, ~${hoursActual} ч${kgPart}.`,
});
