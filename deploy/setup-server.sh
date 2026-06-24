#!/usr/bin/env bash
# =============================================================================
# Golden Hour — Initial Server Setup Script
# Run ONCE on a fresh Ubuntu/Debian server as root or with sudo.
# After this, all subsequent deploys happen via GitHub Actions → run-deploy.sh.
# =============================================================================
set -euo pipefail

# ---- Config (override via env before running) --------------------------------
BOT_USER="${BOT_USER:-golden-hour}"
DEPLOY_PATH="${DEPLOY_PATH:-/opt/golden-hour}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/golden-hour}"
REPO_URL="${REPO_URL:-https://github.com/margoshkagt-star/Golden-Hour.git}"
REPO_BRANCH="${REPO_BRANCH:-deploy}"
NODE_VERSION="${NODE_VERSION:-20}"
# Non-standard SSH port (default 47822) — set this as GitHub Secret SSH_PORT
SSH_PORT="${SSH_PORT:-47822}"
SERVICE_NAME="${SERVICE_NAME:-golden-hour}"
# The OS user that GitHub Actions SSHes in as (NOT the bot service user)
DEPLOY_SUDO_USER="${DEPLOY_SUDO_USER:-ubuntu}"
# OpenClaw config directory (HOME-relative ~/.openclaw → /opt/golden-hour/.openclaw)
OPENCLAW_DIR="$DEPLOY_PATH/.openclaw"
# Local fallback model (Ollama). Set INSTALL_OLLAMA=0 to skip on a tiny VPS.
INSTALL_OLLAMA="${INSTALL_OLLAMA:-1}"
OLLAMA_FALLBACK_MODEL="${OLLAMA_FALLBACK_MODEL:-qwen2.5:7b-instruct}"

# ---- Colors ------------------------------------------------------------------
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*" >&2; exit 1; }

# ---- Prerequisites -----------------------------------------------------------
[[ $EUID -eq 0 ]] || error "Run as root: sudo bash deploy/setup-server.sh"

info "=== Golden Hour Server Setup ==="
info "Deploy path   : $DEPLOY_PATH"
info "SSH port      : $SSH_PORT"
info "Bot user      : $BOT_USER"
info "Deploy user   : $DEPLOY_SUDO_USER"
info "Branch        : $REPO_BRANCH"
echo ""

# ---- 1. System packages ------------------------------------------------------
info "[1/11] Updating packages..."
apt-get update -qq
apt-get install -y -qq git curl ufw fail2ban sudo

# ---- 2. Node.js --------------------------------------------------------------
info "[2/11] Installing Node.js $NODE_VERSION..."
if ! command -v node &>/dev/null; then
  curl -fsSL "https://deb.nodesource.com/setup_${NODE_VERSION}.x" | bash -
  apt-get install -y nodejs
fi
info "Node.js: $(node --version)"

# ---- 2b. OpenClaw CLI --------------------------------------------------------
info "[2b/14] Installing OpenClaw CLI..."
if ! command -v openclaw &>/dev/null; then
  npm install -g openclaw@latest
fi
command -v openclaw &>/dev/null || error "openclaw not found on PATH after npm install."
# NodeSource installs global bins under /usr/bin, not /usr/local/bin. The
# systemd unit hardcodes /usr/local/bin/openclaw, so pin a stable symlink there.
OPENCLAW_BIN="$(command -v openclaw)"
if [ "$OPENCLAW_BIN" != "/usr/local/bin/openclaw" ]; then
  ln -sf "$OPENCLAW_BIN" /usr/local/bin/openclaw
  info "Symlinked /usr/local/bin/openclaw -> $OPENCLAW_BIN"
fi
info "OpenClaw: $(openclaw --version 2>/dev/null || echo 'installed')"

# ---- 2c. Ollama (local fallback model) --------------------------------------
if [ "$INSTALL_OLLAMA" = "1" ]; then
  info "[2c/14] Installing Ollama + pulling '$OLLAMA_FALLBACK_MODEL'..."
  warn "Local model needs RAM (~6-8GB for a 7b model). On a small VPS, rerun"
  warn "with INSTALL_OLLAMA=0 or OLLAMA_FALLBACK_MODEL=llama3.2:3b."
  if ! command -v ollama &>/dev/null; then
    curl -fsSL https://ollama.com/install.sh | sh
  fi
  systemctl enable --now ollama 2>/dev/null || true
  # Wait briefly for the daemon socket, then pull the model
  for _ in $(seq 1 10); do
    curl -fsS http://127.0.0.1:11434/api/version &>/dev/null && break
    sleep 1
  done
  ollama pull "$OLLAMA_FALLBACK_MODEL" || warn "Could not pull $OLLAMA_FALLBACK_MODEL — pull it manually later."
else
  warn "[2c/14] INSTALL_OLLAMA=0 — skipping local fallback. The fallback model"
  warn "will be unreachable until Ollama is installed and the model pulled."
fi

# ---- 3. System tunables (must be done before service starts) -----------------
info "[3/14] Setting system tunables..."
cat > /etc/sysctl.d/99-golden-hour.conf <<'EOF'
# Allow high file descriptor limits for the bot service
fs.file-max = 131072
EOF
sysctl -p /etc/sysctl.d/99-golden-hour.conf

# ---- 4. Dedicated bot user ---------------------------------------------------
info "[4/14] Creating system user '$BOT_USER'..."
if ! id "$BOT_USER" &>/dev/null; then
  useradd --system --no-create-home --shell /usr/sbin/nologin "$BOT_USER"
  info "User '$BOT_USER' created."
else
  warn "User '$BOT_USER' already exists — skipping."
fi

# ---- 5. Deploy directory -----------------------------------------------------
info "[5/14] Setting up deploy directory..."
if [ -d "$DEPLOY_PATH/.git" ]; then
  warn "Repo already cloned at $DEPLOY_PATH — pulling latest."
  git -C "$DEPLOY_PATH" fetch origin "$REPO_BRANCH"
  git -C "$DEPLOY_PATH" checkout "$REPO_BRANCH"
  git -C "$DEPLOY_PATH" reset --hard "origin/$REPO_BRANCH"
else
  git clone --branch "$REPO_BRANCH" --depth 50 "$REPO_URL" "$DEPLOY_PATH"
fi

# ---- 6. Persistent data + OpenClaw dirs (NEVER overwrite on deploy) ---------
info "[6/14] Creating persistent data directories..."
# These live INSIDE the git repo directory but are .gitignored —
# git reset --hard never touches untracked directories.
# For extra safety, run-deploy.sh backs them up before every deploy.
mkdir -p \
  "$DEPLOY_PATH/users" \
  "$DEPLOY_PATH/data/teams" \
  "$DEPLOY_PATH/memory" \
  "$OPENCLAW_DIR/workspace-code" \
  "$BACKUP_DIR"

# ---- 7. Permissions ----------------------------------------------------------
info "[7/14] Setting permissions..."
# Code owned by root, readable/executable by golden-hour group
chown -R root:"$BOT_USER" "$DEPLOY_PATH"
chmod 750 "$DEPLOY_PATH"
chmod -R 750 "$DEPLOY_PATH/scripts" "$DEPLOY_PATH/skills" 2>/dev/null || true
# Deploy scripts must be owned by root and NOT writable by the deploy user
chown root:root "$DEPLOY_PATH/deploy/run-deploy.sh" "$DEPLOY_PATH/deploy/ssh-deploy-wrapper.sh"
chmod 555 "$DEPLOY_PATH/deploy/run-deploy.sh" "$DEPLOY_PATH/deploy/ssh-deploy-wrapper.sh"
# User data + OpenClaw state: bot user owns it, no world access
chown -R "$BOT_USER:$BOT_USER" \
  "$DEPLOY_PATH/users" "$DEPLOY_PATH/data" "$DEPLOY_PATH/memory" "$OPENCLAW_DIR"
chmod 700 "$DEPLOY_PATH/users" "$DEPLOY_PATH/data" "$OPENCLAW_DIR"
chown -R "$BOT_USER:$BOT_USER" "$BACKUP_DIR"

# ---- 8. Environment file -----------------------------------------------------
info "[8/14] Setting up .env..."
if [ ! -f "$DEPLOY_PATH/.env" ]; then
  cp "$DEPLOY_PATH/deploy/.env.example" "$DEPLOY_PATH/.env"
  # Auto-generate a gateway auth token (loopback control plane defense-in-depth)
  GW_TOKEN=$(openssl rand -hex 32)
  sed -i "s|^OPENCLAW_GATEWAY_TOKEN=.*|OPENCLAW_GATEWAY_TOKEN=$GW_TOKEN|" "$DEPLOY_PATH/.env"
  # Keep the Ollama model choice consistent with what we pulled
  sed -i "s|^OLLAMA_FALLBACK_MODEL=.*|OLLAMA_FALLBACK_MODEL=$OLLAMA_FALLBACK_MODEL|" "$DEPLOY_PATH/.env"
  chown "$BOT_USER:$BOT_USER" "$DEPLOY_PATH/.env"
  # 600 = owner-only, never group-readable (the deploy user cannot read secrets via SSH)
  chmod 600 "$DEPLOY_PATH/.env"
  warn "Created $DEPLOY_PATH/.env — FILL IN MINIMAX_API_KEY and TELEGRAM_BOT_TOKEN."
else
  warn ".env already exists — not overwriting. Verify it has chmod 600."
  chmod 600 "$DEPLOY_PATH/.env"
fi

# ---- 8b. OpenClaw config -----------------------------------------------------
info "[8b/14] Installing OpenClaw config (openclaw.json)..."
# Config contains NO secrets — only ${ENV} refs resolved at runtime from .env.
cp "$DEPLOY_PATH/deploy/openclaw.config.json" "$OPENCLAW_DIR/openclaw.json"
chown "$BOT_USER:$BOT_USER" "$OPENCLAW_DIR/openclaw.json"
chmod 640 "$OPENCLAW_DIR/openclaw.json"
info "Config placed at $OPENCLAW_DIR/openclaw.json"

# ---- 9. Systemd service + sudoers -------------------------------------------
info "[9/14] Installing systemd service..."
cp "$DEPLOY_PATH/deploy/service/golden-hour.service" "/etc/systemd/system/$SERVICE_NAME.service"
systemctl daemon-reload
systemctl enable "$SERVICE_NAME"

# Minimal sudoers: the deploy user may run ONLY the root-owned, immutable
# run-deploy.sh (which performs the privileged deploy steps). It cannot run
# arbitrary commands as root. The script path is owned by root + chmod 555,
# so the deploy user cannot alter what it does.
SUDOERS_FILE="/etc/sudoers.d/golden-hour-deploy"
cat > "$SUDOERS_FILE" <<EOF
# Allow $DEPLOY_SUDO_USER to run ONLY the deploy script as root.
# This file is managed by deploy/setup-server.sh — do not edit manually.
$DEPLOY_SUDO_USER ALL=(root) NOPASSWD: $DEPLOY_PATH/deploy/run-deploy.sh, $DEPLOY_PATH/deploy/run-deploy.sh *
EOF
chmod 440 "$SUDOERS_FILE"
visudo -cf "$SUDOERS_FILE" || error "sudoers syntax check failed — fix $SUDOERS_FILE"
info "sudoers installed: $SUDOERS_FILE"

# ---- 10. SSH ForceCommand (C-4: restrict deploy key to run-deploy.sh only) --
info "[10/14] Configuring SSH ForceCommand for deploy key..."
DEPLOY_HOME=$(eval echo "~$DEPLOY_SUDO_USER")
SSH_DIR="$DEPLOY_HOME/.ssh"
mkdir -p "$SSH_DIR"
chmod 700 "$SSH_DIR"

AUTH_KEYS="$SSH_DIR/authorized_keys"

# Instructions for the operator — we cannot write the key here because
# we don't know the public key at setup time. Print instructions instead.
warn "========================================================"
warn "ACTION REQUIRED: Add deploy public key to $AUTH_KEYS"
warn "The key MUST use ForceCommand pointing at the WRAPPER:"
warn ""
warn "  command=\"$DEPLOY_PATH/deploy/ssh-deploy-wrapper.sh\","
warn "  no-port-forwarding,no-X11-forwarding,no-agent-forwarding,no-pty"
warn "  ssh-ed25519 AAAA... deploy@golden-hour"
warn ""
warn "Generate a dedicated deploy key pair (Ed25519):"
warn "  ssh-keygen -t ed25519 -C deploy@golden-hour -f ~/.ssh/golden_hour_deploy"
warn "  # Add private key as GitHub Secret: SSH_PRIVATE_KEY"
warn "  # Add public key here with the ForceCommand prefix above"
warn "========================================================"

# ---- 11. Firewall & SSH hardening -------------------------------------------
info "[11/14] Configuring UFW and SSH..."

ufw --force reset
ufw default deny incoming
ufw default allow outgoing
# Allow BOTH the new non-standard port AND 22 during setup. sshd is still on 22
# at this point (the port change happens below). Removing 22 now would lock out
# the current session. After confirming login on $SSH_PORT works, remove 22:
#   sudo ufw delete allow 22/tcp
ufw allow "$SSH_PORT/tcp" comment 'SSH non-standard'
ufw allow 22/tcp comment 'SSH legacy — remove after verifying new port'
ufw --force enable
warn "UFW: allowing $SSH_PORT/tcp AND 22/tcp. Remove 22 after verifying new port:"
warn "  sudo ufw delete allow 22/tcp"

# Harden SSH
SSH_CONFIG="/etc/ssh/sshd_config"
cp -n "$SSH_CONFIG" "${SSH_CONFIG}.bak.$(date +%s)"  # backup before modifying

if grep -qE "^Port $SSH_PORT$" "$SSH_CONFIG"; then
  warn "SSH already on port $SSH_PORT — skipping port change."
else
  warn "Changing SSH port to $SSH_PORT."
  warn "CRITICAL: Open a second SSH session on port $SSH_PORT BEFORE closing this one!"
  sed -i "s/^#*Port .*/Port $SSH_PORT/" "$SSH_CONFIG"
fi

sed -i "s/^#*PermitRootLogin .*/PermitRootLogin no/" "$SSH_CONFIG"
sed -i "s/^#*PasswordAuthentication .*/PasswordAuthentication no/" "$SSH_CONFIG"

# Validate config before reloading — prevents lockout from syntax errors
sshd -t || error "sshd config validation FAILED. Check $SSH_CONFIG before reloading sshd!"
info "sshd config validated OK."
systemctl reload sshd
info "sshd reloaded on port $SSH_PORT."

# fail2ban
systemctl enable fail2ban
systemctl start fail2ban

# ---- Done --------------------------------------------------------------------
echo ""
info "=== Setup complete! ==="
echo ""
echo "Next steps:"
echo "  1. Edit $DEPLOY_PATH/.env — add MINIMAX_API_KEY and TELEGRAM_BOT_TOKEN"
echo "     (OPENCLAW_GATEWAY_TOKEN was auto-generated; Ollama model: $OLLAMA_FALLBACK_MODEL)"
echo "  2. Add the deploy public key to $AUTH_KEYS with ForceCommand (see above)"
echo "  3. Start the service: systemctl start $SERVICE_NAME"
echo "  4. Check logs: journalctl -u $SERVICE_NAME -f"
echo "  5. Verify model: openclaw doctor  (and 'ollama list' for the local fallback)"
echo ""
echo "GitHub Actions secrets to set (Settings → Secrets → Actions):"
echo "  SERVER_HOST      = your server IP or hostname"
echo "  SERVER_USER      = $DEPLOY_SUDO_USER"
echo "  SSH_PRIVATE_KEY  = contents of the deploy private key"
echo "  SSH_PORT         = $SSH_PORT"
