# High Agency for Codex

A lightweight Codex plugin focused on high-agency coding without process-heavy ceremony.

Current version: **0.4.0**

It provides:

- `$high-agency-coding` — define done → act → verify affected scope → repair → finish
- `$bounded-autonomy` — opt-in bounded continuation
- lightweight hooks that track edits/verification only when High Agency is explicitly requested

## Install

```bash
codex plugin marketplace add Ssojux2/high-agency-codex
```

Then open `/plugins`, install **high-agency**, and review/trust the bundled hooks in `/hooks`.

## Targeted verification

High Agency now defaults to the smallest verification scope that can falsify the change:

1. touched scope
2. affected/related scope
3. full package/workspace only when risk justifies escalation

It prefers repository-native selective mechanisms such as related/changed/affected tests when already available. It does not install a new test-selection dependency just for this optimization.

The Stop hook does **not** automatically run tests. When High Agency was explicitly requested, it records edits and verification commands. If code/config was edited but no verification command was observed, it blocks stopping once and asks Codex to run the narrowest relevant check. Documentation-only edits are ignored by this guard.

## Bounded autonomy

Default: up to 3 additional passes. Hard cap: 12.

Each pass should use targeted verification first. A new pass is requested only after meaningful progress. The final pass cannot request another continuation.

## Evals

See `evals/`.

Use the same task/model/effort/repository state for each variant and compare no-skill vs High Agency. Record correctness, verification quality, scope discipline, autonomy, tool/token efficiency, false completion, and no-progress loops.

```bash
python3 evals/score.py evals/example-result.json
```

## License

MIT
