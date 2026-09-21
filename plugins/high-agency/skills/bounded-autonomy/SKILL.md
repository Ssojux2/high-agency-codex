---
name: bounded-autonomy
description: Use when the user asks Codex to keep working autonomously, iterate until done, fix until tests pass, or run a bounded Ralph-style loop with objective or practically verifiable acceptance criteria.
---

# Bounded Autonomy

Continue useful work without turning the task into an unbounded loop.

Use this skill only when the user explicitly asks for autonomous iteration or clearly asks to keep going until a condition is met.

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

Never weaken verification to manufacture success.