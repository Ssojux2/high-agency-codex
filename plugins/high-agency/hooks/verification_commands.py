#!/usr/bin/env python3
"""Conservative command recognition and host-result interpretation.

This module does not execute commands or infer test coverage from console text.
Only a single check (optionally after a leading cd) earns automatic credit.
"""
from __future__ import annotations

import os
import re
import shlex
from pathlib import Path

DIRECT_CHECKS = {"pytest", "jest", "vitest", "rspec", "tsc", "eslint", "mypy", "pyright"}
PACKAGE_MANAGERS = {"npm", "pnpm", "yarn", "bun"}
SCRIPT_RE = re.compile(r"^(?:test|lint|typecheck|check|build)(?:[:_-].+)?$")
PYTHON_RE = re.compile(r"^python(?:[0-9]+(?:\.[0-9]+)*)?$")
PY_LAUNCHER_VERSION_RE = re.compile(r"^-3(?:\.[0-9]+)?(?:-(?:32|64))?$")
ASSIGNMENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
META_FLAGS = {"--help", "--version", "--versions", "--usage"}
RUNNER_META_FLAGS = {
    "pytest": {"--collect-only", "--co", "--fixtures", "--funcargs", "--fixtures-per-test",
               "--markers", "--setup-only", "--setup-plan", "--cache-show"},
    "jest": {"--listtests", "--showconfig", "--clearcache", "--init", "--passwithnotests"},
    "vitest": {"--list", "--passwithnotests"},
    "rspec": {"--dry-run", "--dryrun"},
    "tsc": {"--init", "--showconfig", "--listfilesonly", "--dry"},
    "eslint": {"--print-config", "--env-info", "--inspect-config", "--pass-on-no-patterns"},
    "ruff": {"--show-files", "--show-settings"},
    "pyright": {"--createstub"},
    "playwright": {"--list"},
    "cargo": {"--list", "--dry-run"},
    "dotnet": {"--list-tests", "--listtests"},
    "swift": {"--list-tests", "--skip-build"},
    "gradle": {"--dry-run", "--gui"},
    "gradlew": {"--dry-run", "--gui"},
}
PACKAGE_META_FLAGS = {"--if-present", "--script-shell", "--shell", "--eval", "--call"}
OPTION_ENV_NAMES = {"path", "pathext", "pythonpath", "pythonhome", "pytest_addopts",
                    "pytest_plugins", "node_options", "node_path", "goflags",
                    "maven_opts", "maven_args", "gradle_opts", "java_opts",
                    "java_tool_options", "jdk_java_options", "rspec_opts", "spec_opts"}
DIFF_FLAGS = {"-p", "-u", "--patch", "--no-color", "--no-ext-diff", "--no-textconv",
              "--full-index", "--binary", "--text", "--no-renames", "--no-prefix",
              "-W", "--function-context", "--minimal", "--patience", "--histogram",
              "--patch-with-stat", "--patch-with-raw"}
SHELL_OPERATORS = {";", "&&", "||", "|", "&", ">", ">>", "<", "<<", "(", ")", ";;", "|&", "&>"}

def _basename(value: str) -> str:
    name = value.replace("\\", "/").rsplit("/", 1)[-1].lower()
    if name.endswith(".exe"):
        return name[:-4]
    if name.endswith((".cmd", ".bat")) and name[:-4] in PACKAGE_MANAGERS | {"npx", "mvn", "mvnw", "gradle", "gradlew"}:
        return name[:-4]
    return name


def _unwrapped(tokens: list[str], shell: str) -> list[str] | None:
    tokens = list(tokens)
    if shell != "Bash":
        return tokens
    if tokens and tokens[0] == "env":
        tokens.pop(0)
    while tokens and ASSIGNMENT_RE.match(tokens[0]):
        name = tokens.pop(0).split("=", 1)[0].lower()
        # These settings can replace the executable or inject options that
        # report success without running a check. Other literal assignments
        # remain part of the returned argv and therefore its evidence identity.
        if name in OPTION_ENV_NAMES or name.startswith(("npm_config_", "yarn_", "pnpm_", "git_")):
            return None
    return tokens


def _has_meta_flag(args: list[str], runner: str) -> bool:
    flags = META_FLAGS | RUNNER_META_FLAGS.get(runner, set())
    if runner in PACKAGE_MANAGERS:
        flags |= PACKAGE_META_FLAGS
    for arg in args:
        name = arg.split("=", 1)[0]
        if name.startswith("--"):
            lowered = name.lower()
            # argparse and several JavaScript CLIs accept long-option
            # abbreviations. The =value form does not turn help into a check.
            if len(lowered) > 2 and any(flag.startswith(lowered) for flag in flags):
                return True
        elif name.startswith("-") and len(name) > 1:
            short = name[1:]
            bundled_runner = runner in PACKAGE_MANAGERS | {"unittest", "pytest", "compileall", "py_compile", "mypy", "pyright", "ruff", "tsc", "eslint", "rspec", "jest", "vitest"}
            if name in {"-h", "-V"} or (bundled_runner and short.isalpha() and ("h" in short or "V" in short)):
                return True
            if runner in PACKAGE_MANAGERS | {"tsc", "eslint", "rspec"} and "v" in short:
                return True
            if runner == "go" and name == "-n":
                return True
            if runner in {"gradle", "gradlew"} and short == "m":
                return True
        if runner == "pytest" and ("addopts=" in arg or arg == "--last-failed-no-failures=none"):
            return True
    return False


def _python_check(args: list[str]) -> bool:
    while args and args[0] in {"-u", "-B", "-I", "-E", "-s", "-S"}:
        args = args[1:]
    if len(args) < 2 or args[0] != "-m":
        return False
    module = args[1]
    if _has_meta_flag(args[2:], module):
        return False
    if module in {"pytest", "unittest", "compileall", "py_compile", "mypy", "pyright"}:
        return True
    return module == "ruff" and _is_check(["ruff", *args[2:]])


def _is_check(tokens: list[str]) -> bool:
    if not tokens:
        return False
    executable = _basename(tokens[0])
    args = tokens[1:]
    if _has_meta_flag(args, executable):
        return False
    if executable in DIRECT_CHECKS:
        if executable == "vitest" and args and args[0] in {"list", "init", "bench"}:
            return False
        return True
    if executable == "ruff":
        return bool(args) and (args[0] == "check" or (args[0] == "format" and "--check" in args))
    if PYTHON_RE.fullmatch(executable):
        return _python_check(args)
    if executable == "py":
        if args and PY_LAUNCHER_VERSION_RE.fullmatch(args[0]):
            args = args[1:]
        return _python_check(args)
    if executable in PACKAGE_MANAGERS:
        if not args:
            return False
        if args[0] in {"run", "run-script"}:
            return len(args) > 1 and SCRIPT_RE.fullmatch(args[1]) is not None
        return SCRIPT_RE.fullmatch(args[0]) is not None
    if executable in {"npx", "bunx"}:
        while args and args[0] in {"--no-install", "--yes", "-y", "--"}:
            args = args[1:]
        return bool(args) and _is_check(args)
    if executable == "uv" and args and args[0] == "run":
        args = args[1:]
        while args and args[0] in {"--no-sync", "--frozen", "--offline", "--"}:
            args = args[1:]
        return bool(args) and _is_check(args)
    if executable in {"poetry", "pipenv"} and args and args[0] == "run":
        return _is_check(args[1:])
    if executable == "cargo":
        return bool(args) and args[0] in {"test", "check", "clippy"}
    if executable in {"go", "dotnet", "swift"}:
        return bool(args) and args[0] == "test"
    if executable in {"mvn", "mvnw", "gradle", "gradlew"}:
        return any(arg in {"test", "check", "verify"} or arg.endswith(":test") for arg in args)
    if executable == "xcodebuild":
        return "test" in args
    if executable == "playwright":
        return bool(args) and args[0] == "test"
    if executable == "cypress":
        return bool(args) and args[0] == "run"
    return False


def _dynamic_syntax(command: str, shell: str) -> bool:
    if any(char in command for char in ("\n", "\r", "\x00", "$", "`")):
        return True
    if shell == "PowerShell" and any(char in command for char in "\u2018\u2019\u201c\u201d"):
        return True
    quote = None
    index = 0
    while index < len(command):
        char = command[index]
        if char.isspace() and char not in " \t":
            return True
        if quote is not None:
            if char == quote:
                if shell == "PowerShell" and index + 1 < len(command) and command[index + 1] == quote:
                    # PowerShell doubled-quote escaping differs from shlex.
                    return True
                quote = None
            elif char == "\\" and quote == '"' and shell == "Bash" and index + 1 < len(command) and command[index + 1] in '\\"':
                index += 1
        elif char in "'\"":
            quote = char
        elif char == "\\" and shell == "Bash":
            index += 1
        elif char in "#*?[]{}~%!^" or (shell == "PowerShell" and char in "@,"):
            # No comments, wildcard/brace expansion, splatting, cmd expansion,
            # or escaping that could change the executable's actual options.
            return True
        index += 1
    return False


def command_tokens(command, shell: str = "Bash") -> list[str] | None:
    if shell not in {"Bash", "PowerShell"} or not isinstance(command, str) or not command.strip():
        return None
    if _dynamic_syntax(command, shell):
        return None
    if shell == "PowerShell" and re.search(r"(?:\A|&&)\s*['\"]", command):
        # A quoted string is a successful PowerShell expression, not a process.
        # Variable/subexpression evaluation is outside this conservative parser.
        return None
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|<>()")
        lexer.whitespace_split = True
        # shlex otherwise treats a mid-word # as a comment and can silently
        # discard a real Bash failure-swallowing suffix such as `|| true`.
        lexer.commenters = ""
        if shell == "PowerShell":
            lexer.escape = ""
        tokens = list(lexer)
    except ValueError:
        return None
    if shell == "PowerShell" and tokens[:1] == ["&"]:
        tokens = tokens[1:]
    return tokens


def _directory(cwd: Path, target: str, shell: str) -> Path | None:
    if target == "-" or any(char in target for char in "$~*?[]"):
        return None
    if shell == "PowerShell" and os.name != "nt" and ("\\" in target or re.match(r"^[A-Za-z]:", target)):
        # Do not interpret a Windows path as a relative POSIX filename.
        return None
    if shell == "Bash" and os.name == "nt" and target.startswith("/"):
        # A Git Bash/MSYS mount is not a native Windows path.
        return None
    return (cwd / target).resolve()


def _diff_scope(args: list[str]) -> str | None:
    staged = False
    head = False
    for index, arg in enumerate(args):
        if arg in DIFF_FLAGS or arg in {"--color=always", "--color=auto", "--color=never"}:
            continue
        if re.fullmatch(r"(?:-U|--unified=)[0-9]{1,6}", arg):
            continue
        if arg in {"--cached", "--staged"} and not staged:
            staged = True
            continue
        if arg == "HEAD" and not head:
            head = True
            continue
        if arg == "--" and index == len(args) - 1:
            continue
        # Unknown output/filter modes, arbitrary endpoints, and partial
        # pathspecs cannot establish a current-worktree patch review.
        return None
    return "index" if staged else "head" if head else "worktree"


def classify_command(command, cwd: str, shell: str = "Bash") -> dict | None:
    tokens = command_tokens(command, shell)
    if not tokens:
        return None
    directory = Path(cwd).resolve()
    # A common project check is "cd package && npm test". Only this exact
    # prefix is supported; arbitrary shell expressions remain unverified.
    if tokens and tokens[0] == "cd":
        prefix = tokens[1:]
        if prefix and prefix[0] == "--":
            prefix = prefix[1:]
        if len(prefix) < 3 or prefix[1] != "&&":
            return None
        target = prefix[0]
        resolved = _directory(directory, target, shell)
        if resolved is None:
            return None
        directory = resolved
        tokens = prefix[2:]
        if shell == "PowerShell" and tokens[:1] == ["&"]:
            tokens = tokens[1:]
    if any(token in SHELL_OPERATORS or (token and set(token) <= set(";&|<>()")) for token in tokens):
        return None
    executable_tokens = _unwrapped(tokens, shell)
    if not executable_tokens:
        return None
    kind = "verification" if _is_check(executable_tokens) else None
    diff_scope = None
    if _basename(executable_tokens[0]) == "git":
        args = executable_tokens[1:]
        while args and args[0] in {"-C", "--no-pager"}:
            if args[0] == "--no-pager":
                args = args[1:]
            else:
                if len(args) < 3:
                    return None
                resolved = _directory(directory, args[1], shell)
                if resolved is None:
                    return None
                directory = resolved
                args = args[2:]
        if args[:1] == ["diff"] and (diff_scope := _diff_scope(args[1:])) is not None:
            kind = "diff"
    if kind is None:
        return None
    result = {"kind": kind, "command": command[:2000], "argv": tokens, "cwd": str(directory), "shell": shell}
    if diff_scope is not None:
        result["diff_scope"] = diff_scope
    return result


def result_status(payload: dict, host: str) -> dict:
    event = payload.get("hook_event_name")
    response = payload.get("tool_response")
    if event == "PostToolUseFailure":
        return {"status": "cancelled" if payload.get("is_interrupt") is True else "failed", "reason": "tool_failure"}
    if event != "PostToolUse":
        return {"status": "unverified", "reason": "not_a_completion"}
    if isinstance(response, dict):
        if response.get("interrupted") is True:
            return {"status": "cancelled", "reason": "interrupted"}
        if response.get("isError") is True or response.get("is_error") is True or response.get("error"):
            return {"status": "failed", "reason": "tool_reported_error"}
        background = response.get("backgroundTaskId")
        if background or response.get("backgroundedByUser") is True or response.get("timedOutAfterMs"):
            return {"status": "pending", "reason": "background_started", "background_task_id": str(background) if background else None}
        code = response.get("exit_code")
        if isinstance(code, int) and not isinstance(code, bool):
            return {"status": "passed" if code == 0 else "failed", "reason": "exit_code", "exit_code": code}
        if host == "claude":
            # The official BashOutput has no mandatory exit_code. A successful
            # synchronous PostToolUse event plus its concrete output is evidence.
            if all(isinstance(response.get(field), str) for field in ("stdout", "stderr")) and response.get("interrupted") is False:
                return {"status": "passed", "reason": "successful_synchronous_post_tool_use"}
        elif response.get("session_id") is not None and isinstance(response.get("output"), str):
            return {"status": "pending", "reason": "executor_running", "background_task_id": str(response["session_id"])}
    # Native Codex hooks can receive only truncated raw stdout. Text resembling
    # an executor header is still process-controlled output, even at offset 0.
    # Neither successful completion nor a running session can be proved by it.
    return {"status": "unverified", "reason": "missing_authoritative_completion"}
