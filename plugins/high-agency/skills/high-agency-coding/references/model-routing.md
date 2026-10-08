# Adaptive Model and Reasoning Routing — Codex

Load this reference only when delegation is justified by the parent skill.

## Contents

- [Catalog](#current-model-catalog--resolve-before-routing)
- [Runtime evidence](#runtime-evidence)
- [Routes](#routing-table)
- [Stage guidance](#stage-guidance)
- [Fallbacks](#explicit-fallback-chains)
- [Delegation budget](#delegation-budget)

## Principle

Use the **cheapest/fastest configuration that can reliably do the subtask**, while keeping the strongest reasoning at high-leverage decision points.

Do not switch models merely because multiple models exist. Context handoff has a cost.

The main thread keeps integration authority. Prefer native Codex subagents with an explicit model and reasoning effort when supported. Do **not** launch nested `codex exec` processes only to change models.

The parent skill emits one unified preflight before the first mutation. Its `Route` and `Model` lines are the execution decision, not commentary. For a non-DIRECT route, spawn the matching native subagent and, when supported, pass explicit model/reasoning fields that match `Model`.

If a requested model is unavailable, use the nearest available capability tier or the current model and continue.

## Current model catalog — resolve before routing

Use the current account/provider/client model list, not a hard-coded release table. The family names below are policy, never literal spawn IDs.

1. Prefer the active runtime's `model/list` response. Read all pages (`nextCursor`) with `includeHidden: false`. Do not use an API account's catalog as proof of a different ChatGPT account's availability.
2. In a local CLI environment with the same account, provider, profile and configuration, the bundled helper can read the catalog without sending an inference request:

   ```sh
   python3 "<installed-plugin-root>/scripts/model_catalog.py"
   ```

   Use `python` on native Windows and Python 3.10+ on all platforms. Resolve the installed plugin root from this skill's actual path, not the project working directory. The helper only sends `initialize`, `initialized`, and `model/list` to `codex app-server`; it does not start a thread/turn, launch `codex exec`, read credentials directly, install an SDK, or edit configuration. If CLI overrides differ from the active session, use the host's catalog instead.
3. To resolve a complete catalog already supplied by the host, pass its JSON result via `--catalog <file>` or `--catalog -` on stdin. This must be current data from the active account/provider; a saved file is not automatically fresh. Incomplete pagination is rejected.
4. Select the latest available stable numeric version **within the required family**. Compare version components numerically, not alphabetically. Exclude hidden/disabled/unavailable entries. Never fabricate a newer ID, assume a preview is stable, or use a model merely because a public announcement mentions it.
5. Use only `supportedReasoningEfforts` returned for the selected model. When the desired level is missing, use an advertised lower/default level; omit the override if no supported level is known. Never assume `max` is universal.
6. Resolve once per task before the first delegation. Reuse that result only while account, provider, profile, client and model availability are unchanged. Refresh after a model rejection; do not retry the same rejected ID or loop indefinitely. Use at most one refreshed fallback attempt, then the current main model.
7. Missing executable, timeout, malformed/empty catalog, unknown families, or disabled native delegation: keep the current main model and report latest availability unverified. Do not resurrect an old bundled model list. The helper exits 2 on lookup failure with safe fallback JSON.

Record catalog source, lookup time, requested model/effort, fallback, and the effective served model when exposed. Keep `query_status`, `freshness_status`, `entitlement_status`, `dispatch_status`, and `selection_status` separate. An app-server response can be a cached/bundled catalog; a new query timestamp does not establish freshness, account entitlement, or a completed inference. Empty/unknown catalogs explicitly select current-main fallback. Respect explicit user/admin pins; disclose conflicts rather than rewriting global configuration.

## Runtime evidence

The bundled `hooks/routing_observer.py` observes native `Agent`/`spawn_agent` PostToolUse requested model/effort and exposed child identity. Read a known session with `--report --session-id <current-session-id>`. Without a host-supplied ID, `--report` reports capabilities and leaves current-session observations unverified. Do not choose another recent session automatically.

The current Codex adapter marks child `resolvedModel`/`modelsUsed` and actual served-effort metadata as **unsupported**. The common hook `model` is the parent model and cannot identify the child. Request observation and launch metadata remain useful without proving completion or serving identity. The helper never starts agents or performs model discovery; use `high-agency-doctor` to inspect these limits and known state-location access.

## Routing table

| Subtask | Preferred family (latest available version) | Desired effort | Notes |
|---|---|---|---|
| Mechanical search, grep, inventory, command execution, simple test reporting | Luna | low–medium | Cheap, bounded, repetitive work |
| Large codebase mapping, dependency tracing, docs/API lookup, first-pass test triage | Sol | medium | Terra only when Sol is unavailable |
| Normal implementation, refactor, integration, focused debugging | Sol | medium–high | Default delegated builder |
| Complex architecture, ambiguous multi-system plan, difficult root cause, security-critical reasoning, high-consequence synthesis | Astra | high–xhigh | Use only at leverage points |
| Extremely hard unresolved reasoning after strong attempts | Astra | max, only if supported | Rare; never the default |

The helper returns conservative initial efforts. Escalate only to a level advertised in the same current catalog. A latest-family policy does not automatically choose the most expensive family for every task.

## Stage guidance

### Planning / architecture

- Local and obvious: current main model; no subagent.
- Normal multi-step: latest available Sol with supported high effort, or current model if already equally capable.
- Broad repo mapping first: Sol medium; Terra medium only as a compatibility fallback. Return interfaces, dependencies, and unknowns only.
- High-impact or ambiguous architecture: Astra high/xhigh for a concise decision memo, then return implementation to the main thread/Sol.

Do not use Astra to write a routine plan.

### Implementation

- Small bounded edit: current model directly.
- Standard implementation: current model or latest available Sol medium/high.
- Mechanical repeated edits with a precise transformation: Luna when deterministic and easy to verify; otherwise Sol.
- Cross-cutting/novel implementation where design and code are tightly coupled: Sol high; Astra only if the hard reasoning cannot be isolated from implementation.

Avoid multiple writing agents touching overlapping files.

### Testing / verification

- Checking specified acceptance conditions with targeted tests or direct inspection: latest available Luna with supported low effort.
- Mapping failures to likely affected areas: Sol medium; Terra only as a compatibility fallback.
- Non-obvious failure triage: Sol high.
- Deep failure after two evidence-based attempts: escalate once to Sol/Astra rather than adding blind iterations.

The main thread decides whether evidence proves the acceptance criteria. Map expected and observed results to the requested behavior; a passing command covers only what it actually exercised. State unverified criteria instead of inferring success from a green suite.

### Review

- Small local change: no extra reviewer.
- Conditional focused review: Sol high.
- Security/auth/schema/high-impact architecture: Astra high for the risky surface only.

When review is warranted, inspect touched changes for requirement traceability, unnecessary complexity, and unintended scope. Do not turn findings into unrelated cleanup.

## Effort policy

- **low** — deterministic or mechanical work.
- **medium** — normal bounded reasoning.
- **high** — complex logic, debugging, review, integration.
- **xhigh** — ambiguous/high-impact reasoning where missing an edge case is costly.
- **max** — rare last escalation for the hardest unresolved cognition, only if supported.

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

Every family below means its latest available version in the current catalog; every effort must be supported.

- **mechanical / test reporting:** Luna → Terra low/medium → Sol low/medium → current main model
- **broad mapping / triage:** Sol medium → Terra medium → current main model
- **normal delegated implementation:** Sol → current main model
- **hard architecture / root cause / security:** Astra high/xhigh → Sol high/xhigh → current main model
- **exceptional max-depth reasoning:** Astra max → Astra xhigh/high → Sol xhigh/high → current main model

These are candidate preference orders, not permission to repeatedly spawn every entry. Apply the one-refresh/one-fallback budget above.

If multi-agent tools are disabled, skip the chain entirely and continue single-agent with the current model.

Do not silently substitute a weaker model while claiming the stronger model ran. A routing choice counts as executed only when the delegated subagent was actually spawned. When runtime metadata exposes the effective served model/reasoning, record it; when it does not, report the requested route and that model identity remains unverified. Report a fallback when it materially affects confidence or cost.

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

1. **Goal** — one bounded question or deliverable tied to the authorized outcome and observable acceptance conditions.
2. **Relevant evidence** — exact files, symbols, errors, or observations already known; distinguish facts from material assumptions or unknowns.
3. **Constraints** — what not to change and any permissions/risk boundary; delegation does not expand these. Include **do not delegate further** unless the root explicitly wants another independent branch.
4. **Expected return** — findings, bounded patch, decision, or evidence mapped to the checked acceptance conditions with gaps stated plainly.
5. **Stop condition** — when the subagent should return instead of broadening scope; surface unresolved material decisions to the main thread.

Do not send the entire problem statement and repo history to every agent by default.

## Sources

Contracts reviewed 2026-10-06. These links and offline fixture tests are not a static allowlist or proof of a completed native session:
- https://developers.openai.com/codex/app-server#list-models-modellist
- https://developers.openai.com/codex/models
- https://developers.openai.com/codex/hooks
- https://developers.openai.com/siwc/token-sharing-open-source/models-and-inference
