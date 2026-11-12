# Unit examples and attribution

Concrete cases for `high-agency-unit`. They add no workflow stage.

## Keep the implementation proportional

For one existing endpoint's input validation, extend its current validation path and cover the documented valid and invalid cases. Add a validation framework, shared service, or configuration layer only if an actual requirement needs it. Retain existing authentication and other required boundary checks.

When editing that endpoint, preserve nearby comments and unrelated formatting. Remove a helper only if the edit made it unused or its removal is required for this unit. A necessary caller or regression-test update belongs in the same unit; a nearby legacy cleanup does not.

## Checklist hits and their cuts

Request: "Add `is_blank(text: str)` to the string utilities; it recognizes empty and whitespace-only strings."

```python
# Over-implemented
def is_blank(text, *, strip_chars=None, treat_none_as_blank=True):
    """Check blankness."""
    # Validate input first
    if text is None:
        return treat_none_as_blank
    if not isinstance(text, str):
        text = str(text)
    return _normalize(text, strip_chars) == ""

# The unit
def is_blank(text: str) -> bool:
    return not text.strip()
```

| Hit | Checklist item | Cut |
|---|---|---|
| `strip_chars`, `treat_none_as_blank` | option no caller sets | removed |
| `_normalize` | one-caller helper | inlined |
| `None` and non-`str` handling | guard inside trusted internals; unrequested coercion | removed; the signature states the contract |
| `# Validate input first` | narrating comment | removed |

One check with distinct data covers the criterion: `""`, `"  \t\n"`, `"a"`, `" a "`. A separate test of `_normalize` would test implementation.

## Guard or root cause

Report: "`render_invoice` crashes with `KeyError: 'currency'` for imported orders."

- Symptom fix: `order.get("currency", "USD")` in `render_invoice`. The crash disappears and imported invoices silently show the wrong currency.
- Root cause: the importer drops `currency` while mapping rows. An order without a currency is not a legitimate state, so the fix belongs in the importer, and the reproduction is an imported order rendered end to end.

If orders may legitimately lack a currency, handling that state in `render_invoice` is the fix. Decide which case holds before writing either.

## Caller first

Before adding a function that other code will call, write the line the caller will contain:

```python
total = invoice_total(order.lines, tax_rate=region.tax_rate)
```

The signature follows from it. A parameter the usage line does not need is a checklist hit.

## Source and adaptation

The playbooks, the checklist, and the build-less, boundary, test, and comment rules are independently worded adaptations of the `pstack` plugin in [`cursor/plugins`](https://github.com/cursor/plugins/tree/2eaf46574b25cdf7ef8c849837099b866b7438ce/pstack), inspected at commit `2eaf46574b25cdf7ef8c849837099b866b7438ce`. Its `LICENSE` is MIT, copyright Lauren Tan.

Reviewed sources under `pstack/skills/`: `poteto-mode` and its feature, bug-fix, refactoring, perf-issue, and prototype playbooks; the laziness-protocol, subtract-before-you-add, minimize-reader-load, foundational-thinking, model-the-domain, boundary-discipline, sequence-verifiable-units, prove-it-works, fix-root-causes, test-behavior-not-implementation, attack-the-premise, and build-the-lever principles; `architect`, `blast-radius`, `no-comments`, and `tdd`.

Left out on purpose: delegated implementation as a default, parallel multi-model design exploration, adversarial review stages, comment-audit subagents, failing-test-first as a requirement, PR and review-bot handling, and per-role model configuration. High Agency keeps single-agent defaults, its own routing, and its verification budget. No upstream text, runtime, or agent definition is bundled.

The surgical-change and proportional-implementation wording also continues the 0.13.0 adaptation credited in [`high-agency-coding/references/coding-principles.md`](../../high-agency-coding/references/coding-principles.md).
