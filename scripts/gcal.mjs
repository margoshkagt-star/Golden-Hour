#!/usr/bin/env node
// gcal.mjs — Google Calendar engine for the "Золотой час" agent.
// Zero npm deps (node:https/fs/path/crypto). OAuth Device Flow (multi-user).
//
// The Node script does ONLY the Google API plumbing. The agent assembles the
// list of events (from plan/tasks) and interprets pulled changes back.
//
// Commands (all take --user <user_key>):
//   connect        -> start device flow, prints verification url + user code
//   connect:poll   -> poll token endpoint, saves refresh_token on success
//   status         -> connection + counts
//   disconnect     -> remove stored token for the user
//   upsert --file <events.json>  -> create/update events (idempotent by uid)
//   list [--days N] -> list events tagged by this agent (JSON for the agent)
//   delete --uid <uid>           -> delete a single event by its local uid
//
// events.json (for upsert): array of
//   { "uid":"gh:tg-1:daily:2026-06-18:morning", "title":"...",
//     "start":"2026-06-18T10:00:00", "end":"2026-06-18T11:00:00",
//     "allDay":false, "description":"...", "location":"...", "colorId":"5" }
//
// Output: always a single JSON object on stdout: { ok, ... }. Errors -> { ok:false, error }.

import fs from "node:fs";
import path from "node:path";
import https from "node:https";

const TOKEN_URL = "https://oauth2.googleapis.com/token";
const DEVICE_URL = "https://oauth2.googleapis.com/device/code";
const SCOPE = "https://www.googleapis.com/auth/calendar.events";
const API = "https://www.googleapis.com/calendar/v3";
const GH_PREFIX = "gh"; // uid namespace, also extendedProperties.private.gh_uid

// ---------- args ----------
function parseArgs(argv) {
  const cmd = argv[2];
  const opts = {};
  for (let i = 3; i < argv.length; i++) {
    const a = argv[i];
    if (a.startsWith("--")) {
      const k = a.slice(2);
      const v = argv[i + 1] && !argv[i + 1].startsWith("--") ? argv[++i] : "true";
      opts[k] = v;
    }
  }
  return { cmd, opts };
}

function die(error, extra = {}) {
  process.stdout.write(JSON.stringify({ ok: false, error, ...extra }) + "\n");
  process.exit(1);
}
function out(obj) {
  process.stdout.write(JSON.stringify({ ok: true, ...obj }) + "\n");
}

// ---------- paths / config ----------
const WORKSPACE = process.env.GCAL_WORKSPACE || process.cwd();
function userDir(userKey) {
  if (!userKey || !/^[a-zA-Z0-9._-]+$/.test(userKey)) die("invalid --user (user_key)");
  return path.join(WORKSPACE, "users", userKey);
}
function tokenPath(userKey) {
  return path.join(userDir(userKey), "google-calendar.json");
}
function readJson(p, fallback = null) {
  try { return JSON.parse(fs.readFileSync(p, "utf8")); } catch { return fallback; }
}
function writeJson(p, obj) {
  fs.mkdirSync(path.dirname(p), { recursive: true });
  fs.writeFileSync(p, JSON.stringify(obj, null, 2) + "\n", "utf8");
}

// App OAuth client (one per Google Cloud project, shared by all users).
// Type: "TV and Limited Input Device". Provide via env or secrets.json.
function appCreds() {
  let id = process.env.GCAL_CLIENT_ID;
  let secret = process.env.GCAL_CLIENT_SECRET;
  if (!id || !secret) {
    const secretsPath = process.env.GCAL_SECRETS_PATH ||
      path.join(WORKSPACE, "..", "..", "secrets.json");
    const s = readJson(secretsPath, {});
    // accept a few shapes
    id = id || s?.google?.clientId || s?.integrations?.google?.clientId;
    secret = secret || s?.google?.clientSecret || s?.integrations?.google?.clientSecret;
  }
  if (!id || !secret) {
    die("missing Google client id/secret. Set GCAL_CLIENT_ID/GCAL_CLIENT_SECRET " +
        "or add google.clientId / google.clientSecret to secrets.json");
  }
  return { id, secret };
}

// ---------- http ----------
function request(method, url, { headers = {}, body = null } = {}) {
  return new Promise((resolve, reject) => {
    const u = new URL(url);
    const data = body == null ? null
      : (typeof body === "string" ? body : JSON.stringify(body));
    const req = https.request(
      { method, hostname: u.hostname, path: u.pathname + u.search, headers },
      (res) => {
        let buf = "";
        res.on("data", (c) => (buf += c));
        res.on("end", () => {
          let json = null;
          try { json = buf ? JSON.parse(buf) : {}; } catch { json = { raw: buf }; }
          resolve({ status: res.statusCode, json });
        });
      }
    );
    req.on("error", reject);
    if (data) req.write(data);
    req.end();
  });
}
function form(obj) {
  return Object.entries(obj).map(([k, v]) =>
    encodeURIComponent(k) + "=" + encodeURIComponent(v)).join("&");
}

// ---------- auth ----------
async function getAccessToken(userKey) {
  const store = readJson(tokenPath(userKey));
  if (!store || !store.refresh_token) die("user not connected. Run: connect");
  // reuse cached access token if still valid (60s margin)
  if (store.access_token && store.access_expires_at &&
      Date.now() < store.access_expires_at - 60_000) {
    return { token: store.access_token, store };
  }
  const { id, secret } = appCreds();
  const r = await request("POST", TOKEN_URL, {
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: form({
      client_id: id, client_secret: secret,
      refresh_token: store.refresh_token, grant_type: "refresh_token",
    }),
  });
  if (r.status !== 200 || !r.json.access_token) {
    die("token refresh failed", { detail: r.json });
  }
  store.access_token = r.json.access_token;
  store.access_expires_at = Date.now() + (r.json.expires_in || 3600) * 1000;
  writeJson(tokenPath(userKey), store);
  return { token: store.access_token, store };
}

async function cmdConnect(userKey) {
  const { id } = appCreds();
  const r = await request("POST", DEVICE_URL, {
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: form({ client_id: id, scope: SCOPE }),
  });
  if (r.status !== 200 || !r.json.device_code) {
    die("device code request failed", { detail: r.json });
  }
  const store = readJson(tokenPath(userKey)) || {};
  store.pending = {
    device_code: r.json.device_code,
    interval: r.json.interval || 5,
    expires_at: Date.now() + (r.json.expires_in || 1800) * 1000,
  };
  writeJson(tokenPath(userKey), store);
  out({
    action: "connect",
    verification_url: r.json.verification_url,
    user_code: r.json.user_code,
    verification_url_complete: r.json.verification_url_complete || null,
    expires_in_min: Math.round((r.json.expires_in || 1800) / 60),
    next: "after user authorizes, run: connect:poll",
  });
}

async function cmdConnectPoll(userKey) {
  const store = readJson(tokenPath(userKey));
  if (!store?.pending?.device_code) die("no pending connect. Run: connect first");
  if (Date.now() > store.pending.expires_at) {
    delete store.pending; writeJson(tokenPath(userKey), store);
    die("device code expired. Run: connect again");
  }
  const { id, secret } = appCreds();
  const r = await request("POST", TOKEN_URL, {
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: form({
      client_id: id, client_secret: secret,
      device_code: store.pending.device_code,
      grant_type: "urn:ietf:params:oauth:grant-type:device_code",
    }),
  });
  if (r.status === 200 && r.json.refresh_token) {
    store.refresh_token = r.json.refresh_token;
    store.access_token = r.json.access_token;
    store.access_expires_at = Date.now() + (r.json.expires_in || 3600) * 1000;
    store.calendar_id = store.calendar_id || "primary";
    store.connected_at = new Date().toISOString();
    store.events = store.events || {};
    delete store.pending;
    writeJson(tokenPath(userKey), store);
    return out({ action: "connected", calendar_id: store.calendar_id });
  }
  const err = r.json.error;
  if (err === "authorization_pending") return out({ action: "pending", interval: store.pending.interval });
  if (err === "slow_down") {
    store.pending.interval = (store.pending.interval || 5) + 5;
    writeJson(tokenPath(userKey), store);
    return out({ action: "pending", interval: store.pending.interval });
  }
  if (err === "access_denied") { delete store.pending; writeJson(tokenPath(userKey), store); die("user denied access"); }
  die("connect:poll failed", { detail: r.json });
}

function cmdStatus(userKey) {
  const store = readJson(tokenPath(userKey));
  if (!store) return out({ connected: false });
  out({
    connected: !!store.refresh_token,
    pending: !!store.pending,
    calendar_id: store.calendar_id || null,
    connected_at: store.connected_at || null,
    mapped_events: store.events ? Object.keys(store.events).length : 0,
  });
}

function cmdDisconnect(userKey) {
  const p = tokenPath(userKey);
  if (fs.existsSync(p)) fs.rmSync(p);
  out({ action: "disconnected" });
}

// ---------- events ----------
function toGEvent(e, calTz) {
  const ev = {
    summary: e.title || "(без названия)",
    description: (e.description ? e.description + "\n\n" : "") + `[golden-hour:${e.uid}]`,
    extendedProperties: { private: { gh_uid: e.uid } },
  };
  if (e.location) ev.location = e.location;
  if (e.colorId) ev.colorId = String(e.colorId);
  if (e.allDay) {
    ev.start = { date: e.start.slice(0, 10) };
    ev.end = { date: (e.end || e.start).slice(0, 10) };
  } else {
    ev.start = { dateTime: e.start, timeZone: e.timeZone || calTz };
    ev.end = { dateTime: e.end || e.start, timeZone: e.timeZone || calTz };
  }
  return ev;
}

async function cmdUpsert(userKey, opts) {
  if (!opts.file) die("upsert needs --file <events.json>");
  const events = readJson(path.resolve(opts.file));
  if (!Array.isArray(events)) die("events file must be a JSON array");
  const { token, store } = await getAccessToken(userKey);
  const calId = encodeURIComponent(store.calendar_id || "primary");
  const calTz = opts.tz || store.timeZone || "Europe/Moscow";
  store.events = store.events || {};
  const results = [];
  for (const e of events) {
    if (!e.uid || !e.start) { results.push({ uid: e.uid || null, status: "skipped", reason: "uid/start required" }); continue; }
    const body = toGEvent(e, calTz);
    const existingId = store.events[e.uid];
    const method = existingId ? "PATCH" : "POST";
    const url = existingId
      ? `${API}/calendars/${calId}/events/${encodeURIComponent(existingId)}`
      : `${API}/calendars/${calId}/events`;
    const r = await request(method, url, {
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body,
    });
    if (r.status === 200 && r.json.id) {
      store.events[e.uid] = r.json.id;
      results.push({ uid: e.uid, status: existingId ? "updated" : "created", eventId: r.json.id, htmlLink: r.json.htmlLink });
    } else if (existingId && r.status === 404) {
      // mapping stale -> recreate
      delete store.events[e.uid];
      const r2 = await request("POST", `${API}/calendars/${calId}/events`, {
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" }, body,
      });
      if (r2.status === 200 && r2.json.id) {
        store.events[e.uid] = r2.json.id;
        results.push({ uid: e.uid, status: "recreated", eventId: r2.json.id });
      } else results.push({ uid: e.uid, status: "error", detail: r2.json });
    } else {
      results.push({ uid: e.uid, status: "error", detail: r.json });
    }
  }
  writeJson(tokenPath(userKey), store);
  out({ action: "upsert", count: results.length, results });
}

async function cmdList(userKey, opts) {
  const { token, store } = await getAccessToken(userKey);
  const calId = encodeURIComponent(store.calendar_id || "primary");
  const days = parseInt(opts.days || "14", 10);
  const timeMin = new Date(Date.now() - 24 * 3600 * 1000).toISOString();
  const timeMax = new Date(Date.now() + days * 24 * 3600 * 1000).toISOString();
  const q = `?singleEvents=true&orderBy=startTime&showDeleted=true&maxResults=2500` +
    `&timeMin=${encodeURIComponent(timeMin)}&timeMax=${encodeURIComponent(timeMax)}`;
  const r = await request("GET", `${API}/calendars/${calId}/events${q}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (r.status !== 200) die("list failed", { detail: r.json });
  const mapByUid = store.events || {};
  const idToUid = Object.fromEntries(Object.entries(mapByUid).map(([uid, id]) => [id, uid]));
  const items = (r.json.items || []).map((ev) => {
    const uid = ev.extendedProperties?.private?.gh_uid || idToUid[ev.id] || null;
    const title = ev.summary || "";
    const done = /^\s*(✅|\[x\]|done[:\- ])/i.test(title);
    return {
      uid, eventId: ev.id, title, status: ev.status, done,
      start: ev.start?.dateTime || ev.start?.date || null,
      end: ev.end?.dateTime || ev.end?.date || null,
      updated: ev.updated,
    };
  }).filter((x) => x.uid); // only our events
  // detect deletions: mapped uids not present (or cancelled)
  const present = new Set(items.filter((i) => i.status !== "cancelled").map((i) => i.uid));
  const deleted = Object.keys(mapByUid).filter((uid) => {
    const found = items.find((i) => i.uid === uid);
    return found ? found.status === "cancelled" : false;
  });
  out({ action: "list", days, count: items.length, items, deleted });
}

async function cmdDelete(userKey, opts) {
  if (!opts.uid) die("delete needs --uid");
  const { token, store } = await getAccessToken(userKey);
  const calId = encodeURIComponent(store.calendar_id || "primary");
  const id = store.events?.[opts.uid];
  if (!id) die("uid not mapped to any event");
  const r = await request("DELETE", `${API}/calendars/${calId}/events/${encodeURIComponent(id)}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (r.status === 200 || r.status === 204 || r.status === 410) {
    delete store.events[opts.uid];
    writeJson(tokenPath(userKey), store);
    return out({ action: "deleted", uid: opts.uid });
  }
  die("delete failed", { detail: r.json });
}

// ---------- main ----------
const { cmd, opts } = parseArgs(process.argv);
const userKey = opts.user;
try {
  switch (cmd) {
    case "connect": await cmdConnect(userKey); break;
    case "connect:poll": await cmdConnectPoll(userKey); break;
    case "status": cmdStatus(userKey); break;
    case "disconnect": cmdDisconnect(userKey); break;
    case "upsert": await cmdUpsert(userKey, opts); break;
    case "list": await cmdList(userKey, opts); break;
    case "delete": await cmdDelete(userKey, opts); break;
    default:
      die(`unknown command: ${cmd || "(none)"}. ` +
          "Use: connect | connect:poll | status | disconnect | upsert | list | delete");
  }
} catch (e) {
  die("unhandled: " + (e && e.message ? e.message : String(e)));
}
