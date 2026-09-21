# High Agency for Codex

A lightweight Codex plugin focused on high-agency coding without process-heavy ceremony.

It provides two skills:

- `$high-agency-coding` — understand → act → verify → repair → finish
- `$bounded-autonomy` — opt-in bounded Ralph-style continuation using a Codex Stop hook

It intentionally does not require brainstorming, TDD, worktrees, planning files, subagents, or review stages for every task.

## Install from GitHub

Add this repository as a Codex plugin marketplace:

```bash
codex plugin marketplace add Ssojux2/high-agency-codex
```

Or:

```bash
codex plugin marketplace add https://github.com/Ssojux2/high-agency-codex.git
```

Then start Codex:

```bash
codex
```

Open:

```text
/plugins
```

Select **High Agency** and install **high-agency**. Start a new Codex session after installation.

## Use

### Normal coding

```text
$high-agency-coding

Find and fix the refresh-token bug. Run the relevant tests and typecheck before claiming completion.
```

### Bounded autonomous iteration

```text
$bounded-autonomy

Finish this feature autonomously. Keep fixing actionable failures until the relevant tests and typecheck pass.
```

The default autonomous loop allows up to 3 additional continuation passes. The Stop hook has a hard cap of 12.

## Design

The coding skill keeps only four high-value invariants:

1. Understand the actual goal and success evidence.
2. Make the largest safe coherent change.
3. Verify with fresh evidence before claiming completion.
4. Repair based on new evidence instead of repeating failed approaches.

The bounded-autonomy skill may end an unfinished pass with:

```html
<!-- high-agency:continue max=3 -->
```

The bundled Stop hook detects this marker and asks Codex to continue. The hook itself never runs project tests, builds, or repository commands.

## Repository layout

```text
.
├── .agents/plugins/marketplace.json
└── plugins/high-agency/
    ├── plugin.json
    ├── .codex-plugin/plugin.json
    ├── hooks/
    └── skills/
```

## License

MIT
