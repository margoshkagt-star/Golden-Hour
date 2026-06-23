#!/usr/bin/env node
// session-start.mjs — determine user phase and profile snapshot.
//
// Usage:
//   node scripts/session-start.mjs --user <user_key> [--telegram-id N] [--username @x]
//
// Output: { ok, status, profile_summary, paths, actions }

import path from "node:path";
import fs from "node:fs";
import {
  WORKSPACE,
  parseArgs,
  requireUser,
  userDir,
  readText,
  relWorkspacePath,
  out,
  die,
} from "./lib/cli.mjs";
import {
  loadProfile,
  getSetupStatus,
  getTopicsFromProfile,
} from "./lib/profile.mjs";
import { kgDir } from "./lib/temporal-kg-core.mjs";
import { resolvePendingInvites } from "./lib/team-tasks.mjs";

const { opts } = parseArgs(process.argv);
const userKey = requireUser(opts);
const dir = userDir(userKey);
const { exists, profile } = loadProfile(dir, (p) => readText(p));

const telegramId = opts["telegram-id"] || opts.telegramId || null;
const telegramUsername = opts.username || null;

function resolveTeamInvites() {
  if (!telegramId && !telegramUsername) return null;
  try {
    return resolvePendingInvites({
      userKey,
      telegramId: telegramId ? Number(telegramId) : null,
      username: telegramUsername,
    });
  } catch {
    return { accepted: [], count: 0, error: true };
  }
}

const teamInvitesResolveCmd =
  telegramId || telegramUsername
    ? `node scripts/team-tasks.mjs invites resolve --user ${userKey}${telegramId ? ` --telegram-id ${telegramId}` : ""}${telegramUsername ? ` --username ${telegramUsername}` : ""}`
    : null;

if (!exists) {
  const team_invites = resolveTeamInvites();
  out({
    user_key: userKey,
    status: "new",
    setup_status: "new",
    action: "onboarding",
    message: "Новый пользователь — запустить hello-intro",
    paths: { profile: relWorkspacePath(path.join(dir, "profile.md")) },
    team_invites,
    team_invites_resolve_cmd: teamInvitesResolveCmd,
  });
  process.exit(0);
}

const setupStatus = getSetupStatus(profile);
const topics = getTopicsFromProfile(profile);

const summary = {
  name: profile.name,
  purpose: profile.purpose,
  deadline: profile.deadline,
  hours_per_week: profile.hours_per_week,
  daily_load: profile.daily_load,
  topic_count: topics.length,
};

let action = "onboarding";
if (setupStatus === "complete") action = "menu_continue_or_reset";
else if (setupStatus === "in_progress") action = "resume_setup_or_reset";

const files = {
  profile: relWorkspacePath(path.join(dir, "profile.md")),
  plan: readText(path.join(dir, "plan.md"))
    ? relWorkspacePath(path.join(dir, "plan.md"))
    : null,
  progress: readText(path.join(dir, "progress.md"))
    ? relWorkspacePath(path.join(dir, "progress.md"))
    : null,
  tasks: readText(path.join(dir, "tasks.md"))
    ? relWorkspacePath(path.join(dir, "tasks.md"))
    : null,
};

let kg_import_recommended = false;
if (setupStatus === "complete" && files.progress) {
  const ep = path.join(kgDir(dir), "events.jsonl");
  if (!fs.existsSync(ep) || !readText(ep, "").trim()) {
    kg_import_recommended = true;
  }
}

const team_invites = resolveTeamInvites();

out({
  user_key: userKey,
  status: setupStatus === "complete" ? "returning" : setupStatus,
  setup_status: setupStatus,
  action,
  profile_summary: summary,
  paths: files,
  kg_import_recommended,
  kg_import_cmd: kg_import_recommended
    ? `node scripts/temporal-kg.mjs import-progress --user ${userKey}`
    : null,
  team_invites,
  team_invites_resolve_cmd: teamInvitesResolveCmd,
});
