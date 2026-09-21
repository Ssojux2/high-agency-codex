# Comparison Plan: High Agency vs No Skill vs Superpowers vs Ralph

Compare execution scaffolds on the same repository snapshot, task, model, reasoning/effort, permissions, and budget.

## Variants

- **no-skill** — normal coding agent without High Agency/Superpowers/Ralph workflow.
- **high-agency** — current High Agency plugin.
- **superpowers** — current Superpowers workflow.
- **ralph** — Ralph loop with the same acceptance criteria and approximately the same total pass budget as High Agency.

For High Agency `max=3`, compare Ralph with at most 4 total attempts (initial + 3) when the harness permits equivalent configuration.

## Fairness

Use clear implementation tasks for direct four-way comparison. Architectural discovery tasks should be evaluated separately because Superpowers intentionally includes design approval and planning stages.

Do not change the task prompt between variants except for the minimum invocation syntax needed to activate the scaffold.

Record at least:

- task success;
- score from `rubric.md`;
- tool calls;
- input/output or total tokens when available;
- wall time when useful;
- verification scope (`targeted`, `affected`, `full`);
- continuation/iteration count;
- no-progress passes;
- false completion;
- unnecessary user questions;
- unrelated diff or verification tampering.

## Expected High Agency advantage

| Concern | Superpowers / Ralph pattern | High Agency pattern |
|---|---|---|
| Planning | formal design/plan stages in Superpowers | minimal outcome contract; planning only on uncertainty |
| TDD | mandatory in Superpowers | optional; targeted tests when useful |
| Subagents/review | task and branch reviews can be mandatory | subagents only when parallel value exceeds coordination cost |
| Final review | broad review workflow | focused diff review only on risk signals |
| Tests | strong verification discipline | touched → affected → full only on escalation |
| Loop | Ralph repeats until promise/max | progress-gated loop with local `max=1`, normal `max=3` |
| Repeated checks | workflow stages can repeat checks | reuse evidence until relevant inputs change |

The goal is not to win by doing less. It is to spend process only where it changes the probability of a correct result.
