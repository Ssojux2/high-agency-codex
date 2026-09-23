# High Agency for Codex

High Agency is a lightweight coding scaffold designed to use the LLM's own capability first, then spend extra process, stronger models, or deeper reasoning only where they materially improve correctness.

Current version: **0.9.0**

## Install

```bash
codex plugin marketplace add Ssojux2/high-agency-codex
```

Then open `/plugins`, install **high-agency**, and review/trust the bundled hooks.

> **v0.8.1 hook reliability:** Codex hooks now fail open by default. Unexpected hook-state or environment errors no longer interrupt the coding session; set `HIGH_AGENCY_HOOK_DEBUG=1` only when you intentionally want hook tracebacks. Runtime regression tests now exercise real `UserPromptSubmit`, `PostToolUse:Bash`, and `Stop` payloads.

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

## Impact calibration

Before the first code/config mutation, High Agency now asks the model to commit to one compact scope estimate:

```text
Impact: local | files<=2 | modules<=1 | boundary=private
```

The first estimate is immutable. The model should not rewrite it later to match what happened.

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
Terra map ─┐
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

That is why the current roadmap is evaluation-first. Structural overhead is already lower than the measured Superpowers paths, but no claim is made that High Agency has a higher task-success rate until equal-model/equal-budget end-to-end benchmarks are run.

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

**v0.9.0 is the current evaluation baseline.**

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
