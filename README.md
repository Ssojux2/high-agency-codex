# High Agency for Codex

A lightweight coding scaffold that keeps the useful parts of strict workflows—clear completion criteria, evidence, iteration, and review—without making planning, TDD, subagents, full-suite tests, or review stages mandatory.

Current version: **0.6.0**

## Install

```bash
codex plugin marketplace add Ssojux2/high-agency-codex
```

Then open `/plugins`, install **high-agency**, and review/trust the bundled hooks.

## Skills

- `$high-agency-coding` — define done → implement → verify touched/affected scope → conditionally review diff → finish.
- `$bounded-autonomy` — progress-gated iteration with a small dynamic pass budget.

## Lightweight verification

Verification expands only when risk expands:

```text
local change → targeted check
             → affected/related check only if propagation risk exists
             → full check only for broad/release-critical risk
```

Still-valid verification is reused until a relevant later edit invalidates it. Independent read-only checks may run in parallel when both are already necessary.

## Git baseline tracking

v0.6 closes the main v0.5 tracking gap: edits made through shell commands, generators, formatters, or scripts can now invalidate verification even when they bypass native Edit/Write tools.

When High Agency is explicitly invoked:

1. `UserPromptSubmit` records a lightweight Git baseline against the current HEAD.
2. A recognized verification command stores a verification snapshot.
3. At `Stop`, High Agency compares the current working tree to those snapshots.
4. If relevant files changed after verification, it asks for the narrowest targeted/affected check again.

The snapshot stores fingerprints only for files already changed relative to the turn's baseline HEAD, capped at 512 paths. It does not copy the repository or run a diff after every shell command.

For non-Git/unborn repositories the hook falls back to native Edit/Write tracking.

## Conditional final diff review

A final diff review is **not** required for every small fix. The Stop hook asks for a focused final diff only when one or more risk signals are present:

- 3+ code/config files changed;
- changes cross module/package boundaries;
- schema/migration, dependency/lockfile, build/deploy config, auth/security/permissions changed;
- final diff is large (currently 120+ changed lines when Git can measure it).

The hook compares the final Git state to the turn-start baseline, so shell/generator changes participate in the same risk gate.

## Bounded autonomy

Use the smallest useful budget:

- local/narrow fix: `max=1`;
- normal multi-step work: `max=3`;
- more than 3 only when clearly justified or explicitly requested;
- hard cap: 12.

The loop continues only after meaningful progress. The final allowed pass cannot request another pass.

## Why lighter than Superpowers and Ralph

| Concern | Superpowers / Ralph | High Agency |
|---|---|---|
| Planning | Superpowers uses formal design/plan stages | minimal outcome contract; plan only on uncertainty |
| TDD | mandatory in Superpowers | optional; tests chosen by information value |
| Worktree/subagents | often structured into workflow | only when isolation/parallelism materially helps |
| Review | task/branch reviews can be mandatory | focused final diff only on risk signals |
| Test scope | strong verification, often workflow-wide | touched → affected → full only on escalation |
| Iteration | Ralph repeats until promise/max | progress-gated, usually 1 or 3 extra passes |
| Repeated checks | workflow stages may repeat checks | reuse evidence until relevant inputs change |

## Benchmark

A reproducible structural benchmark is in [`benchmarks/2026-09-22-structural.md`](benchmarks/2026-09-22-structural.md).

The v0.6 change is hook-only, so the model-facing workflow instruction footprint is unchanged from v0.5:

| Workflow | Model-facing workflow words |
|---|---:|
| High Agency normal | **1,163** |
| High Agency bounded | **1,634** |
| Superpowers bug-fix path | 3,987 |
| Superpowers feature path | 5,160 |
| Ralph command scaffold | 129 |

These are process-footprint measurements, not task-success claims. End-to-end quality results should only be published after equal-model/equal-budget agent runs.

## Hooks

Hooks are active only when the user explicitly invokes High Agency. They do **not** automatically execute project tests or launch review agents.

## Tests and evals

`tests/test_git_state.py` covers shell edits, pre-existing dirty files, untracked generator output, and verification snapshot invalidation.

`evals/` contains the task-quality rubric and four-way comparison tooling.

```bash
python3 -m unittest tests/test_git_state.py
python3 evals/score.py results.json > scored.json
python3 evals/compare.py scored.json
```

## License

MIT
