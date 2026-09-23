# Structural Benchmark — 2026-09-22

This benchmark measures model-facing workflow instruction footprint, not end-to-end coding quality.

## v0.9 impact calibration

High Agency v0.9 adds one model-facing invariant to the ordinary path: predict expected change scope before mutation, then compare the actual diff against that immutable estimate.

| Codex path | Model-facing workflow words |
|---|---:|
| High Agency core | **816** |
| Core + bounded autonomy | **1,068** |
| Core + adaptive routing reference | **1,758** |
| Bounded + adaptive routing reference | **2,010** |
| Superpowers measured bug-fix path | 3,987 |
| Superpowers measured feature path | 5,160 |
| Ralph command scaffold | 129 |

Compared with the measured Superpowers paths:

- core: **79.5% / 84.2% smaller**;
- bounded: **73.2% / 79.3% smaller**;
- core + routing: **55.9% / 65.9% smaller**;
- bounded + routing: **49.6% / 61.0% smaller**.

The v0.8 core was 648 words. v0.9 adds about 168 words for impact prediction/calibration while keeping routing, doctor, hooks, tests, and eval machinery progressively disclosed or outside model context.

## v0.9 control-flow intent

| Behavior | High Agency |
|---|---|
| Default | current model, single agent |
| Impact estimate | one immutable line before code/config mutation |
| Scope comparison | predicted files/modules/boundary vs actual diff |
| Match | keep targeted path |
| Minor drift | affected verification only |
| Major drift | focused diff + risk-scoped broader verification |
| Stronger model | only if expanded scope creates cognitive leverage |
| Fixed heuristics | fallback when estimate is absent; high-impact/large-diff safety net remains |
| Delegation | only on leverage triggers |
| Concurrent delegated agents | default cap 2 |
| Iteration | progress-gated, usually max 1 or 3 |

## Method

Whitespace-separated words from model-facing workflow files. Hook source, Git snapshot logic, impact parser, tests, benchmark files, and eval files are excluded because they execute outside the normal model prompt.

Superpowers comparison paths:
- bug-fix: using-superpowers + systematic-debugging + test-driven-development + verification-before-completion;
- feature: using-superpowers + brainstorming + test-driven-development + verification-before-completion.

Ralph: official ralph-loop command scaffold only.

These are process-footprint numbers, not tokenizer counts, success rates, or cost claims.

## End-to-end status

No task-success or token-cost advantage is claimed until equal-model/equal-budget runs are performed. v0.9 evaluation should additionally measure impact underestimation, overestimation, drift severity, escalation precision, and escalation recall. See evals/impact-calibration.md.
