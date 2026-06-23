#!/usr/bin/env node
// pomodoro-tick.mjs — tick active pomodoro sessions for all users (cron/heartbeat).
//
// Usage: node scripts/pomodoro-tick.mjs [--dry-run]

import fs from "node:fs";
import path from "node:path";
import { WORKSPACE, parseArgs, out, userDir, readJson } from "./lib/cli.mjs";
import { pomodoroDir, cmdTick } from "./lib/pomodoro-core.mjs";

const { opts } = parseArgs(process.argv);
const dryRun = opts["dry-run"] === "true";
const usersRoot = path.join(WORKSPACE, "users");
const results = [];

if (!fs.existsSync(usersRoot)) {
  out({ ok: true, ticked: 0, results: [] });
  process.exit(0);
}

for (const key of fs.readdirSync(usersRoot)) {
  const dir = userDir(key);
  const session = readJson(path.join(pomodoroDir(dir), "session.json"), null);
  if (!session || !["work", "break", "long_break"].includes(session.phase)) continue;
  if (dryRun) {
    results.push({ user_key: key, dry_run: true, phase: session.phase });
    continue;
  }
  const r = cmdTick(pomodoroDir(dir));
  if (r.notifications?.length) {
    results.push({ user_key: key, notifications: r.notifications, active: r.active });
  }
}

out({
  ok: true,
  ticked: results.length,
  results,
  summary:
    results.length > 0
      ? `Помодоро: ${results.length} сессий с переходом фазы — отправь уведомления из notifications[].`
      : "Активных переходов помодоро нет.",
});
