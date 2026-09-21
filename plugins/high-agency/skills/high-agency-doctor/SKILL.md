---
name: high-agency-doctor
description: Use when diagnosing High Agency installation, routing, hooks, model/effort configuration, or unexpected delegation behavior in Codex. Performs read-only checks and never modifies project files.
---

# High Agency Doctor — Codex

Diagnose configuration without turning the diagnostic into an agent workload.

Do not edit project files. Do not run model probes unless the user explicitly asks for them.

## Checks

Run these cheap read-only checks:

1. `codex --version`
2. `python3 --version`
3. `git --version`
4. Inspect only safe High Agency-relevant Codex configuration values from:
   - `$CODEX_HOME/config.toml` when `CODEX_HOME` is set;
   - otherwise `~/.codex/config.toml`;
   - trusted project `.codex/config.toml` when present.

Use Python `tomllib` or equivalent. Do **not** print the full config file.

Report only:
- `model`
- `model_reasoning_effort`
- `plan_mode_reasoning_effort`
- `allow_managed_hooks_only`
- `agents.enabled`
- `agents.default_subagent_model`
- `agents.default_subagent_reasoning_effort`
- `agents.max_concurrent_threads_per_session`

Also remind the user that session/CLI overrides may differ; `/status` is the authoritative interactive view for the current session.

## Interpret

Flag these conditions:

- **WARN** `agents.enabled = false`: adaptive subagent routing is unavailable; High Agency should stay single-agent.
- **WARN** `allow_managed_hooks_only = true`: bundled High Agency hooks may be skipped unless deployed as managed hooks.
- **INFO** low concurrency: parallel delegation may be limited, but correctness should not depend on parallelism.
- **INFO** default subagent model/effort: explicit High Agency spawn settings take precedence when the runtime supports them.
- **UNVERIFIED** model availability: static config cannot prove that Astra/Sol/Terra/Luna are actually available to the current account/provider.

Do not treat an absent optional setting as an error.

## Routing contract

Expected fallback chains:

- mechanical/test reporting: **Luna → Terra low/medium → current main model**
- broad mapping/triage: **Terra → Sol medium → current main model**
- normal delegated implementation: **Sol → current main model**
- hard architecture/root cause/security: **Astra high/xhigh → Sol high/xhigh → current main model**
- exceptional max-depth reasoning: **Astra max → Astra xhigh/high → Sol xhigh/high → current main model**

Fallback must preserve the task instead of blocking because a preferred model is unavailable.

## Optional model probe

Only if the user explicitly asks to probe models:

- use the smallest possible read-only/no-write one-turn subagent probe;
- probe only the routes relevant to the user's problem, not every model automatically;
- report dispatch success/failure and any runtime model metadata actually exposed;
- do not claim the served model is verified when the runtime does not expose proof;
- stop probes immediately if they would consume meaningful cost or permissions.

## Output

Return a compact table:

| Check | Status | Detail |
|---|---|---|

Then list only actionable warnings and the effective fallback behavior.