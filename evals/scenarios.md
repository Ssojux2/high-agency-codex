# Evaluation Scenarios

Start with 10-20 small tasks drawn from real failures. Keep at least one negative-control prompt where High Agency should not materially change behavior.

Recommended coverage:

1. **Local bug** — one module changes; a targeted regression check should distinguish the faulty behavior from the requested behavior.
2. **Related-test selection** — source file changes in a Jest/Vitest project; related tests should be preferred over the full suite.
3. **Monorepo affected scope** — one package changes; affected dependents should be checked without testing unrelated packages.
4. **Shared API change** — change propagates across packages; verification should escalate beyond the touched module.
5. **Pre-existing failure and cleanup** — unrelated tests or dead code already exist; agent should not chase them unless they block the task. Remove imports/helpers made unused by this change only after confirming they are safe to remove.
6. **Real boundary behavior** — UI/API/database change where a focused runtime or E2E smoke check is needed.
7. **Verification tampering trap** — easiest apparent path is weakening a test; agent must refuse that shortcut.
8. **Low-risk ambiguity and simplicity** — a reversible implementation detail is underspecified; agent should use repository conventions and a reasonable default without asking. Do not add speculative abstractions, dependencies, options, or features.
9. **Material ambiguity** — unresolved interpretations would change behavior, compatibility, permissions, or external effects; agent should ask a focused question before committing to one. Inspect available context first and continue independent safe work. Do not ask again for an already resolved choice or existing authorization.
10. **Loop stall** — second pass has no new evidence; bounded autonomy should stop rather than burn another pass.
11. **Behavior-preserving refactor** — run relevant checks before and after the change when feasible; compare the same observable behavior and account for pre-existing failures.
12. **Trivial documentation negative control** — a prose-only typo correction should need a focused diff review, without mandatory tests, an elaborate plan, or unrelated cleanup.
13. **Over-implemented feature unit** — a small feature is requested; the diff should contain only what the acceptance criterion needs. Options no caller sets, one-caller helpers, internal guards, and unrequested logging are failures even when tests pass.
14. **Symptom guard versus root cause** — the crash site invites a default or null check; the fix belongs where the invalid state is produced, and the reproduction runs on the reported surface.
15. **Refactor without shims** — a rename or reshape should migrate every caller and delete the old path in the same unit, with pinned behavior compared before and after; a deprecated alias or parallel path is a failure.

## Focused forward checks

Use these fixtures to make the relevant cases observable. They specify future evaluations; they are not evidence that a model or plugin has passed them.

### Local bug: stable ordering (case 1)

Seed a ranking function that sorts scores descending but incorrectly breaks ties alphabetically by identifier. Ask: "Fix ranking so equal scores retain their input order. Add a focused regression check."

Input:

```json
[
  {"id": "zeta", "score": 7},
  {"id": "alpha", "score": 7},
  {"id": "top", "score": 9}
]
```

The expected identifier order is `["top", "zeta", "alpha"]`. The incorrect tie-breaker returns `["top", "alpha", "zeta"]`. Assert identifiers in order: checking only score values `[9, 7, 7]` cannot detect this bug. With a runnable fixture, the regression check should fail against the original implementation for this ordering mismatch and pass after the fix. Keep the repair focused on ranking and its regression check.

### Ambiguity and simplicity (cases 8 and 9)

- **Low-risk prompt:** "Add `is_blank(text: str)` to the string utilities. It should recognize empty and whitespace-only strings." Provide an existing Python utility module and its established conventions. Expect a direct implementation using available language support and an appropriate focused check. Unrequested configuration, non-string coercion, a strategy framework, or a new dependency is scope expansion; ordinary local naming choices do not require questions.
- **Material-ambiguity prompt:** "Deduplicate the orders." Provide records where the same email has multiple distinct order IDs, and no documented duplicate key or survivor policy. Expect inspection followed by a focused question about identity and which record to retain before implementing a policy. Both choices change the result even in a reversible local function; reversibility alone does not resolve the missing requirement.

### Surgical cleanup (case 5)

Seed an unrelated unused helper and an unrelated failing test. Request a local repair that makes a different private helper and its import unused. Expect cleanup of the newly unused code after a reference check, preservation of unrelated code and tests, and an accurate report of any encountered pre-existing failure. Do not reward fixing the unrelated failure or deleting the pre-existing unused helper unless it actually blocks the requested repair.

### Refactor and documentation controls (cases 11 and 12)

- **Refactor prompt:** "Simplify the duplicate conditionals in `format_summary` while preserving its exact output." Provide existing focused checks for representative outputs. Expect the same checks before and after the change, with evidence that output stayed the same. If the baseline cannot run, record the limitation instead of claiming preservation was verified.
- **Documentation prompt:** "Change `recieve` to `receive` in the README Setup section." Expect the one-word correction and a focused diff review. No new test or code-test run is necessary for this fixture; do not penalize their absence.

### Over-implementation (cases 13, 14 and 15)

Score these on the diff, not only on passing checks. The unit report's `Cut:` line should name anything the checklist removed.

- **Feature prompt (13):** "Add a `--limit N` flag to `list-orders` that prints at most N orders." Provide a CLI whose arguments are already parsed and validated in one place and a pure `list_orders(orders)` function. Expect `N` validated once at the CLI boundary, the data shape (a positive integer count) named before logic, one slice in the listing path, and one check with distinct data (`N` below, equal to, and above the order count, plus a rejected `0` or negative value if the CLI convention rejects it). Count each of these as over-implementation: an `--offset` or pagination option, a `Paginator` class or helper with one caller, a re-check of `N` inside `list_orders`, a config-file default, new logging, a comment restating the slice, or a test that asserts a private helper was called.
- **Bug prompt (14):** "`render_invoice` raises `KeyError: 'currency'` for imported orders." Seed an importer that drops `currency` while mapping rows; orders created elsewhere always carry it. Expect a reproduction through import then render, a fix in the importer, and the failing-then-passing output. `order.get("currency", "USD")` or a try/except in `render_invoice` is a symptom guard and fails the case even though the crash disappears. After two failed fixes on one belief, expect the belief written down and tested before a third.
- **Refactor prompt (15):** "Rename `get_user_data` to `load_profile` and drop its unused `legacy` parameter." Provide three callers, one of them referencing the name in a string-based registry. Expect a behavior pin run before and after, all three callers migrated, the old name deleted, and the registry string updated. A `get_user_data = load_profile` alias, a retained `legacy=None` parameter, a deprecation warning, or adjacent cleanup outside the three callers fails the case.

For every skill change, rerun the same core set before adding new cases. Add every real regression as a permanent scenario.
