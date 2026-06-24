"""
Felpik Dashboard backend.
Wraps `openclaw <cmd> --json` calls and serves a single-page dashboard.

Run:
    python backend.py [--port 18790] [--host 127.0.0.1]
    .\\start_dashboard.ps1
"""
import argparse
import asyncio
import hashlib
import hmac
import json
import os
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qsl, unquote

# Force UTF-8 on Windows
if sys.platform == "win32":
    sys.stdout = open(sys.stdout.fileno(), mode="w", encoding="utf-8", buffering=1)
    sys.stderr = open(sys.stderr.fileno(), mode="w", encoding="utf-8", buffering=1)

OPENCLAW = r"C:\Users\Admin\AppData\Roaming\npm\openclaw.cmd"
OPENCLAW_HOME = Path(r"C:\Users\Admin\.openclaw")
WORKSPACE = OPENCLAW_HOME / "workspace"
DASHBOARD_DIR = Path(__file__).parent
STATIC_FILE = DASHBOARD_DIR / "dashboard.html"
GATEWAY_CHAT_JS = DASHBOARD_DIR / "gateway-chat.js"
TELEGRAM_MINIAPP_JS = DASHBOARD_DIR / "telegram-miniapp.js"
TELEGRAM_MINIAPP_CSS = DASHBOARD_DIR / "telegram-miniapp.css"
MINIAPP_BOOT = (
    '<script>document.documentElement.classList.add("tg-miniapp");'
    'sessionStorage.setItem("tg_miniapp","1");</script>'
)
OPENCLAW_JSON = OPENCLAW_HOME / "openclaw.json"
AGENTS_DIR = OPENCLAW_HOME / "agents"

# CLI ~5–35s per call; cache must outlive one full refresh cycle
CACHE_TTL_SEC = 45
_cache: dict = {}
_cost_cache: dict = {"ts": 0, "data": None}
COST_CACHE_TTL_SEC = 120
DASHBOARD_PORT = 18790
TASK_POOL_ACTIVE = WORKSPACE / "memory" / "task-pool" / "active.json"
_snapshot_lock = threading.Lock()
_snapshot_building = False


def _read_env_file() -> dict[str, str]:
    out: dict[str, str] = {}
    env_path = OPENCLAW_HOME / ".env"
    if not env_path.exists():
        return out
    for line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def _load_telegram_bot_token() -> str:
    for key in ("TELEGRAM_MINIAPP_BOT_TOKEN", "TELEGRAM_BOT_TOKEN", "TEAM_BOT_TOKEN"):
        v = os.environ.get(key, "").strip()
        if v:
            return v
    env = _read_env_file()
    for key in ("TELEGRAM_MINIAPP_BOT_TOKEN", "TELEGRAM_BOT_TOKEN", "TEAM_BOT_TOKEN"):
        v = env.get(key, "").strip()
        if v:
            return v
    return ""


def validate_telegram_init_data(init_data: str, bot_token: str) -> dict | None:
    init_data = str(init_data or "").strip()
    bot_token = str(bot_token or "").strip()
    if not init_data or not bot_token:
        return None
    parsed = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = parsed.pop("hash", None)
    if not received_hash:
        return None
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    computed = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()
    if computed != received_hash:
        return None
    user_raw = parsed.get("user") or "{}"
    try:
        user = json.loads(user_raw)
    except json.JSONDecodeError:
        user = {}
    return {
        "user": user,
        "auth_date": parsed.get("auth_date"),
        "query_id": parsed.get("query_id"),
    }


def telegram_miniapp_config() -> dict:
    token = _load_telegram_bot_token()
    public_url = os.environ.get("TELEGRAM_MINIAPP_URL", "").strip().rstrip("/")
    return {
        "hasBotToken": bool(token),
        "publicUrl": public_url,
        "miniappPath": "/miniapp",
        "dashboardPath": "/dashboard.html?miniapp=1",
    }


def _load_gateway_token() -> str:
    tok = os.environ.get("GATEWAY_AUTH_TOKEN", "")
    if tok:
        return tok.strip()
    env = _read_env_file()
    return env.get("GATEWAY_AUTH_TOKEN", "").strip()


def chat_go_path(session: str = "agent:main:main") -> str:
    from urllib.parse import quote

    return f"/go/chat?session={quote(session)}"


def chat_go_url(session: str = "agent:main:main", port: int | None = None) -> str:
    p = port if port is not None else DASHBOARD_PORT
    return f"http://127.0.0.1:{p}{chat_go_path(session)}"


def chat_link(session: str = "agent:main:main") -> dict:
    from urllib.parse import quote

    token = _load_gateway_token()
    base = "http://127.0.0.1:18789/chat"
    direct = f"{base}?session={quote(session)}"
    if token:
        direct = f"{direct}#token={token}"
    return {
        "url": chat_go_url(session),
        "goPath": chat_go_path(session),
        "hasToken": bool(token),
        "session": session,
        "directUrl": direct,
    }


def go_chat_html(session: str) -> bytes:
    from urllib.parse import quote

    token = _load_gateway_token()
    if not token:
        msg = (
            "<!doctype html><html><body style='font-family:system-ui;padding:24px'>"
            "<h1>Нет GATEWAY_AUTH_TOKEN</h1>"
            "<p>Добавьте токен в <code>C:\\Users\\Admin\\.openclaw\\.env</code> "
            "и перезапустите gateway.</p></body></html>"
        )
        return msg.encode("utf-8")
    sess_q = quote(session)
    tok_js = json.dumps(token)
    sess_js = json.dumps(session)
    html = f"""<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><title>Чат OpenClaw…</title>
<script>
(function(){{
  var s = {sess_js};
  var t = {tok_js};
  location.replace('http://127.0.0.1:18789/chat?session=' + encodeURIComponent(s) + '#token=' + t);
}})();
</script>
<style>body{{font-family:system-ui;background:#0d1117;color:#e6edf3;display:grid;place-items:center;min-height:100vh;margin:0}}</style>
</head><body><p>Открываем чат с автовходом…</p></body></html>"""
    return html.encode("utf-8")


def chat_config_dict() -> dict:
    token = _load_gateway_token()
    cfg = _read_json(OPENCLAW_JSON) or {}
    port = (cfg.get("gateway") or {}).get("port") or 18789
    return {
        "wsUrl": f"ws://127.0.0.1:{port}",
        "hasToken": bool(token),
        "protocol": 4,
    }


def portal_dict() -> dict:
    embed = "http://127.0.0.1:3000/d/openclaw-overview/openclaw-overview?orgId=1&refresh=30s&kiosk"
    return {
        "dashboard": f"http://127.0.0.1:{DASHBOARD_PORT}",
        "gatewayChat": "http://127.0.0.1:18789/chat",
        "chatMain": chat_link("agent:main:main"),
        "clawDash": "http://127.0.0.1:3939",
        "grafana": os.environ.get("GRAFANA_URL", embed),
        "grafanaEmbed": embed,
        "prometheus": "http://127.0.0.1:9090",
    }


def _port_open(host: str, port: int, timeout: float = 1.5) -> bool:
    import socket

    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def fetch_prometheus_metrics() -> tuple[int, bytes, str]:
    import urllib.error
    import urllib.request

    token = _load_gateway_token()
    url = "http://127.0.0.1:18789/api/diagnostics/prometheus"
    req = urllib.request.Request(url, method="GET")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            return resp.status, resp.read(), ""
    except urllib.error.HTTPError as e:
        return e.code, e.read()[:500], f"HTTP {e.code}"
    except Exception as e:
        return 0, b"", str(e)


def grafana_status() -> dict:
    cfg = _read_json(OPENCLAW_JSON) or {}
    plugin_on = bool(
        cfg.get("plugins", {}).get("entries", {}).get("diagnostics-prometheus", {}).get("enabled")
    )
    diag_on = bool(cfg.get("diagnostics", {}).get("enabled"))
    code, body, err = fetch_prometheus_metrics()
    text = body.decode("utf-8", errors="replace")
    lines = len([ln for ln in text.splitlines() if ln and not ln.startswith("#")])
    portal = portal_dict()
    return {
        "grafanaUp": _port_open("127.0.0.1", 3000),
        "prometheusUp": _port_open("127.0.0.1", 9090),
        "metricsAvailable": code == 200 and lines > 0,
        "metricsHttp": code,
        "metricsLines": lines,
        "metricsError": err,
        "pluginEnabled": plugin_on,
        "diagnosticsEnabled": diag_on,
        "dashboardUrl": portal["grafana"],
        "embedUrl": portal["grafanaEmbed"],
        "prometheusUrl": portal["prometheus"],
        "needsGatewayRestart": plugin_on and (not diag_on or code in (0, 404, 502)),
    }


def _read_json(path: Path):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return None


def run_cli_sync(args: list[str], timeout: float = 30.0) -> dict | list | None:
    try:
        proc = subprocess.run(
            [OPENCLAW] + args,
            capture_output=True,
            timeout=timeout,
            shell=True,
            text=False,
        )
    except subprocess.TimeoutExpired:
        return {"_error": "timeout", "_cmd": " ".join(args)}
    if proc.returncode != 0:
        err = (proc.stderr.decode("utf-8", "replace") or "exit " + str(proc.returncode))[:200]
        try:
            parsed = json.loads(proc.stdout.decode("utf-8", "replace"))
            if isinstance(parsed, dict):
                parsed["_cli_exit"] = proc.returncode
                if not parsed.get("_error"):
                    parsed["_error"] = err
                return parsed
        except json.JSONDecodeError:
            pass
        return {"_error": err, "_cmd": " ".join(args)}
    try:
        return json.loads(proc.stdout.decode("utf-8", "replace"))
    except json.JSONDecodeError as e:
        return {"_error": f"json: {e}", "_raw": proc.stdout[:300].decode("utf-8", "replace")}


async def run_cli(args: list[str], timeout: float = 30.0) -> dict | list | None:
    return await asyncio.to_thread(run_cli_sync, args, timeout)


def load_channel_bindings() -> list[dict]:
    """Map channels to agents from openclaw.json bindings (for topology graph)."""
    cfg = _read_json(OPENCLAW_JSON) or {}
    out: list[dict] = []
    for b in cfg.get("bindings") or []:
        if not isinstance(b, dict):
            continue
        match = b.get("match") or {}
        channel = match.get("channel")
        if not channel:
            continue
        out.append({
            "channel": channel,
            "agentId": b.get("agentId"),
            "accountId": match.get("accountId"),
        })
    return out


def _agent_id_from_session_key(session_key: str) -> str | None:
    if not session_key or not str(session_key).startswith("agent:"):
        return None
    parts = str(session_key).split(":")
    return parts[1] if len(parts) >= 2 else None


def _task_pool_items(pool) -> list[dict]:
    if not pool:
        return []
    if isinstance(pool, list):
        return [t for t in pool if isinstance(t, dict)]
    if isinstance(pool, dict):
        for key in ("tasks", "failed_tasks", "completed_tasks", "items"):
            val = pool.get(key)
            if isinstance(val, list):
                return [t for t in val if isinstance(t, dict)]
    return []


def load_agent_links() -> list[dict]:
    """Agent-to-agent edges for topology: delegate config, cross-agent spawns, tasks."""
    merged: dict[tuple[str, str], dict] = {}
    priority = {"spawn": 3, "task": 2, "delegate": 1}

    def add(from_id: str, to_id: str, kind: str, count: int = 1) -> None:
        if not from_id or not to_id or from_id == to_id:
            return
        key = (from_id, to_id)
        label = {
            "delegate": "может делегировать",
            "spawn": f"{count} spawn" if count != 1 else "spawn",
            "task": f"{count} task" if count != 1 else "task",
        }.get(kind, kind)
        cur = merged.get(key)
        if not cur or priority.get(kind, 0) > priority.get(cur["kind"], 0):
            merged[key] = {
                "fromAgent": from_id,
                "toAgent": to_id,
                "kind": kind,
                "count": count,
                "label": label,
            }
        elif cur["kind"] == kind:
            cur["count"] = int(cur.get("count") or 1) + count
            if kind == "spawn":
                cur["label"] = f"{cur['count']} spawn"
            elif kind == "task":
                cur["label"] = f"{cur['count']} task"

    cfg = _read_json(OPENCLAW_JSON) or {}
    for a in cfg.get("agents", {}).get("list", []):
        if not isinstance(a, dict):
            continue
        from_id = a.get("id")
        for to_id in (a.get("subagents") or {}).get("allowAgents") or []:
            add(str(from_id), str(to_id), "delegate")

    if AGENTS_DIR.is_dir():
        spawn_counts: dict[tuple[str, str], int] = {}
        for agent_dir in AGENTS_DIR.iterdir():
            if not agent_dir.is_dir():
                continue
            store_path = agent_dir / "sessions" / "sessions.json"
            if not store_path.exists():
                continue
            try:
                store = json.loads(store_path.read_text(encoding="utf-8"))
            except Exception:
                continue
            for session_key, meta in store.items():
                if not isinstance(meta, dict):
                    continue
                spawned = meta.get("spawnedBy") or meta.get("spawned_by")
                if not spawned:
                    continue
                parent = _agent_id_from_session_key(str(spawned))
                child = _agent_id_from_session_key(str(session_key))
                if parent and child and parent != child:
                    k = (parent, child)
                    spawn_counts[k] = spawn_counts.get(k, 0) + 1
        for (parent, child), cnt in spawn_counts.items():
            add(parent, child, "spawn", cnt)

    roster_ids = {a.get("id") for a in load_agents_roster() if a.get("id") and not a.get("_error")}
    task_counts: dict[tuple[str, str], int] = {}
    for path in (
        WORKSPACE / "memory" / "task-pool" / "active.json",
        WORKSPACE / "memory" / "task-pool" / "history.json",
    ):
        for task in _task_pool_items(_read_json(path)):
            owner = str(task.get("agent") or "").strip()
            sub = str(task.get("subagent_id") or task.get("subagentId") or "").strip()
            runner = _agent_id_from_session_key(sub) if sub else None
            if runner and owner and runner != owner and owner in roster_ids and runner in roster_ids:
                k = (runner, owner)
                task_counts[k] = task_counts.get(k, 0) + 1
            elif owner and owner in roster_ids:
                for dep in task.get("depends_on") or task.get("dependsOn") or []:
                    dep_agent = str(dep).split(":")[0] if isinstance(dep, str) else ""
                    if dep_agent in roster_ids and dep_agent != owner:
                        k = (dep_agent, owner)
                        task_counts[k] = task_counts.get(k, 0) + 1
    for (src, dst), cnt in task_counts.items():
        add(src, dst, "task", cnt)

    return list(merged.values())


def load_agents_roster() -> list[dict]:
    try:
        cfg = json.loads(OPENCLAW_JSON.read_text(encoding="utf-8"))
        out = []
        for a in cfg.get("agents", {}).get("list", []):
            ident = a.get("identity") or {}
            out.append({
                "id": a.get("id"),
                "name": ident.get("name") or a.get("name") or a.get("id"),
                "emoji": ident.get("emoji") or "🤖",
                "model": (
                    a.get("model")
                    or cfg.get("agents", {}).get("defaults", {}).get("model", {}).get("primary")
                ),
                "workspace": a.get("workspace")
                or cfg.get("agents", {}).get("defaults", {}).get("workspace"),
            })
        return out
    except Exception as e:
        return [{"_error": str(e)}]


def _model_pricing() -> dict[str, dict]:
    prices: dict[str, dict] = {}
    try:
        cfg = json.loads(OPENCLAW_JSON.read_text(encoding="utf-8"))
        for prov, pdata in (cfg.get("models", {}).get("providers") or {}).items():
            for m in pdata.get("models") or []:
                c = m.get("cost") or {}
                prices[f"{prov}/{m.get('id')}"] = {
                    "input": float(c.get("input") or 0),
                    "output": float(c.get("output") or 0),
                    "cacheRead": float(c.get("cacheRead") or 0),
                    "cacheWrite": float(c.get("cacheWrite") or 0),
                }
    except Exception:
        pass
    return prices


def _usage_cost(usage: dict, model_key: str, prices: dict[str, dict]) -> float:
    p = prices.get(model_key) or {}
    if not p:
        return 0.0
    inp = float(usage.get("input") or 0)
    out = float(usage.get("output") or 0)
    cr = float(usage.get("cacheRead") or 0)
    cw = float(usage.get("cacheWrite") or 0)
    return (
        inp * p.get("input", 0)
        + out * p.get("output", 0)
        + cr * p.get("cacheRead", 0)
        + cw * p.get("cacheWrite", 0)
    ) / 1_000_000


def collect_costs(days: int = 7, force: bool = False) -> dict:
    now = time.time()
    if not force and _cost_cache.get("data") and now - _cost_cache.get("ts", 0) < COST_CACHE_TTL_SEC:
        return _cost_cache["data"]
    from datetime import datetime, timedelta

    cutoff_ms = int((now - days * 86400) * 1000)
    today_start = int(time.mktime(time.localtime(now)) // 86400 * 86400 * 1000)
    prices = _model_pricing()
    by_day: dict[str, float] = {}
    by_model: dict[str, float] = {}
    by_agent: dict[str, float] = {}
    breakdown = {"input": 0.0, "output": 0.0, "cacheRead": 0.0, "cacheWrite": 0.0}
    sessions_seen: set[str] = set()
    runs = 0
    today_spend = 0.0
    week_spend = 0.0
    if not AGENTS_DIR.is_dir():
        return {"_error": "agents dir missing", "today": 0, "week": 0, "days": days}
    for agent_dir in AGENTS_DIR.iterdir():
        if not agent_dir.is_dir():
            continue
        sess_dir = agent_dir / "sessions"
        if not sess_dir.is_dir():
            continue
        agent_id = agent_dir.name
        for fp in sess_dir.glob("*.trajectory.jsonl"):
            try:
                if int(fp.stat().st_mtime * 1000) < cutoff_ms:
                    continue
            except OSError:
                continue
            try:
                for line in fp.read_text(encoding="utf-8", errors="replace").splitlines():
                    if not line.strip():
                        continue
                    try:
                        ev = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    ts_s = ev.get("ts") or ""
                    try:
                        ts_ms = int(datetime.fromisoformat(ts_s.replace("Z", "+00:00")).timestamp() * 1000)
                    except Exception:
                        ts_ms = int(fp.stat().st_mtime * 1000)
                    if ts_ms < cutoff_ms:
                        continue
                    if (ev.get("type") or "") not in ("model.completed", "trace.artifacts"):
                        continue
                    usage = (ev.get("data") or {}).get("usage")
                    if not usage:
                        continue
                    provider = ev.get("provider") or ""
                    model_id = ev.get("modelId") or ""
                    model_key = f"{provider}/{model_id}" if provider and model_id else model_id or "unknown"
                    cost = _usage_cost(usage, model_key, prices)
                    runs += 1
                    sid = ev.get("sessionId") or ev.get("traceId") or ""
                    if sid:
                        sessions_seen.add(sid)
                    day = ts_s[:10] if len(ts_s) >= 10 else "unknown"
                    by_day[day] = by_day.get(day, 0) + cost
                    by_model[model_key] = by_model.get(model_key, 0) + cost
                    by_agent[agent_id] = by_agent.get(agent_id, 0) + cost
                    week_spend += cost
                    if ts_ms >= today_start:
                        today_spend += cost
                    p = prices.get(model_key) or {}
                    breakdown["input"] += float(usage.get("input") or 0) * p.get("input", 0) / 1_000_000
                    breakdown["output"] += float(usage.get("output") or 0) * p.get("output", 0) / 1_000_000
                    breakdown["cacheRead"] += float(usage.get("cacheRead") or 0) * p.get("cacheRead", 0) / 1_000_000
                    breakdown["cacheWrite"] += float(usage.get("cacheWrite") or 0) * p.get("cacheWrite", 0) / 1_000_000
            except OSError:
                continue
    yday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    yesterday_spend = by_day.get(yday, 0)
    pct_vs_yesterday = None
    if yesterday_spend > 0:
        pct_vs_yesterday = round((today_spend - yesterday_spend) / yesterday_spend * 100, 1)
    data = {
        "today": round(today_spend, 4),
        "week": round(week_spend, 4),
        "yesterday": round(yesterday_spend, 4),
        "pctVsYesterday": pct_vs_yesterday,
        "dailyAvg": round(week_spend / max(days, 1), 4),
        "runs": runs,
        "sessions": len(sessions_seen),
        "byDay": {k: round(v, 4) for k, v in sorted(by_day.items())},
        "byModel": {k: round(v, 4) for k, v in sorted(by_model.items(), key=lambda x: -x[1])},
        "byAgent": {k: round(v, 4) for k, v in sorted(by_agent.items(), key=lambda x: -x[1])},
        "breakdown": {k: round(v, 4) for k, v in breakdown.items()},
        "days": days,
        "priced": bool(prices),
    }
    _cost_cache["ts"] = now
    _cost_cache["data"] = data
    return data


def bootstrap() -> dict:
    """Instant data from disk — no openclaw CLI."""
    costs = _cost_cache.get("data")
    if not costs:
        costs = {"today": 0, "week": 0, "_loading": True}
    return {
        "ts": int(time.time() * 1000),
        "partial": True,
        "agents_roster": load_agents_roster(),
        "channel_bindings": load_channel_bindings(),
        "agent_links": load_agent_links(),
        "history": _read_json(WORKSPACE / "memory" / "task-pool" / "history.json"),
        "active_pool": _read_json(WORKSPACE / "memory" / "task-pool" / "active.json"),
        "costs": costs,
        "portal": portal_dict(),
        "health": None,
        "crons_all": None,
        "tasks_running": None,
        "tasks_pending": None,
    }


async def _build_snapshot() -> dict:
    t0 = time.time()
    health, cron_all, tasks_running, tasks_pending = await asyncio.gather(
        run_cli(["health", "--json"], timeout=12.0),
        run_cli(["cron", "list", "--all", "--json"], timeout=35.0),
        run_cli(["tasks", "list", "--status", "running", "--json"], timeout=18.0),
        run_cli(["tasks", "list", "--status", "queued", "--json"], timeout=18.0),
    )
    data = {
        "ts": int(time.time() * 1000),
        "fetchMs": int((time.time() - t0) * 1000),
        "partial": False,
        "health": health,
        "crons_all": cron_all,
        "tasks_running": tasks_running,
        "tasks_pending": tasks_pending,
        "history": _read_json(WORKSPACE / "memory" / "task-pool" / "history.json"),
        "active_pool": _read_json(WORKSPACE / "memory" / "task-pool" / "active.json"),
        "agents_roster": load_agents_roster(),
        "channel_bindings": load_channel_bindings(),
        "agent_links": load_agent_links(),
        "costs": _cost_cache.get("data") or {"today": 0, "week": 0, "_loading": True},
        "portal": portal_dict(),
    }
    return data


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def add_task_to_pool(payload: dict) -> dict:
    from datetime import datetime

    title = str(payload.get("title") or "").strip()
    if not title:
        raise ValueError("title is required")
    data = _read_json(TASK_POOL_ACTIVE)
    if not isinstance(data, dict):
        data = {"version": "1.0", "tasks": []}
    tasks = data.get("tasks")
    if not isinstance(tasks, list):
        tasks = []
        data["tasks"] = tasks
    now = datetime.now().astimezone().isoformat(timespec="seconds")
    source = str(payload.get("source") or "dashboard").strip().lower() or "dashboard"
    if source not in ("dashboard", "agent", "telegram", "miniapp", "openclaw"):
        source = "agent"
    if payload.get("id"):
        task_id = str(payload.get("id")).strip()
    elif source == "agent":
        task_id = f"AGENT-{int(time.time())}"
    else:
        task_id = f"DASH-{int(time.time())}"
    if any(str(t.get("id")) == task_id for t in tasks):
        raise ValueError(f"task id already exists: {task_id}")
    status = str(payload.get("status") or "pending").strip().lower()
    task = {
        "id": task_id,
        "agent": str(payload.get("agent") or "main").strip() or "main",
        "title": title,
        "description": str(payload.get("description") or "").strip(),
        "priority": str(payload.get("priority") or "medium").strip().lower(),
        "status": status,
        "complexity": str(payload.get("complexity") or "medium").strip().lower(),
        "spawned_at": now,
        "created_at": now,
        "updated_at": now,
        "tags": payload.get("tags") if isinstance(payload.get("tags"), list) else [],
        "source": source,
    }
    created_by = str(payload.get("created_by") or "").strip()
    if created_by:
        task["created_by"] = created_by
    tag = str(payload.get("tag") or "").strip().lower()
    if tag:
        task["tag"] = tag
    week_goal = bool(payload.get("week_goal"))
    due = str(payload.get("due_date") or "").strip()[:10]
    if due:
        task["due_date"] = due
        task.pop("week_goal", None)
    elif week_goal:
        task["week_goal"] = True
    elif source == "dashboard":
        task["due_date"] = now[:10]
    tasks.append(task)
    data["updated_at"] = now
    _write_json(TASK_POOL_ACTIVE, data)
    return task


def list_tasks_from_pool(status: str | None = None) -> dict:
    data = _read_json(TASK_POOL_ACTIVE)
    if not isinstance(data, dict):
        return {"version": "1.0", "tasks": [], "updated_at": None}
    tasks = data.get("tasks")
    if not isinstance(tasks, list):
        tasks = []
    if status:
        want = str(status).strip().lower()
        tasks = [t for t in tasks if str(t.get("status") or "").lower() == want]
    return {
        "version": data.get("version", "1.0"),
        "tasks": tasks,
        "updated_at": data.get("updated_at"),
    }


def update_task_in_pool(task_id: str, updates: dict) -> dict:
    from datetime import datetime

    tid = str(task_id or "").strip()
    if not tid:
        raise ValueError("task id is required")
    data = _read_json(TASK_POOL_ACTIVE)
    if not isinstance(data, dict):
        raise ValueError("task pool not found")
    tasks = data.get("tasks")
    if not isinstance(tasks, list):
        raise ValueError("task pool empty")
    idx = next((i for i, t in enumerate(tasks) if str(t.get("id")) == tid), None)
    if idx is None:
        raise ValueError(f"task not found: {tid}")
    task = dict(tasks[idx])
    if "status" in updates and updates["status"] is not None:
        task["status"] = str(updates["status"]).strip().lower()
    if "priority" in updates and updates["priority"] is not None:
        task["priority"] = str(updates["priority"]).strip().lower()
    if "agent" in updates and updates["agent"] is not None:
        task["agent"] = str(updates["agent"]).strip() or task.get("agent", "main")
    if "title" in updates and updates["title"] is not None:
        title = str(updates["title"]).strip()
        if not title:
            raise ValueError("title is required")
        task["title"] = title
    if "description" in updates and updates["description"] is not None:
        task["description"] = str(updates["description"]).strip()
    if "tag" in updates:
        tag = str(updates["tag"] or "").strip().lower()
        if tag:
            task["tag"] = tag
        else:
            task.pop("tag", None)
    if "week_goal" in updates:
        if updates["week_goal"]:
            task["week_goal"] = True
            task.pop("due_date", None)
        else:
            task.pop("week_goal", None)
    if "due_date" in updates:
        raw_due = updates["due_date"]
        if raw_due is None or str(raw_due).strip() == "":
            task.pop("due_date", None)
        else:
            due = str(raw_due).strip()[:10]
            if due:
                task["due_date"] = due
                task.pop("week_goal", None)
    now = datetime.now().astimezone().isoformat(timespec="seconds")
    task["updated_at"] = now
    tasks[idx] = task
    data["updated_at"] = now
    _write_json(TASK_POOL_ACTIVE, data)
    return task


def delete_task_from_pool(task_id: str) -> dict:
    tid = str(task_id or "").strip()
    if not tid:
        raise ValueError("task id is required")
    data = _read_json(TASK_POOL_ACTIVE)
    if not isinstance(data, dict):
        raise ValueError("task pool not found")
    tasks = data.get("tasks")
    if not isinstance(tasks, list):
        raise ValueError("task pool empty")
    idx = next((i for i, t in enumerate(tasks) if str(t.get("id")) == tid), None)
    if idx is None:
        raise ValueError(f"task not found: {tid}")
    from datetime import datetime

    removed = tasks.pop(idx)
    data["updated_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    _write_json(TASK_POOL_ACTIVE, data)
    return removed


async def snapshot(force: bool = False) -> dict:
    global _snapshot_building
    now = time.time()
    if not force and _cache.get("data") and now - _cache.get("ts", 0) < CACHE_TTL_SEC:
        return _cache["data"]
    if _snapshot_building and _cache.get("data"):
        return {**_cache["data"], "_stale": True, "_building": True}
    with _snapshot_lock:
        now = time.time()
        if not force and _cache.get("data") and now - _cache.get("ts", 0) < CACHE_TTL_SEC:
            return _cache["data"]
        _snapshot_building = True
        try:
            data = await _build_snapshot()
            _cache["ts"] = time.time()
            _cache["data"] = data
            return data
        finally:
            _snapshot_building = False


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _send(self, status: int, body: bytes, ctype: str = "application/json; charset=utf-8"):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        from urllib.parse import parse_qs, urlparse, unquote

        parsed = urlparse(self.path)
        path = parsed.path
        if path in ("/miniapp", "/miniapp.html"):
            if not STATIC_FILE.exists():
                self._send(404, b"dashboard.html not found", "text/plain; charset=utf-8")
                return
            html = STATIC_FILE.read_text(encoding="utf-8")
            html = html.replace("<head>", "<head>" + MINIAPP_BOOT, 1)
            self._send(200, html.encode("utf-8"), "text/html; charset=utf-8")
            return
        if path == "/telegram-miniapp.js":
            if not TELEGRAM_MINIAPP_JS.exists():
                self._send(404, b"not found", "text/plain; charset=utf-8")
                return
            self._send(200, TELEGRAM_MINIAPP_JS.read_bytes(), "application/javascript; charset=utf-8")
            return
        if path == "/telegram-miniapp.css":
            if not TELEGRAM_MINIAPP_CSS.exists():
                self._send(404, b"not found", "text/plain; charset=utf-8")
                return
            self._send(200, TELEGRAM_MINIAPP_CSS.read_bytes(), "text/css; charset=utf-8")
            return
        if path in ("/", "/dashboard", "/dashboard.html", "/index.html"):
            if not STATIC_FILE.exists():
                self._send(404, b"dashboard.html not found", "text/plain; charset=utf-8")
                return
            self._send(200, STATIC_FILE.read_bytes(), "text/html; charset=utf-8")
            return
        if path == "/gateway-chat.js":
            if not GATEWAY_CHAT_JS.exists():
                self._send(404, b"gateway-chat.js not found", "text/plain; charset=utf-8")
                return
            self._send(200, GATEWAY_CHAT_JS.read_bytes(), "application/javascript; charset=utf-8")
            return
        if path == "/go/chat":
            qs = parse_qs(parsed.query)
            session = unquote((qs.get("session") or ["agent:main:main"])[0])
            if not session or ".." in session:
                self._send(400, b"bad session", "text/plain; charset=utf-8")
                return
            self._send(200, go_chat_html(session), "text/html; charset=utf-8")
            return
        if path == "/api/bootstrap":
            self._send(200, json.dumps(bootstrap(), ensure_ascii=False).encode("utf-8"))
            return
        if path == "/api/snapshot":
            loop = asyncio.new_event_loop()
            try:
                data = loop.run_until_complete(snapshot())
            finally:
                loop.close()
            self._send(200, json.dumps(data, ensure_ascii=False).encode("utf-8"))
            return
        if path == "/api/costs":
            data = collect_costs(days=7)
            self._send(200, json.dumps(data, ensure_ascii=False).encode("utf-8"))
            return
        if path == "/api/inbox":
            p = WORKSPACE / "memory" / "agents-inbox.md"
            if p.exists():
                self._send(200, p.read_bytes())
            else:
                self._send(404, b"inbox not found", "text/plain; charset=utf-8")
            return
        if path == "/api/tasks":
            qs = parse_qs(parsed.query)
            status = (qs.get("status") or [None])[0]
            if status is not None:
                status = str(status).strip() or None
            body = json.dumps(
                {"ok": True, **list_tasks_from_pool(status)},
                ensure_ascii=False,
            ).encode("utf-8")
            self._send(200, body)
            return
        if path == "/api/file":
            qs = parse_qs(parsed.query)
            rel = (qs.get("path") or [""])[0]
            if not rel or ".." in rel or rel.startswith("/"):
                self._send(400, b"bad path", "text/plain; charset=utf-8")
                return
            p = WORKSPACE / rel
            if not p.exists() or not p.is_file():
                self._send(404, b"not found", "text/plain; charset=utf-8")
                return
            try:
                self._send(200, p.read_bytes(), "text/markdown; charset=utf-8")
            except Exception as e:
                self._send(500, str(e).encode(), "text/plain; charset=utf-8")
            return
        if path == "/api/prometheus/metrics":
            code, body, err = fetch_prometheus_metrics()
            if code == 200:
                self._send(200, body, "text/plain; version=0.0.4; charset=utf-8")
            else:
                msg = err or f"gateway metrics HTTP {code}"
                self._send(502, msg.encode("utf-8"), "text/plain; charset=utf-8")
            return
        if path == "/api/grafana/status":
            self._send(200, json.dumps(grafana_status(), ensure_ascii=False).encode("utf-8"))
            return
        if path == "/api/telegram/config":
            self._send(200, json.dumps(telegram_miniapp_config(), ensure_ascii=False).encode("utf-8"))
            return
        if path == "/api/chat/config":
            body = chat_config_dict()
            if body["hasToken"]:
                body["token"] = _load_gateway_token()
            self._send(200, json.dumps(body, ensure_ascii=False).encode("utf-8"))
            return
        if path == "/api/health":
            self._send(200, b'{"ok":true,"service":"felpik-dashboard"}')
            return
        self._send(404, b"not found", "text/plain; charset=utf-8")

    def _read_json_body(self, max_len: int = 65536) -> dict | None:
        length = int(self.headers.get("Content-Length") or 0)
        if length > max_len:
            self._send(413, b"payload too large", "text/plain; charset=utf-8")
            return None
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            self._send(400, b"invalid json", "text/plain; charset=utf-8")
            return None
        if not isinstance(payload, dict):
            self._send(400, b"expected json object", "text/plain; charset=utf-8")
            return None
        return payload

    def do_POST(self):
        from urllib.parse import urlparse

        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/api/telegram/auth":
            payload = self._read_json_body()
            if payload is None:
                return
            init_data = str(payload.get("initData") or "").strip()
            token = _load_telegram_bot_token()
            auth = validate_telegram_init_data(init_data, token) if token else None
            if not auth:
                body = json.dumps(
                    {"ok": False, "error": "invalid_init_data", "dev": not bool(token)},
                    ensure_ascii=False,
                ).encode("utf-8")
                self._send(401 if token else 200, body)
                return
            user = auth.get("user") or {}
            body = json.dumps(
                {"ok": True, "user": user, "telegram_id": user.get("id")},
                ensure_ascii=False,
            ).encode("utf-8")
            self._send(200, body)
            return
        if path != "/api/tasks":
            self._send(404, b"not found", "text/plain; charset=utf-8")
            return
        payload = self._read_json_body()
        if payload is None:
            return
        try:
            task = add_task_to_pool(payload)
            body = json.dumps({"ok": True, "task": task}, ensure_ascii=False).encode("utf-8")
            self._send(201, body)
        except ValueError as e:
            self._send(400, str(e).encode("utf-8"), "text/plain; charset=utf-8")
        except Exception as e:
            self._send(500, str(e).encode("utf-8"), "text/plain; charset=utf-8")

    def do_PATCH(self):
        from urllib.parse import unquote, urlparse

        parsed = urlparse(self.path)
        path = parsed.path
        prefix = "/api/tasks/"
        if not path.startswith(prefix):
            self._send(404, b"not found", "text/plain; charset=utf-8")
            return
        task_id = unquote(path[len(prefix) :]).strip()
        if not task_id or ".." in task_id or "/" in task_id:
            self._send(400, b"bad task id", "text/plain; charset=utf-8")
            return
        length = int(self.headers.get("Content-Length") or 0)
        if length > 65536:
            self._send(413, b"payload too large", "text/plain; charset=utf-8")
            return
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            self._send(400, b"invalid json", "text/plain; charset=utf-8")
            return
        if not isinstance(payload, dict):
            self._send(400, b"expected json object", "text/plain; charset=utf-8")
            return
        try:
            task = update_task_in_pool(task_id, payload)
            body = json.dumps({"ok": True, "task": task}, ensure_ascii=False).encode("utf-8")
            self._send(200, body)
        except ValueError as e:
            self._send(400, str(e).encode("utf-8"), "text/plain; charset=utf-8")
        except Exception as e:
            self._send(500, str(e).encode("utf-8"), "text/plain; charset=utf-8")

    def do_DELETE(self):
        from urllib.parse import unquote, urlparse

        parsed = urlparse(self.path)
        path = parsed.path
        prefix = "/api/tasks/"
        if not path.startswith(prefix):
            self._send(404, b"not found", "text/plain; charset=utf-8")
            return
        task_id = unquote(path[len(prefix) :]).strip()
        if not task_id or ".." in task_id or "/" in task_id:
            self._send(400, b"bad task id", "text/plain; charset=utf-8")
            return
        try:
            task = delete_task_from_pool(task_id)
            body = json.dumps({"ok": True, "task": task}, ensure_ascii=False).encode("utf-8")
            self._send(200, body)
        except ValueError as e:
            self._send(400, str(e).encode("utf-8"), "text/plain; charset=utf-8")
        except Exception as e:
            self._send(500, str(e).encode("utf-8"), "text/plain; charset=utf-8")


def main():
    global DASHBOARD_PORT
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=18790)
    ap.add_argument("--host", default="127.0.0.1", help="127.0.0.1 или 0.0.0.0 для LAN")
    args = ap.parse_args()
    DASHBOARD_PORT = args.port
    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"[dashboard] http://{args.host}:{args.port}/")
    print(f"[dashboard] bootstrap: /api/bootstrap (быстро)")
    print(f"[dashboard] snapshot:  /api/snapshot (~30-60s первый раз)")
    print(f"[dashboard] autologin chat: http://127.0.0.1:{args.port}/go/chat")
    print(f"[dashboard] telegram miniapp: http://127.0.0.1:{args.port}/miniapp")
    if args.host == "0.0.0.0":
        print("[dashboard] LAN mode: доступ с других устройств в сети по IP этого ПК")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("[dashboard] shutting down")


if __name__ == "__main__":
    main()
