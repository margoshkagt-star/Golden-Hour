// team-tasks.mjs — team orchestration: membership, invites, shared tasks.
// All timestamps UTC ISO-8601 (+00:00). Storage: data/teams/<team_id>/.

import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import { WORKSPACE, readJson, writeJson } from "./cli.mjs";

const INVITE_TTL_DAYS = 5;
const TASK_STATUSES = new Set([
  "planned",
  "in_progress",
  "awaiting_review",
  "done",
  "blocked",
]);

export function teamsRoot(workspace = WORKSPACE) {
  return path.join(workspace, "data", "teams");
}

export function teamDir(teamId, workspace = WORKSPACE) {
  if (!teamId || !/^team-[a-z0-9-]+$/.test(teamId)) {
    throw new TeamError("invalid team_id");
  }
  return path.join(teamsRoot(workspace), teamId);
}

export function userTeamsPath(userKey, workspace = WORKSPACE) {
  return path.join(workspace, "users", userKey, "teams.json");
}

export class TeamError extends Error {
  constructor(message, extra = {}) {
    super(message);
    this.name = "TeamError";
    this.extra = extra;
  }
}

export function nowUtc() {
  return new Date().toISOString().replace(/\.\d{3}Z$/, "+00:00");
}

export function addDaysUtc(iso, days) {
  const d = new Date(iso.replace(/\+00:00$/, "Z"));
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().replace(/\.\d{3}Z$/, "+00:00");
}

export function isExpiredUtc(iso, ref = nowUtc()) {
  if (!iso) return false;
  return iso <= ref;
}

export function newTeamId() {
  return `team-${crypto.randomBytes(4).toString("hex")}`;
}

export function newInviteCode() {
  return crypto.randomBytes(4).toString("hex");
}

export function newTaskId(nextNum) {
  return `task-${String(nextNum).padStart(3, "0")}`;
}

function readTeamFile(teamId, name, fallback, workspace) {
  return readJson(path.join(teamDir(teamId, workspace), name), fallback);
}

function writeTeamFile(teamId, name, obj, workspace) {
  writeJson(path.join(teamDir(teamId, workspace), name), obj);
}

export function loadMeta(teamId, workspace = WORKSPACE) {
  const meta = readTeamFile(teamId, "meta.json", null, workspace);
  if (!meta?.team_id) throw new TeamError("team not found", { team_id: teamId });
  return meta;
}

export function loadMembers(teamId, workspace = WORKSPACE) {
  return readTeamFile(teamId, "members.json", { members: [] }, workspace);
}

export function loadInvites(teamId, workspace = WORKSPACE) {
  return readTeamFile(teamId, "invites.json", { invites: [] }, workspace);
}

export function loadTasks(teamId, workspace = WORKSPACE) {
  return readTeamFile(teamId, "tasks.json", { tasks: [], next_id: 1 }, workspace);
}

export function loadUserTeams(userKey, workspace = WORKSPACE) {
  return readJson(userTeamsPath(userKey, workspace), { teams: [] });
}

export function saveUserTeams(userKey, data, workspace = WORKSPACE) {
  writeJson(userTeamsPath(userKey, workspace), data);
}

function findMember(membersDoc, userKey) {
  return membersDoc.members.find((m) => m.user_key === userKey) || null;
}

export function assertMember(teamId, userKey, workspace = WORKSPACE) {
  const members = loadMembers(teamId, workspace);
  const m = findMember(members, userKey);
  if (!m) throw new TeamError("not a team member", { team_id: teamId, user_key: userKey });
  return m;
}

export function assertOwner(teamId, userKey, workspace = WORKSPACE) {
  const m = assertMember(teamId, userKey, workspace);
  if (m.role !== "owner") throw new TeamError("owner only", { team_id: teamId });
  return m;
}

function appendNotification(teamId, event, workspace) {
  const line = JSON.stringify({ at: nowUtc(), ...event }) + "\n";
  const p = path.join(teamDir(teamId, workspace), "notifications.log");
  fs.mkdirSync(path.dirname(p), { recursive: true });
  fs.appendFileSync(p, line, "utf8");
}

function syncUserTeamIndex(userKey, teamId, role, joinedAt, workspace) {
  const idx = loadUserTeams(userKey, workspace);
  const existing = idx.teams.find((t) => t.team_id === teamId);
  if (existing) {
    existing.role = role;
    existing.joined_at = joinedAt;
  } else {
    idx.teams.push({ team_id: teamId, role, joined_at: joinedAt });
  }
  saveUserTeams(userKey, idx, workspace);
}

function removeUserTeamIndex(userKey, teamId, workspace) {
  const idx = loadUserTeams(userKey, workspace);
  idx.teams = idx.teams.filter((t) => t.team_id !== teamId);
  saveUserTeams(userKey, idx, workspace);
}

export function computeDisplayStatus(task, ref = nowUtc()) {
  if (
    task.deadline &&
    isExpiredUtc(task.deadline, ref) &&
    task.status !== "done" &&
    task.status !== "awaiting_review"
  ) {
    return "overdue";
  }
  return task.status;
}

export function enrichTask(task, ref = nowUtc()) {
  return {
    ...task,
    display_status: computeDisplayStatus(task, ref),
  };
}

export function listMemberUserKeys(teamId, workspace = WORKSPACE) {
  return loadMembers(teamId, workspace).members.map((m) => m.user_key);
}

export function buildNotifications(teamId, type, payload, workspace = WORKSPACE) {
  const meta = loadMeta(teamId, workspace);
  const members = loadMembers(teamId, workspace);
  const recipients = members.members
    .filter((m) => m.user_key !== payload.exclude_user_key)
    .map((m) => ({
      user_key: m.user_key,
      telegram_id: m.telegram_id,
      username: m.username || null,
    }));
  return {
    team_id: teamId,
    goal: meta.goal,
    type,
    payload,
    recipients,
    message: payload.message || null,
  };
}

export function createTeam({
  userKey,
  telegramId,
  username,
  goal,
  workspace = WORKSPACE,
}) {
  if (!goal?.trim()) throw new TeamError("missing --goal");
  const teamId = newTeamId();
  const at = nowUtc();
  const dir = teamDir(teamId, workspace);
  fs.mkdirSync(dir, { recursive: true });

  writeTeamFile(
    teamId,
    "meta.json",
    {
      team_id: teamId,
      goal: goal.trim(),
      owner_user_key: userKey,
      owner_telegram_id: telegramId ? Number(telegramId) : null,
      created_at: at,
    },
    workspace
  );

  const owner = {
    user_key: userKey,
    telegram_id: telegramId ? Number(telegramId) : null,
    username: username || null,
    role: "owner",
    joined_at: at,
  };

  writeTeamFile(teamId, "members.json", { members: [owner] }, workspace);
  writeTeamFile(teamId, "invites.json", { invites: [] }, workspace);
  writeTeamFile(teamId, "tasks.json", { tasks: [], next_id: 1 }, workspace);
  fs.writeFileSync(path.join(dir, "notifications.log"), "", "utf8");

  syncUserTeamIndex(userKey, teamId, "owner", at, workspace);
  appendNotification(teamId, { type: "team_created", by: userKey }, workspace);

  return {
    team_id: teamId,
    goal: goal.trim(),
    role: "owner",
    created_at: at,
    notifications: buildNotifications(
      teamId,
      "team_created",
      {
        message: `Создана команда «${goal.trim()}». Owner: ${username || userKey}.`,
        exclude_user_key: userKey,
      },
      workspace
    ),
  };
}

export function inviteMember({
  userKey,
  teamId,
  targetTelegramId,
  targetUsername,
  workspace = WORKSPACE,
}) {
  assertOwner(teamId, userKey, workspace);
  const at = nowUtc();
  const expiresAt = addDaysUtc(at, INVITE_TTL_DAYS);
  const code = newInviteCode();

  const invites = loadInvites(teamId, workspace);
  invites.invites.push({
    invite_code: code,
    created_by: userKey,
    target_telegram_id: targetTelegramId ? Number(targetTelegramId) : null,
    target_username: targetUsername || null,
    created_at: at,
    expires_at: expiresAt,
    status: "pending",
  });
  writeTeamFile(teamId, "invites.json", invites, workspace);
  appendNotification(
    teamId,
    {
      type: "invite_created",
      by: userKey,
      invite_code: code,
      target_telegram_id: targetTelegramId || null,
    },
    workspace
  );

  return {
    team_id: teamId,
    invite_code: code,
    expires_at: expiresAt,
    target_telegram_id: targetTelegramId ? Number(targetTelegramId) : null,
    target_username: targetUsername || null,
    summary: `Инвайт ${code} действует до ${expiresAt} UTC.`,
  };
}

function acceptInviteInternal({
  userKey,
  telegramId,
  username,
  invite,
  teamId,
  workspace,
}) {
  const members = loadMembers(teamId, workspace);
  if (findMember(members, userKey)) {
    invite.status = "accepted";
    return { team_id: teamId, already_member: true };
  }

  const at = nowUtc();
  members.members.push({
    user_key: userKey,
    telegram_id: telegramId ? Number(telegramId) : null,
    username: username || null,
    role: "member",
    joined_at: at,
  });
  writeTeamFile(teamId, "members.json", members, workspace);
  invite.status = "accepted";
  invite.accepted_at = at;
  invite.accepted_by = userKey;
  syncUserTeamIndex(userKey, teamId, "member", at, workspace);
  appendNotification(
    teamId,
    { type: "member_joined", user_key: userKey, telegram_id: telegramId || null },
    workspace
  );

  const meta = loadMeta(teamId, workspace);
  return {
    team_id: teamId,
    goal: meta.goal,
    role: "member",
    joined_at: at,
    notifications: buildNotifications(
      teamId,
      "member_joined",
      {
        message: `${username || userKey} вступил(а) в команду «${meta.goal}».`,
        exclude_user_key: userKey,
      },
      workspace
    ),
  };
}

export function acceptInvite({
  userKey,
  inviteCode,
  telegramId,
  username,
  workspace = WORKSPACE,
}) {
  if (!inviteCode) throw new TeamError("missing --code");
  const root = teamsRoot(workspace);
  if (!fs.existsSync(root)) throw new TeamError("invite not found");

  for (const entry of fs.readdirSync(root)) {
    const teamId = entry;
    if (!teamId.startsWith("team-")) continue;
    const invites = loadInvites(teamId, workspace);
    const invite = invites.invites.find(
      (i) => i.invite_code === inviteCode && i.status === "pending"
    );
    if (!invite) continue;
    if (isExpiredUtc(invite.expires_at)) {
      invite.status = "expired";
      writeTeamFile(teamId, "invites.json", invites, workspace);
      throw new TeamError("invite expired", { invite_code: inviteCode });
    }
    const result = acceptInviteInternal({
      userKey,
      telegramId,
      username,
      invite,
      teamId,
      workspace,
    });
    writeTeamFile(teamId, "invites.json", invites, workspace);
    return result;
  }
  throw new TeamError("invite not found", { invite_code: inviteCode });
}

export function resolvePendingInvites({
  userKey,
  telegramId,
  username,
  workspace = WORKSPACE,
}) {
  const root = teamsRoot(workspace);
  const accepted = [];
  if (!fs.existsSync(root)) return { accepted };

  for (const entry of fs.readdirSync(root)) {
    const teamId = entry;
    if (!teamId.startsWith("team-")) continue;
    const invites = loadInvites(teamId, workspace);
    let changed = false;
    for (const invite of invites.invites) {
      if (invite.status !== "pending") continue;
      if (isExpiredUtc(invite.expires_at)) {
        invite.status = "expired";
        changed = true;
        continue;
      }
      const matchId =
        telegramId &&
        invite.target_telegram_id &&
        Number(invite.target_telegram_id) === Number(telegramId);
      const matchUser =
        username &&
        invite.target_username &&
        invite.target_username.replace(/^@/, "").toLowerCase() ===
          username.replace(/^@/, "").toLowerCase();
      if (!matchId && !matchUser) continue;
      const result = acceptInviteInternal({
        userKey,
        telegramId,
        username,
        invite,
        teamId,
        workspace,
      });
      changed = true;
      accepted.push(result);
    }
    if (changed) writeTeamFile(teamId, "invites.json", invites, workspace);
  }
  return { accepted, count: accepted.length };
}

export function leaveTeam({ userKey, teamId, workspace = WORKSPACE }) {
  const member = assertMember(teamId, userKey, workspace);
  const meta = loadMeta(teamId, workspace);
  if (member.role === "owner") {
    throw new TeamError("owner cannot leave; transfer ownership first", {
      team_id: teamId,
    });
  }

  const tasksDoc = loadTasks(teamId, workspace);
  const autoSubmitted = [];
  for (const task of tasksDoc.tasks) {
    if (
      task.assignee_user_key === userKey &&
      task.status === "in_progress"
    ) {
      task.status = "awaiting_review";
      task.submit_at = nowUtc();
      task.submit_note = "auto-submit on member leave";
      autoSubmitted.push(task.id);
    }
  }
  if (autoSubmitted.length) writeTeamFile(teamId, "tasks.json", tasksDoc, workspace);

  const members = loadMembers(teamId, workspace);
  members.members = members.members.filter((m) => m.user_key !== userKey);
  writeTeamFile(teamId, "members.json", members, workspace);
  removeUserTeamIndex(userKey, teamId, workspace);
  appendNotification(teamId, { type: "member_left", user_key: userKey }, workspace);

  return {
    team_id: teamId,
    left: true,
    auto_submitted_tasks: autoSubmitted,
    notifications: buildNotifications(
      teamId,
      "member_left",
      {
        message: `${member.username || userKey} вышел(а) из команды «${meta.goal}».`,
        exclude_user_key: userKey,
        auto_submitted_tasks: autoSubmitted,
      },
      workspace
    ),
  };
}

export function listTeams(userKey, workspace = WORKSPACE) {
  const idx = loadUserTeams(userKey, workspace);
  const teams = [];
  for (const t of idx.teams) {
    try {
      const meta = loadMeta(t.team_id, workspace);
      const members = loadMembers(t.team_id, workspace);
      const tasksDoc = loadTasks(t.team_id, workspace);
      teams.push({
        team_id: t.team_id,
        goal: meta.goal,
        role: t.role,
        joined_at: t.joined_at,
        member_count: members.members.length,
        open_tasks: tasksDoc.tasks.filter((x) => x.status !== "done").length,
      });
    } catch {
      // stale index entry
    }
  }
  return { teams };
}

export function showTeam({ userKey, teamId, workspace = WORKSPACE }) {
  assertMember(teamId, userKey, workspace);
  const meta = loadMeta(teamId, workspace);
  const members = loadMembers(teamId, workspace);
  const tasksDoc = loadTasks(teamId, workspace);
  const ref = nowUtc();
  return {
    team_id: teamId,
    goal: meta.goal,
    owner_user_key: meta.owner_user_key,
    created_at: meta.created_at,
    members: members.members,
    tasks: tasksDoc.tasks.map((t) => enrichTask(t, ref)),
  };
}

export function addTask({
  userKey,
  teamId,
  title,
  description,
  deadline,
  workspace = WORKSPACE,
}) {
  assertMember(teamId, userKey, workspace);
  if (!title?.trim()) throw new TeamError("missing --title");
  const tasksDoc = loadTasks(teamId, workspace);
  const id = newTaskId(tasksDoc.next_id);
  const at = nowUtc();
  const task = {
    id,
    title: title.trim(),
    description: description?.trim() || "",
    status: "planned",
    assignee_user_key: null,
    assignee_telegram_id: null,
    created_by: userKey,
    created_at: at,
    deadline: deadline || null,
    submit_at: null,
    submit_note: null,
    approved_at: null,
    blocked_reason: null,
  };
  tasksDoc.tasks.push(task);
  tasksDoc.next_id += 1;
  writeTeamFile(teamId, "tasks.json", tasksDoc, workspace);
  appendNotification(teamId, { type: "task_added", task_id: id, by: userKey }, workspace);

  const meta = loadMeta(teamId, workspace);
  return {
    task: enrichTask(task),
    notifications: buildNotifications(
      teamId,
      "task_added",
      {
        message: `Новая таска в «${meta.goal}»: «${title.trim()}».`,
        task_id: id,
        exclude_user_key: userKey,
      },
      workspace
    ),
  };
}

function getTask(tasksDoc, taskId) {
  const task = tasksDoc.tasks.find((t) => t.id === taskId);
  if (!task) throw new TeamError("task not found", { task_id: taskId });
  return task;
}

export function takeTask({ userKey, teamId, taskId, telegramId, workspace = WORKSPACE }) {
  assertMember(teamId, userKey, workspace);
  const tasksDoc = loadTasks(teamId, workspace);
  const task = getTask(tasksDoc, taskId);
  if (task.status !== "planned" && task.status !== "blocked") {
    throw new TeamError("task not available to take", {
      task_id: taskId,
      status: task.status,
    });
  }
  if (task.assignee_user_key && task.assignee_user_key !== userKey) {
    throw new TeamError("task already assigned", { task_id: taskId });
  }
  task.status = "in_progress";
  task.assignee_user_key = userKey;
  task.assignee_telegram_id = telegramId ? Number(telegramId) : null;
  task.blocked_reason = null;
  writeTeamFile(teamId, "tasks.json", tasksDoc, workspace);
  appendNotification(
    teamId,
    { type: "task_taken", task_id: taskId, by: userKey },
    workspace
  );

  const meta = loadMeta(teamId, workspace);
  return {
    task: enrichTask(task),
    notifications: buildNotifications(
      teamId,
      "task_taken",
      {
        message: `«${task.title}» взял(а) ${userKey} (команда «${meta.goal}»).`,
        task_id: taskId,
        exclude_user_key: userKey,
      },
      workspace
    ),
  };
}

export function submitTask({
  userKey,
  teamId,
  taskId,
  note,
  workspace = WORKSPACE,
}) {
  assertMember(teamId, userKey, workspace);
  const tasksDoc = loadTasks(teamId, workspace);
  const task = getTask(tasksDoc, taskId);
  if (task.assignee_user_key !== userKey) {
    throw new TeamError("only assignee can submit", { task_id: taskId });
  }
  if (task.status !== "in_progress" && task.status !== "blocked") {
    throw new TeamError("task not in progress", {
      task_id: taskId,
      status: task.status,
    });
  }
  task.status = "awaiting_review";
  task.submit_at = nowUtc();
  task.submit_note = note?.trim() || null;
  writeTeamFile(teamId, "tasks.json", tasksDoc, workspace);
  appendNotification(
    teamId,
    { type: "task_submitted", task_id: taskId, by: userKey },
    workspace
  );

  const meta = loadMeta(teamId, workspace);
  return {
    task: enrichTask(task),
    notifications: buildNotifications(
      teamId,
      "task_submitted",
      {
        message: `«${task.title}» сдана на проверку (команда «${meta.goal}»). Owner: подтвердите.`,
        task_id: taskId,
        exclude_user_key: userKey,
      },
      workspace
    ),
  };
}

export function approveTask({ userKey, teamId, taskId, workspace = WORKSPACE }) {
  assertOwner(teamId, userKey, workspace);
  const tasksDoc = loadTasks(teamId, workspace);
  const task = getTask(tasksDoc, taskId);
  if (task.status !== "awaiting_review") {
    throw new TeamError("task not awaiting review", {
      task_id: taskId,
      status: task.status,
    });
  }
  task.status = "done";
  task.approved_at = nowUtc();
  writeTeamFile(teamId, "tasks.json", tasksDoc, workspace);
  appendNotification(
    teamId,
    { type: "task_approved", task_id: taskId, by: userKey },
    workspace
  );

  const meta = loadMeta(teamId, workspace);
  return {
    task: enrichTask(task),
    notifications: buildNotifications(
      teamId,
      "task_approved",
      {
        message: `«${task.title}» принята ✅ (команда «${meta.goal}»).`,
        task_id: taskId,
      },
      workspace
    ),
  };
}

export function reopenTask({
  userKey,
  teamId,
  taskId,
  reason,
  workspace = WORKSPACE,
}) {
  assertOwner(teamId, userKey, workspace);
  const tasksDoc = loadTasks(teamId, workspace);
  const task = getTask(tasksDoc, taskId);
  if (task.status !== "awaiting_review") {
    throw new TeamError("only awaiting_review can be reopened", {
      task_id: taskId,
      status: task.status,
    });
  }
  task.status = "in_progress";
  task.submit_at = null;
  task.submit_note = reason?.trim() || "reopened by owner";
  task.approved_at = null;
  writeTeamFile(teamId, "tasks.json", tasksDoc, workspace);
  appendNotification(
    teamId,
    { type: "task_reopened", task_id: taskId, by: userKey },
    workspace
  );

  return { task: enrichTask(task) };
}

export function blockTask({
  userKey,
  teamId,
  taskId,
  reason,
  workspace = WORKSPACE,
}) {
  assertMember(teamId, userKey, workspace);
  const tasksDoc = loadTasks(teamId, workspace);
  const task = getTask(tasksDoc, taskId);
  if (task.status === "done") {
    throw new TeamError("cannot block done task", { task_id: taskId });
  }
  task.status = "blocked";
  task.blocked_reason = reason?.trim() || "blocked";
  writeTeamFile(teamId, "tasks.json", tasksDoc, workspace);
  return { task: enrichTask(task) };
}

export function unblockTask({ userKey, teamId, taskId, workspace = WORKSPACE }) {
  assertMember(teamId, userKey, workspace);
  const tasksDoc = loadTasks(teamId, workspace);
  const task = getTask(tasksDoc, taskId);
  if (task.status !== "blocked") {
    throw new TeamError("task not blocked", { task_id: taskId });
  }
  task.status = task.assignee_user_key ? "in_progress" : "planned";
  task.blocked_reason = null;
  writeTeamFile(teamId, "tasks.json", tasksDoc, workspace);
  return { task: enrichTask(task) };
}

export function listTasks({
  userKey,
  teamId,
  statusFilter,
  workspace = WORKSPACE,
}) {
  assertMember(teamId, userKey, workspace);
  const tasksDoc = loadTasks(teamId, workspace);
  const ref = nowUtc();
  let tasks = tasksDoc.tasks.map((t) => enrichTask(t, ref));
  if (statusFilter) {
    tasks = tasks.filter(
      (t) =>
        t.status === statusFilter || t.display_status === statusFilter
    );
  }
  return { team_id: teamId, tasks };
}

export function readNotifications({ userKey, teamId, workspace = WORKSPACE }) {
  assertOwner(teamId, userKey, workspace);
  const p = path.join(teamDir(teamId, workspace), "notifications.log");
  const text = fs.existsSync(p) ? fs.readFileSync(p, "utf8") : "";
  const lines = text
    .trim()
    .split("\n")
    .filter(Boolean)
    .map((l) => {
      try {
        return JSON.parse(l);
      } catch {
        return { raw: l };
      }
    });
  return { team_id: teamId, notifications: lines };
}

export function expireStaleInvites(workspace = WORKSPACE) {
  const root = teamsRoot(workspace);
  let expired = 0;
  if (!fs.existsSync(root)) return { expired };
  for (const entry of fs.readdirSync(root)) {
    if (!entry.startsWith("team-")) continue;
    const invites = loadInvites(entry, workspace);
    let changed = false;
    for (const invite of invites.invites) {
      if (invite.status === "pending" && isExpiredUtc(invite.expires_at)) {
        invite.status = "expired";
        expired++;
        changed = true;
      }
    }
    if (changed) writeTeamFile(entry, "invites.json", invites, workspace);
  }
  return { expired };
}
