// Pomodoro state machine for golden-hour (per-user storage).

import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import { readJson } from "./cli.mjs";
import { resolveToday } from "./dates.mjs";

const TZ = "+03:00";
export const VARIANTS = {
  classic: { work: 25, break: 5 },
  long: { work: 50, break: 10 },
  extended: { work: 100, break: 20 },
  short: { work: 15, break: 3 },
};
export const LONG_BREAK_EVERY = 4;
export const LONG_BREAK_MINUTES = 15;
const ACTIVE = new Set(["work", "break", "long_break"]);
const DONE_STATUS = new Set(["done", "skipped"]);

export function pomodoroDir(userDir) {
  return path.join(userDir, "pomodoro");
}

function mskDate(d = new Date()) {
  const utc = d.getTime() + d.getTimezoneOffset() * 60000;
  return new Date(utc + 3 * 3600000);
}

export function nowISO(d = new Date()) {
  const m = mskDate(d);
  const pad = (n) => String(n).padStart(2, "0");
  return `${m.getFullYear()}-${pad(m.getMonth() + 1)}-${pad(m.getDate())}T${pad(m.getHours())}:${pad(m.getMinutes())}:${pad(m.getSeconds())}${TZ}`;
}

export function todayLocal(d = new Date()) {
  const m = mskDate(d);
  const pad = (n) => String(n).padStart(2, "0");
  return `${m.getFullYear()}-${pad(m.getMonth() + 1)}-${pad(m.getDate())}`;
}

function parseTs(iso) {
  if (!iso) return NaN;
  return Date.parse(iso);
}

function fmtTime(iso) {
  const m = /T(\d{2}):(\d{2})/.exec(iso || "");
  return m ? `${m[1]}:${m[2]}` : "—";
}

function addMinutesIso(iso, minutes) {
  const t = parseTs(iso) + minutes * 60000;
  return nowISO(new Date(t));
}

function atomicWriteJson(p, obj) {
  const tmp = `${p}.tmp`;
  fs.mkdirSync(path.dirname(p), { recursive: true });
  fs.writeFileSync(tmp, JSON.stringify(obj, null, 2) + "\n", "utf8");
  fs.renameSync(tmp, p);
}

function appendJsonl(p, row) {
  fs.mkdirSync(path.dirname(p), { recursive: true });
  fs.appendFileSync(p, JSON.stringify(row) + "\n", "utf8");
}

function logDir(dir) {
  return path.join(dir, "log");
}

function sessionPath(dir) {
  return path.join(dir, "session.json");
}

function statsPath(dir) {
  return path.join(dir, "stats.json");
}

function pendingPath(dir) {
  return path.join(dir, "schedule-pending.json");
}

function suggestionsPath(dir) {
  return path.join(dir, "suggestions.json");
}

export function loadSession(dir) {
  return readJson(sessionPath(dir), null);
}

function saveSession(dir, session) {
  atomicWriteJson(sessionPath(dir), session);
}

function emptyStats() {
  return {
    schema: "openclaw.pomodoro.stats.v1",
    total_work_minutes_all_time: 0,
    total_cycles_all_time: 0,
    total_work_minutes_by_date: {},
    total_cycles_by_date: {},
    first_credit_at: null,
    last_credit_at: null,
    last_updated: null,
  };
}

function loadStats(dir) {
  return readJson(statsPath(dir), emptyStats());
}

function creditWork(dir, session, credited, planned, elapsed, reason) {
  if (!credited || credited <= 0) return;
  const stats = loadStats(dir);
  const day = todayLocal();
  const now = nowISO();
  stats.total_work_minutes_all_time = (stats.total_work_minutes_all_time || 0) + credited;
  stats.total_cycles_all_time = (stats.total_cycles_all_time || 0) + 1;
  stats.total_work_minutes_by_date[day] = (stats.total_work_minutes_by_date[day] || 0) + credited;
  stats.total_cycles_by_date[day] = (stats.total_cycles_by_date[day] || 0) + 1;
  if (!stats.first_credit_at) stats.first_credit_at = now;
  stats.last_credit_at = now;
  stats.last_updated = now;
  atomicWriteJson(statsPath(dir), stats);
  appendJsonl(path.join(logDir(dir), `${day}-stats.jsonl`), {
    ts: now,
    variant: session?.variant,
    credited_minutes: credited,
    planned_minutes: planned,
    elapsed_minutes: elapsed,
    reason,
  });
}

function elapsedMinutes(session, now = nowISO()) {
  const start = parseTs(session.phase_started_at);
  const end = parseTs(now);
  return Math.max(0, Math.ceil((end - start) / 60000));
}

function workCredit(session, reason, full = false) {
  const planned = session.phase_duration_minutes || session.work_minutes;
  const elapsed = elapsedMinutes(session);
  if (full || reason === "completed" || reason === "drift_recovered") {
    return { credited: planned, planned, elapsed };
  }
  return { credited: Math.min(planned, elapsed), planned, elapsed };
}

function phaseButtons() {
  return [
    [{ text: "Пропустить фазу", callback_data: "pomodoro:skip" }],
    [{ text: "Завершить", callback_data: "pomodoro:stop" }],
  ];
}

function workStartMessage(session) {
  const n = (session.cycles_done || 0) + 1;
  const w = session.phase_duration_minutes || session.work_minutes;
  return `помодоро Помодоро #${n} • время работы • ${w} мин. Погнали!`;
}

function breakStartMessage(session) {
  const n = session.cycles_done || 0;
  const isLong = session.phase === "long_break";
  const m = session.phase_duration_minutes;
  if (isLong) return `🌿 Время большого отдыха • ${m} мин. Погуляй, попей воды.`;
  return `☕ Помодоро #${n} • время отдыха • ${m} мин. Отдыхай!`;
}

function sessionEndMessage(session) {
  const work = session.session_work_minutes || 0;
  return `🏁 Сессия завершена • ${session.cycles_done || 0} циклов • итого ${work} мин работы.`;
}

function statusMessage(session) {
  const phaseRu =
    session.phase === "work"
      ? "время работы"
      : session.phase === "long_break"
        ? "время большого отдыха"
        : "время отдыха";
  const elapsed = elapsedMinutes(session);
  const left = Math.max(0, (session.phase_duration_minutes || 0) - elapsed);
  const variant =
    session.variant === "custom"
      ? `custom ${session.work_minutes}/${session.break_minutes}`
      : session.variant;
  return {
    message: `Сейчас: *${phaseRu}* (${elapsed}/${session.phase_duration_minutes} мин)\nЦиклов сделано: *${session.cycles_done || 0}*\nВариант: ${variant}\nОсталось ~${left} мин`,
    buttons: phaseButtons(),
  };
}

function isActive(session) {
  return session && ACTIVE.has(session.phase);
}

export function parseVariantInput(variant, work, brk) {
  if (variant && VARIANTS[variant]) {
    const v = VARIANTS[variant];
    return { ok: true, variant, work_minutes: v.work, break_minutes: v.break };
  }
  if (work != null && brk != null) {
    const w = Number(work);
    const b = Number(brk);
    if (!Number.isInteger(w) || !Number.isInteger(b) || w < 1 || w > 240 || b < 1 || b > 60) {
      return { ok: false, error: "custom_invalid" };
    }
    return { ok: true, variant: "custom", work_minutes: w, break_minutes: b };
  }
  const v = VARIANTS.classic;
  return { ok: true, variant: "classic", work_minutes: v.work, break_minutes: v.break };
}

function newSession(parsed, opts = {}) {
  const now = nowISO();
  return {
    schema: "openclaw.pomodoro.session.v1",
    variant: parsed.variant,
    phase: "work",
    phase_started_at: now,
    phase_duration_minutes: parsed.work_minutes,
    cycles_done: 0,
    long_break_every: LONG_BREAK_EVERY,
    work_minutes: parsed.work_minutes,
    break_minutes: parsed.break_minutes,
    long_break_minutes: LONG_BREAK_MINUTES,
    started_at: now,
    deferred_count: 0,
    dialog_opened: opts.dialog_opened !== false,
    session_work_minutes: 0,
    mode: opts.mode || null,
    scheduled_blocks: opts.scheduled_blocks || null,
    scheduled_block_index: opts.scheduled_block_index ?? null,
    window_start_at: opts.window_start_at || null,
    window_end_at: opts.window_end_at || null,
    window_topic: opts.window_topic || null,
    window_source: opts.window_source || null,
  };
}

function nextImmediatePhase(session) {
  if (session.phase === "work") {
    const cycles = (session.cycles_done || 0) + 1;
    const isLong = cycles % (session.long_break_every || LONG_BREAK_EVERY) === 0;
    return {
      phase: isLong ? "long_break" : "break",
      phase_duration_minutes: isLong ? session.long_break_minutes : session.break_minutes,
      cycles_done: cycles,
      work_minutes: session.work_minutes,
    };
  }
  return {
    phase: "work",
    phase_duration_minutes: session.work_minutes,
    cycles_done: session.cycles_done,
    work_minutes: session.work_minutes,
  };
}

function transitionImmediate(session, dir, reason, creditReason) {
  const notifications = [];
  if (session.phase === "work") {
    const { credited, planned, elapsed } = workCredit(session, creditReason, creditReason === "drift_recovered");
    session.session_work_minutes = (session.session_work_minutes || 0) + credited;
    creditWork(dir, session, credited, planned, elapsed, creditReason);
  }
  const next = nextImmediatePhase(session);
  const from = session.phase;
  session.phase = next.phase;
  session.phase_started_at = nowISO();
  session.phase_duration_minutes = next.phase_duration_minutes;
  session.cycles_done = next.cycles_done;
  appendJsonl(path.join(logDir(dir), `${todayLocal()}.jsonl`), {
    ts: session.phase_started_at,
    from,
    to: next.phase,
    cycles_done: session.cycles_done,
    deferred: false,
  });
  notifications.push({
    template: next.phase === "work" ? "work-start" : next.phase === "long_break" ? "long-break-start" : "break-start",
    message: next.phase === "work" ? workStartMessage(session) : breakStartMessage(session),
    buttons: phaseButtons(),
  });
  return notifications;
}

function stopSession(session, dir, reason) {
  const notifications = [];
  if (session.phase === "work") {
    const { credited, planned, elapsed } = workCredit(session, "stopped_partial");
    session.session_work_minutes = (session.session_work_minutes || 0) + credited;
    creditWork(dir, session, credited, planned, elapsed, "stopped_partial");
  }
  session.phase = "stopped";
  session.ended_at = nowISO();
  session.ended_reason = reason;
  saveSession(dir, session);
  notifications.push({ template: "session-end", message: sessionEndMessage(session), buttons: null });
  return notifications;
}

export function cmdStart(dir, parsed, opts = {}) {
  const existing = loadSession(dir);
  if (isActive(existing)) {
    return {
      ok: false,
      error: "session_active",
      message: `Сессия уже идёт, ${existing.cycles_done || 0} циклов.`,
    };
  }
  if (opts.require_dialog && existing && existing.dialog_opened === false) {
    return {
      ok: false,
      error: "warmup",
      message:
        "Привет! Чтобы я мог присылать уведомления, сначала нажми /start в этом чате. После этого /pomodoro start заработает.",
    };
  }
  const session = newSession(parsed, { dialog_opened: existing?.dialog_opened !== false });
  saveSession(dir, session);
  return {
    ok: true,
    action: "started",
    message: workStartMessage(session),
    buttons: phaseButtons(),
    summary: `Помодоро запущен (${parsed.variant}, ${parsed.work_minutes}/${parsed.break_minutes}).`,
  };
}

export function cmdStatus(dir) {
  const session = loadSession(dir);
  if (!isActive(session)) {
    return { ok: true, active: false, message: "Сейчас нет активной сессии помодоро. `/pomodoro start classic` — начать." };
  }
  const s = statusMessage(session);
  return { ok: true, active: true, ...s };
}

export function cmdSkip(dir) {
  const session = loadSession(dir);
  if (!isActive(session)) return { ok: false, error: "no_session" };
  const notifications = transitionImmediate(session, dir, "skip", "skipped_partial");
  saveSession(dir, session);
  return { ok: true, action: "skip", notifications, summary: "Фаза пропущена." };
}

export function cmdStop(dir) {
  const session = loadSession(dir);
  if (!isActive(session)) return { ok: false, error: "no_session" };
  const notifications = stopSession(session, dir, "user_stopped");
  return { ok: true, action: "stopped", notifications, summary: "Сессия завершена." };
}

export function cmdStats(dir) {
  const stats = loadStats(dir);
  const day = todayLocal();
  const todayWork = stats.total_work_minutes_by_date?.[day] || 0;
  const todayCycles = stats.total_cycles_by_date?.[day] || 0;
  return {
    ok: true,
    message: `📊 Сегодня: *${todayWork} мин* работы, ${todayCycles} циклов.\nЗа всё время: *${stats.total_work_minutes_all_time || 0} мин* работы, ${stats.total_cycles_all_time || 0} циклов.`,
    stats,
  };
}

export function cmdMarkDialog(dir) {
  const session = loadSession(dir) || {
    schema: "openclaw.pomodoro.session.v1",
    phase: "stopped",
    dialog_opened: true,
  };
  session.dialog_opened = true;
  saveSession(dir, session);
  return { ok: true };
}

export function cmdTick(dir) {
  const session = loadSession(dir);
  if (!isActive(session)) return { ok: true, active: false };

  if (session.mode === "scheduled" && session.scheduled_blocks?.length) {
    return tickScheduled(dir, session);
  }

  const elapsed = elapsedMinutes(session);
  if (elapsed < session.phase_duration_minutes) {
    return { ok: true, active: true, remaining_min: session.phase_duration_minutes - elapsed };
  }

  const notifications = [];
  if (elapsed >= session.phase_duration_minutes * 2) {
    notifications.push(...transitionImmediate(session, dir, "drift", "drift_recovered"));
  } else {
    notifications.push(...transitionImmediate(session, dir, "tick", "completed"));
  }
  saveSession(dir, session);
  return { ok: true, active: true, notifications };
}

function tickScheduled(dir, session) {
  const now = parseTs(nowISO());
  const endAt = parseTs(session.window_end_at);
  if (now >= endAt) {
    const notifications = stopSession(session, dir, "window_complete");
    return { ok: true, active: false, notifications };
  }
  const idx = session.scheduled_block_index ?? 0;
  const block = session.scheduled_blocks[idx];
  if (!block) {
    const notifications = stopSession(session, dir, "window_complete");
    return { ok: true, active: false, notifications };
  }
  const blockEnd = parseTs(block.start_at) + block.duration_minutes * 60000;
  if (now < blockEnd) {
    return { ok: true, active: true, remaining_min: Math.ceil((blockEnd - now) / 60000) };
  }

  const notifications = [];
  if (block.phase === "work") {
    const { credited, planned, elapsed } = workCredit(session, "completed", true);
    session.session_work_minutes = (session.session_work_minutes || 0) + credited;
    creditWork(dir, session, credited, planned, elapsed, "completed");
    session.cycles_done = (session.cycles_done || 0) + 1;
  }

  let nextIdx = idx + 1;
  while (nextIdx < session.scheduled_blocks.length) {
    const nb = session.scheduled_blocks[nextIdx];
    if (parseTs(nb.start_at) + nb.duration_minutes * 60000 <= now) {
      nextIdx++;
      continue;
    }
    break;
  }

  if (nextIdx >= session.scheduled_blocks.length || now >= endAt) {
    notifications.push(...stopSession(session, dir, "window_complete"));
    return { ok: true, active: false, notifications };
  }

  const nb = session.scheduled_blocks[nextIdx];
  session.scheduled_block_index = nextIdx;
  session.phase = nb.phase;
  session.phase_started_at = nb.start_at;
  session.phase_duration_minutes = nb.duration_minutes;
  saveSession(dir, session);
  notifications.push({
    template: nb.phase === "work" ? "work-start" : nb.phase === "long_break" ? "long-break-start" : "break-start",
    message: nb.phase === "work" ? workStartMessage(session) : breakStartMessage(session),
    buttons: phaseButtons(),
  });
  return { ok: true, active: true, notifications };
}

export function generateScheduleBlocks(fromIso, toIso, parsed, strategy = "shrink") {
  const from = parseTs(fromIso);
  const to = parseTs(toIso);
  if (to <= from) return { ok: false, error: "invalid_window" };
  const work = parsed.work_minutes;
  const brk = parsed.break_minutes;
  const minCycle = work + brk;
  if (to - from < work * 60000) return { ok: false, error: "too_short", minCycle };

  const blocks = [];
  let cursor = from;
  let cycles = 0;

  while (cursor < to) {
    let workDur = work;
    if (cursor + workDur * 60000 > to) {
      workDur = Math.floor((to - cursor) / 60000);
      if (workDur < 5) break;
    }
    blocks.push({
      phase: "work",
      start_at: nowISO(new Date(cursor)),
      duration_minutes: workDur,
      shortened: workDur < work,
    });
    cursor += workDur * 60000;
    cycles++;
    if (cursor >= to) break;

    const isLong = cycles % LONG_BREAK_EVERY === 0;
    let breakDur = isLong ? LONG_BREAK_MINUTES : brk;
    let phase = isLong ? "long_break" : "break";
    if (cursor + breakDur * 60000 > to) {
      if (strategy === "drop" && isLong) {
        breakDur = brk;
        phase = "break";
      } else if (strategy === "shrink") {
        breakDur = Math.floor((to - cursor) / 60000);
        if (breakDur <= 0) break;
        if (isLong && breakDur < LONG_BREAK_MINUTES) phase = "break";
      } else {
        breakDur = Math.floor((to - cursor) / 60000);
        if (breakDur <= 0) break;
      }
    }
    blocks.push({
      phase,
      start_at: nowISO(new Date(cursor)),
      duration_minutes: breakDur,
      shortened: phase === "break" ? breakDur < brk : breakDur < LONG_BREAK_MINUTES,
    });
    cursor += breakDur * 60000;
  }

  if (!blocks.some((b) => b.phase === "work")) {
    return { ok: false, error: "too_short", minCycle };
  }
  return { ok: true, blocks, cycles: blocks.filter((b) => b.phase === "work").length };
}

function readTodayPlan(userDir, today) {
  const p = path.join(userDir, "plans", `${today}.json`);
  return readJson(p, null);
}

function planTaskWindow(task) {
  const start = task.scheduled_at;
  const dur = task.est_minutes || task.duration || 60;
  const end = addMinutesIso(start, dur);
  return { start, end, topic: task.title || task.name || "задача", duration: dur };
}

export function findPlanWindow(userDir, today) {
  const plan = readTodayPlan(userDir, today);
  if (!plan?.tasks?.length) return null;
  const now = parseTs(nowISO());
  const open = plan.tasks.filter((t) => !DONE_STATUS.has(t.status));
  let current = null;
  let next = null;
  for (const t of open) {
    const w = planTaskWindow(t);
    const s = parseTs(w.start);
    const e = parseTs(w.end);
    if (now >= s && now < e) current = w;
    if (s > now && (!next || s < parseTs(next.start))) next = w;
  }
  return current || next;
}

export function isPlanBehind(userDir, today, opts = {}) {
  const plan = readTodayPlan(userDir, today);
  if (!plan?.tasks?.length) return { behind: false, reason: "no_plan" };
  const overdueMin = opts.overdue_minutes ?? 60;
  const threshold = opts.completion_threshold ?? 0.4;
  const checkAfter = opts.check_after ?? "14:00";
  const now = nowISO();
  const nowH = /T(\d{2}):(\d{2})/.exec(now);
  const afterH = checkAfter.split(":").map(Number);
  const pastCheck =
    nowH && Number(nowH[1]) * 60 + Number(nowH[2]) >= afterH[0] * 60 + (afterH[1] || 0);

  const tasks = plan.tasks;
  let overdue = false;
  for (const t of tasks) {
    if (DONE_STATUS.has(t.status)) continue;
    const sched = t.scheduled_at;
    if (!sched) continue;
    const late = Math.ceil((parseTs(now) - parseTs(sched)) / 60000);
    if (late > overdueMin) {
      overdue = true;
      break;
    }
  }
  const done = tasks.filter((t) => t.status === "done").length;
  const rate = tasks.length ? done / tasks.length : 1;
  if (overdue) return { behind: true, reason: "overdue" };
  if (pastCheck && rate < threshold) return { behind: true, reason: "low_completion" };
  return { behind: false, reason: "plan_ok" };
}

function formatScheduleProposal(blocks, from, to, topic) {
  const lines = blocks.map((b) => {
    const end = addMinutesIso(b.start_at, b.duration_minutes);
    const emoji = b.phase === "work" ? "🔴" : b.phase === "long_break" ? "🌿" : "🟢";
    const label = b.phase === "work" ? "работа" : b.phase === "long_break" ? "большой перерыв" : "перерыв";
    const short = b.shortened ? " (укороченный)" : "";
    return `${emoji} ${fmtTime(b.start_at)}–${fmtTime(end)} ${label} (${b.duration_minutes} мин)${short}`;
  });
  const workMin = blocks.filter((b) => b.phase === "work").reduce((s, b) => s + b.duration_minutes, 0);
  const breakMin = blocks.filter((b) => b.phase !== "work").reduce((s, b) => s + b.duration_minutes, 0);
  const cycles = blocks.filter((b) => b.phase === "work").length;
  const h = Math.floor(workMin / 60);
  const m = workMin % 60;
  const workStr = h ? `${h}ч ${m ? `${m}м` : ""}`.trim() : `${workMin} мин`;
  return `🗓 Расписание по плану (${fmtTime(from)}–${fmtTime(to)}, ${topic}):\n\n${lines.join("\n")}\n\nИтого: ${workStr} работы, ${breakMin} мин перерывов, ${cycles} циклов.\n\nПодойдёт? Или скажи другое время.`;
}

export function cmdSchedule(dir, userDir, parsed, opts = {}) {
  const existing = loadSession(dir);
  if (isActive(existing)) {
    return { ok: false, error: "session_active", message: "Сессия уже идёт." };
  }
  const today = resolveToday(opts);
  let from;
  let to;
  let topic = opts.topic || "";
  let source = "user";

  if (opts.plan) {
    const w = findPlanWindow(userDir, today);
    if (!w) {
      return {
        ok: false,
        error: "no_plan",
        message:
          "В плане на сегодня нет подходящего блока. Скажи время вручную:\n• `/pomodoro schedule 15:00-17:00`\n• `/pomodoro schedule 2h`\n• `/pomodoro start classic`",
      };
    }
    from = w.start;
    to = w.end;
    topic = w.topic;
    source = "plan";
  } else if (opts.hours) {
    from = nowISO();
    to = addMinutesIso(from, Number(opts.hours) * 60);
    source = "duration";
  } else if (opts.from && opts.to) {
    const day = today;
    from = opts.from.includes("T") ? opts.from : `${day}T${opts.from}:00${TZ}`;
    to = opts.to.includes("T") ? opts.to : `${day}T${opts.to}:00${TZ}`;
    if (parseTs(to) <= parseTs(from)) to = addMinutesIso(from, 120);
  } else {
    return { ok: false, error: "missing_window", message: "Укажи окно: `--plan`, `--from 15:00 --to 17:00` или `--hours 2`." };
  }

  const gen = generateScheduleBlocks(from, to, parsed);
  if (!gen.ok) {
    return {
      ok: false,
      error: gen.error,
      message: `Окно слишком маленькое для ${parsed.variant}. Попробуй /pomodoro start short или большее окно.`,
    };
  }

  const proposal = {
    schema: "openclaw.pomodoro.schedule-pending.v1",
    proposal_id: `prop-${Date.now()}-${crypto.randomBytes(3).toString("hex")}`,
    created_at: nowISO(),
    expires_at: addMinutesIso(nowISO(), 30),
    window_start_at: from,
    window_end_at: to,
    window_topic: topic,
    window_source: source,
    variant: parsed.variant,
    work_minutes: parsed.work_minutes,
    break_minutes: parsed.break_minutes,
    scheduled_blocks: gen.blocks.map(({ phase, start_at, duration_minutes }) => ({
      phase,
      start_at,
      duration_minutes,
    })),
  };
  atomicWriteJson(pendingPath(dir), proposal);
  return {
    ok: true,
    action: "schedule_proposed",
    message: formatScheduleProposal(gen.blocks, from, to, topic || "работа"),
    buttons: [
      [{ text: "Подтвердить", callback_data: "pomodoro:schedule:confirm" }],
      [{ text: "Изменить", callback_data: "pomodoro:schedule:edit" }],
      [{ text: "Отмена", callback_data: "pomodoro:schedule:cancel" }],
    ],
    proposal_id: proposal.proposal_id,
  };
}

export function cmdScheduleConfirm(dir) {
  const pending = readJson(pendingPath(dir), null);
  if (!pending) return { ok: false, error: "no_proposal" };
  if (parseTs(pending.expires_at) < parseTs(nowISO())) {
    fs.unlinkSync(pendingPath(dir));
    return { ok: false, error: "expired" };
  }
  const parsed = {
    variant: pending.variant,
    work_minutes: pending.work_minutes,
    break_minutes: pending.break_minutes,
  };
  const first = pending.scheduled_blocks[0];
  const session = newSession(parsed, {
    mode: "scheduled",
    scheduled_blocks: pending.scheduled_blocks,
    scheduled_block_index: 0,
    window_start_at: pending.window_start_at,
    window_end_at: pending.window_end_at,
    window_topic: pending.window_topic,
    window_source: pending.window_source,
  });
  session.phase = first.phase;
  session.phase_started_at = first.start_at;
  session.phase_duration_minutes = first.duration_minutes;
  saveSession(dir, session);
  fs.unlinkSync(pendingPath(dir));
  const msg =
    first.phase === "work" ? workStartMessage(session) : breakStartMessage(session);
  return {
    ok: true,
    action: "schedule_started",
    message: msg,
    buttons: phaseButtons(),
    summary: `Запланированная сессия: ${pending.window_topic || "работа"}.`,
  };
}

export function cmdScheduleCancel(dir) {
  const p = pendingPath(dir);
  if (fs.existsSync(p)) fs.unlinkSync(p);
  return {
    ok: true,
    message: "Окей, расписание отменено. Скажи, когда будешь готов(а) — `/pomodoro start` или `/pomodoro schedule`.",
  };
}

export function cmdSuggest(dir, userDir, opts = {}) {
  const session = loadSession(dir);
  if (isActive(session)) return { ok: true, fired: false, reason: "session_active" };
  const today = todayLocal();
  const sug = readJson(suggestionsPath(dir), null);
  if (sug?.last_suggestion_date === today) return { ok: true, fired: false, reason: "cap_hit" };
  const behind = isPlanBehind(userDir, today, opts);
  if (!behind.behind) return { ok: true, fired: false, reason: behind.reason };
  const message =
    "Вижу, что план на сегодня подгоняет. Хочешь попробовать `/pomodoro start classic` — 25 минут сфокусированной работы?";
  atomicWriteJson(suggestionsPath(dir), {
    schema: "openclaw.pomodoro.suggestions.v1",
    last_suggestion_date: today,
    last_suggestion_at: nowISO(),
    total_sent_today: 1,
    total_sent_all_time: (sug?.total_sent_all_time || 0) + 1,
  });
  appendJsonl(path.join(logDir(dir), `${today}-suggestions.jsonl`), {
    ts: nowISO(),
    fired: true,
    reason: "sent",
  });
  return { ok: true, fired: true, message, reason: "sent" };
}

const POMODORO_RE =
  /(?:^\/pomodoro\b|помодоро|pomodoro\s+(?:start|stop|skip|status|stats|schedule|variants))/i;

export function cmdRoute(dir, text) {
  const session = loadSession(dir);
  const t = String(text || "").trim();
  if (t.startsWith("callback_data:")) {
    if (/pomodoro:/i.test(t)) return { ok: true, is_pomodoro: true };
    if (isActive(session)) {
      const elapsed = elapsedMinutes(session);
      const left = Math.max(0, (session.phase_duration_minutes || 0) - elapsed);
      const phaseRu =
        session.phase === "work" ? "время работы" : session.phase === "long_break" ? "время большого отдыха" : "время отдыха";
      return {
        ok: true,
        dnd: true,
        message: `Сейчас идёт *${phaseRu}* (осталось ~${left} мин) — сфокусируйся, отвечу после помодоро`,
      };
    }
    return { ok: true, dnd: false };
  }
  if (POMODORO_RE.test(t) || /^\/pomodoro/i.test(t)) return { ok: true, is_pomodoro: true };
  if (isActive(session)) {
    const elapsed = elapsedMinutes(session);
    const left = Math.max(0, (session.phase_duration_minutes || 0) - elapsed);
    const phaseRu =
      session.phase === "work" ? "время работы" : session.phase === "long_break" ? "время большого отдыха" : "время отдыха";
    appendJsonl(path.join(logDir(dir), `${todayLocal()}-dnd.jsonl`), {
      ts: nowISO(),
      message_kind: "text",
      preview: t.slice(0, 60),
    });
    return {
      ok: true,
      dnd: true,
      message: `Сейчас идёт *${phaseRu}* (осталось ~${left} мин) — сфокусируйся, отвечу после помодоро`,
    };
  }
  return { ok: true, dnd: false };
}

export function variantsListMessage() {
  return `Доступные варианты:
помодоро classic — 25/5
помодоро long — 50/10
помодоро extended — 100/20 (1ч40м / 20м)
помодоро short — 15/3
⚙️ custom — работа 1–240 мин, отдых 1–60 мин. Например: \`/pomodoro start 30/60\`.`;
}
