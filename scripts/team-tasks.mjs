#!/usr/bin/env node
// team-tasks.mjs — team orchestration CLI (membership + shared tasks).
//
// Usage:
//   node scripts/team-tasks.mjs team create --user <key> --goal "..." [--telegram-id N] [--username @x]
//   node scripts/team-tasks.mjs team invite --user <key> --team <id> [--telegram-id N] [--username @x]
//   node scripts/team-tasks.mjs team accept --user <key> --code <invite> [--telegram-id N] [--username @x]
//   node scripts/team-tasks.mjs team leave --user <key> --team <id>
//   node scripts/team-tasks.mjs team list --user <key>
//   node scripts/team-tasks.mjs team show --user <key> --team <id>
//   node scripts/team-tasks.mjs invites resolve --user <key> [--telegram-id N] [--username @x]
//   node scripts/team-tasks.mjs task add --user <key> --team <id> --title "..." [--deadline ISO] [--description ...]
//   node scripts/team-tasks.mjs task take --user <key> --team <id> --task <id> [--telegram-id N]
//   node scripts/team-tasks.mjs task submit --user <key> --team <id> --task <id> [--note ...]
//   node scripts/team-tasks.mjs task approve --user <key> --team <id> --task <id>
//   node scripts/team-tasks.mjs task reopen --user <key> --team <id> --task <id> [--reason ...]
//   node scripts/team-tasks.mjs task block --user <key> --team <id> --task <id> --reason "..."
//   node scripts/team-tasks.mjs task unblock --user <key> --team <id> --task <id>
//   node scripts/team-tasks.mjs task list --user <key> --team <id> [--status planned|...|overdue]
//   node scripts/team-tasks.mjs notifications --user <key> --team <id>

import { parseArgs, requireUser, out, die } from "./lib/cli.mjs";
import {
  TeamError,
  createTeam,
  inviteMember,
  acceptInvite,
  resolvePendingInvites,
  leaveTeam,
  listTeams,
  showTeam,
  addTask,
  takeTask,
  submitTask,
  approveTask,
  reopenTask,
  blockTask,
  unblockTask,
  listTasks,
  readNotifications,
  expireStaleInvites,
} from "./lib/team-tasks.mjs";

const { cmd, opts, positional } = parseArgs(process.argv);

function tgId(opts) {
  return opts["telegram-id"] || opts.telegramId || null;
}

function username(opts) {
  return opts.username || null;
}

function teamId(opts) {
  const t = opts.team || opts.t;
  if (!t) die("missing --team <team_id>");
  return t;
}

function taskId(opts) {
  const t = opts.task || opts.id;
  if (!t) die("missing --task <task_id>");
  return t;
}

function handle(err) {
  if (err instanceof TeamError) {
    die(err.message, err.extra);
  }
  throw err;
}

try {
  expireStaleInvites();

  if (!cmd) {
    die("missing subcommand (team|task|invites|notifications)");
  }

  const domain = cmd;
  const action =
    positional[0] ||
    (cmd.includes(".") ? cmd.split(".")[1] : null) ||
    (cmd === "notifications" ? "read" : null);

  if (domain === "team") {
    if (!action) die("missing team action (create|invite|accept|leave|list|show)");
    const userKey = requireUser(opts);
    switch (action) {
      case "create":
        out(
          createTeam({
            userKey,
            telegramId: tgId(opts),
            username: username(opts),
            goal: opts.goal,
          })
        );
        break;
      case "invite":
        out(
          inviteMember({
            userKey,
            teamId: teamId(opts),
            targetTelegramId: tgId(opts),
            targetUsername: username(opts),
          })
        );
        break;
      case "accept":
        out(
          acceptInvite({
            userKey,
            inviteCode: opts.code,
            telegramId: tgId(opts),
            username: username(opts),
          })
        );
        break;
      case "leave":
        out(leaveTeam({ userKey, teamId: teamId(opts) }));
        break;
      case "list":
        out(listTeams(userKey));
        break;
      case "show":
        out(showTeam({ userKey, teamId: teamId(opts) }));
        break;
      default:
        die(`unknown team action: ${action}`);
    }
  } else if (domain === "invites" && action === "resolve") {
    const userKey = requireUser(opts);
    out(
      resolvePendingInvites({
        userKey,
        telegramId: tgId(opts),
        username: username(opts),
      })
    );
  } else if (domain === "task") {
    if (!action) die("missing task action (add|take|submit|approve|reopen|block|unblock|list)");
    const userKey = requireUser(opts);
    const tid = teamId(opts);
    switch (action) {
      case "add":
        out(
          addTask({
            userKey,
            teamId: tid,
            title: opts.title,
            description: opts.description,
            deadline: opts.deadline || null,
          })
        );
        break;
      case "take":
        out(
          takeTask({
            userKey,
            teamId: tid,
            taskId: taskId(opts),
            telegramId: tgId(opts),
          })
        );
        break;
      case "submit":
        out(
          submitTask({
            userKey,
            teamId: tid,
            taskId: taskId(opts),
            note: opts.note,
          })
        );
        break;
      case "approve":
        out(approveTask({ userKey, teamId: tid, taskId: taskId(opts) }));
        break;
      case "reopen":
        out(
          reopenTask({
            userKey,
            teamId: tid,
            taskId: taskId(opts),
            reason: opts.reason,
          })
        );
        break;
      case "block":
        out(
          blockTask({
            userKey,
            teamId: tid,
            taskId: taskId(opts),
            reason: opts.reason,
          })
        );
        break;
      case "unblock":
        out(unblockTask({ userKey, teamId: tid, taskId: taskId(opts) }));
        break;
      case "list":
        out(
          listTasks({
            userKey,
            teamId: tid,
            statusFilter: opts.status || null,
          })
        );
        break;
      default:
        die(`unknown task action: ${action}`);
    }
  } else if (domain === "notifications" || (domain === "notifications.read")) {
    const userKey = requireUser(opts);
    out(readNotifications({ userKey, teamId: teamId(opts) }));
  } else if (domain === "invites" && !action) {
    die("missing invites action (resolve)");
  } else {
    die(`unknown command: ${cmd}`);
  }
} catch (e) {
  handle(e);
}
