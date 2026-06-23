"""Watchdog for telegram_notes_bot.

Spawns the bot in a loop. If it dies, waits RESTART_DELAY seconds and starts
again. Never gives up — that's the whole point. Used for #7: "when beatusx
comes up, all sent messages should be processed" — getUpdates with
drop_pending_updates=False picks up the queue on every restart.

Run with:
    python telegram_notes_bot_watchdog.py

Logs go to telegram_notes_bot.watchdog.log next to this script.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
BOT = HERE / "telegram_notes_bot.py"
LOG = HERE / "telegram_notes_bot.watchdog.log"
RESTART_DELAY = int(os.environ.get("NOTES_BOT_RESTART_DELAY", "5"))
MAX_BACKOFF = 60  # seconds; cap exponential growth


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log(line: str) -> None:
    msg = f"{now()} {line}"
    print(msg, flush=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(msg + "\n")


def main() -> int:
    log(f"watchdog start; bot={BOT}; restart_delay={RESTART_DELAY}s")
    backoff = RESTART_DELAY
    while True:
        log("spawning bot...")
        try:
            rc = subprocess.call([sys.executable, str(BOT)])
        except KeyboardInterrupt:
            log("watchdog: KeyboardInterrupt, exiting")
            return 0
        log(f"bot exited with code {rc}; restarting in {backoff}s")
        time.sleep(backoff)
        backoff = min(backoff * 2, MAX_BACKOFF) if rc != 0 else RESTART_DELAY


if __name__ == "__main__":
    sys.exit(main())
