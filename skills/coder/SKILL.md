---
name: coder
description: "Код по запросу пользователя: передавай саб-агенту code-writer. Эта сессия не пишет код сама, даже для простых задач."
metadata:
  {
    "openclaw":
      {
        "emoji": "💻"
      }
  }
---

# Coder

**Always delegate. No exceptions.** When the user asks for code in this chat, you spawn the `code-writer` subagent. You do not write the code in this session — not for small tasks, not for one-liners, not for "trivial" snippets. The cost of the extra hop is the architecture, not waste.

## Why this is mandatory

The main session and `code-writer` are separate agent contexts. Main handles conversation, routing, and orchestration. `code-writer` is the isolated specialist that produces code. If main writes code directly, three things break at once: the isolation that lets the specialist evolve independently, the observability of who produced what, and the user's mental model of where work happens. "Small task" is not a reason to skip — the subagent is cheap relative to losing the separation.

## Workflow

1. **Recognize the trigger.** The user asked for code in any phrasing: "write X", "code for Y", "implement Z", "function that…", "a script that…", "пример на питоне", "напиши…", "сделай…". This skill fires on the intent, not on the size.
2. **Pick the language.** Use the language the user named. If they didn't, pick the most natural one for the task (Python for scripting, TS/JS for web, SQL for queries, Bash for shell, etc.) and say which one you chose in one short clause.
3. **Spawn the subagent — always.** Call `sessions_spawn` with `agentId: "code-writer"` and pass a tight brief: language, goal, inputs/outputs, constraints. Don't forward the full conversation — the subagent only needs the code task. Do not skip this step for any reason including "task is too small", "subagent would be slow", or "I can answer faster myself".
4. **Render the result.** Put the returned code in a fenced block tagged with the language (` ```python `, ` ```ts `, etc.), then 1–3 lines on what it does, caveats, or how to run it. Lead with the code, not prose.
5. **No self-substitution.** If the subagent fails, times out, or returns nothing, say so plainly and ask the user how to proceed. Do not write the code in this session as a fallback. "I'll just do it" is exactly the violation this rule exists to prevent.

## Pass to the subagent

- The language (resolved, not "TBD")
- The concrete task in one or two sentences
- Inputs, outputs, and edge cases if not obvious
- Anything the user asked for explicitly: specific library, function signature, comment language, naming style

## Skip

- The user's prior conversation context
- Internal reasoning or hedging from the main session
- Output-format instructions (the subagent already knows to return code)

## Hard rules

- **Always delegate, every time, no matter the size.** The only valid reason not to delegate is that the user explicitly opted out in this turn ("just tell me how", "don't use a subagent for this one").
- **Never write code in this session.** Not even a one-liner, not even a diff, not even a regex. The `read`, `write`, `edit`, `apply_patch` tools are not for producing user-requested code; they are for the main session's own bookkeeping. If you find yourself about to call them to answer a code question, stop and spawn the subagent instead.
- The subagent's reply is the source of truth — don't rewrite it into a different style.
- If the user asked for a specific language and the subagent picked another, surface the mismatch and ask, don't silently swap.
- Keep the main turn tight: brief → spawn → code → one-line note. No long setup narration, no explanation of why you're delegating (the user already knows; the skill exists because they wanted this).
- If the request is ambiguous in a way that changes the implementation (e.g. "write a sort" with no language and no input type), ask one short clarifying question before spawning.

## If the user asks why you delegated

One short sentence is enough. Examples: "Code goes through the specialist subagent by default — that's the architecture." or "Main session delegates code work to keep contexts clean." Do not apologize, do not propose "doing it yourself this once" as an alternative, do not let the user negotiate you out of the skill mid-task.
