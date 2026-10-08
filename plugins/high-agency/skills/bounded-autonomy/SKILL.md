---
name: bounded-autonomy
description: Use when the user asks Codex to keep working autonomously, iterate until done, fix until tests pass, or run a bounded Ralph-style loop with objective or practically verifiable acceptance criteria.
---

# Bounded Autonomy

Continue useful work without turning the task into an unbounded loop.

Use this skill only when the user explicitly asks for autonomous iteration or clearly asks to keep going until a condition is met.

Before the first mutating pass, run `python3 "<installed-plugin-root>/hooks/verification_state.py" --activate` through the host shell on Linux/macOS; use `python` on native Windows. Require Python 3.10+ and resolve this skill's actual installed root. The PreToolUse hook supplies session identity; preserve an already active task. If hooks are unavailable, use manual verification and report the continuation guard as UNVERIFIED. Do not install an interpreter or change global settings automatically.

Keep acceptance criteria anchored to the user's requested outcome. Clarify material gaps before dependent work; use a stated reversible assumption for low-risk choices. Do not add requirements or lower the completion bar just to keep the loop moving.

For each pass:

1. pick the highest-value unresolved acceptance criterion;
2. make one independently verifiable unit of progress;
3. verify only evidence invalidated by the pass, expanding to affected scope only on risk;
4. continue only after meaningful new progress.

## Loop budget

Use the smallest useful continuation budget:

- local/narrow fix: `max=1`
- normal multi-step work: `max=3`
- more than 3: only when clearly justified or explicitly requested
- hard cap: 12

Do not use more passes to compensate for weak reasoning. If the same underlying failure survives two evidence-based attempts, use the model/reasoning escalation policy from `high-agency-coding/references/model-routing.md` when available before asking for more iterations.

## Continue

If meaningful progress occurred, work remains, and the next step is actionable, end with:

`<!-- high-agency:continue max=N -->`

Keep `N` stable across continuation passes. If the continuation prompt says this is the final pass, do not emit another marker.

Do not continue merely because the task is incomplete. Stop when blocked, when no new evidence/progress was produced, or when another pass would repeat the same approach.

Stop when the acceptance criteria have sufficient fresh evidence; do not consume unused passes on speculative features, adjacent cleanup, or extra tests. If a criterion remains unverified, report it explicitly.

Never weaken verification to manufacture success.
