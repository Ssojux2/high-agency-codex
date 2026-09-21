---
name: bounded-autonomy
description: Use when the user asks Codex to keep working autonomously, iterate until done, fix until tests pass, or run a bounded Ralph-style loop with objective or practically verifiable acceptance criteria.
---

# Bounded Autonomy

Continue useful work without turning the task into an unbounded loop.

Use this skill only when the user explicitly asks for autonomous iteration or clearly asks to keep going until a condition is met.

## Pass loop

For each pass:

1. Re-read the user's goal, acceptance criteria, and current repository state.
2. Identify the highest-value unresolved acceptance criterion.
3. Make one coherent, independently verifiable unit of progress.
4. Run fresh relevant verification.
5. Decide whether the pass produced meaningful new progress.
6. Continue only when more work is both necessary and actionable.

Prefer direct work over status narration. Do not create long progress files. The repository, tests, diff, and current conversation are the primary state.

## Progress gate

Request another continuation only if this pass produced at least one of:

- a meaningful repository state change
- new verification evidence
- a newly identified root cause or disproven assumption
- a completed or materially refined acceptance criterion

Do not continue merely because the task is incomplete.

## Completion

Finish normally when the requested acceptance criteria are verified. State the verification evidence.

Do not request another continuation merely because more polish is possible.

## Continue

If meaningful progress occurred, work remains, and the next step is actionable, end the assistant message with exactly one hidden marker:

`<!-- high-agency:continue max=3 -->`

The bundled Codex Stop hook recognizes this marker and starts another continuation pass in the same turn.

- `max` is the maximum number of additional continuation passes.
- Default to `max=3`.
- Use a smaller value for narrow tasks.
- Do not exceed `max=8` unless the user explicitly requests a higher bounded limit; the hook has a hard safety cap of 12.
- Keep the same `max` value across continuation passes.
- If the continuation prompt says this is the final bounded-autonomy pass, do not emit another marker.

Do not emit the marker when complete, blocked, or when the pass produced no meaningful new progress.

## Failure discipline

- Never repeat an unchanged failed approach.
- After two failures with the same likely cause, reassess assumptions before continuing.
- Reduce scope to the smallest failing surface when debugging.
- Treat fresh test/build/runtime output as stronger evidence than prior reasoning.
- Do not weaken verification to manufacture a passing result.

## Blocked conditions

Stop without a continuation marker when progress requires:

- unavailable credentials or external access;
- destructive action needing user approval;
- a subjective product decision with materially different outcomes;
- missing information that cannot be responsibly inferred;
- another pass that would only repeat existing evidence.

When blocked, state the blocker and the smallest user action needed to unblock it.

## Interaction with coding work

When changing code, use the same lightweight principles as `high-agency-coding`: define done, act in independently verifiable steps, verify real behavior, repair from evidence, and finish without scope drift.
