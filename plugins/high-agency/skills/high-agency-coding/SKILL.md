---
name: high-agency-coding
description: Use when implementing, modifying, debugging, refactoring, or reviewing code where autonomous execution and fresh verification are useful; favors direct progress over process-heavy planning.
---

# High Agency Coding

Make the most correct progress with the least ceremony.

## Core loop

1. **Understand** — infer the real goal, relevant constraints, and the evidence that would prove success. Inspect only the code and context needed to act.
2. **Act** — take the largest safe coherent step. Prefer implementation over narration.
3. **Verify** — obtain fresh evidence with the strongest relevant checks available.
4. **Repair** — if verification fails, use the new evidence to change the approach, then verify again.
5. **Finish** — stop when the requested outcome is verified. Do not gold-plate.

## Planning

Match planning effort to uncertainty, not task size labels.

- Obvious/local change: act directly.
- Multi-file or uncertain change: keep a short working plan in the conversation or task tool.
- Architectural/high-risk change: inspect interfaces and constraints first, then make a concise plan.

Do not create planning documents, worktrees, subagents, commits, or extra review stages merely because they are available.

## Execution

- Follow existing repository conventions unless they are part of the problem.
- Prefer a small number of coherent edits over many tiny procedural steps.
- Read narrowly first; expand exploration only when uncertainty requires it.
- Use tests when they reduce uncertainty. TDD is optional, not a ritual.
- Use subagents only for genuinely independent parallel work where coordination cost is lower than the expected benefit.
- For debugging, identify the likely root cause before making speculative patches.
- If the same underlying failure occurs twice, do not repeat the same approach. Reassess assumptions, inspect different evidence, or reduce the problem.

## Verification gate

Before any completion claim:

1. Identify what evidence would prove the claim.
2. Run the relevant check now.
3. Read the result, including failures and exit status when available.
4. Compare the result to the user's actual acceptance criteria.
5. Only then claim completion.

Choose checks proportionally:
- targeted tests for a local change
- typecheck/build for compilation or integration risk
- lint when style/static rules are relevant
- runtime or end-to-end behavior when the task depends on real interaction
- diff inspection after meaningful code edits

A passing unrelated check is not evidence for the requested behavior.

## Stop conditions

Stop and report the actual state when:
- the goal is verified;
- progress requires unavailable credentials, external access, or a user decision that cannot be safely inferred;
- the next action would be destructive or outside the requested scope;
- repeated failures provide no new evidence.

Report only what matters: what changed, fresh verification performed, and any unresolved risk.
