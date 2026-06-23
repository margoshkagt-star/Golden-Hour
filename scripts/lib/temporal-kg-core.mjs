// Temporal KG — per-user event graph (events.jsonl + edges.jsonl + topic-index.json).

import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import { readJson } from "./cli.mjs";
import { daysBetween } from "./dates.mjs";

const TZ = "+03:00";
const EVENT_TYPES = new Set([
  "study",
  "solve",
  "checkin",
  "milestone",
  "drift",
  "reflection",
]);
const EDGE_TYPES = new Set([
  "preceded_by",
  "followed_by",
  "same_topic",
  "caused_by",
  "resolves",
  "blocked_by",
  "unblocks",
]);

export function kgDir(userDir) {
  return path.join(userDir, "temporal-kg");
}

function eventsPath(dir) {
  return path.join(dir, "events.jsonl");
}

function edgesPath(dir) {
  return path.join(dir, "edges.jsonl");
}

function indexPath(dir) {
  return path.join(dir, "topic-index.json");
}

function nowISO() {
  const d = new Date();
  const utc = d.getTime() + d.getTimezoneOffset() * 60000;
  const m = new Date(utc + 3 * 3600000);
  const pad = (n) => String(n).padStart(2, "0");
  return `${m.getFullYear()}-${pad(m.getMonth() + 1)}-${pad(m.getDate())}T${pad(m.getHours())}:${pad(m.getMinutes())}:${pad(m.getSeconds())}${TZ}`;
}

function todayLocal() {
  return nowISO().slice(0, 10);
}

function ensureDir(dir) {
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
}

function newEventId() {
  return `e_${Date.now()}_${crypto.randomBytes(3).toString("hex")}`;
}

export function normalizeTopic(topic) {
  return String(topic || "общее")
    .toLowerCase()
    .trim()
    .replace(/\s+/g, " ")
    .replace(/[/\\]+/g, "/");
}

function appendJsonl(p, row) {
  ensureDir(path.dirname(p));
  fs.appendFileSync(p, JSON.stringify(row) + "\n", "utf8");
}

function readEvents(dir) {
  const p = eventsPath(dir);
  if (!fs.existsSync(p)) return [];
  return fs
    .readFileSync(p, "utf8")
    .split("\n")
    .filter(Boolean)
    .map((line) => {
      try {
        return JSON.parse(line);
      } catch {
        return null;
      }
    })
    .filter(Boolean);
}

function readEdges(dir) {
  const p = edgesPath(dir);
  if (!fs.existsSync(p)) return [];
  return fs
    .readFileSync(p, "utf8")
    .split("\n")
    .filter(Boolean)
    .map((line) => {
      try {
        return JSON.parse(line);
      } catch {
        return null;
      }
    })
    .filter(Boolean);
}

function loadIndex(dir) {
  return readJson(indexPath(dir), {});
}

function saveIndex(dir, index) {
  ensureDir(dir);
  fs.writeFileSync(indexPath(dir), JSON.stringify(index, null, 2) + "\n", "utf8");
}

function matchTopicKey(topic, index) {
  const t = normalizeTopic(topic);
  if (index[t]) return t;
  for (const key of Object.keys(index)) {
    if (key === t || key.includes(t) || t.includes(key)) return key;
  }
  return t;
}

function updateTopicIndex(dir, topic, eventId, event) {
  const index = loadIndex(dir);
  const key = matchTopicKey(topic, index);
  const day = (event.ts || nowISO()).slice(0, 10);
  const entry = index[key] || {
    events: [],
    first_seen: day,
    last_seen: day,
    success_count: 0,
    fail_count: 0,
    solve_count: 0,
    drift_count: 0,
    milestone_closed: false,
  };
  if (!entry.events.includes(eventId)) entry.events.push(eventId);
  if (!entry.first_seen || day < entry.first_seen) entry.first_seen = day;
  if (!entry.last_seen || day > entry.last_seen) entry.last_seen = day;

  if (event.type === "solve") {
    entry.solve_count = (entry.solve_count || 0) + 1;
    if (event.result === "success") entry.success_count = (entry.success_count || 0) + 1;
    if (event.result === "fail") entry.fail_count = (entry.fail_count || 0) + 1;
  }
  if (event.type === "drift") entry.drift_count = (entry.drift_count || 0) + 1;
  if (event.type === "milestone" && event.status === "closed") entry.milestone_closed = true;

  index[key] = entry;
  saveIndex(dir, index);
  return key;
}

export function emitEvent(dir, fields) {
  const type = fields.type;
  if (!EVENT_TYPES.has(type)) {
    return { ok: false, error: "invalid_type", allowed: [...EVENT_TYPES] };
  }
  const topic = normalizeTopic(fields.topic || fields.subject || "общее");
  const id = fields.id || newEventId();
  const { link_type, ...rest } = fields;
  const event = {
    id,
    ts: rest.ts || nowISO(),
    type,
    topic,
    ...rest,
  };

  appendJsonl(eventsPath(dir), event);
  const topicKey = updateTopicIndex(dir, topic, id, event);

  if (fields.linked_event) {
    linkEvents(dir, id, fields.linked_event, link_type || "caused_by");
  }

  return { ok: true, event_id: id, topic_key: topicKey, event };
}

export function linkEvents(dir, fromId, toId, edgeType) {
  if (!EDGE_TYPES.has(edgeType)) {
    return { ok: false, error: "invalid_edge", allowed: [...EDGE_TYPES] };
  }
  const row = { from: fromId, to: toId, type: edgeType, ts: nowISO() };
  appendJsonl(edgesPath(dir), row);
  return { ok: true, edge: row };
}

function eventsByIds(dir, ids) {
  const set = new Set(ids);
  return readEvents(dir).filter((e) => set.has(e.id));
}

function edgesForEvents(dir, ids) {
  const set = new Set(ids);
  return readEdges(dir).filter((e) => set.has(e.from) || set.has(e.to));
}

export function queryTopic(dir, topic) {
  const index = loadIndex(dir);
  const key = matchTopicKey(topic, index);
  const entry = index[key];
  if (!entry) {
    return { ok: true, topic: key, found: false, summary: `По теме «${topic}» событий в графе пока нет.` };
  }

  const events = eventsByIds(dir, entry.events).sort((a, b) => a.ts.localeCompare(b.ts));
  const edges = edgesForEvents(
    dir,
    events.map((e) => e.id)
  );
  const solveTotal = entry.solve_count || 0;
  const successRate =
    solveTotal > 0 ? Math.round(((entry.success_count || 0) / solveTotal) * 100) : null;
  const daysSince = entry.last_seen ? daysBetween(entry.last_seen, todayLocal()) : null;

  const timeline = events.map((e) => formatEventLine(e));
  const edgeLines = edges.map((e) => `- ${e.from} → ${e.to} (${e.type})`);

  const summary = [
    `📊 ${key}`,
    "",
    "**Timeline:**",
    ...timeline.map((l) => `- ${l}`),
    "",
    "**Stats:**",
    `- solve: ${solveTotal}, success rate: ${successRate != null ? `${successRate}%` : "—"}`,
    `- drift: ${entry.drift_count || 0}`,
    `- last_seen: ${entry.last_seen}${daysSince != null ? ` (${daysSince} дн. назад)` : ""}`,
    entry.milestone_closed ? "- status: ✅ milestone закрыт" : "- status: в процессе",
    edgeLines.length ? "\n**Связи:**\n" + edgeLines.join("\n") : "",
  ]
    .filter(Boolean)
    .join("\n");

  return {
    ok: true,
    found: true,
    topic_key: key,
    index_entry: entry,
    events,
    edges,
    success_rate: successRate,
    days_since_last: daysSince,
    summary,
  };
}

function formatEventLine(e) {
  const d = e.ts?.slice(0, 16).replace("T", " ") || "—";
  if (e.type === "solve") {
    const icon = e.result === "success" ? "✅" : e.result === "fail" ? "❌" : "·";
    const err = e.error_type ? ` (${e.error_type})` : "";
    const pid = e.problem_id ? ` ${e.problem_id}` : "";
    return `${d} — solve${pid} — ${icon}${err}`;
  }
  if (e.type === "reflection") {
    return `${d} — reflection — ${e.causes || e.cause || e.adaptation || "разбор"}`;
  }
  if (e.type === "checkin") {
    return `${d} — checkin — mood ${e.mood ?? "?"}, topics: ${(e.topics || []).join(", ") || "—"}`;
  }
  if (e.type === "drift") {
    return `${d} — drift — +${e.days_late || "?"} дн.${e.reason ? `: ${e.reason}` : ""}`;
  }
  if (e.type === "milestone") {
    return `${d} — milestone — ${e.status || "update"}`;
  }
  if (e.type === "study") {
    return `${d} — study — ${e.result || "—"}`;
  }
  return `${d} — ${e.type}`;
}

export function queryWindow(dir, fromDate, toDate) {
  const events = readEvents(dir).filter((e) => {
    const d = e.ts?.slice(0, 10);
    return d && d >= fromDate && d <= toDate;
  });
  const byType = {};
  const topics = new Set();
  for (const e of events) {
    byType[e.type] = (byType[e.type] || 0) + 1;
    if (e.topic) topics.add(e.topic);
  }
  return {
    ok: true,
    from: fromDate,
    to: toDate,
    count: events.length,
    by_type: byType,
    topics: [...topics],
    events,
    summary: `За ${fromDate}…${toDate}: ${events.length} событий, тем: ${topics.size}.`,
  };
}

export function queryForgotten(dir, reviewDays = 7) {
  const index = loadIndex(dir);
  const today = todayLocal();
  const forgotten = [];
  for (const [topic, entry] of Object.entries(index)) {
    if (!entry.last_seen) continue;
    const gap = daysBetween(entry.last_seen, today);
    if (gap >= reviewDays && !entry.milestone_closed) {
      forgotten.push({ topic, last_seen: entry.last_seen, days_since: gap, ...entry });
    }
  }
  forgotten.sort((a, b) => b.days_since - a.days_since);
  return {
    ok: true,
    review_days: reviewDays,
    forgotten,
    count: forgotten.length,
    summary:
      forgotten.length > 0
        ? `Забытые темы (≥${reviewDays} дн.): ${forgotten.map((f) => f.topic).join(", ")}`
        : `Все темы трогали за последние ${reviewDays} дн.`,
  };
}

/** Merge KG last_seen into spaced-repetition lookups */
export function topicLastSeenMap(dir) {
  const index = loadIndex(dir);
  const map = {};
  for (const [topic, entry] of Object.entries(index)) {
    if (entry.last_seen) map[topic] = entry.last_seen;
  }
  return map;
}

export function ingestCheckin(dir, { mood, energy, topics, note }) {
  return emitEvent(dir, {
    type: "checkin",
    topic: topics?.[0] || "общее",
    mood,
    energy,
    topics: topics || [],
    note,
  });
}

export function ingestReflection(dir, { topic, what, causes, adaptation, linked_event, deadline, progress_pct }) {
  return emitEvent(dir, {
    type: "reflection",
    topic: topic || "общее",
    what,
    causes,
    adaptation,
    linked_event,
    deadline,
    progress_pct,
    link_type: linked_event ? "caused_by" : undefined,
  });
}

export function ingestSolve(dir, { topic, problem_id, result, error_type, duration_min, linked_fail_event }) {
  const r = emitEvent(dir, {
    type: "solve",
    topic,
    problem_id,
    result,
    error_type,
    duration_min,
  });
  if (linked_fail_event && result === "success" && r.ok) {
    linkEvents(dir, r.event_id, linked_fail_event, "resolves");
  }
  return r;
}

export function ingestDrift(dir, { topic, days_late, reason, linked_event }) {
  return emitEvent(dir, {
    type: "drift",
    topic,
    days_late,
    reason,
    linked_event,
    link_type: linked_event ? "caused_by" : undefined,
  });
}

export function ingestMilestone(dir, { topic, target_date, actual_date, status }) {
  return emitEvent(dir, {
    type: "milestone",
    topic,
    target_date,
    actual_date,
    status,
  });
}

function tsForDate(date, hour = 20) {
  const pad = (n) => String(n).padStart(2, "0");
  return `${date}T${pad(hour)}:00:00${TZ}`;
}

function extractTopicsFromStudied(text) {
  const m = /изучил[аи]?:\s*(.+)/i.exec(text || "");
  if (!m) return [];
  return m[1]
    .split(/[,;]+/)
    .map((t) => t.trim())
    .filter((t) => t.length > 1)
    .slice(0, 8);
}

function eventKey(e) {
  return `${e.ts}|${e.type}|${e.topic}|${e.causes || ""}|${e.what || ""}`;
}

/** Import historical events from progress.md (idempotent via content hash). */
export function importProgress(dir, progressText, opts = {}) {
  if (!progressText?.trim()) {
    return { ok: true, imported: 0, skipped: "no_progress_file" };
  }

  const manifestPath = path.join(dir, "import-manifest.json");
  const hash = crypto.createHash("sha256").update(progressText).digest("hex");
  const manifest = readJson(manifestPath, null);
  if (manifest?.progress_hash === hash && !opts.force) {
    return { ok: true, imported: 0, skipped: "unchanged", manifest };
  }

  const existing = new Set(readEvents(dir).map(eventKey));
  let imported = 0;

  const closedRe = /^-\s+\[x\]\s+(.+?)\s+[—–-]\s+(\d{4}-\d{2}-\d{2})/gim;
  let m;
  while ((m = closedRe.exec(progressText))) {
    const topic = m[1].trim();
    const date = m[2];
    const event = {
      ts: tsForDate(date, 19),
      type: "milestone",
      topic: normalizeTopic(topic),
      status: "closed",
      actual_date: date,
      source: "import-progress",
    };
    if (existing.has(eventKey(event))) continue;
    emitEvent(dir, event);
    existing.add(eventKey(event));
    imported++;
  }

  const sections = progressText.split(/^###\s+/m).slice(1);
  for (const block of sections) {
    const headerLine = block.split("\n")[0].trim();
    const isReflection = /рефлексия/i.test(headerLine);
    const dateMatch = headerLine.match(/^(\d{4}-\d{2}-\d{2})/);
    if (!dateMatch) continue;
    const date = dateMatch[1];
    const body = block.slice(block.indexOf("\n") + 1);

    if (isReflection) {
      const what = /\*\*Что:\*\*\s*(.+)/i.exec(body)?.[1]?.trim();
      const causes = /\*\*Причины[^:]*:\*\*\s*(.+)/i.exec(body)?.[1]?.trim();
      const adaptation = /\*\*Адаптация:\*\*\s*(.+)/i.exec(body)?.[1]?.trim();
      const topic = what || "общее";
      const event = {
        ts: tsForDate(date, 21),
        type: "reflection",
        topic: normalizeTopic(topic),
        what,
        causes,
        adaptation,
        source: "import-progress",
      };
      if (existing.has(eventKey(event))) continue;
      emitEvent(dir, event);
      existing.add(eventKey(event));
      imported++;
      continue;
    }

    const studied = extractTopicsFromStudied(body);
    const blockers = /блокеры?:\s*(.+)/i.exec(body)?.[1]?.trim();
    const event = {
      ts: tsForDate(date, 20),
      type: "checkin",
      topic: studied[0] ? normalizeTopic(studied[0]) : "общее",
      topics: studied,
      note: blockers || undefined,
      source: "import-progress",
    };
    if (existing.has(eventKey(event))) continue;
    emitEvent(dir, event);
    existing.add(eventKey(event));
    imported++;
  }

  const srRe = /\[sr\]\s+([^:]+):\s*done\s+at\s+(\d{4}-\d{2}-\d{2})/gi;
  while ((m = srRe.exec(progressText))) {
    const topic = m[1].trim();
    const date = m[2];
    const event = {
      ts: tsForDate(date, 18),
      type: "study",
      topic: normalizeTopic(topic),
      result: "success",
      source: "import-progress",
    };
    if (existing.has(eventKey(event))) continue;
    emitEvent(dir, event);
    existing.add(eventKey(event));
    imported++;
  }

  atomicWriteJson(manifestPath, {
    schema: "openclaw.temporal-kg.import.v1",
    progress_hash: hash,
    imported_at: nowISO(),
    events_imported: imported,
    total_events: readEvents(dir).length,
  });

  return {
    ok: true,
    imported,
    total_events: readEvents(dir).length,
    topics: Object.keys(loadIndex(dir)).length,
    summary: `Импорт из progress.md: +${imported} событий (всего ${readEvents(dir).length}).`,
  };
}

/** Stats for longterm-stats / dashboards */
export function kgPeriodStats(dir, since, today) {
  const events = readEvents(dir).filter((e) => {
    const d = e.ts?.slice(0, 10);
    return d && (!since || d >= since) && (!today || d <= today);
  });
  const byType = {};
  const topics = new Set();
  for (const e of events) {
    byType[e.type] = (byType[e.type] || 0) + 1;
    if (e.topic) topics.add(e.topic);
  }
  const index = loadIndex(dir);
  return {
    event_count: events.length,
    topics_tracked: Object.keys(index).length,
    topics_active_in_period: topics.size,
    by_type: byType,
  };
}

function atomicWriteJson(p, obj) {
  const tmp = `${p}.tmp`;
  ensureDir(path.dirname(p));
  fs.writeFileSync(tmp, JSON.stringify(obj, null, 2) + "\n", "utf8");
  fs.renameSync(tmp, p);
}
