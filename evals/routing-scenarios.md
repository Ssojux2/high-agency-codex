# Adaptive Routing Eval Scenarios

Evaluate routing on tasks with a clear expected execution shape. The goal is the smallest sufficient supported model/effort configuration. Keep the current main model as integrator; routing is optional native subtask guidance, and hooks do not force agent dispatch.

## Evidence to record

Keep these evidence categories separate. A successful catalog query is not proof of freshness, entitlement, dispatch, or served identity.

| Category | Required record |
|---|---|
| Preflight | Exact five-line unified preflight before the first mutation; expected task shape and why delegation helps, if used. |
| Host context | Client/runtime version, provider, non-secret account/profile context, main model/effort, relevant native controls, and explicit user/admin pins. |
| Platform / interpreter | Native operating system, Python version and executable visible to the host, launcher used, and whether the evidence is a native CLI run, WSL/POSIX run, or offline fixture. |
| Observation scope | Explicit current host session ID, optional child agent ID, known routing-state directory where required, and state-access/observation status. Never select a latest session automatically. |
| Catalog query | Query success/failure, source, lookup time, source-data time when exposed, pagination/completeness, and whether the catalog matches the active host context. |
| Freshness | Whether the inventory and latest stable release within the chosen family can be established; record the supporting host metadata or **UNVERIFIED**. A saved catalog, successful parse, or alias alone does not prove freshness. |
| Entitlement / availability | Explicit host visibility/restriction flags and any native rejection or successful dispatch evidence. Distinguish advertised models from proven request outcomes; a failed lookup does not prove lack of access. |
| Native dispatch | Whether a native subagent was actually dispatched, role where applicable, agent count, dispatch outcome, and the host evidence source. A prose routing recommendation is only policy selection. |
| Model identity | Separate requested ID/alias, host-resolved model, and host-reported `modelsUsed`, each with its evidence source and status. Leave missing fields **UNVERIFIED** and preserve multiple reported models without reducing them to a guessed single identity. |
| Effort | Desired, supported, requested, and host-reported effective effort as separate values; source of supported-effort evidence and any downgrade or omitted override. An accepted request alone does not prove effective effort. |
| Fallback | Rejection/override reason, supported replacement or current-main route, whether pins were preserved, and evidence for at most one catalog refresh and one supported fallback attempt after rejection. |
| Outcome / efficiency | Task success, acceptance evidence, necessary vs unnecessary delegation, duplicate work/conflicting writes, tool calls/tokens, wall time, and cost only when exposed. Record missing metrics as unavailable. |

Never store credentials, prompts, or tool output in routing-observer state. Evaluate the bounded routing metadata in the per-session report; keep task acceptance evidence in the normal evaluation record.

## Platform prerequisites

Python **3.10+** must be on the PATH inherited by Codex: `python3` on Linux/macOS (POSIX), and `python` on native Windows through the hook's `commandWindows` entry. An activated virtual environment is acceptable. Record unsupported host launcher behavior or a missing interpreter without installing Python or editing global PATH/configuration automatically.

## Validation modes

- **Offline fixtures/mocks:** exercise catalog statuses, selection/fallback logic, and hook-payload/report handling. Label these results offline; they do not establish real account entitlement or CLI dispatch.
- **Native CLI configuration checks:** CI uses real Codex local installation and metadata-only catalog queries on Windows, Linux and macOS in an isolated home without API credentials or model inference. These checks complement the regression suite; they do not establish authenticated dispatch or task quality.
- **Explicit user-run CLI end-to-end evaluation:** use a real relevant task or an explicitly requested bounded native probe, then capture the evidence above. Do not automatically spend on probes, install SDKs, start nested CLI sessions, or change model pins to make a scenario pass.

The 0.12.0 audit combines regression fixtures with native CLI configuration checks. Actual CLI end-to-end routing remains to be evaluated explicitly on each target platform. Windows-style argv or payload tests on Linux are not native Windows evidence; WSL results must be labeled separately. Neither fixture success nor routing observations establish token, latency, cost, or task-success improvements; those require comparable real task runs with equal model/budget conditions.

## Scenarios

1. **One-file local bug**
   - Expected: current main model, zero subagents; no routing reference needed.
   - Failure: unnecessary planner/reviewer/test team or a changed main model.

2. **Large unfamiliar repository map**
   - Expected: BROAD MAP uses latest available Sol at supported medium effort, then Terra if Sol is unavailable, then the current main model.
   - Mechanical inventory alone may use Luna. Return concise paths/interfaces and unknowns.

3. **Normal isolated implementation**
   - Expected: current main model directly, or WORKHORSE on latest available Sol with supported medium/high effort when independent work or context savings justify it; fallback to the current main model.

4. **Independent dual investigation**
   - Expected: two bounded read-only investigations may run in parallel when both are necessary.
   - Failure: duplicate agents investigate the same hypothesis or copy unnecessary context.

5. **Targeted test execution**
   - Expected: current model for a cheap local command, or latest available Luna at supported low/medium effort when delegation helps. Fallback order: Luna → Terra → Sol → current main model.
   - Main thread interprets whether the evidence proves completion.

6. **Complex failure after two good attempts**
   - Expected: escalate model/effort once at the cognitive bottleneck before increasing loop count; Sol high or Astra high/xhigh when supported and justified.
   - Hard-reasoning fallback: Astra → Sol → current main model.

7. **Security/auth/high-impact architecture**
   - Expected: latest available Astra with supported strong effort only on the risky reasoning surface when needed; implementation returns to main/Sol.
   - Request max only when advertised and justified; otherwise record a supported lower effort or fallback.

8. **Mechanical repetitive edit**
   - Expected: cheap bounded work only when the transformation is precise and independently verifiable; use the mechanical fallback chain.
   - Failure: Astra handles boilerplate without a cognitive reason.

9. **Overlapping implementation**
   - Expected: one writer owns each affected surface.
   - Failure: two agents edit overlapping files.

10. **Unavailable preferred model**
    - Expected: record whether the host marked the model unavailable or rejected a request, exclude the rejected ID, refresh at most once, and attempt one supported fallback before using the current main model.
    - Failure: fabricated model IDs, repeated rejected requests, automatic paid probes, or blocking a task that the main model can complete.

11. **Successful query with stale or alias-only catalog data**
    - Expected: record query success separately from source-data freshness. An old saved result, alias-only entries, or missing release metadata must not be upgraded into a verified latest-version claim.
    - Use a supported alias only if the host accepts it; otherwise retain the current main model. Record latest-version freshness **UNVERIFIED** when it cannot be established.

12. **Explicit model pin or forced host route**
    - Expected: preserve the user/admin pin, record any conflict with the preferred latest-family route, and report the native request and observed outcome separately.
    - A configured/default model does not prove served identity; do not silently rewrite settings or claim that the preferred route ran.

13. **Unsupported or unexposed effort control**
    - Expected: use only advertised effort levels, or omit the override/use a compatible route when support is unknown. Record desired, requested, and effective effort separately.
    - Failure: assuming every model supports high/xhigh/max or treating an omitted override as verified effective effort.

14. **Native request event without child model metadata**
    - Expected: `PostToolUse` events for `spawn_agent|Agent` support requested-model and dispatch observations. Because a canonical child `resolvedModel`/`modelsUsed` schema is unavailable, mark only the served-model metadata capability **unsupported** and identity **UNVERIFIED**.
    - Keep event/request support distinct from model-metadata support. An empty observer report alone establishes neither dispatch failure nor served identity.

15. **Separate host identity evidence or model substitution**
    - Expected: if the active host exposes explicit child identity through another supported surface, preserve requested, resolved, and `modelsUsed` evidence with its source, including mismatches or multiple models. This does not turn the hook's unsupported served-metadata capability into a supported one.
    - Failure: substituting the requested ID for absent resolved metadata, inferring identity from prose, or treating fixture-only response fields or a catalog selection as proof of live service.

16. **Native Windows and Linux launcher prerequisites**
    - Expected: use `python3` on Linux/macOS and `python` through `commandWindows` on native Windows, with Python 3.10+ visible to the host. Include plugin/state paths with spaces and non-ASCII characters.
    - Record actual target-platform runs separately from mocked argv/payload checks or WSL. A missing interpreter or unsupported `commandWindows` remains a platform limitation, not proof that routing succeeded.

17. **Explicit session and child scope in reports**
    - Expected: `--report` alone exposes capabilities and **UNVERIFIED** observations. `--report --session-id "<current-session-id>"` reads only that explicit session; optional `--agent-id "<current-agent-id>"` selects its child scope.
    - Without `PLUGIN_DATA`, use `--state-dir "<routing-directory>"` only with a directory supplied by the host. Unknown state access or missing records remain **UNVERIFIED**; never scan for or auto-select a latest session.

## Runtime routing evidence

For each non-DIRECT preflight, compare the intended route with the actual native request when the host supports it. A matching request establishes execution intent; a native dispatch result establishes that delegation occurred; only explicit host metadata can establish resolved or served model information.

From the plugin root, run `python3 hooks/routing_observer.py --report --session-id "<current-session-id>"` on Linux/macOS or the same command with `python` on native Windows. Add `--agent-id "<current-agent-id>"` for child scope and, when `PLUGIN_DATA` is absent, a host-known `--state-dir "<routing-directory>"`. This inspects only the explicit session/scope; `--report` alone reports capabilities with observations **UNVERIFIED**. Unknown state access remains **UNVERIFIED**, and no latest session is selected automatically. Request/dispatch observation is supported for `PostToolUse` events on `spawn_agent|Agent`; the absent canonical child-model schema limits served-model metadata support. Missing or unsupported evidence is a limitation to report, not permission to fabricate identity. The observer does not launch agents, enforce the route, or verify task quality.

Score task completion, routing policy, dispatch, identity evidence, and fallback handling separately. A documented supported fallback can satisfy the task without establishing that the preferred model ran. No latency, token, or cost saving should be claimed from these observations alone.
