# Coding principle examples

Use these examples when a requirement, scope boundary, or verification choice is unclear. Apply the main skill's risk budget; these examples do not create extra workflow stages.

## Resolve the consequential uncertainty

For “add a CSV export,” inspect the existing export conventions. If column order is unspecified and easy to change, state the order you inferred and implement it. If exporting private records would change who can access data, resolve that decision before the dependent change. Continue any independent work that is already authorized.

## Keep the implementation proportional

For one existing endpoint's input validation, extend its current validation path and cover the documented valid and invalid cases. Add a new validation framework, shared service, or configuration layer only if an actual requirement needs it. Retain existing authentication and other required boundary checks.

When editing that endpoint, preserve nearby comments and unrelated formatting. Remove a helper only if the edit made it unused or its removal is required for this task. A necessary caller or regression-test update belongs in the same coherent change; a nearby legacy cleanup usually does not.

## Choose evidence that can expose the failure

| Request | Observable criterion | Smallest useful evidence |
|---|---|---|
| Reject malformed input | Invalid input is rejected and valid input keeps working | Focused invalid and valid cases at the affected boundary |
| Preserve input order for equal scores | Tied records retain their identifier order | Regression that asserts identifiers, not only scores |
| Refactor a parser without behavior changes | Supported inputs retain outputs and error behavior | Relevant checks before and after, including documented edge cases |
| Correct a README typo | Requested text is correct and surrounding content is preserved | Inspect the changed text and diff; no new test suite |

For the tie-order case, an assertion such as `[row.score for row in result] == [10, 10]` passes even when the records are reversed. Check the contract instead:

```python
rows = [{"id": "b", "score": 10}, {"id": "a", "score": 10}]
result = rank(rows)
assert [row["id"] for row in result] == ["b", "a"]
```

Use this only when the established contract requires stable ordering. Confirm the regression exposes the old failure when feasible, then passes on the changed implementation. Do not change the expected order just to accept the result.

A successful process exit is evidence about that process. It proves task completion only when the exercised behavior and assertions cover the acceptance criterion. Record any missing baseline or unavailable boundary check honestly.

## Source and adaptation

These examples and the main skill's four principles are independently worded adaptations of the Karpathy-inspired community guidelines in [`multica-ai/andrej-karpathy-skills`](https://github.com/multica-ai/andrej-karpathy-skills/tree/2c606141936f1eeef17fa3043a72095b4765b9c2), inspected at commit `2c606141936f1eeef17fa3043a72095b4765b9c2`.

Reviewed sources: [`CLAUDE.md`](https://github.com/multica-ai/andrej-karpathy-skills/blob/2c606141936f1eeef17fa3043a72095b4765b9c2/CLAUDE.md), [`skills/karpathy-guidelines/SKILL.md`](https://github.com/multica-ai/andrej-karpathy-skills/blob/2c606141936f1eeef17fa3043a72095b4765b9c2/skills/karpathy-guidelines/SKILL.md), and [`EXAMPLES.md`](https://github.com/multica-ai/andrej-karpathy-skills/blob/2c606141936f1eeef17fa3043a72095b4765b9c2/EXAMPLES.md). Upstream plugin metadata names `forrestchang` as author and declares MIT. The project is inspired by Karpathy's observations; it is not presented as authored or endorsed by him.

High Agency keeps reversible defaults, proportional verification, conditional review, and bounded continuation. Its hooks do not automatically judge simplicity or semantic requirement coverage. No upstream runtime or example implementation is bundled.
