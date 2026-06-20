# code-writer workspace

OpenClaw workspace for the **`code-writer`** agent — isolated code-generation specialist with mandatory safety gates.

## Pipeline

```
User message
    │
    ▼
┌─────────────────┐
│ clawsec         │  prompt-injection audit (every turn)
└────────┬────────┘
         │ clean / proceed_with_caution
         ▼
┌─────────────────┐
│ complexity-check│  LLM estimate + scripts/complexity-check.ps1 (hard patterns)
└────────┬────────┘
         │ within_limit + proceed
         ▼
┌─────────────────┐
│ coding-agent    │  writes files; self-gates with complexity-check again
└────────┬────────┘
         │
         ▼
    code returned to main
```

## Subagents

| Agent | Template | Role |
|---|---|---|
| `clawsec` | `agents/clawsec-prompt-injection-check.md` | Audit untrusted text for injection / policy evasion |
| `complexity-check` | `agents/complexity-check.md` | Estimate whether task fits ≤1000 lines |
| `coding-agent` | `agents/coding-agent.md` | Write code after gates pass |

## Install

Copy this folder to `~/.openclaw/workspace-code` (or set `agents.list[].workspace` in `openclaw.json`):

```bash
cp -r code-writer-workspace ~/.openclaw/workspace-code
```

Register subagents in `openclaw.json` (`agents.list` entries for `clawsec`, `complexity-check`, `coding-agent` with their template paths).

Pair with `skills/coder/` in the **main** workspace — see `skills/coder/README.md`.

Sibling workspaces: `clawsec-workspace/`, `complexity-check-workspace/`.

## Verify

```powershell
cd ~/.openclaw/workspace-code
.\scripts\check-gates.ps1
.\scripts\test-gates.ps1
```
