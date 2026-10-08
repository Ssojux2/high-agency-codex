# high-agency

Version: **0.13.0**

Version 0.13.0 adds explicit assumptions, proportional implementation, focused edits, and observable acceptance criteria to the coding and bounded-autonomy skills. See [coding examples and attribution](skills/high-agency-coding/references/coding-principles.md). Existing hooks, model selection, and platform launchers are unchanged.

The 0.12.1 hook fix remains included: whitespace-heavy assistant responses stay within the Impact parser timeout, CRLF and horizontal whitespace are supported, and Codex keeps its native Stop decision format.

## Prerequisites

**Python 3.10+ must be available on the PATH inherited by Codex.**

| Platform | Required interpreter / hook launcher |
|---|---|
| Linux and macOS (POSIX) | `python3` |
| Native Windows | `python`, selected by the hook's `commandWindows` entry |

An activated virtual environment is acceptable if Codex inherits its PATH. Native Windows requires a host that honors `commandWindows`; a POSIX or WSL run does not validate the native Windows launcher. The plugin does not install Python or edit global PATH/configuration. CI runs native Windows, Linux, and macOS regression suites and real Codex local-installation and model-catalog checks. Authenticated task execution remains a separate acceptance check.

## Contents

Lightweight Codex plugin containing:

- `high-agency-coding`: direct autonomous coding with explicit assumptions, focused edits, and fresh verification.
- `bounded-autonomy`: opt-in bounded continuation via the bundled Stop hook.
- `high-agency-doctor`: read-only configuration and routing diagnostics.
- `scripts/model_catalog.py`: catalog metadata lookup and family selection.
- `hooks/routing_observer.py`: read-only reporting of routing evidence.

## Routing and evidence

The current main model stays the integrator. Native subtask delegation is optional skill guidance; plugin code does not force dispatch or launch agents. Resolve exact model IDs and supported efforts from the active host's current catalog rather than a fixed release list.

| Work | Family preference order |
|---|---|
| Mechanical work / test reporting | Luna → Terra → Sol → current main model |
| BROAD MAP | Sol → Terra → current main model |
| WORKHORSE implementation | Sol → current main model |
| Hard reasoning | Astra → Sol → current main model |

Each family means its latest available supported release. Catalog query success, freshness, account entitlement/availability, native dispatch, and served-model evidence are separate checks. A successful lookup does not establish all of them.

From this plugin directory, run `python3 hooks/routing_observer.py --report --session-id "<current-session-id>"` on Linux/macOS, or `python hooks/routing_observer.py --report --session-id "<current-session-id>"` on native Windows. Supply the current session ID from the host. `--report` alone returns capabilities and **UNVERIFIED** observations; it never chooses a current/latest session automatically. Add `--agent-id "<current-agent-id>"` for child scope. If `PLUGIN_DATA` is absent, pass `--state-dir "<routing-directory>"` only with the host-known routing directory; otherwise state access remains **UNVERIFIED**.

The scoped report separates observer capability and requested-model, resolved-model, and `modelsUsed` statuses. Codex `PostToolUse` events for `spawn_agent|Agent` support requested-model and dispatch observations. The canonical child `resolvedModel`/`modelsUsed` schema is unavailable, so only the **served-model metadata capability is unsupported**, and served identity remains **UNVERIFIED**. Do not infer served identity or absence of delegation from an empty report.

State is kept per session under the plugin state directory, without copying prompts, tool output, or credentials. Diagnostics do not run paid probes automatically, install SDKs, or start nested CLI inference sessions.

The 0.12.0 audit changes are checked with regression fixtures and real Codex local plugin installation and model-catalog queries on Windows, Linux, and macOS CI. Authenticated end-to-end evaluation is still needed; token, latency, and cost savings are not established by this patch.

Codex 0.160.1 native `exec_command` hook responses omit the exit status and effective working directory. Raw output therefore remains **UNVERIFIED**, including printed success headers. The main agent must inspect the actual tool result; the hook issues bounded reminders and does not certify evidence the host did not provide.

See the [repository README](../../README.md), [routing scenarios](../../evals/routing-scenarios.md), and [runtime validation](../../docs/runtime-validation.md) for installation, usage, and evaluation evidence.
