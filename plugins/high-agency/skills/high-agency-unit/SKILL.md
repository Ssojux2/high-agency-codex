---
name: high-agency-unit
description: Use when writing or changing one unit of code - a feature slice, bug fix, refactor step, perf fix, or throwaway prototype - to build exactly what the unit needs and nothing more; supplies unit playbooks, an over-implementation checklist applied to the diff, and the unit report returned to high-agency-coding.
---

# High Agency Unit

Execution discipline for one unit of code work. `high-agency-coding` owns direction: outcome, Impact budget, route, verification budget, finish. This skill owns how the unit is written.

A unit is **known-good state → one change → its check → unit report**. Never start the next unit on an unchecked one.

## Contract

Direction passes down; when this skill is used alone, infer each from the request and state it in one line:

- **Outcome** — the acceptance criteria this unit owns and the check that could disprove each.
- **Budget** — the preflight `Impact:` line and the write boundary.
- **Scope of proof** — the route and the verification scope allowed (touched / affected / broad).

The unit returns the [unit report](#unit-report). It never widens outcome, budget, or verification scope on its own: it reports the pressure under `Open:` and direction decides.

This skill adds no plan document, mandatory TDD cycle, subagent fan-out, or review stage. How often a check may run is set by `high-agency-coding` → "Run once, retest once, vary the data"; follow it, do not restate it.

## Playbooks

Pick the one that matches the unit and copy its steps into working context verbatim. A step you skip stays listed as `skip: <reason>`.

### Feature

1. State the criterion this unit satisfies and the check that could disprove it.
2. Name the data shape before any logic: the type, table, state set, or collection the code operates on. Reuse an existing one when it fits.
3. If the change crosses a function boundary, write the caller's usage line first and derive the signature and types from it.
4. Delete what the change makes dead or redundant before adding anything.
5. Write the least code that satisfies the criterion through patterns already in the repository.
6. Run the check on the real surface.
7. Apply the over-implementation checklist to the diff. Cut every hit.
8. Emit the unit report.

### Bug fix

1. Reproduce the failure on the surface where it was reported and keep the failing output. If it will not reproduce, instrument and read actual state; do not guess.
2. Trace back to the first wrong decision in the code. Keep asking why until the answer is a decision, not a consequence of an earlier one.
3. Decide whether the triggering state is legitimate. Legitimate → handle it where it broke. Illegitimate → fix what produced it; a guard at the crash site hides the bug.
4. Make the smallest fix the evidence justifies. Revert every edit motivated by a hypothesis the evidence refuted.
5. Rerun the reproduction; it now passes. Check sibling sites for the same fault inside the budget; report the rest.
6. Apply the checklist, then emit the unit report with the failing-then-passing output.

**Attack the premise.** When two fixes resting on the same belief have failed, write that belief as one sentence and make one observation that would come out differently if it were false. No third fix before that observation.

### Refactor

1. Pin current behavior with an existing check, or a characterization check or recorded output when none covers it. A typecheck is not a pin.
2. Name the target shape. It must delete branches, invalid states, or layers; if it only adds indirection, stop and report.
3. Remove dead code, one-caller wrappers, and redundant validators first.
4. Move in behavior-preserving steps with the pin passing after each. Migrate every caller and delete the old path in the same unit; leave no shim or parallel old/new path.
5. Compare the pinned behavior before and after.
6. Keep the change only if a reader now traces fewer layers or holds less state. A bug or missing feature found on the way goes to direction as a separate unit.

### Perf

Measure a baseline first. Try the cheapest lever in order: stop doing the work, stop repeating it, do less of it, defer it. Re-measure the same way and report both numbers. No number, no fix.

### Prototype

Only to settle a question that observation can answer. Build it in a scratch directory outside production source with no tests or abstractions, observe the result, report the decision. The sketch is discarded; the real build is a Feature unit.

## Build less

- **Smallest sufficient diff.** Fewer lines that meet the criterion beat a tidier structure that also meets it. Decide a thing once and pass the result; do not repeat the decision at each use.
- **Model the domain, not the control flow.** A second boolean that must stay in sync with the first, or one more branch on a growing if/else chain, means a state set, lookup table, or typed record is missing. When the current shape is clear and local, plain code stays.
- **Write for callers that exist.** Three similar statements beat an abstraction with one user.
- **Every layer and every piece of state costs the reader.** Add one only when it removes more tracing elsewhere. Prefer return values over mutation and locals over fields over module state. A reader should find where a value comes from and what can change it in under a minute.
- **Stay surgical.** Match surrounding style. Leave unrelated formatting, comments, and pre-existing dead code alone. Remove imports, variables, and helpers this change made unused. Required caller, schema, doc, or test updates belong to the unit; do not force a one-file patch.
- **Simplicity is not permission to weaken a contract.** Required validation, security, compatibility, and documented edge cases stay.
- **Repeated edits get a script.** For a run of similar edits, do the first by hand, then apply the rest with the smallest script and check each unit.

## Boundaries

Validate, narrow types, and handle errors where data enters the system: user input, CLI arguments, config, files, network, external APIs. Inside, trust the types: no re-validation, no null check for a value the boundary already checked, no catch that only re-raises or hides. Keep logic in plain functions and the framework wiring thin.

## Tests and proof

- A test asserts what a caller can observe: return value, raised error type, readable state, effect on an outside system. Private helpers, call order, and intermediate data are implementation.
- Judge a test by two imagined edits: break the behavior and it must fail; restructure the internals and it must still pass. Derive expected values from the requirement, never from a run of the code.
- Add a test only when it is the cheapest check that can disprove the criterion or the repository's convention requires one. Prefer no new test over one that mostly exercises mocks.
- Prove the unit on the surface the request named (UI, API, CLI, database, process). A clean compile or exit code proves only what was exercised. If the real surface is out of reach, report the criterion as unverified.
- Never weaken a test, assertion, or check to get a pass.

## Comments

Write a comment only for a non-obvious why the code cannot show. No narration of what the next line does, no change history, no phase headings in tests; the assertion message documents the step.

## Over-implementation checklist

Run this against the unit's diff before reporting. For each hit, delete it or name the acceptance criterion that requires it.

- [ ] Option, flag, parameter, or config key that no current caller sets.
- [ ] Wrapper, helper, class, or interface with one caller or one implementation.
- [ ] Guard, try/except, null check, or fallback inside trusted internal code.
- [ ] Compatibility shim, deprecated alias, or old and new paths kept side by side.
- [ ] Feature, edge case, output field, log line, or metric nobody requested.
- [ ] Generalization ("handles any X") where one X was asked for.
- [ ] New dependency or framework where the existing path would do.
- [ ] Comment that narrates the code or the change.
- [ ] Test of a private helper, call order, or mock wiring; test duplicating an existing case.
- [ ] Edit outside the write boundary: unrelated cleanup, renames, or reformatting.

## Unit report

```text
Unit: <one line: what changed>
Files: <changed paths>
Check: <command or inspected surface> → <observed result>
Cut: <what the checklist removed, or none>
Open: <unverified criteria, budget pressure, risk, or none>
```

Read [unit examples and attribution](references/unit-craft.md) when a checklist item or playbook step needs a concrete case.
