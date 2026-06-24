#!/usr/bin/env bash
# =============================================================================
# Golden Hour — SSH ForceCommand wrapper
#
# This is the ONLY command the deploy SSH key may run. It ignores whatever the
# client tries to execute and instead extracts a single validated commit SHA
# from $SSH_ORIGINAL_COMMAND, then runs the (root) deploy script via sudo.
#
# This file must be:
#   - Owned by root:  chown root:root /opt/golden-hour/deploy/ssh-deploy-wrapper.sh
#   - Read-only:      chmod 555 /opt/golden-hour/deploy/ssh-deploy-wrapper.sh
#
# authorized_keys entry for the deploy user:
#   command="/opt/golden-hour/deploy/ssh-deploy-wrapper.sh",\
#   no-port-forwarding,no-X11-forwarding,no-agent-forwarding,no-pty \
#   ssh-ed25519 AAAA... deploy@golden-hour
# =============================================================================
set -euo pipefail

DEPLOY_SCRIPT="/opt/golden-hour/deploy/run-deploy.sh"

# The client's requested command (we do NOT execute it — only inspect it).
ORIG_CMD="${SSH_ORIGINAL_COMMAND:-}"

# Extract a git SHA token. Use word boundaries so a 41+ hex blob does not get
# silently truncated to a wrong-but-valid-looking 40-char SHA.
SHA="$(printf '%s' "$ORIG_CMD" | grep -oE '\b[0-9a-f]{40}\b' | head -n1 || true)"

# Require an exact 40-hex SHA. A missing/malformed SHA must NOT fall through to
# an unverified "deploy whatever HEAD is" — that would defeat SHA pinning.
if [[ ! "$SHA" =~ ^[0-9a-f]{40}$ ]]; then
  echo "ssh-deploy-wrapper: refusing — no valid 40-hex commit SHA in request." >&2
  exit 2
fi

exec sudo -n "$DEPLOY_SCRIPT" "$SHA"
