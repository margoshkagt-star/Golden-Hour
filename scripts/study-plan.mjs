#!/usr/bin/env node
// study-plan.mjs — generate users/<user_key>/plan.md from profile.
//
// Usage:
//   node scripts/study-plan.mjs --user <user_key> [--dry-run] [--force]

import path from "node:path";
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
import { buildStudyPlan } from "./lib/study-plan.mjs";
import { todayISO } from "./lib/dates.mjs";

const { opts } = parseArgs(process.argv);
const userKey = requireUser(opts);
const dir = userDir(userKey);
const planPath = path.join(dir, "plan.md");

const { exists, profile } = loadProfile(dir, (p) => readText(p));
if (!exists) die("profile not found");
if (getSetupStatus(profile) !== "complete") {
  die("setup_status not complete", { setup_status: getSetupStatus(profile) });
}

const existing = readText(planPath);
if (existing && opts.force !== "true" && !isDryRun(opts)) {
  die("plan.md already exists — use --force to overwrite", {
    path: relWorkspacePath(planPath),
  });
}

const result = buildStudyPlan(profile, opts.date || todayISO());
if (result.error) die(result.error);

if (isDryRun(opts)) {
  out({
    user_key: userKey,
    dry_run: true,
    path: relWorkspacePath(planPath),
    meta: result.meta,
    preview: result.markdown.slice(0, 800) + "...",
    markdown: result.markdown,
  });
  process.exit(0);
}

writeText(planPath, result.markdown);

out({
  user_key: userKey,
  path: relWorkspacePath(planPath),
  meta: result.meta,
  summary: `План: ${result.meta.totalWeeks} нед., ${result.meta.totalHours} ч, ${result.meta.topicCount} тем.`,
});
