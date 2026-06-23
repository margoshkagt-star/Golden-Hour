#!/usr/bin/env node
// run-tests.mjs — team-tasks-install unit tests

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  createTeam,
  inviteMember,
  acceptInvite,
  addTask,
  takeTask,
  submitTask,
  approveTask,
  leaveTeam,
  listTasks,
  resolvePendingInvites,
} from "./lib/team-tasks.mjs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const WORKSPACE = path.resolve(__dirname, "..");

let passed = 0;
let failed = 0;

function assert(cond, msg) {
  if (cond) passed++;
  else {
    failed++;
    console.error(`FAIL: ${msg}`);
  }
}

const ttDir = path.join(WORKSPACE, ".test-team-tasks-" + Date.now());
const prevGh = process.env.GH_WORKSPACE;
process.env.GH_WORKSPACE = ttDir;
fs.mkdirSync(path.join(ttDir, "users"), { recursive: true });

const owner = "tg-100";
const member = "tg-200";
const created = createTeam({
  userKey: owner,
  telegramId: 100,
  username: "@alice",
  goal: "Test team",
  workspace: ttDir,
});
const teamId = created.team_id;
assert(teamId.startsWith("team-"), "team id prefix");

const inv = inviteMember({
  userKey: owner,
  teamId,
  targetTelegramId: 200,
  targetUsername: "@bob",
  workspace: ttDir,
});
assert(inv.invite_code, "invite code");

const joined = acceptInvite({
  userKey: member,
  inviteCode: inv.invite_code,
  telegramId: 200,
  username: "@bob",
  workspace: ttDir,
});
assert(joined.role === "member", "member joined");

const added = addTask({
  userKey: owner,
  teamId,
  title: "Build feature",
  deadline: "2000-01-01T00:00:00+00:00",
  workspace: ttDir,
});
const taskId = added.task.id;
assert(taskId === "task-001", "task id");

const taken = takeTask({
  userKey: member,
  teamId,
  taskId,
  telegramId: 200,
  workspace: ttDir,
});
assert(taken.task.status === "in_progress", "in progress");
assert(taken.task.display_status === "overdue", "overdue computed");

const submitted = submitTask({
  userKey: member,
  teamId,
  taskId,
  note: "done",
  workspace: ttDir,
});
assert(submitted.task.status === "awaiting_review", "submitted");

const approved = approveTask({
  userKey: owner,
  teamId,
  taskId,
  workspace: ttDir,
});
assert(approved.task.status === "done", "approved");

const task2 = addTask({
  userKey: owner,
  teamId,
  title: "Second",
  workspace: ttDir,
});
takeTask({
  userKey: member,
  teamId,
  taskId: task2.task.id,
  telegramId: 200,
  workspace: ttDir,
});
const left = leaveTeam({ userKey: member, teamId, workspace: ttDir });
assert(left.auto_submitted_tasks.includes(task2.task.id), "auto submit on leave");

const resolved = resolvePendingInvites({
  userKey: "tg-300",
  telegramId: 300,
  username: "@carol",
  workspace: ttDir,
});
assert(resolved.count === 0, "no orphan resolve");

try {
  listTasks({ userKey: member, teamId, workspace: ttDir });
  assert(false, "ex-member should not list");
} catch (e) {
  assert(e.message === "not a team member", "isolation");
}

fs.rmSync(ttDir, { recursive: true, force: true });
if (prevGh === undefined) delete process.env.GH_WORKSPACE;
else process.env.GH_WORKSPACE = prevGh;

console.log(`\nTests: ${passed} passed, ${failed} failed`);
process.exit(failed > 0 ? 1 : 0);
