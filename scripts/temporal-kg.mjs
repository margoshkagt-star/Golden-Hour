#!/usr/bin/env node
// temporal-kg.mjs — event graph for adaptive learning.
//
// Usage:
//   node scripts/temporal-kg.mjs emit --user <key> --type solve --topic "..." --result success
//   node scripts/temporal-kg.mjs link --user <key> --from e_xxx --to e_yyy --edge resolves
//   node scripts/temporal-kg.mjs topic --user <key> --topic "..."
//   node scripts/temporal-kg.mjs window --user <key> --days 14
//   node scripts/temporal-kg.mjs forgotten --user <key> [--days 7]
//   node scripts/temporal-kg.mjs checkin --user <key> --mood 4 --topics "Алгебра,Геометрия"
//   node scripts/temporal-kg.mjs reflection --user <key> --topic "..." --causes "..." --adaptation "..."
//   node scripts/temporal-kg.mjs solve --user <key> --topic "..." --problem-id p_42 --result fail
//   node scripts/temporal-kg.mjs import-progress --user <key> [--force true]
//   node scripts/temporal-kg.mjs import-all [--force true]

import path from "node:path";
import {
  parseArgs,
  requireUser,
  userDir,
  readText,
  out,
  die,
} from "./lib/cli.mjs";
import { loadProfile, getSetupStatus } from "./lib/profile.mjs";
import { resolveToday, addDays } from "./lib/dates.mjs";
import {
  kgDir,
  emitEvent,
  linkEvents,
  queryTopic,
  queryWindow,
  queryForgotten,
  ingestCheckin,
  ingestReflection,
  ingestSolve,
  ingestDrift,
  ingestMilestone,
  importProgress,
  kgPeriodStats,
} from "./lib/temporal-kg-core.mjs";
import { listActiveUsers } from "./lib/users.mjs";

const { cmd, opts } = parseArgs(process.argv);
if (!cmd) die("missing command");

if (cmd === "import-all") {
  const users = listActiveUsers((p) => readText(p));
  const rows = [];
  for (const u of users) {
    const text = readText(path.join(u.dir, "progress.md"), "");
    const r = importProgress(kgDir(u.dir), text, { force: opts.force === "true" });
    rows.push({ user_key: u.user_key, ...r });
  }
  out({
    ok: true,
    users: rows.length,
    results: rows,
    summary: `Импорт KG: ${rows.length} пользователей, +${rows.reduce((s, r) => s + (r.imported || 0), 0)} событий.`,
  });
  process.exit(0);
}

const userKey = requireUser(opts);
const dir = userDir(userKey);
const store = kgDir(dir);

const { exists, profile } = loadProfile(dir, (p) => readText(p));
if (!exists) die("profile not found");
if (getSetupStatus(profile) !== "complete") die("setup_status not complete");

function parseJsonOpt(name) {
  if (!opts[name]) return {};
  try {
    return JSON.parse(opts[name]);
  } catch {
    die(`invalid --${name} JSON`);
  }
}

function splitTopics(s) {
  if (!s) return [];
  return String(s)
    .split(/[,;]+/)
    .map((t) => t.trim())
    .filter(Boolean);
}

let result;
switch (cmd) {
  case "emit": {
    const extra = parseJsonOpt("payload");
    result = emitEvent(store, {
      type: opts.type,
      topic: opts.topic,
      ...extra,
      problem_id: opts["problem-id"] || extra.problem_id,
      result: opts.result || extra.result,
      error_type: opts["error-type"] || extra.error_type,
      linked_event: opts["linked-event"] || extra.linked_event,
      link_type: opts["link-type"] || extra.link_type,
    });
    break;
  }
  case "link":
    result = linkEvents(store, opts.from, opts.to, opts.edge || opts.type);
    break;
  case "topic":
    if (!opts.topic) die("missing --topic");
    result = queryTopic(store, opts.topic);
    break;
  case "window": {
    const today = resolveToday(opts);
    const days = Number(opts.days || 14);
    const from = opts.from || addDays(today, -(days - 1));
    const to = opts.to || today;
    result = queryWindow(store, from, to);
    break;
  }
  case "forgotten":
    result = queryForgotten(store, Number(opts.days || 7));
    break;
  case "checkin":
    result = ingestCheckin(store, {
      mood: opts.mood != null ? Number(opts.mood) : undefined,
      energy: opts.energy != null ? Number(opts.energy) : undefined,
      topics: splitTopics(opts.topics),
      note: opts.note,
    });
    break;
  case "reflection":
    result = ingestReflection(store, {
      topic: opts.topic,
      what: opts.what,
      causes: opts.causes,
      adaptation: opts.adaptation,
      linked_event: opts["linked-event"],
      deadline: opts.deadline,
      progress_pct: opts["progress-pct"] != null ? Number(opts["progress-pct"]) : undefined,
    });
    break;
  case "solve":
    result = ingestSolve(store, {
      topic: opts.topic,
      problem_id: opts["problem-id"],
      result: opts.result,
      error_type: opts["error-type"],
      duration_min: opts["duration-min"] != null ? Number(opts["duration-min"]) : undefined,
      linked_fail_event: opts["linked-fail"],
    });
    break;
  case "drift":
    result = ingestDrift(store, {
      topic: opts.topic,
      days_late: opts["days-late"] != null ? Number(opts["days-late"]) : undefined,
      reason: opts.reason,
      linked_event: opts["linked-event"],
    });
    break;
  case "milestone":
    result = ingestMilestone(store, {
      topic: opts.topic,
      target_date: opts["target-date"],
      actual_date: opts["actual-date"],
      status: opts.status,
    });
    break;
  case "import-progress": {
    const progressText = readText(path.join(dir, "progress.md"), "");
    result = importProgress(store, progressText, { force: opts.force === "true" });
    break;
  }
  default:
    die("unknown command", { cmd });
}

out(result);
if (result.ok === false) process.exit(1);
