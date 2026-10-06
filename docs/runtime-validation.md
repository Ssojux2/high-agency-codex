# Runtime validation

The regression suite validates the plugin's hooks and catalog selection. It does
not establish that a chosen model is available to an account, was actually served,
or produces the same quality and cost as the Claude port.

## Validation targets

| Layer | Target | What it checks |
| --- | --- | --- |
| Python hooks | Python 3.10+ on Windows/Linux/macOS | Process input/output, task state, snapshots, locking and bounded continuation |
| CI regression matrix | Ubuntu Python 3.10/3.12; macOS Python 3.12; Windows Python 3.12/3.14 | The same regression suite on all three operating systems |
| Catalog helper tests | A protocol-compatible local child process | Initialization, pagination, selection, timeout and explicit fallback |
| Native Codex CLI | Codex 0.160.1 on Windows/Linux/macOS | Local marketplace installation and metadata-only model/list query |
| Authenticated Codex session | Account-dependent; run the cases below | Actual tool events, model dispatch, permissions and completion behavior |

Windows support is native and does not require WSL. Install Git and Python 3.10+
on PATH: `python3` on Linux/macOS, `python` on Windows. The hook configuration uses
Codex's `commandWindows` override; state locks use `msvcrt` on Windows and `fcntl`
on Unix. An activated Python virtual environment is also suitable.

Hook commands use a fixed Python `-c` launcher. It removes the implicit current
directory from Python's import path before loading bootstrap modules, reads
`PLUGIN_ROOT` from the environment, adds the hook directory to its import path,
and runs the chosen hook file with `runpy`. Installation paths remain data even when they
contain spaces, `&`, `%PATH%`, `$`, or backticks.

This matters because Codex 0.160.1
[substitutes `${PLUGIN_ROOT}` directly into command text during discovery](https://github.com/openai/codex/blob/rust-v0.160.1/codex-rs/hooks/src/engine/discovery.rs#L559-L575),
then [uses the selected environment's shell](https://github.com/openai/codex/blob/rust-v0.160.1/codex-rs/core/src/session/mod.rs#L5183-L5191).
On Windows that can be PowerShell or CMD; the
[runner's fallback is `COMSPEC`/`cmd.exe`](https://github.com/openai/codex/blob/rust-v0.160.1/codex-rs/hooks/src/engine/command_runner.rs#L384-L461).
The fixed launcher works with both shell forms while preserving hook stdin and
the Python entry point. Codex's normal hook trust review still applies.

Catalog fixtures do not perform inference. `model/list` may return cached or bundled data depending on the
provider; a successful query does not prove entitlement or actual model serving.

```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

On Windows run the same command with `python` instead of `python3`.

With Codex 0.160.1 installed, run `python scripts/validate_codex_plugin.py`.
The checker accepts `--codex /absolute/path/to/codex` and optional `--output`.
It creates an isolated temporary home, installs only this local marketplace,
checks the enabled/versioned installation, and calls the catalog helper against
the real CLI. It does not inherit API credentials, enable hook trust, or start an
inference task. A catalog response can be bundled/cached and remains unverified
for freshness and account entitlement.

The catalog helper can consume a supplied JSON inventory for deterministic checks.
Its normal app-server query is metadata-only. It reports query status separately
from selection, freshness, entitlement and serving evidence. See the doctor and
model-routing reference for the supported invocation.

## Hook contracts

The [official hooks reference](https://developers.openai.com/codex/hooks) documents
the canonical `Bash` name for shell/exec tools and `apply_patch` for patch edits.
Other local function tools also use the hook path; `spawn_agent` additionally
matches `Agent`. A later `write_stdin` poll can deliver the original command's
`PostToolUse` when it finishes. Nonzero shell exits still deliver `PostToolUse`,
so the event name alone is not a successful verification result.

The plugin recognizes supported result metadata conservatively. A command string,
a task ID, parent `model` field, or model name inside assistant prose is not proof
that a check completed or that a child model was served. Missing or ambiguous
metadata remains unverified.

### Codex 0.160.1 execution-result limitation

The native unified executor sends the hook a
[truncated stdout string, without its exit-code header](https://github.com/openai/codex/blob/rust-v0.160.1/codex-rs/core/src/tools/context.rs#L432-L499).
Its normalized hook input contains the command but omits the effective `workdir`;
the common hook `cwd` describes the session environment. The structured result
visible to the model in code mode is a different surface from `tool_response`.

Consequently, native `exec_command` output cannot automatically certify a passing
check in this version, even when it contains text such as `Process exited with
code 0`. Such text can be printed by a failing program. Both foreground and
background raw-string results remain **UNVERIFIED** in the hook state. Structured
exit-code adapter fixtures test the evidence logic; they do not establish that
this native Codex version supplies those fields.

The main agent must still inspect its real tool result and report the command,
effective directory, exit status and any limitations. Stop gives a bounded
reminder and then permits an honest final report. Repeating the same foreground
command does not repair absent hook metadata. Automatic certification on this
surface would require a separately designed verification runner or a host API
that exposes trustworthy exit and directory metadata; neither is claimed here.

## Authenticated session acceptance

Run each case in a disposable project using the normal account permissions and
available models. Record CLI/plugin version, actual hook payloads with sensitive
content removed, requested and observed model fields, command results and outcome.
Do not change global model pins or disable permissions merely to pass a test.

| Case | Acceptance evidence |
| --- | --- |
| Small direct fix | A focused change, no unnecessary delegate, successful current check |
| Automatic skill use | Tracking is activated before the first mutation |
| Read-only delegate | A real dispatch is recorded; requested and observed identities stay distinct |
| Implementation delegate | Changes are attributed to the parent task and require current checks |
| Model pin/allowlist | Restrictions are respected; replacement is explicit and bounded |
| Failed check then repair | No success from the failed check; a repaired snapshot gets new evidence |
| Background check | Start remains pending; a correlated final result determines the outcome |
| Two consecutive tasks | Impact, baseline and loop budget are scoped to the current task |
| Bounded continuation | Host-generated continuation keeps task state and the loop eventually exits |
| Expanded impact | Added files/modules/high-impact paths request corresponding review |

The Stop guard is advisory and bounded. Once its warning budget is exhausted it
allows a truthful final report of failed/pending/unverified checks; it does not
certify correctness or force an endless testing loop.

Authenticated task-quality, entitlement, background event delivery and token-cost
measurements are separate release evidence. Passing subprocess fixtures should
never be reported as an authenticated end-to-end model test.
