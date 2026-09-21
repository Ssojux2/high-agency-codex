# Structural Benchmark — 2026-09-22

This benchmark measures model-facing workflow instruction footprint, not end-to-end coding quality.

## v0.8 progressive disclosure

High Agency keeps the ordinary coding path small. Diagnostics and model-routing details are optional resources.

| Codex path | Model-facing workflow words |
|---|---:|
| High Agency core | **648** |
| Core + bounded autonomy | **900** |
| Core + adaptive routing reference | **1,577** |
| Bounded + adaptive routing reference | **1,829** |
| Doctor skill, opt-in only | **462** |
| Superpowers measured bug-fix path | 3,987 |
| Superpowers measured feature path | 5,160 |
| Ralph command scaffold | 129 |

Compared with the measured Superpowers paths:

- core: **83.7% / 87.4% smaller**;
- bounded: **77.4% / 82.6% smaller**;
- core + routing: **60.4% / 69.4% smaller**;
- bounded + routing: **54.1% / 64.6% smaller**.

Doctor is not part of normal coding context. The fallback/fan-out/handoff rules live in the routing reference and are loaded only when delegation is justified.

Ralph remains much smaller as a fixed scaffold; its trade-off is repeated iteration rather than richer verification/routing policy.

## Method

Whitespace-separated words from model-facing files. Hook code, Git snapshot code, tests, and benchmark/eval files are excluded because they do not enter the normal model context.

Superpowers comparison paths:
- bug-fix: using-superpowers + systematic-debugging + test-driven-development + verification-before-completion;
- feature: using-superpowers + brainstorming + test-driven-development + verification-before-completion.

Ralph: official ralph-loop command scaffold only.

These are word-count/process-footprint numbers, not tokenizer counts, success rates, or cost claims.

## v0.8 control-flow intent

| Behavior | High Agency |
|---|---|
| Default | current model, single agent |
| Delegation | only on leverage triggers |
| Concurrent delegated agents | default cap 2 |
| Recursive delegation | discouraged; root owns orchestration |
| Handoff | compact goal/evidence/constraints/return/stop packet |
| Planning | short in-context unless uncertainty warrants more |
| Testing | touched → affected → broad on risk |
| Review | focused diff only on risk |
| Iteration | progress-gated, usually max 1 or 3 |
| Diagnostics | separate read-only doctor |
| Fallback | explicit model chains, then current main model |

## End-to-end status

No task-success or token-cost advantage is claimed until equal-model/equal-budget runs are performed. Use evals/ for those comparisons.
