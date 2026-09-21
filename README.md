# High Agency for Codex

High Agency is a lightweight coding scaffold designed to use the LLM's own capability first, then spend extra process, stronger models, or deeper reasoning only where they materially improve correctness.

Current version: **0.8.0**

## Install

```bash
codex plugin marketplace add Ssojux2/high-agency-codex
```

Then open `/plugins`, install **high-agency**, and review/trust the bundled hooks.

## Core behavior

`$high-agency-coding` defaults to **single-agent execution with the current model**.

It keeps only five invariants:

- observable outcome;
- independently verifiable progress;
- fresh evidence after relevant edits;
- scope discipline;
- conditional escalation.

It does **not** require planning documents, TDD, worktrees, subagents, broad test suites, or review stages for every task.

## Adaptive model routing

Multi-model work is optional and only activates when delegation has real leverage: independent workstreams, large read-only exploration, high-impact architecture/security, repeated hard failures, or cheap bounded mechanical work.

When native Codex multi-agent tools are available, High Agency asks for an explicit model and reasoning effort per delegated subtask:

| Work | Preferred route |
|---|---|
| mechanical search / simple command execution / test reporting | **GPT-5.6 Luna**, low–medium |
| large repo mapping / dependency tracing / docs lookup / first-pass triage | **GPT-5.6 Terra**, medium |
| normal delegated implementation / integration / focused debugging | **GPT-5.6 Sol**, medium–high |
| difficult architecture / cross-system reasoning / high-impact security / hard root cause | **GPT-6 Astra**, high–xhigh |
| exceptional unresolved reasoning | **GPT-6 Astra**, max, rarely |

The main thread remains the integrator.

**Important:** the skill does not silently change the primary session's `/model`. It uses the current main model directly when that is efficient and routes only bounded subproblems to other models. If native subagents or a requested model are unavailable, it stays single-agent or uses the nearest available tier.

The detailed routing table lives in `skills/high-agency-coding/references/model-routing.md` and is loaded only when delegation is justified.

Explicit fallback chains keep work moving when a preferred delegated model is unavailable: Luna→Terra→main for mechanical work, Terra→Sol→main for mapping, Sol→main for implementation, and Astra→Sol→main for hard reasoning.

## Reasoning policy

Reasoning effort is treated as a budget:

- low — deterministic/mechanical;
- medium — normal bounded reasoning;
- high — complex implementation/debugging/review;
- xhigh — ambiguous or high-impact reasoning;
- max — rare final escalation.

High Agency prefers increasing effort or model quality at a cognitive bottleneck before adding blind loop iterations.

## Doctor

Run:

```text
$high-agency-doctor
```

The doctor is read-only. It checks CLI/Python/Git availability and only safe routing-related Codex settings such as the current configured model/effort, `agents.enabled`, subagent defaults/concurrency, and `allow_managed_hooks_only`.

Important diagnostics:

- `agents.enabled = false` → adaptive routing is disabled; High Agency stays single-agent.
- `allow_managed_hooks_only = true` → bundled plugin hooks may be skipped unless deployed as managed hooks.
- account/provider model availability is reported as **UNVERIFIED** unless the user explicitly requests a bounded model probe.
- session CLI overrides may differ from config; use `/status` for the live session view.

Doctor never probes every model by default.

## Verification

Verification expands only when risk expands:

```text
local change → targeted check
             → affected/related check only if propagation risk exists
             → full check only for broad/release-critical risk
```

Still-valid evidence is reused until a relevant later edit invalidates it. Independent read-only checks may run in parallel when both are already necessary.

## Git baseline tracking

Hooks detect edits made through native edit tools **and** shell commands, generators, formatters, or scripts:

1. High Agency activation records a lightweight Git baseline.
2. A verification command stores a verification snapshot.
3. Stop compares the current tree against those snapshots.
4. A relevant later edit invalidates stale verification.

The hook does not run project tests automatically.

## Conditional review

Focused final diff review triggers only for risk signals such as:

- 3+ code/config files;
- cross-module/package changes;
- schema/migrations, dependencies/lockfiles, build/deploy config, auth/security/permissions;
- a large diff.

Small local fixes normally skip an extra review stage.

## Bounded autonomy

`$bounded-autonomy` is progress-gated:

- local/narrow fix: `max=1`;
- normal multi-step work: `max=3`;
- more only when justified or explicitly requested;
- hard cap: 12.

A repeated cognitive failure should trigger model/reasoning escalation before more passes.

## Why this stays lightweight

High Agency follows a **single-agent first** rule.

A one-file fix should look like:

```text
current model → edit → targeted verification → finish
```

A hard multi-system problem may look like:

```text
Terra map ─┐
           ├→ main integrator / Sol implementation
Astra plan ┘
                    ↓
              Luna test run
                    ↓
        conditional focused review
```

The second shape appears only when its expected benefit exceeds handoff cost.

## Benchmarks and evals

`benchmarks/` contains structural process-footprint measurements. `evals/` contains task-quality and four-way comparison tooling for no-skill, High Agency, Superpowers, and Ralph.

End-to-end success claims are intentionally not published without equal-model/equal-budget runs.

## License

MIT
