#!/usr/bin/env node
// pomodoro.mjs — Pomodoro timer engine (per-user state).
//
// Usage:
//   node scripts/pomodoro.mjs start --user <key> [--variant classic|long|extended|short] [--work N --break N]
//   node scripts/pomodoro.mjs status|skip|stop|stats|tick|suggest|mark-dialog --user <key>
//   node scripts/pomodoro.mjs schedule --user <key> [--plan | --from HH:MM --to HH:MM | --hours N] [--variant ...]
//   node scripts/pomodoro.mjs schedule-confirm|schedule-cancel --user <key>
//   node scripts/pomodoro.mjs route --user <key> --text "..."
//   node scripts/pomodoro.mjs variants --user <key>

import {
  parseArgs,
  requireUser,
  userDir,
  readText,
  out,
  die,
} from "./lib/cli.mjs";
import { loadProfile, getSetupStatus } from "./lib/profile.mjs";
import {
  pomodoroDir,
  parseVariantInput,
  cmdStart,
  cmdStatus,
  cmdSkip,
  cmdStop,
  cmdStats,
  cmdTick,
  cmdSuggest,
  cmdMarkDialog,
  cmdSchedule,
  cmdScheduleConfirm,
  cmdScheduleCancel,
  cmdRoute,
  variantsListMessage,
} from "./lib/pomodoro-core.mjs";

const { cmd, opts } = parseArgs(process.argv);
if (!cmd) die("missing command: start|status|skip|stop|stats|tick|suggest|schedule|...");

const userKey = requireUser(opts);
const dir = userDir(userKey);
const pDir = pomodoroDir(dir);

const { exists, profile } = loadProfile(dir, (p) => readText(p));
if (!exists) die("profile not found");
if (getSetupStatus(profile) !== "complete") die("setup_status not complete");

function parsedVariant() {
  let variant = opts.variant;
  let work = opts.work;
  let brk = opts.break;
  if (opts.shorthand) {
    const [w, b] = String(opts.shorthand).split("/");
    work = w;
    brk = b;
    variant = "custom";
  }
  const p = parseVariantInput(variant, work, brk);
  if (!p.ok) {
    out({
      ok: false,
      error: "custom_invalid",
      message:
        "Кастомные тайминги: работа 1–240 мин, отдых 1–60 мин. Например: `/pomodoro start 30/60` или `/pomodoro start custom 30 60`.",
    });
    process.exit(0);
  }
  return p;
}

let result;
switch (cmd) {
  case "start":
    result = cmdStart(pDir, parsedVariant(), { require_dialog: true });
    break;
  case "status":
    result = cmdStatus(pDir);
    break;
  case "skip":
    result = cmdSkip(pDir);
    break;
  case "stop":
    result = cmdStop(pDir);
    break;
  case "stats":
    result = cmdStats(pDir);
    break;
  case "tick":
    result = cmdTick(pDir);
    break;
  case "suggest":
    result = cmdSuggest(pDir, dir, opts);
    break;
  case "mark-dialog":
    result = cmdMarkDialog(pDir);
    break;
  case "schedule":
    result = cmdSchedule(pDir, dir, parsedVariant(), {
      plan: opts.plan === "true",
      from: opts.from,
      to: opts.to,
      hours: opts.hours,
      topic: opts.topic,
      date: opts.date,
    });
    break;
  case "schedule-confirm":
    result = cmdScheduleConfirm(pDir);
    break;
  case "schedule-cancel":
    result = cmdScheduleCancel(pDir);
    break;
  case "route":
    result = cmdRoute(pDir, opts.text || "");
    break;
  case "variants":
    result = { ok: true, message: variantsListMessage() };
    break;
  default:
    die("unknown command", { cmd });
}

out(result);
if (result.ok === false && result.error && !result.message) process.exit(1);
