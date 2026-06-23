// Core daily-plan builder (shared by daily-plan.mjs and morning-plan.mjs).

import path from "node:path";
import { readText, readJson, writeJson, relWorkspacePath } from "./cli.mjs";
import { loadProfile, getSetupStatus } from "./profile.mjs";
import { getCurrentPlanTopic } from "./plan-parse.mjs";
import { weightTopic, getDailyBudget } from "./task-weighting.mjs";
import { balanceDay, buildGoalId } from "./daily-balancer.mjs";
import { dueTopics, reviewTaskCandidates } from "./spaced-repetition.mjs";
import { studyBlocksForTopic } from "./task-templates.mjs";

export function buildDailyPlan(userKey, userDirPath, date, { dryRun = false } = {}) {
  const { exists, profile } = loadProfile(userDirPath, (p) => readText(p));
  if (!exists) {
    return { ok: false, user_key: userKey, error: "profile not found" };
  }
  if (getSetupStatus(profile) !== "complete") {
    return {
      ok: false,
      user_key: userKey,
      error: "setup_status not complete",
      setup_status: getSetupStatus(profile),
    };
  }

  const planText = readText(path.join(userDirPath, "plan.md"));
  if (!planText) {
    return { ok: false, user_key: userKey, error: "plan.md not found" };
  }

  const { week, topic } = getCurrentPlanTopic(planText, date);
  if (!topic) {
    return { ok: false, user_key: userKey, error: "no topic for current week", week };
  }

  const progressText = readText(path.join(userDirPath, "progress.md"), "");
  const budget = getDailyBudget(profile.daily_load);
  const candidates = [];

  for (const b of studyBlocksForTopic(topic, profile, week)) {
    const w = weightTopic(topic.title, profile, date, {
      est_minutes: b.est_minutes,
      kind: b.kind,
      eff_difficulty: b.difficulty,
    });
    candidates.push({ ...w, title: b.title, kind: b.kind });
  }

  for (const r of reviewTaskCandidates(
    dueTopics(profile, progressText, date, 3),
    profile,
    date
  )) {
    candidates.push(weightTopic(r.title, profile, date, r));
  }

  const recurring = readJson(path.join(userDirPath, "recurring.json"), { items: [] });
  for (const item of recurring.items || []) {
    candidates.push(
      weightTopic(item.title, profile, date, {
        est_minutes: item.est_minutes || 30,
        kind: "recurring",
      })
    );
  }

  const balanced = balanceDay(candidates, budget, date);
  const purpose = profile.purpose || "study";
  const goalId = buildGoalId(topic.title, purpose);
  const topicWeight = weightTopic(topic.title, profile, date);

  const goals = [
    {
      id: goalId,
      title: `${topic.title} (нед. ${week}, eff_p=${topicWeight.eff_priority})`,
      weight: topicWeight.eff_priority,
      deadline: profile.deadline
        ? profile.deadline.length === 7
          ? `${profile.deadline}-01`
          : profile.deadline
        : null,
    },
  ];

  let taskNum = 1;
  const tasks = balanced.tasks.map((t) => ({
    id: `t_${String(taskNum++).padStart(3, "0")}`,
    goal_id: goals[0].id,
    title: t.title,
    scheduled_at: t.scheduled_at,
    est_minutes: t.est_minutes,
    weight: t.eff_priority,
    difficulty: t.eff_difficulty,
    status: "planned",
    snoozed_until: null,
    ...(t.tag ? { tag: t.tag } : {}),
  }));

  const plan = {
    date,
    user_id: userKey,
    goals,
    tasks,
    load: balanced.load,
    meta: {
      week,
      topic: topic.title,
      deferred_count: balanced.deferred.length,
      generated_by: "daily-plan.mjs",
    },
  };

  const outPath = path.join(userDirPath, "plans", `${date}.json`);
  const hours =
    Math.round(tasks.reduce((s, t) => s + t.est_minutes, 0) / 60 * 10) / 10;
  const summary = `План на ${date}: ${tasks.length} задач, ~${hours} ч, нагрузка ${balanced.load.sum_difficulty}/${balanced.load.budget}. Приоритет: ${topic.title}.`;

  if (!dryRun) {
    writeJson(outPath, plan);
  }

  return {
    ok: true,
    user_key: userKey,
    path: relWorkspacePath(outPath),
    plan,
    summary,
    dry_run: dryRun,
    deferred: balanced.deferred.map((d) => d.title),
  };
}
