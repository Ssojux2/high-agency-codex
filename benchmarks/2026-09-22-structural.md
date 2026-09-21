# Structural Benchmark — 2026-09-22

This benchmark measures **workflow instruction footprint and default control-flow overhead**, not end-to-end coding quality.

The execution environment used to maintain these repositories does not currently have the `codex` or `claude` CLI installed, so no task-success or token-cost claims are fabricated here. Those metrics belong in the reproducible task evals under `evals/`.

## Method

- Count whitespace-separated words in model-facing workflow documents.
- Exclude hook source code from model instruction footprint because hooks execute outside the model context.
- High Agency:
  - normal = `high-agency-coding/SKILL.md`
  - bounded = normal + `bounded-autonomy/SKILL.md`
- Superpowers bug-fix path = `using-superpowers` + `systematic-debugging` + `test-driven-development` + `verification-before-completion`.
- Superpowers feature path = `using-superpowers` + `brainstorming` + `test-driven-development` + `verification-before-completion`.
- Ralph instruction footprint = official `ralph-loop.md` command scaffold only. Its Stop hook is executable shell code, not model-facing process text. Repeated user prompts across iterations are not included in the word count.

These are **word counts, not model token counts**. They are a proxy for process/instruction footprint only.

## Results

| Workflow | Model-facing workflow words | Relative note |
|---|---:|---|
| No skill | 0 | baseline |
| High Agency normal | 1,163 | one lightweight coding skill |
| High Agency bounded | 1,634 | normal + bounded autonomy |
| Superpowers bug-fix path | 3,987 | debugging + mandatory TDD + verification path |
| Superpowers feature path | 5,160 | brainstorming + mandatory TDD + verification path |
| Ralph command scaffold | 129 | very small scaffold; repeated prompt/iterations dominate runtime instead |

Derived comparison:

- High Agency normal uses **70.8% fewer workflow words** than the measured Superpowers bug-fix path.
- High Agency normal uses **77.5% fewer workflow words** than the measured Superpowers feature path.
- High Agency bounded uses **59.0% fewer workflow words** than the measured Superpowers bug-fix path.
- High Agency bounded uses **68.3% fewer workflow words** than the measured Superpowers feature path.

High Agency is **not smaller than Ralph's command scaffold**. Its goal is different: spend more instruction on verification quality and stopping rules while using fewer continuation passes and avoiding unconditional repetition.

## Control-flow comparison

| Behavior | High Agency | Superpowers | Ralph |
|---|---|---|---|
| Planning | only when uncertainty justifies it | formal brainstorming/design/planning paths | none built in |
| TDD | optional | mandatory for feature/bugfix workflow | none built in |
| Test scope | touched → affected → full on risk | strong verification discipline; workflow-dependent | none built in |
| Review | focused final diff only on risk signals | review stages can be mandatory | none built in |
| Iteration | progress-gated; local `max=1`, normal `max=3` | execution workflow dependent | same prompt repeats until promise/max |
| Default unbounded loop | no | no | official Ralph defaults to unlimited unless bounded |
| Reuse valid evidence | yes | not a central default rule | no verification model built in |
| Reviewer subagent | only when separately justified | can be part of standard workflow | no |

## Hook behavior

High Agency hooks do not automatically execute project tests.

When High Agency is explicitly invoked:

1. edits invalidate verification evidence;
2. stopping after relevant edits without fresh verification triggers one targeted-verification guard;
3. final diff review triggers only on risk signals:
   - 3+ code/config files;
   - cross-module/package changes;
   - schema/migration, dependencies/lockfile, build/deploy config, auth/security/permissions;
   - 120+ changed lines when Git can measure it;
4. bounded autonomy continues only after meaningful progress.

This means the runtime guardrails are mostly dormant on small successful tasks.

## End-to-end quality benchmark status

Not yet published.

A valid quality benchmark must execute the same repository snapshot and task with:

- same model;
- same reasoning/effort setting;
- same permissions;
- same time/token budget;
- multiple repetitions for noisy tasks.

The repository already includes `evals/rubric.md`, `evals/scenarios.md`, `evals/score.py`, and `evals/compare.py` for a four-way comparison across:

- no-skill;
- High Agency;
- Superpowers;
- Ralph.

Until those actual agent runs are performed, this document makes no claim that High Agency has a higher task-success rate.
