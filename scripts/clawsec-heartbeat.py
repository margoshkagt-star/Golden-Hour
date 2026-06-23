#!/usr/bin/env python3
"""Minimal clawsec-suite heartbeat check for Windows (no bash/jq).

Runs:
1. Sanity: clawsec-suite installed locally.
2. Optional: latest release vs installed.
3. Advisory feed fetch + diff vs state file.
4. Match installed skills against advisory `affected` lists.
"""
import json
import os
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

INSTALL_ROOT = Path(os.environ.get("INSTALL_ROOT") or Path.home() / ".openclaw/skills")
SUITE_DIR = Path(os.environ.get("SUITE_DIR") or INSTALL_ROOT / "clawsec-suite")
FEED_URL = os.environ.get("CLAWSEC_FEED_URL") or "https://clawsec.prompt.security/advisories/feed.json"
STATE_FILE = Path(os.environ.get("CLAWSEC_SUITE_STATE_FILE") or Path.home() / ".openclaw/clawsec-suite-feed-state.json")
GITHUB_RELEASES_API = os.environ.get("GITHUB_RELEASES_API") or "https://api.github.com/repos/prompt-security/clawsec/releases?per_page=100"
RELEASE_DOWNLOAD_BASE_URL = os.environ.get("RELEASE_DOWNLOAD_BASE_URL") or "https://github.com/prompt-security/clawsec/releases/download"
MIN_FEED_INTERVAL_SECONDS = int(os.environ.get("MIN_FEED_INTERVAL_SECONDS") or "300")


def http_get(url: str, timeout: int = 15) -> bytes | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "golden-hour-heartbeat/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as e:
        print(f"WARNING: GET {url} failed: {e}", file=sys.stderr)
        return None


def load_state() -> dict:
    if not STATE_FILE.exists():
        return {"schema_version": "1.0", "known_advisories": [], "last_feed_check": None, "last_feed_updated": None}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        print(f"WARNING: invalid state file {STATE_FILE}, resetting", file=sys.stderr)
        return {"schema_version": "1.0", "known_advisories": [], "last_feed_check": None, "last_feed_updated": None}


def save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    try:
        os.chmod(STATE_FILE, 0o600)
    except OSError:
        pass


def main() -> int:
    print("=== ClawSec Suite Heartbeat ===")
    print(f"When:  {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}")
    print(f"Suite: {SUITE_DIR}")

    # Step 0
    if not SUITE_DIR.is_dir():
        print(f"NOTE: clawsec-suite not installed at {SUITE_DIR} (optional).")
        return 0
    skill_json = SUITE_DIR / "skill.json"
    if not skill_json.is_file():
        print(f"NOTE: {skill_json} missing, skipping detail.")
        return 0

    try:
        installed_ver = json.loads(skill_json.read_text(encoding="utf-8")).get("version", "unknown")
    except json.JSONDecodeError:
        installed_ver = "unknown"
    print(f"Installed suite: {installed_ver}")

    # Step 1 — release check (best effort)
    latest_ver = ""
    try:
        releases_raw = http_get(GITHUB_RELEASES_API)
        if releases_raw:
            releases = json.loads(releases_raw)
            for rel in releases:
                tag = rel.get("tag_name") or ""
                if tag.startswith("clawsec-suite-v"):
                    rel_meta = http_get(f"{RELEASE_DOWNLOAD_BASE_URL}/{tag}/skill.json")
                    if rel_meta:
                        latest_ver = json.loads(rel_meta).get("version", "")
                        break
    except json.JSONDecodeError:
        pass
    print(f"Latest suite:    {latest_ver or 'unknown'}")
    if latest_ver and latest_ver != installed_ver:
        print(f"UPDATE AVAILABLE: clawsec-suite {installed_ver} -> {latest_ver}")
    elif latest_ver:
        print("Suite appears up to date.")

    # Step 2 — state
    state = load_state()
    known = set(state.get("known_advisories") or [])

    # Step 3 — feed rate limit
    last_check = state.get("last_feed_check") or "1970-01-01T00:00:00Z"
    try:
        last_epoch = int(time.mktime(time.strptime(last_check, "%Y-%m-%dT%H:%M:%SZ")))
    except ValueError:
        last_epoch = 0
    now_epoch = int(time.time())
    if (now_epoch - last_epoch) < MIN_FEED_INTERVAL_SECONDS:
        print(f"Feed check skipped (rate limit: {MIN_FEED_INTERVAL_SECONDS}s).")
        return 0

    feed_raw = http_get(FEED_URL)
    feed_source = FEED_URL
    if not feed_raw:
        local_feed = SUITE_DIR / "advisories" / "feed.json"
        if local_feed.is_file():
            feed_raw = local_feed.read_bytes()
            feed_source = str(local_feed)
            print("WARNING: Remote feed unavailable, using local fallback.")
        else:
            print("ERROR: Remote feed unavailable and no local fallback feed found.")
            return 1

    try:
        feed = json.loads(feed_raw)
    except json.JSONDecodeError:
        print("ERROR: Advisory feed has invalid format.")
        return 1

    if not isinstance(feed.get("advisories"), list) or "version" not in feed:
        print("ERROR: Advisory feed has invalid format.")
        return 1

    print(f"Feed source: {feed_source}")
    print(f"Feed updated: {feed.get('updated', 'unknown')}")

    advisories = feed["advisories"]
    new_ids = [a["id"] for a in advisories if a.get("id") and a["id"] not in known]

    if new_ids:
        print("New advisories:")
        for a in advisories:
            if a.get("id") in new_ids:
                sev = (a.get("severity") or "").upper()
                expl = (a.get("exploitability_score") or "unknown").upper()
                action = a.get("action") or "Review advisory details"
                print(f"- [{sev}] {a.get('id')}: {a.get('title')}")
                print(f"  Exploitability: {expl}")
                print(f"  Action: {action}")
    else:
        print("FEED_OK - no new advisories")

    # Step 4 — match installed skills
    print("Affected installed skills (if any):")
    found_affected = False
    removal_recommended = False
    if INSTALL_ROOT.is_dir():
        for skill_dir in sorted(INSTALL_ROOT.iterdir()):
            if not skill_dir.is_dir():
                continue
            skill_name = skill_dir.name
            skill_prefix = f"{skill_name}@"
            hits = []
            needs_removal = False
            for a in advisories:
                affected = a.get("affected") or []
                if any(isinstance(x, str) and x.startswith(skill_prefix) for x in affected):
                    hits.append(a)
                    sev = (a.get("severity") or "").lower()
                    typ = (a.get("type") or "").lower()
                    title = (a.get("title") or "").lower()
                    desc = (a.get("description") or "").lower()
                    act = (a.get("action") or "").lower()
                    if (
                        typ == "malicious_skill"
                        or any(w in title for w in ("malicious", "exfiltrat", "backdoor", "trojan", "stealer"))
                        or any(w in desc for w in ("malicious", "exfiltrat", "backdoor", "trojan", "stealer"))
                        or any(w in act for w in ("remove", "uninstall", "disable", "do not use", "quarantine"))
                    ):
                        needs_removal = True
            if hits:
                found_affected = True
                print(f"- {skill_name} is referenced by advisory feed entries")
                for a in hits:
                    sev = (a.get("severity") or "").upper()
                    act = a.get("action") or "Review advisory details"
                    print(f"  [{sev}] {a.get('id')}: {a.get('title')}")
                    print(f"    Action: {act}")
                if needs_removal:
                    removal_recommended = True
    if not found_affected:
        print("- none")

    if removal_recommended:
        print("Approval required: ask the user for explicit approval before removing any skill.")
        print("Double-confirmation policy: install request is first intent; require a second explicit confirmation with advisory context.")

    # persist state
    state["last_feed_check"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    if feed.get("updated"):
        state["last_feed_updated"] = feed["updated"]
    state["known_advisories"] = sorted(known.union(a.get("id") for a in advisories if a.get("id")))
    save_state(state)
    return 0


if __name__ == "__main__":
    sys.exit(main())