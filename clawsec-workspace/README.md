# clawsec workspace

OpenClaw workspace for the **`clawsec`** agent — read-only prompt-injection auditor.

## Install

```bash
cp -r clawsec-workspace ~/.openclaw/workspace-clawsec
```

Register in `openclaw.json` with `tools.deny` for write/exec/message/sessions_spawn.

**Spawn template:** `code-writer-workspace/agents/clawsec-prompt-injection-check.md`

**Suite skill:** `skills/clawsec-suite/` (install via `npx clawhub@latest install clawsec-suite`)
