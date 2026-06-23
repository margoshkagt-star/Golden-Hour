#!/usr/bin/env node
// spaced-repetition.mjs — list due review topics for a user/day.
//
// Usage:
//   node scripts/spaced-repetition.mjs --user <user_key> [--date YYYY-MM-DD] [--max 3]

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
import { dueTopics, reviewTaskCandidates } from "./lib/spaced-repetition.mjs";
import { resolveToday } from "./lib/dates.mjs";
import { kgDir, topicLastSeenMap } from "./lib/temporal-kg-core.mjs";

const { opts } = parseArgs(process.argv);
const userKey = requireUser(opts);
const date = resolveToday(opts);
const maxDue = opts.max ? Number(opts.max) : 3;
const dir = userDir(userKey);

const { exists, profile } = loadProfile(dir, (p) => readText(p));
if (!exists) die("profile not found");
if (getSetupStatus(profile) !== "complete") {
  die("setup_status not complete");
}

const progressText = readText(path.join(dir, "progress.md"), "");
const kgLastSeen = topicLastSeenMap(kgDir(dir));
const due = dueTopics(profile, progressText, date, maxDue, kgLastSeen);
const candidates = reviewTaskCandidates(due, profile, date);

out({
  user_key: userKey,
  date,
  due,
  candidates,
  count: due.length,
});
