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
2. `python3 --version` on Linux/macOS; `python --version` on native Windows. Require Python 3.10+. An activated virtual environment can supply the interpreter; do not install it or edit global aliases/settings automatically.
3. `git --version`
4. Inspect only safe High Agency-relevant Codex configuration values from:
   - `$CODEX_HOME/config.toml` when `CODEX_HOME` is set;
   - otherwise `~/.codex/config.toml`;
   - trusted project `.codex/config.toml` when present.

Use Python `tomllib` where available, an existing trusted parser, or a supported host config-read capability. Python 3.10 lacks `tomllib`; if no safe parser is available, report parsing unverified instead of installing one for this check. Do **not** print the full config file.

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

## Current model catalog

Read `../high-agency-coding/references/model-routing.md`. Prefer the active host's complete `model/list` response. In a matching local account/provider/profile, run `python3 "<installed-plugin-root>/scripts/model_catalog.py"` on Linux/macOS, or `python "<installed-plugin-root>/scripts/model_catalog.py"` on native Windows, to inspect available role models and supported reasoning efforts. Resolve the script from the installed skill path, not the project working directory.

This is a metadata query, not an inference/model probe. It sends no prompt and starts no thread or turn. Do not install another SDK or read credentials. Skip the CLI helper when its configuration differs from the active host; use the host catalog instead. A saved JSON catalog must have current provenance.

Report `query_status`, `freshness_status`, `entitlement_status`, `dispatch_status`, and `selection_status` separately with source, lookup time, requested/selected IDs, supported efforts, and fallback. An app-server query can return a cached/bundled catalog; its timestamp does not establish freshness or entitlement. A failed lookup is **UNVERIFIED**, not proof the account lacks access. An empty/unknown catalog explicitly keeps the current main model. Do not change user/admin pins or global configuration to make a model appear available.

## Recorded routing evidence

Run the installed `hooks/routing_observer.py --report --session-id <current-session-id>` with the platform's interpreter above. Use only a session ID supplied by the active host. With no reliable ID, use `--report` alone and leave current-session observations UNVERIFIED. Never select another recent session automatically.

The observer records native `Agent`/`spawn_agent` PostToolUse requested model/effort and exposed child identity. The current Codex adapter has **unsupported** child `resolvedModel`/`modelsUsed` and served-effort metadata capabilities. The common hook `model` describes the parent, so it is never substituted as the child's model. A launch does not prove completion, and request evidence does not prove serving identity.

If `PLUGIN_DATA` is unavailable, pass `--state-dir` only with the routing-state directory explicitly supplied by the host; otherwise report state access UNVERIFIED. The report is read-only. `capabilities` describes the documented contract, not a live host probe. The helper neither dispatches agents nor performs model discovery. Missing events can indicate disabled/untrusted hooks or absent metadata and are not proof that routing never happened.

## Interpret

Flag these conditions:

- **WARN** `agents.enabled = false`: adaptive subagent routing is unavailable; High Agency should stay single-agent.
- **WARN** `allow_managed_hooks_only = true`: bundled High Agency hooks may be skipped unless deployed as managed hooks.
- **INFO** low concurrency: parallel delegation may be limited, but correctness should not depend on parallelism.
- **INFO** default subagent model/effort: explicit High Agency spawn settings take precedence when the runtime supports them.
- **WARN** configured model is older than the latest available version of its family: report the mismatch; do not rewrite an intentional pin.
- **UNVERIFIED** model availability: static config cannot prove that Astra/Sol/Terra/Luna are actually available to the current account/provider.
- **UNVERIFIED** bundled hook trust: Codex requires plugin hooks to be reviewed/trusted; static config alone may not prove the current hook trust state. Ask the user to inspect `/hooks` when hook behavior is unexpectedly absent.

Do not treat an absent optional setting as an error.

## Routing contract

Resolve the latest available version and supported effort for every candidate in these fallback chains:

- mechanical/test reporting: **Luna → Terra low/medium → Sol low/medium → current main model**
- broad mapping/triage: **Sol medium → Terra medium → current main model**
- normal delegated implementation: **Sol → current main model**
- hard architecture/root cause/security: **Astra high/xhigh → Sol high/xhigh → current main model**
- exceptional max-depth reasoning: **Astra max → Astra xhigh/high → Sol xhigh/high → current main model**

Fallback must preserve the task instead of blocking because a preferred model is unavailable. No fixed release ID is a fallback catalog. After rejection, refresh at most once, exclude the rejected ID (`--exclude-model`), and attempt at most one supported fallback before continuing on the main model.

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
