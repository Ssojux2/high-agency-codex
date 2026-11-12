# Feature branch and pull request

Feature work runs on its own branch and ends in an open pull request. The main thread owns every git step below; a delegate edits files and returns a unit report, but never switches branches, commits, pushes, or opens a PR.

## When it applies

Apply by default when the task adds or changes behavior (a Feature unit) in a git repository.

Skip, and say so in one line, when:

- the user says not to branch, commit, push, or open a PR, or names another branch to work on;
- the work is a Prototype, an investigation, or an edit outside a git repository;
- the repository's own instructions (CLAUDE.md, AGENTS.md, CONTRIBUTING) prescribe a different flow. Follow theirs.

A bug fix or refactor follows the same flow when the user asks for a branch or PR, or the repository requires one.

## 1. Start the branch (before activation)

Do this after read-only inspection and before `verification_state.py --activate`, so the verification baseline starts on the new branch.

1. `git status --porcelain` and `git branch --show-current`. Find the default branch with `git symbolic-ref --short refs/remotes/origin/HEAD` (fall back to `main`, then `master`).
2. Already on a non-default branch the user created for this work → stay on it.
3. On the default branch with a clean worktree → `git pull --ff-only` when a remote exists, then `git switch -c <type>/<slug>`.
4. On the default branch with pre-existing uncommitted changes → `git switch -c <type>/<slug>` from the current HEAD. Do not stash, reset, or discard them, and never stage them in this task's commits. Name them under `Open:` in the final report.
5. Name: `<type>/<slug>` where type is `feat`, `fix`, or `refactor` and slug is 2-5 lowercase words from the outcome (`feat/csv-export-filter`). If the name exists, append `-2`.

Branch creation does not change HEAD, so it never invalidates evidence.

## 2. Commit each verified unit

After a unit's check passes and its over-implementation checklist is applied, commit that unit before starting the next.

- Stage only the unit's files by path (`git add -- <files from the unit report>`). Never `git add -A` or `git add .`.
- Message: Conventional Commits, `<type>(<scope>): <what changed>`, with a body line for the why when the subject cannot carry it.
- Never commit secrets, `.env` files, credentials, build output, or large binaries. Never pass `--no-verify`. If a pre-commit hook fails, treat it as a failed check: one focused fix, one retry.
- Small units mean small commits. Order them so the history argues for the change: subtraction before reshaping, scaffold before feature, failing test before fix when one exists.

Commits made during the task stay inside the Impact baseline: the hooks diff the activation commit against the working tree, so committed changes still count toward drift.

## 3. Open the pull request (after Finish)

Only after every Finish check holds:

1. `git push -u origin <branch>`. Never push to the default branch, never force-push a branch someone else may hold.
2. Open the PR against the default branch with the GitHub CLI: `gh pr create --base <default> --head <branch> --title "<conventional title>" --body-file <tmp file>`. Use `--draft` when any acceptance criterion is unverified or any `Open:` item is unresolved.
3. Body sections, short and factual:
   - `## Why` — the user's goal in one or two sentences.
   - `## What changed` — one line per unit, from the unit reports.
   - `## Verification` — each unit's `Check:` line with its observed result.
   - `## Open` — unresolved items, or `none`.
4. Do not merge, enable auto-merge, request reviewers, or add labels unless the user asked.

When the Codex sandbox blocks network or `.git` writes, request escalation through the active approval policy once for that command. If the push or PR step still cannot run (no remote, `gh` missing or unauthenticated, network blocked, escalation declined), do not retry in a loop or switch tools. Leave the branch and commits in place and report the exact command for the user to run.

## Final report

Name the branch, the commit count, and the PR URL (or the reason it was not opened and the command to open it).
