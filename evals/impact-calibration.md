# Impact Calibration Evaluation

High Agency v0.9 asks the model to predict its expected change scope before the first code/config mutation, then compares that prediction with the actual diff.

## Required estimate

```text
Impact: <local|propagating|high> | files<=N | modules<=N | boundary=<private|shared-api|high-impact>
```

Use the **first valid estimate** as the immutable baseline.

## Record per run

- initial impact line;
- actual changed code/config file count;
- actual module count;
- expected and actual high-impact boundary signal;
- drift classification: `match | minor | major`;
- whether semantic public/shared API drift was discovered during final diff review;
- verification scope used: `touched | affected | broad`;
- whether stronger model/reasoning was escalated;
- task success / false completion;
- input/output tokens when available;
- tool calls and wall time when available.

## Calibration metrics

### Underestimation rate

A run is underestimated when actual scope materially exceeds the immutable estimate.

Track separately:
- file-count underestimation;
- module-spread underestimation;
- boundary underestimation;
- major-drift rate.

### Overestimation rate

A run is overestimated when the model predicts a materially broader scope/risk tier than the actual diff required.

Do not penalize a conservative estimate merely because the exact file count is lower. Count overestimation when it would have caused unnecessary broader verification, review, or expensive routing.

### Escalation precision

Measure how often a drift-triggered escalation was useful:

```text
useful drift escalations / total drift escalations
```

A useful escalation catches a real propagation/risk issue, changes the verification scope appropriately, or prevents false completion.

### Escalation recall

Measure how often material underestimation was caught by either the hook or semantic final-diff comparison.

```text
caught material underestimates / all material underestimates
```

## Scenario set

Include at least:

1. one-file local bug that stays within estimate;
2. local estimate that grows to three files in one module;
3. local estimate that crosses into a second module;
4. private estimate that unexpectedly touches auth/security/schema/config;
5. propagating estimate that remains within a broad-but-correct bound;
6. high-impact estimate that is accurate from the start;
7. public/shared API change not obvious from file paths, requiring semantic diff comparison;
8. pre-existing dirty files plus task-local drift;
9. shell/generator edits that expand scope after verification;
10. missing/malformed estimate, confirming fixed heuristics still provide fallback safety.

## Decision rule

Do not tune thresholds from one anecdotal task. Change impact thresholds or escalation behavior only after repeated equal-model/equal-budget runs show a consistent calibration failure mode.
