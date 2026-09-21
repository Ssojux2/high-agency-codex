# Structural Benchmark — 2026-09-22

This benchmark measures model-facing workflow instruction footprint, not end-to-end coding quality.

## v0.7 progressive disclosure

High Agency v0.7 moved model-routing detail out of the core skill. The routing reference is read only when delegation has a real trigger.

| Codex path | Model-facing workflow words |
|---|---:|
| High Agency core | **648** |
| High Agency core + bounded autonomy | **900** |
| High Agency core + adaptive routing reference | **1,260** |
| High Agency bounded + adaptive routing reference | **1,512** |
| Superpowers measured bug-fix path | 3,987 |
| Superpowers measured feature path | 5,160 |
| Ralph command scaffold | 129 |

Compared with the measured Superpowers paths:

- High Agency core is **83.7% smaller** than the bug-fix path and **87.4% smaller** than the feature path.
- High Agency bounded is **77.4% / 82.6% smaller**.
- Even when the optional model-routing reference is loaded, normal High Agency is **68.4% / 75.6% smaller**.
- Bounded + routing remains **62.1% / 70.7% smaller**.

The v0.6 core was 1,163 words, so v0.7's ordinary core path is about **44% smaller** while adding optional multi-model routing through progressive disclosure.

Ralph's command scaffold is much smaller than High Agency. That comparison is intentionally shown rather than hidden: Ralph spends very little fixed instruction but relies on repeated iterations; High Agency spends more fixed instruction on outcome/evidence/routing/stopping rules and tries to reduce unnecessary passes.

## Method

Whitespace-separated word counts from model-facing workflow files:

High Agency:
- core = `skills/high-agency-coding/SKILL.md`
- bounded = core + `skills/bounded-autonomy/SKILL.md`
- routing = core + `skills/high-agency-coding/references/model-routing.md`

Superpowers bug-fix path:
- `using-superpowers`
- `systematic-debugging`
- `test-driven-development`
- `verification-before-completion`

Superpowers feature path:
- `using-superpowers`
- `brainstorming`
- `test-driven-development`
- `verification-before-completion`

Ralph:
- official `ralph-loop.md` command scaffold only

Hook source code is excluded because it executes outside model context. Repeated Ralph prompts and platform-level agent/system prompts are also excluded.

These are word counts, not tokenizer counts.

## Control-flow intent

| Behavior | High Agency v0.7 |
|---|---|
| Default execution | current model, single agent |
| Planning | short in-context only when uncertainty needs it |
| Stronger model | only at high-leverage cognitive bottlenecks |
| Cheap model | bounded mechanical/read-heavy/test tasks |
| TDD | optional |
| Verification | touched → affected → broad on risk |
| Review | conditional focused diff |
| Iteration | progress-gated; typically max 1 or 3 |
| Evidence reuse | yes, until relevant edits invalidate it |
| Shell/generator edits | Git snapshot guard |

## End-to-end status

No task-success or token-cost advantage is claimed from this structural benchmark.

A valid quality benchmark must hold constant:
- repository snapshot;
- task;
- model availability;
- main model and effort;
- permissions;
- budget;
- repetitions.

Use `evals/` for those runs.
