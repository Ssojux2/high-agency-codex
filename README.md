# High Agency for Codex

High Agency is a lightweight coding scaffold designed to use the LLM's own capability first, then spend extra process, stronger models, or deeper reasoning only where they materially improve correctness.

Current version: **0.12.1**

## Prerequisites

**Python 3.10+ must be available on the PATH inherited by Codex.**

| Platform | Required interpreter / hook launcher |
|---|---|
| Linux and macOS (POSIX) | `python3` |
| Native Windows | `python`, selected by the hook's `commandWindows` entry |

An activated virtual environment is acceptable if Codex inherits its PATH. Native Windows requires a host that honors `commandWindows`; a POSIX or WSL run does not validate the native Windows launcher. The plugin does not install Python or edit global PATH/configuration. CI runs native Windows, Linux, and macOS regression suites and real Codex local-installation and model-catalog checks. Authenticated task execution remains a separate acceptance check.

## Install

```bash
codex plugin marketplace add Ssojux2/high-agency-codex
```

Then open `/plugins`, install **high-agency**, and review/trust the bundled hooks.

**0.12.1 hook fix:** Impact parsing stays within individual lines. This fixes a reproducible 12-second hook timeout on whitespace-heavy assistant responses while preserving the first valid estimate. Native Windows, Linux, and macOS run the regression coverage. Codex keeps its own supported Stop decision format.

> **v0.12.0 routing audit:** catalog query success, freshness, account entitlement, and native dispatch are now separate evidence checks. Read-only routing observations report only the metadata the host exposes. Validation combines regression fixtures with real Codex local plugin installation and model-catalog queries on Windows, Linux, and macOS CI. Authenticated end-to-end routing still needs user-run evaluation.

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

When native Codex multi-agent tools are available, High Agency asks for an explicit model and supported reasoning effort per delegated subtask. Resolve exact model IDs from the active host's complete, current catalog for the same account, provider, and configuration. Family names below are policy preferences; they are not fixed release IDs.

| Work | Preferred family and desired effort |
|---|---|
| mechanical search / simple command execution / test reporting | latest available **Luna**, low–medium |
| large repo mapping / dependency tracing / docs lookup / first-pass triage | latest available **Sol**, medium; Terra if Sol is unavailable |
| normal delegated implementation / integration / focused debugging | latest available **Sol**, medium–high |
| difficult architecture / cross-system reasoning / high-impact security / hard root cause | latest available **Astra**, high–xhigh |
| exceptional unresolved reasoning | latest available **Astra**, max only if supported, rarely |

Use only effort levels supported by the selected model and host. If a desired effort is unavailable, choose a supported substitute or keep the current model and record the fallback. A catalog query succeeding does not, by itself, prove freshness, account entitlement, or that inference ran.

The main thread remains the integrator.

**Important:** the primary session model stays unchanged. Routing is optional guidance for bounded native subtasks; plugin code does not force dispatch or launch agents. The skill uses the current main model directly when that is efficient. If native subagents or a requested model are unavailable, it stays single-agent or follows the supported fallback chain. Explicit user/admin model pins remain in place.

Before the first code/config mutation, High Agency now emits one unified preflight from the same read-only inspection:

```text
Preflight: <short task-shape summary>
Complexity: low | medium | high | frontier
Route: DIRECT | CHEAP DELEGATE | BROAD MAP | WORKHORSE | STRONG REASONING
Model: <current main model or exact delegated model + reasoning effort>
Impact: local | files<=N | modules<=N | boundary=private|shared-api|high-impact
```

The summary, complexity, route, model, and impact estimate are one decision. For non-DIRECT routes, the requested native subagent model/reasoning should match the preflight `Model:` line when the runtime supports explicit per-spawn selection.

A routing choice counts as executed only when a native Codex subagent is actually spawned. When supported, the spawn should carry the intended model and reasoning effort explicitly. Merely recommending Astra/Sol/Terra/Luna in prose is not considered successful routing. If the runtime cannot select a model per spawn, High Agency reports the effective fallback/default route instead of pretending the requested model ran.

Explicit fallback chains use the latest available version within each family: **Luna → Terra → Sol → current main model** for mechanical work, **Sol → Terra → current main model** for BROAD MAP, **Sol → current main model** for WORKHORSE implementation, and **Astra → Sol → current main model** for hard reasoning. These are candidate preferences, not a request to try every model. After a rejection, refresh at most once and attempt one supported fallback before continuing on the current main model.

## Reasoning policy

Reasoning effort is treated as a budget, constrained by the selected model's advertised capabilities:

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
- catalog query success, freshness, account entitlement/availability, and dispatch success are reported separately; static configuration or a parsed catalog cannot establish all four.
- use the active host's model catalog. The bundled `scripts/model_catalog.py` helper is a metadata query only, and its local account/provider/profile/configuration must match the session before its result is used for routing.
- missing availability evidence is **UNVERIFIED**. A lookup failure is not proof that the account lacks access.
- session CLI overrides may differ from config; use `/status` for the live session view.

Doctor does not run paid model probes automatically, install an SDK, or start nested CLI inference sessions. A bounded native model probe requires an explicit user request.

## Read-only routing observations

From the plugin root (`plugins/high-agency/` in a checkout), select the current host session explicitly. Replace the placeholder with the session ID supplied by the host.

Linux/macOS:

```sh
python3 hooks/routing_observer.py --report --session-id "<current-session-id>"
```

Native Windows:

```powershell
python hooks/routing_observer.py --report --session-id "<current-session-id>"
```

`--report` alone shows capabilities with observations **UNVERIFIED**; it does not read a current or latest session automatically. Add `--agent-id "<current-agent-id>"` when inspecting a child agent's scope. If the report process does not have Codex's `PLUGIN_DATA`, add `--state-dir "<routing-directory>"` only when the host supplies that routing-state directory. If its location is unknown, state access remains **UNVERIFIED**; do not guess a directory or choose another session.

The scoped report separates observer capability from requested-model, resolved-model, and `modelsUsed` statuses. A request is evidence of intent; only explicit host model metadata can support a claim about the resolved or served model. Missing model metadata remains **UNVERIFIED**.

Codex supports request/dispatch observations through native `PostToolUse` events for `spawn_agent|Agent`. A canonical child `resolvedModel`/`modelsUsed` schema is not available for these hook events, so the **served-model metadata capability is unsupported** and served identity remains **UNVERIFIED**. Keep that limitation separate from supported request/dispatch observations. An empty report does not prove that no subagent ran; assess any other host-provided dispatch evidence separately.

Observation state is kept per session under the plugin state directory. It retains bounded routing metadata without copying prompts, tool output, or credentials. The observer reports evidence; it does not change the main model, dispatch agents, or enforce a routing choice.

## Impact calibration

The `Impact:` line is now the final line of the unified preflight. The first estimate remains immutable so existing scope-drift hooks can use it as the baseline. The model should not rewrite it later to match what happened.

At completion, the hook compares the actual Git diff against that estimate:

```text
match
→ keep targeted verification

minor drift
→ extend verification only to the newly affected surface

major drift / unexpected high-impact boundary
→ inspect the focused final diff
→ broaden verification only for the expanded risk
→ escalate model/reasoning only if the new scope creates a real cognitive bottleneck
```

The hook objectively checks file count, module spread, truncated change sets, and known high-impact paths such as auth/security/schema/dependency/build/deploy surfaces. Public/shared API drift that cannot be inferred reliably from paths remains a semantic final-diff check for the model.

If no valid estimate was produced, High Agency falls back to its fixed safety heuristics rather than silently assuming the task is local.

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

Focused final diff review is calibration-aware. When a valid impact estimate exists, ordinary file/module growth is judged against that estimate rather than a fixed count. High-impact shared paths and unusually large diffs remain safety nets. If no estimate exists, fixed multi-file/cross-module heuristics remain the fallback.

Small changes that stay inside their predicted scope normally skip an extra review stage.

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
Sol map ───┐
           ├→ main integrator / Sol implementation
Astra plan ┘
                    ↓
              Luna test run
                    ↓
        conditional focused review
```

The second shape appears only when its expected benefit exceeds handoff cost.

## High Agency vs Superpowers vs Ralph Loop

The three approaches optimize for different things:

- **Superpowers** — maximize consistency by enforcing a development process.
- **Ralph Loop** — maximize persistence by repeating until a completion condition is reached.
- **High Agency** — maximize model capability per unit of process by staying single-agent first and adding planning, stronger models, broader verification, review, or continuation only when evidence/risk justifies it.

### Summary

| Dimension | High Agency | Superpowers | Ralph Loop |
|---|---|---|---|
| Core philosophy | model judgment + conditional guardrails | process discipline | persistent iteration |
| Default process overhead | low | high | very low |
| Planning | only when uncertainty warrants it | formal brainstorming/spec/plan workflow | no built-in planning discipline |
| TDD | optional | central/mandatory in feature/bug-fix paths | not built in |
| Subagents | only when delegation has leverage | actively used by workflow | not core |
| Model/effort routing | adaptive | not the main design goal | not built in |
| Verification | touched → affected → broad on risk | strong verification/TDD discipline | depends on the prompt/agent |
| Review | focused and conditional | review stages can be part of the normal workflow | not built in |
| Iteration | progress-gated, usually 1–3 extra passes | workflow-dependent | core mechanism |
| Reuse of valid evidence | yes | not a central default rule | no verification model built in |
| False-completion defense | fresh evidence + Stop guard | strong | completion promise / loop condition |
| Token/process efficiency | explicit design goal | secondary to process consistency | highly dependent on iteration count |

### Where High Agency is stronger than Superpowers

High Agency deliberately avoids forcing the full development ceremony onto every task.

A small local fix can remain:

```text
current model
→ inspect
→ edit
→ targeted verification
→ finish
```

There is no mandatory brainstorming, plan document, worktree, TDD cycle, reviewer, or broad test suite unless the task actually benefits from it.

This gives High Agency three main advantages:

1. **Lower process overhead on routine work**  
   Strong models can act directly instead of spending tokens proving that a simple task deserves a simple solution.

2. **Adaptive compute allocation**  
   Cheap/read-heavy/mechanical work can be delegated to lower-cost models, while difficult architecture, security, or root-cause reasoning can escalate to stronger models and higher reasoning effort.

3. **Risk-based verification instead of workflow-wide verification**  
   Verification starts at the changed surface and expands only when propagation risk exists.

The trade-off is that High Agency trusts model judgment more. If the model underestimates task complexity, chooses the wrong verification scope, or fails to escalate when it should, Superpowers' stronger procedural constraints may be more robust.

### Where Superpowers is stronger

Superpowers is intentionally more prescriptive.

That can be valuable when:

- a weaker or less reliable model needs process discipline;
- the project benefits from explicit design approval before implementation;
- a team wants TDD and review to be mandatory rather than discretionary;
- reducing behavioral variance matters more than minimizing token/process overhead.

In short:

```text
Superpowers
= lower behavioral variance
  + stronger process guarantees
  - higher ceremony and context cost
```

### Where High Agency is stronger than Ralph Loop

Ralph's key strength is persistence:

```text
not complete
→ run again
→ run again
→ run again
```

High Agency keeps that useful idea but adds a progress gate.

Another pass is justified only when the previous pass produced something such as:

- a meaningful repository-state change;
- new verification evidence;
- a newly identified or disproven root cause;
- material progress on an acceptance criterion.

So the default rule is closer to:

```text
not complete
+ meaningful progress
+ actionable next step
→ continue
```

rather than simply:

```text
not complete
→ continue
```

High Agency also prefers **reasoning/model escalation before blind iteration** when the same cognitive failure survives multiple evidence-based attempts.

### Where Ralph Loop is stronger

Ralph is much simpler and can be very effective when persistence itself is the main requirement.

It can be a good fit for:

- long-running migrations;
- large repetitive refactors;
- many failing tests that can be fixed incrementally;
- tasks with a very clear completion condition and cheap iterations.

Its simplicity is also its weakness: it does not define which tests to run, when evidence is stale, whether the approach is repeating itself, or when a stronger model would be more effective than another iteration.

### High Agency's design position

High Agency is not intended to be a compromise halfway between Superpowers and Ralph.

It selectively borrows the useful parts of both:

From Superpowers:
- verification discipline;
- root-cause discipline;
- planning when uncertainty is real.

From Ralph:
- continuation;
- persistence.

And adds:
- adaptive model and reasoning routing;
- single-agent-first execution;
- targeted → affected → broad verification;
- evidence reuse;
- Git-state invalidation;
- conditional diff review;
- bounded, progress-gated continuation.

The intended runtime shape is:

```text
                     main model
                         │
              simple task? ── yes ──→ direct implementation
                         │
                         no
                         ↓
                 adaptive escalation
            ┌────────────┼────────────┐
            │            │            │
       cheap/broad    workhorse    frontier
            │            │            │
       lower-cost       normal      strongest
         model          model       reasoning
            └────────────┼────────────┘
                         ↓
                 main integration
                         ↓
              targeted verification
                         ↓
                 risk propagation?
                  │             │
                 no            yes
                  │             ↓
                  │       affected/broad check
                  │             ↓
                  │       conditional review
                  └─────────────┘
                         ↓
                       done
```

### Current trade-off

High Agency's biggest advantage is also its biggest risk: **it relies more on the model making good meta-decisions**.

The important questions are not hard-coded into a fixed workflow:

- Is this task complex enough to plan?
- Is delegation worth its context/handoff cost?
- Is targeted verification enough?
- Should reasoning/model quality escalate?
- Is another continuation likely to produce new evidence?

That is why the current roadmap is evaluation-first. Existing structural measurements describe prescribed process footprint. They do not establish a higher end-to-end task-success rate, token or latency savings, or a benefit caused by the 0.12.0 routing changes. Those outcomes need equal-model/equal-budget end-to-end benchmarks.

### Practical fit

| Task type | Likely fit |
|---|---|
| routine coding / small bug fix | High Agency |
| strong modern model with tight token/time budget | High Agency |
| adaptive multi-model execution | High Agency |
| mandatory TDD / formal development workflow | Superpowers |
| strict design-before-code process | Superpowers |
| very long autonomous repetitive work | Ralph Loop |
| clear completion condition + cheap retries | Ralph Loop |
| long-running work where iteration cost also matters | High Agency bounded autonomy |

## Benchmarks and evals

`benchmarks/` contains structural process-footprint measurements. `evals/` contains task-quality and four-way comparison tooling for no-skill, High Agency, Superpowers, and Ralph.

End-to-end success claims are intentionally not published without equal-model/equal-budget runs.

## Development status

**v0.12.0 is the current evaluation baseline.**

This audit release updates family routing, separates catalog lookup from freshness, entitlement, and dispatch evidence, and adds read-only routing observations. The main model remains the integrator, and delegation stays an optional native subtask decision.

**Codex 0.160.1 limitation:** native `exec_command` hooks receive raw output without the exit status and effective working directory needed to certify a successful check. Those results remain **UNVERIFIED**; a printed success message never upgrades them. The main agent still inspects its real tool results, and Stop uses bounded reminders. See [execution-result limitations](docs/runtime-validation.md#codex-01601-execution-result-limitation).

Validation combines regression fixtures with real Codex local plugin installation and model-catalog queries on Windows, Linux, and macOS CI. Actual CLI end-to-end dispatch, served-model identity where exposed, fallback behavior, and efficiency still require explicit user-run evaluation. See [routing scenarios](evals/routing-scenarios.md) and [runtime validation](docs/runtime-validation.md) for the evidence to capture; these changes do not establish token, latency, or cost savings.

Further runtime features, routing rules, thresholds, or orchestration complexity should not be added based on intuition alone. The next behavioral changes should be driven by real end-to-end Codex/Claude Code runs using the existing `evals/` scenarios and comparable model/budget settings, including impact-estimate calibration.

Before changing the runtime, collect evidence such as:

- task success and false-completion rate;
- impact underestimation / overestimation rate;
- match / minor-drift / major-drift frequency;
- tokens/tool calls/wall time;
- unnecessary delegation or duplicate work;
- targeted vs affected vs full verification frequency;
- no-progress continuation passes;
- routing/fallback failures;
- hook latency or false-positive guards.

Exceptions to the freeze are limited to clear compatibility, security, or correctness bugs.

## License

MIT
