#!/usr/bin/env bash
# =============================================================================
# Golden Hour — Server-Side Deploy Script
#
# This file must be:
#   - Owned by root:  chown root:root /opt/golden-hour/deploy/run-deploy.sh
#   - Read-only:      chmod 555 /opt/golden-hour/deploy/run-deploy.sh
#
# It runs as ROOT (it chowns files, writes /opt and /etc, manages systemd).
# It is NOT the SSH ForceCommand directly — ssh-deploy-wrapper.sh is, and it
# calls this script via `sudo`. The deploy SSH key therefore cannot run
# arbitrary commands: the wrapper only ever invokes this script with a
# validated commit SHA. See deploy/ssh-deploy-wrapper.sh and setup-server.sh.
#
# If invoked as a non-root user, it re-executes itself via sudo (the deploy
# user is granted NOPASSWD sudo for exactly this path).
# =============================================================================
set -euo pipefail

# Re-exec as root if needed (deploy user has NOPASSWD sudo for this exact path).
if [ "$(id -u)" -ne 0 ]; then
  exec sudo -n "$0" "$@"
fi

DEPLOY_PATH="/opt/golden-hour"
SERVICE_NAME="golden-hour"
BACKUP_DIR="/var/backups/golden-hour"
BRANCH="deploy"
OPENCLAW_DIR="$DEPLOY_PATH/.openclaw"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${GREEN}[DEPLOY]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}   $*"; }
error() { echo -e "${RED}[ERROR]${NC}  $*" >&2; }

# Expected commit SHA passed by the wrapper (first argument or $DEPLOY_SHA).
# Empty is allowed ONLY for manual `sudo run-deploy.sh` by an admin (deploys
# current origin/deploy HEAD). When set it must be an exact 40-hex SHA — this
# guards against a loose sudoers wildcard passing junk as argv.
EXPECTED_SHA="${1:-${DEPLOY_SHA:-}}"
if [ -n "$EXPECTED_SHA" ] && ! [[ "$EXPECTED_SHA" =~ ^[0-9a-f]{40}$ ]]; then
  error "Invalid SHA argument: '$EXPECTED_SHA' (expected 40-hex)."
  exit 2
fi

# ---- [0] Acquire deploy lock (prevents cron race during deploy) ---------------
LOCK_FILE="/var/lock/golden-hour-deploy.lock"
exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  error "Another deploy is already running. Aborting."
  exit 1
fi

# ---- [1] Verify deploy directory exists --------------------------------------
info "[1/7] Checking deploy path..."
if [ ! -d "$DEPLOY_PATH/.git" ]; then
  error "No git repo at $DEPLOY_PATH. Run deploy/setup-server.sh first."
  exit 1
fi

# ---- [2] Backup persistent data before touching the repo ---------------------
info "[2/7] Backing up persistent data..."
mkdir -p "$BACKUP_DIR"
BACKUP_TS=$(date +%Y%m%d-%H%M%S)
# Back up if ANY of users/ data/ memory/ has content — not just users/.
# (Team data can exist in data/ before any per-user dir is created.)
if [ -n "$(ls -A "$DEPLOY_PATH/users" "$DEPLOY_PATH/data" "$DEPLOY_PATH/memory" 2>/dev/null)" ]; then
  tar -czf "$BACKUP_DIR/users-$BACKUP_TS.tar.gz" \
    -C "$DEPLOY_PATH" users data memory 2>/dev/null || true
  info "Backup saved: $BACKUP_DIR/users-$BACKUP_TS.tar.gz"
  # Keep only the last 10 backups
  ls -t "$BACKUP_DIR"/users-*.tar.gz 2>/dev/null | tail -n +11 | xargs -r rm --
else
  warn "No persistent data to back up yet."
fi

# ---- [3] Pull code (NEVER touches untracked user data) -----------------------
info "[3/7] Pulling code..."
cd "$DEPLOY_PATH"

# Save current HEAD for rollback
PREV_SHA=$(git rev-parse HEAD 2>/dev/null || echo "")

git fetch origin "$BRANCH" --quiet

# Verify we are about to deploy what GitHub Actions says we are
REMOTE_SHA=$(git rev-parse "origin/$BRANCH")
if [ -n "$EXPECTED_SHA" ] && [ "$REMOTE_SHA" != "$EXPECTED_SHA" ]; then
  error "SHA mismatch: expected $EXPECTED_SHA, remote has $REMOTE_SHA"
  error "Another push may have arrived. Aborting to avoid deploying the wrong commit."
  exit 1
fi

# Reset only tracked files — untracked users/ data/ memory/ are NOT touched.
# NEVER run 'git clean' here — it would delete user data.
git reset --hard "origin/$BRANCH"
NEW_SHA=$(git rev-parse HEAD)
info "Deployed commit: $NEW_SHA"

# ---- [4] Fix permissions (errors are fatal — do not suppress) ----------------
info "[4/7] Fixing permissions..."
# Code files owned by root, readable by golden-hour
chown -R root:golden-hour "$DEPLOY_PATH/scripts" "$DEPLOY_PATH/skills" 2>/dev/null || true
chmod -R 750 "$DEPLOY_PATH/scripts" "$DEPLOY_PATH/skills" 2>/dev/null || true
# Secrets: owner-only (service user golden-hour owns .env)
chmod 600 "$DEPLOY_PATH/.env" 2>/dev/null || true

# ---- [4b] Re-sync OpenClaw config + systemd unit -----------------------------
info "[4b/7] Syncing OpenClaw config and systemd unit..."
# Back up the live config alongside the user-data backup, then re-deploy the
# committed template. The config has no secrets (only ${ENV} refs), so this is
# safe to overwrite on every deploy.
if [ -f "$OPENCLAW_DIR/openclaw.json" ]; then
  cp "$OPENCLAW_DIR/openclaw.json" "$BACKUP_DIR/openclaw.json.$BACKUP_TS.bak" 2>/dev/null || true
fi
install -o golden-hour -g golden-hour -m 640 \
  "$DEPLOY_PATH/deploy/openclaw.config.json" "$OPENCLAW_DIR/openclaw.json"

# Keep the installed systemd unit in sync with the repo (e.g. ExecStart changes).
if ! cmp -s "$DEPLOY_PATH/deploy/service/$SERVICE_NAME.service" \
            "/etc/systemd/system/$SERVICE_NAME.service"; then
  cp "$DEPLOY_PATH/deploy/service/$SERVICE_NAME.service" \
     "/etc/systemd/system/$SERVICE_NAME.service"
  info "systemd unit updated from repo."
fi

# ---- [5] Reload systemd and restart with graceful drain ----------------------
info "[5/7] Restarting service (graceful drain via TimeoutStopSec)..."
systemctl daemon-reload
# systemctl restart sends SIGTERM; golden-hour.service has TimeoutStopSec=30
# to allow in-flight requests to finish before SIGKILL.
systemctl restart "$SERVICE_NAME"

# ---- [6] Health check with retry (detects crash loops) -----------------------
# A service can flap active↔restarting. Require STABLE_NEEDED consecutive
# samples that are (a) active and (b) show no new restart vs the previous
# sample. Comparing each sample to the previous one (not a fixed baseline)
# correctly tolerates a single early restart while still catching a loop.
info "[6/7] Waiting for service to become healthy..."
HEALTHY=false
STABLE_NEEDED=3
stable=0
PREV_RESTARTS=$(systemctl show "$SERVICE_NAME" --property=NRestarts --value 2>/dev/null || echo 0)

for i in $(seq 1 12); do
  sleep 5
  CUR_RESTARTS=$(systemctl show "$SERVICE_NAME" --property=NRestarts --value 2>/dev/null || echo 0)
  if systemctl is-active --quiet "$SERVICE_NAME" && [ "$CUR_RESTARTS" -le "$PREV_RESTARTS" ]; then
    stable=$((stable + 1))
    info "  Attempt $i/12 — active, stable sample $stable/$STABLE_NEEDED."
    if [ "$stable" -ge "$STABLE_NEEDED" ]; then
      HEALTHY=true
      info "Service is healthy (stable for $STABLE_NEEDED samples, ~$((i*5))s)."
      break
    fi
  else
    [ "$CUR_RESTARTS" -gt "$PREV_RESTARTS" ] && warn "  Attempt $i/12 — restart detected (crash loop?)."
    stable=0
  fi
  PREV_RESTARTS="$CUR_RESTARTS"
done

if [ "$HEALTHY" != "true" ]; then
  error "Service failed to start. Showing journal:"
  journalctl -u "$SERVICE_NAME" -n 50 --no-pager || true

  # Automatic rollback to previous commit
  if [ -n "$PREV_SHA" ] && [ "$PREV_SHA" != "$NEW_SHA" ]; then
    warn "Rolling back to $PREV_SHA..."
    git reset --hard "$PREV_SHA"
    # After the reset, the working tree holds the OLD committed versions of the
    # config AND the systemd unit. Restore both so we don't run old code under
    # a new (possibly broken) unit.
    if [ -f "$DEPLOY_PATH/deploy/openclaw.config.json" ]; then
      install -o golden-hour -g golden-hour -m 640 \
        "$DEPLOY_PATH/deploy/openclaw.config.json" "$OPENCLAW_DIR/openclaw.json" || true
    fi
    if [ -f "$DEPLOY_PATH/deploy/service/$SERVICE_NAME.service" ]; then
      cp "$DEPLOY_PATH/deploy/service/$SERVICE_NAME.service" \
         "/etc/systemd/system/$SERVICE_NAME.service" || true
    fi
    systemctl daemon-reload || true
    systemctl restart "$SERVICE_NAME" || true
    error "Deployment FAILED. Rolled back code, config and unit to $PREV_SHA."
  fi
  exit 1
fi

# ---- [7] Summary -------------------------------------------------------------
info "[7/7] Deployment complete."
echo ""
echo "  Previous : ${PREV_SHA:-none}"
echo "  Current  : $NEW_SHA"
echo "  Backup   : $BACKUP_DIR/users-$BACKUP_TS.tar.gz"
