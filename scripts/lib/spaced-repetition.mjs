// Spaced repetition due topics (skills/spaced-repetition).

import { addDays, daysBetween } from "./dates.mjs";
import { isWeakLevel, normalizeLevel } from "./task-weighting.mjs";

const DEFAULT_INTERVALS = {
  zero: 1,
  weak: 3,
  medium: 7,
  strong: 14,
  expert: 30,
};

function intervalForLevel(level, daysToDeadline) {
  const lv = normalizeLevel(level);
  let intervals = { ...DEFAULT_INTERVALS };

  if (daysToDeadline != null && daysToDeadline < 14) {
    intervals = { zero: 1, weak: 2, medium: 4, strong: 7, expert: 14 };
  }
  if (daysToDeadline != null && daysToDeadline < 7) {
    return 1;
  }

  if (lv === "zero" || lv === "с нуля") return intervals.zero;
  if (lv === "weak") return intervals.weak;
  if (lv === "medium" || lv === "средний") return intervals.medium;
  if (lv === "strong") return intervals.strong;
  if (lv === "expert") return intervals.expert;
  if (isWeakLevel(lv)) return intervals.weak;
  return intervals.medium;
}

export function parseProgressReviews(text) {
  const reviews = {};
  if (!text) return reviews;
  const re =
    /(?:last_reviewed|последний повтор).*?["«]([^"»]+)["»].*?(\d{4}-\d{2}-\d{2})/gi;
  let m;
  while ((m = re.exec(text))) {
    reviews[m[1]] = m[2];
  }
  const lineRe = /^-\s+\*\*([^*]+)\*\*.*?(\d{4}-\d{2}-\d{2})/gm;
  while ((m = lineRe.exec(text))) {
    reviews[m[1].trim()] = m[2];
  }
  return reviews;
}

export function dueTopics(profile, progressText, today, maxDue = 3, kgLastSeen = {}) {
  const levelMap =
    profile.exam_topic_levels ||
    profile.olympiad_levels ||
    profile.olympiad_topic_levels ||
    profile.topic_sublevels ||
    {};

  const reviews = parseProgressReviews(progressText);
  const deadline = profile.deadline;
  const daysLeft = deadline
    ? daysBetween(today, deadline.length === 7 ? `${deadline}-01` : deadline)
    : null;

  const due = [];

  for (const [title, level] of Object.entries(levelMap)) {
    const lv = normalizeLevel(level);
    if (lv === "strong" || lv === "expert") continue;

    const interval = intervalForLevel(lv, daysLeft);
    const reviewKey = title;
    const kgKey = Object.keys(kgLastSeen).find(
      (k) => k === title || k.includes(title) || title.includes(k)
    );
    const last =
      reviews[reviewKey] ||
      reviews[title] ||
      (kgKey ? kgLastSeen[kgKey] : null) ||
      profile.started_at ||
      profile.created;
    const nextReview = last ? addDays(last, interval) : today;

    if (nextReview <= today) {
      due.push({
        title,
        level: lv,
        last_reviewed: last || null,
        interval,
        days_overdue: last ? daysBetween(nextReview, today) : 0,
      });
    }
  }

  due.sort((a, b) => (b.days_overdue || 0) - (a.days_overdue || 0));
  return due.slice(0, maxDue);
}

export function reviewTaskCandidates(due, profile, today) {
  return due.map((d) => ({
    title: `[review] Решить 3–5 задач: ${d.title} (уровень ${d.level}, последний повтор ${d.last_reviewed || "—"})`,
    level: d.level,
    kind: "review",
    tag: "review",
    est_minutes: 45,
    eff_priority: 4,
    eff_difficulty: 2,
  }));
}
