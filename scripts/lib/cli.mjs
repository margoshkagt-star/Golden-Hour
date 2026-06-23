#!/usr/bin/env node
// Shared CLI helpers for golden-hour scripts (same contract as gcal.mjs).

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export const WORKSPACE =
  process.env.GH_WORKSPACE ||
  path.resolve(__dirname, "..", "..");

export function parseArgs(argv) {
  let start = 2;
  let cmd = null;
  if (argv[2] && !argv[2].startsWith("--")) {
    cmd = argv[2];
    start = 3;
  }
  const opts = {};
  const positional = [];
  for (let i = start; i < argv.length; i++) {
    const a = argv[i];
    if (a.startsWith("--")) {
      const k = a.slice(2);
      const v =
        argv[i + 1] && !argv[i + 1].startsWith("--") ? argv[++i] : "true";
      opts[k] = v;
    } else {
      positional.push(a);
    }
  }
  return { cmd, opts, positional };
}

export function die(error, extra = {}) {
  process.stdout.write(JSON.stringify({ ok: false, error, ...extra }) + "\n");
  process.exit(1);
}

export function out(obj) {
  process.stdout.write(JSON.stringify({ ok: true, ...obj }) + "\n");
}

export function userDir(userKey) {
  if (!userKey || !/^[a-zA-Z0-9._-]+$/.test(userKey)) {
    die("invalid --user (user_key)");
  }
  return path.join(WORKSPACE, "users", userKey);
}

/** Relative path from workspace root (POSIX slashes) for agent JSON — not for user chat. */
export function relWorkspacePath(absPath) {
  if (!absPath) return null;
  const rel = path.relative(WORKSPACE, absPath);
  if (rel.startsWith("..") || path.isAbsolute(rel)) return null;
  return rel.split(path.sep).join("/");
}

export function requireUser(opts) {
  const user = opts.user || opts.u;
  if (!user) die("missing --user <user_key>");
  return user;
}

export function readText(p, fallback = null) {
  try {
    return fs.readFileSync(p, "utf8");
  } catch {
    return fallback;
  }
}

export function readJson(p, fallback = null) {
  try {
    return JSON.parse(fs.readFileSync(p, "utf8"));
  } catch {
    return fallback;
  }
}

export function writeJson(p, obj) {
  fs.mkdirSync(path.dirname(p), { recursive: true });
  fs.writeFileSync(p, JSON.stringify(obj, null, 2) + "\n", "utf8");
}

export function writeText(p, text) {
  fs.mkdirSync(path.dirname(p), { recursive: true });
  fs.writeFileSync(p, text, "utf8");
}

export function isDryRun(opts) {
  return opts["dry-run"] === "true" || opts.dryRun === "true";
}
