# High Agency for Codex

A lightweight coding scaffold that keeps the useful parts of strict workflows—clear completion criteria, evidence, iteration, and review—without making planning, TDD, subagents, full-suite tests, or review stages mandatory.

Current version: **0.5.0**

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

## Conditional final diff review

A final diff review is **not** required for every small fix. The Stop hook asks for a focused final diff only when one or more risk signals are present:

- 3+ code/config files changed;
- changes cross module/package boundaries;
- schema/migration, dependency/lockfile, build/deploy config, auth/security/permissions changed;
- final diff is large (currently 120+ changed lines when Git can measure it).

The hook uses files touched during the High Agency turn and asks for a focused `git diff`, not a reviewer subagent or whole-branch review.

If an edit occurs after verification or diff review, the relevant evidence is invalidated and must be refreshed.

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

The goal is not to win by doing less. It is to spend process only where it changes the probability of a correct result.

## Hooks

The hooks are active only when the user explicitly invokes High Agency in the prompt. They track edits, verification commands, and focused diff inspection.

They do **not** automatically execute project tests or launch review agents.

## Evals

`evals/` contains a rubric, scenario set, scorer, and four-way comparison plan.

```bash
python3 evals/score.py results.json > scored.json
python3 evals/compare.py scored.json
```

Compare the same task/repository/model/effort across `no-skill`, `high-agency`, `superpowers`, and `ralph`.

## License

MIT
