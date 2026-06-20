# complexity-check workspace

OpenClaw workspace for the **`complexity-check`** agent — read-only line-budget auditor (default limit: 1000 lines).

## Install

```bash
cp -r complexity-check-workspace ~/.openclaw/workspace-complexity-check
```

Register in `openclaw.json` with read-only tools (no write/exec/message/sessions_spawn).

**Spawn template:** `code-writer-workspace/agents/complexity-check.md`

**Hard enforcement script:** `code-writer-workspace/scripts/complexity-check.ps1`
