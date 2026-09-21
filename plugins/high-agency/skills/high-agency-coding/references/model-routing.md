# Adaptive Model and Reasoning Routing — Codex

Load this reference only when delegation is justified by the parent skill.

## Principle

Use the **cheapest/fastest configuration that can reliably do the subtask**, while keeping the strongest reasoning at high-leverage decision points.

Do not switch models merely because multiple models exist. Context handoff has a cost.

The main thread keeps integration authority. Prefer native Codex subagents with an explicit model and reasoning effort when supported. Do **not** launch nested `codex exec` processes only to change models.

If a requested model is unavailable, use the nearest available capability tier or the current model and continue.

## Routing table

| Subtask | Preferred model | Effort | Notes |
|---|---|---|---|
| Mechanical search, grep, file inventory, command execution, simple test reporting | `gpt-5.6-luna` | low–medium | Cheap, bounded, repetitive work |
| Large codebase mapping, dependency tracing, docs/API lookup, first-pass test triage | `gpt-5.6-terra` | medium | Read-heavy work where breadth matters |
| Normal implementation, refactor, integration, focused debugging | `gpt-5.6-sol` | medium–high | Default delegated builder |
| Complex architecture, ambiguous multi-system plan, difficult root cause, security-critical reasoning, final synthesis when consequences are high | `gpt-6-astra` | high–xhigh | Use only at leverage points |
| Extremely hard unresolved reasoning after strong attempts | `gpt-6-astra` | max | Rare; do not make this the default |

Astra supports `low|medium|high|xhigh|max`; GPT-5.6 models also support lower effort levels. Never request an unsupported effort.

## Stage guidance

### Planning / architecture

- Local and obvious: current main model; no subagent.
- Normal multi-step: Sol high, or current model if already equally capable.
- Broad repo mapping first: Terra medium; return interfaces, dependencies, and unknowns only.
- High-impact or ambiguous architecture: Astra high/xhigh for a concise decision memo, then return implementation to the main thread/Sol.

Do not use Astra to write a routine plan.

### Implementation

- Small bounded edit: current model directly.
- Standard implementation: current model or Sol medium/high.
- Mechanical repeated edits with a precise transformation: Terra medium; Luna only if the transformation is deterministic and easy to verify.
- Cross-cutting/novel implementation where design and code are tightly coupled: Sol high; Astra only if the hard reasoning cannot be isolated from implementation.

Avoid multiple writing agents touching overlapping files.

### Testing / verification

- Running commands and summarizing results: Luna low.
- Mapping failures to likely affected areas: Terra medium.
- Non-obvious failure triage: Terra high or Sol high.
- Deep failure after two evidence-based attempts: escalate once to Sol/Astra rather than adding blind iterations.

The main thread decides whether evidence proves the acceptance criteria.

### Review

- Small local change: no extra reviewer.
- Conditional focused review: Terra high or Sol high.
- Security/auth/schema/high-impact architecture: Astra high for the risky surface only.

## Effort policy

- **low** — deterministic or mechanical work.
- **medium** — normal bounded reasoning.
- **high** — complex logic, debugging, review, integration.
- **xhigh** — ambiguous/high-impact reasoning where missing an edge case is costly.
- **max** — rare last escalation for the hardest unresolved cognition.

Start lower when success is easy to verify. Escalate effort before escalating model only when the current model is otherwise appropriate.

## Parallelism

Use at most the few independent agents that materially shorten the critical path.

Good parallel work:
- two independent read-only investigations;
- codebase map + external API/docs verification;
- targeted test execution + independent static analysis when both are already required.

Bad parallel work:
- multiple agents editing the same module;
- planner + reviewer + implementer for a one-file fix;
- four agents answering the same question.

Return only findings, decisions, file references, commands, and evidence needed by the integrator.

## Explicit fallback chains

Do not block the task because a preferred delegated model is unavailable. Preserve the subtask and fall back deterministically:

- **mechanical / test reporting:** `gpt-5.6-luna` → `gpt-5.6-terra` low/medium → current main model
- **broad mapping / triage:** `gpt-5.6-terra` → `gpt-5.6-sol` medium → current main model
- **normal delegated implementation:** `gpt-5.6-sol` → current main model
- **hard architecture / root cause / security:** `gpt-6-astra` high/xhigh → `gpt-5.6-sol` high/xhigh → current main model
- **exceptional max-depth reasoning:** `gpt-6-astra` max → Astra xhigh/high → Sol xhigh/high → current main model

If multi-agent tools are disabled, skip the chain entirely and continue single-agent with the current model.

Do not silently substitute a weaker model while claiming the stronger model ran. Report the fallback only when it materially affects confidence or cost.


## Delegation budget

Keep the agent tree shallow.

- The main/root agent owns delegation by default.
- Child agents should not recursively spawn more agents unless the root explicitly assigns a task that genuinely requires another independent branch.
- Default to **at most 2 concurrent delegated agents**.
- Use 3 only when there are 3 clearly independent workstreams and the expected wall-clock/quality gain exceeds context duplication.
- Never fill available concurrency slots just because they exist.

When the runtime exposes context-fork controls, propagate the smallest context that preserves correctness. Prefer a compact task message over full-history duplication unless the subtask truly depends on the entire conversation.

## Handoff packet

A delegated task should normally contain only:

1. **Goal** — one bounded question or deliverable.
2. **Relevant evidence** — exact files, symbols, errors, or observations already known.
3. **Constraints** — what not to change and any permissions/risk boundary. Include **do not delegate further** unless the root explicitly wants another independent branch.
4. **Expected return** — findings, bounded patch, command result, or decision.
5. **Stop condition** — when the subagent should return instead of broadening scope.

Do not send the entire problem statement and repo history to every agent by default.
