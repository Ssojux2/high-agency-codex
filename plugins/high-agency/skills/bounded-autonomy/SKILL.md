---
name: bounded-autonomy
description: Use when the user asks Codex to keep working autonomously, iterate until done, fix until tests pass, or run a bounded Ralph-style loop with objective or practically verifiable acceptance criteria.
---

# Bounded Autonomy

Continue useful work without turning the task into an unbounded loop.

Use this skill only when the user explicitly asks for autonomous iteration or clearly asks to keep going until a condition is met.

## Pass loop

For each pass:

1. Re-read the goal, acceptance criteria, and current repository state.
2. Pick the highest-value unresolved criterion.
3. Make one coherent, independently verifiable unit of progress.
4. Verify the touched or affected scope first.
5. Broaden only when dependency/integration risk requires it.
6. Continue only after meaningful new progress.

Do not create long progress files. Repository state, tests, diff, and current conversation are the primary state.

## Loop budget

Use the smallest useful continuation budget:

- **Local/narrow fix:** `max=1`
- **Normal multi-step work:** `max=3`
- **More than 3:** only when the task clearly needs it or the user requests it

The hook hard cap remains 12. A smaller budget is preferred over using the cap as a target.

## Verification budget

Do not rerun the full suite merely because a new pass started. Verify only checks invalidated by changes in the current pass, then expand to affected scope if risk requires it.

Reuse still-valid evidence from previous passes when relevant inputs have not changed.

## Progress gate

Request another continuation only if this pass produced at least one of:

- meaningful repository state change;
- new verification evidence;
- newly identified root cause or disproven assumption;
- completed or materially refined acceptance criterion.

Do not continue merely because the task is incomplete.

## Continue

If meaningful progress occurred, work remains, and the next step is actionable, end with one marker:

`<!-- high-agency:continue max=N -->`

Use the budget rules above for `N`. Keep `N` stable across continuation passes.

The bundled Stop hook starts another pass in the same turn. If the continuation prompt says this is the final pass, do not emit another marker.

Do not emit a marker when complete, blocked, or no meaningful new progress occurred.

## Failure discipline

- Never repeat an unchanged failed approach.
- After two failures with the same likely cause, reassess assumptions.
- Reduce debugging to the smallest failing surface.
- Do not weaken verification to manufacture a pass.

## Blocked conditions

Stop without a marker when progress requires unavailable access, destructive approval, a material subjective decision, missing information that cannot be inferred responsibly, or another pass would only repeat existing evidence.

When blocked, state the blocker and smallest user action needed.

## Interaction with coding work

Apply `high-agency-coding`: define done, make independently verifiable progress, use targeted/affected verification, conditionally review the final diff, and finish without scope drift.
