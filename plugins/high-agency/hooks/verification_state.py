#!/usr/bin/env python3
"""Track task-local verification evidence without executing project commands."""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import time
import traceback
import uuid
from contextlib import contextmanager
from pathlib import Path

from git_state import file_fingerprint, fingerprint_complete, snapshot, snapshot_complete, snapshots_equal
from impact_scope import first_impact_from_transcript
from state_store import HOST_KIND, data_root, load_json, state_transaction, verification_path
from verification_commands import classify_command, command_tokens, result_status

SCHEMA_VERSION = 2
MAX_NATIVE_FILES = 512
MAX_PENDING_CHECKS = 64
MAX_TRACKING_BYTES = 3 * 1024 * 1024
NATIVE_TOOLS = {"Edit", "Write", "NotebookEdit", "apply_patch"}
SHELL_TOOLS = {"Bash", "PowerShell"}
PATCH_PATH_RE = re.compile(r"^\*\*\* (?:Update|Add|Delete) File:\s*(.+?)\s*$", re.MULTILINE)
PATCH_MOVE_RE = re.compile(r"^\*\*\* Move to:\s*(.+?)\s*$", re.MULTILINE)
SKILL_NAMES = {"high-agency-coding", "bounded-autonomy"}


def state_dir() -> Path:
    return data_root()


def path_for(payload: dict) -> Path:
    return verification_path(payload)


def load(path: Path) -> dict:
    return load_json(path)


def active_prompt(prompt: str) -> bool:
    value = prompt.lower()
    return "high-agency" in value or "high agency" in value or "bounded-autonomy" in value


def active_skill(tool_input) -> bool:
    if not isinstance(tool_input, dict):
        return False
    name = tool_input.get("skill")
    return isinstance(name, str) and name.rsplit(":", 1)[-1] in SKILL_NAMES


def _normal_path(raw: str, cwd: str) -> str:
    path = raw if os.path.isabs(raw) else os.path.join(cwd, raw)
    # Preserve the leaf symlink for lstat/readlink fingerprinting.
    return os.path.normcase(os.path.abspath(path))


def extract_paths(tool_name: str, tool_input, cwd: str = ".") -> list[str]:
    if not isinstance(tool_input, dict):
        return []
    found = []
    for field in ("file_path", "path", "notebook_path"):
        value = tool_input.get(field)
        if isinstance(value, str) and value:
            found.append(value)
    if tool_name == "apply_patch" and isinstance(tool_input.get("command"), str):
        found.extend(PATCH_PATH_RE.findall(tool_input["command"]))
        found.extend(PATCH_MOVE_RE.findall(tool_input["command"]))
    return sorted({_normal_path(value, cwd) for value in found})


def _transcript_cursor(payload: dict) -> tuple[int, dict | None]:
    raw = payload.get("transcript_path")
    if not isinstance(raw, str) or not raw:
        return 0, None
    try:
        stat = Path(raw).stat()
        return stat.st_size, {"device": stat.st_dev, "inode": stat.st_ino}
    except OSError:
        return 0, None


def new_task_state(payload: dict, cwd: str, *, active: bool = False) -> dict:
    offset, identity = _transcript_cursor(payload)
    return {
        "schema_version": SCHEMA_VERSION,
        "session_id": payload.get("session_id"),
        "agent_id": payload.get("agent_id"),
        "task_id": uuid.uuid4().hex,
        "task_completed": False,
        "continuing_stop": False,
        "active": active,
        "activation_reason": "explicit_prompt" if active else None,
        "cwd": _normal_path(cwd, "."),
        "prompt_ids": [],
        "turn_ids": [],
        "transcript_path": payload.get("transcript_path"),
        "transcript_start_offset": offset,
        "transcript_identity": identity,
        # Always take the baseline before any later tool mutation, including
        # ordinary prompts whose skill is selected automatically afterwards.
        "baseline_snapshot": snapshot(cwd),
        "verification_snapshot": None,
        "diff_snapshot": None,
        "verification_status": "unverified",
        "verification_failure": None,
        "verification_commands": [],
        "verification_evidence": [],
        "pending_checks": {},
        "pending_mutations": {},
        "seen_tool_ids": [],
        "retired_tool_ids": [],
        "child_tasks": {},
        "retired_agent_ids": [],
        "verification_tracking_incomplete": False,
        "failed_checks": {},
        "native_files": {},
        "native_tracking_truncated": False,
        "native_dirty": False,
        "all_edited_files": [],
        "verification_guard_warned": False,
        "diff_guard_warned": False,
        "impact_estimate": None,
        "impact_drift_warned": False,
        "continuation": {},
        "created_at": int(time.time()),
    }


def _validate_state(data: dict) -> None:
    if not isinstance(data.get("task_id"), str) or not data["task_id"]:
        raise ValueError("Invalid hook task identity")
    for field in ("pending_checks", "pending_mutations", "failed_checks", "native_files", "baseline_snapshot", "child_tasks"):
        if not isinstance(data.get(field), dict):
            raise ValueError("Invalid hook state collection")
    for field in ("active", "task_completed", "continuing_stop", "verification_tracking_incomplete", "native_tracking_truncated"):
        if not isinstance(data.get(field), bool):
            raise ValueError("Invalid hook state flag")
    for field in ("prompt_ids", "turn_ids", "verification_commands", "verification_evidence", "seen_tool_ids", "retired_tool_ids", "retired_agent_ids"):
        if not isinstance(data.get(field), list):
            raise ValueError("Invalid hook state history")
    for path, entry in data["native_files"].items():
        if not isinstance(path, str) or not isinstance(entry, dict) or not all(isinstance(entry.get(field), str) for field in ("before", "current")):
            raise ValueError("Invalid native edit record")
    for tool_id, entry in data["pending_checks"].items():
        if not isinstance(tool_id, str) or not isinstance(entry, dict):
            raise ValueError("Invalid pending check record")
        if not all(isinstance(entry.get(field), str) for field in ("task_id", "kind", "command", "command_digest", "cwd", "shell", "status")) or not isinstance(entry.get("argv"), list) or not isinstance(entry.get("start_snapshot"), dict):
            raise ValueError("Invalid pending check evidence")
    for tool_id, entry in data["pending_mutations"].items():
        if not isinstance(tool_id, str) or not isinstance(entry, dict) or not isinstance(entry.get("task_id"), str) or not isinstance(entry.get("paths"), list):
            raise ValueError("Invalid pending mutation record")
    for key, entry in data["failed_checks"].items():
        if not isinstance(key, str) or not isinstance(entry, dict) or not all(isinstance(entry.get(field), str) for field in ("status", "reason", "command", "tool_use_id")):
            raise ValueError("Invalid failed check record")
    for agent_id, entry in data["child_tasks"].items():
        if not isinstance(agent_id, str) or not isinstance(entry, dict) or not isinstance(entry.get("task_id"), str):
            raise ValueError("Invalid child task binding")
    if not isinstance(data.get("continuation"), dict):
        raise ValueError("Invalid continuation state")


def _remember_identity(data: dict, payload: dict) -> None:
    for source, target in (("prompt_id", "prompt_ids"), ("turn_id", "turn_ids")):
        value = payload.get(source)
        if isinstance(value, str) and value and value not in data[target]:
            data[target] = (data[target] + [value])[-64:]


def _fingerprint(path: str, *, deadline: float | None = None) -> str:
    target = Path(path)
    return file_fingerprint(target.parent, target.name, deadline=deadline)


def _refresh_native(data: dict) -> dict:
    current = {}
    edited = []
    deadline = time.monotonic() + 1.0
    for path, entry in data["native_files"].items():
        if not isinstance(path, str) or not isinstance(entry, dict):
            raise ValueError("Invalid native edit record")
        fingerprint = _fingerprint(path, deadline=deadline)
        entry["current"] = fingerprint
        if entry.get("before") != fingerprint or not fingerprint_complete(fingerprint):
            current[path] = fingerprint
            edited.append(path)
    data["all_edited_files"] = edited
    data["native_dirty"] = bool(edited) or bool(data.get("native_tracking_truncated"))
    return current


def capture(data: dict, cwd: str) -> dict:
    baseline = data.get("baseline_snapshot") or {}
    ref = baseline.get("base_ref")
    current = snapshot(cwd, base_ref=ref if isinstance(ref, str) and ref else None)
    current["native_files"] = _refresh_native(data)
    if data.get("native_tracking_truncated"):
        current.update(available=False, complete=False, error="native_path_limit_exceeded")
    if data.get("verification_tracking_incomplete"):
        current.update(available=False, complete=False, error="verification_tracking_limit_exceeded")
    return current


def _track_native(data: dict, tool_name: str, tool_input, cwd: str, *, before: bool) -> None:
    deadline = time.monotonic() + 1.0
    for path in extract_paths(tool_name, tool_input, cwd):
        entry = data["native_files"].get(path)
        fingerprint = _fingerprint(path, deadline=deadline)
        if entry is None:
            if len(data["native_files"]) >= MAX_NATIVE_FILES:
                data["native_tracking_truncated"] = True
                continue
            data["native_files"][path] = {
                "before": fingerprint if before else "unknown:missing_pre_tool_use",
                "current": fingerprint,
            }
        else:
            entry["current"] = fingerprint
    _refresh_native(data)
    if not before and data["native_dirty"]:
        data["verification_guard_warned"] = False
        data["diff_guard_warned"] = False


def _command_key(check: dict) -> str:
    raw = json.dumps([check.get("command_digest"), check.get("cwd"), check.get("shell")], ensure_ascii=True, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


def _set_status(data: dict) -> None:
    if data.get("verification_tracking_incomplete"):
        data["verification_snapshot"] = None
        data["verification_status"] = "unverified"
        data["verification_failure"] = {"status": "unverified", "reason": "verification_tracking_limit_exceeded"}
        return
    failures = list(data["failed_checks"].values())
    if failures:
        latest = failures[-1]
        data["verification_failure"] = latest
        data["verification_status"] = latest.get("status", "failed")
    elif any(item.get("kind") == "verification" for item in data["pending_checks"].values() if isinstance(item, dict)):
        data["verification_failure"] = None
        data["verification_status"] = "pending"
    elif data.get("verification_snapshot") is not None:
        data["verification_failure"] = None
        data["verification_status"] = "passed"
    else:
        data["verification_failure"] = None
        data["verification_status"] = "unverified"


def _record_failure(data: dict, tool_id: str, check: dict, result: dict) -> None:
    data["verification_snapshot"] = None
    failure = {
        "status": result["status"],
        "reason": result.get("reason", "check_did_not_complete"),
        "command": check["command"],
        "tool_use_id": tool_id,
        "exit_code": result.get("exit_code"),
    }
    data["failed_checks"][_command_key(check)] = failure
    while len(data["failed_checks"]) > 32:
        data["verification_tracking_incomplete"] = True
        data["failed_checks"].pop(next(iter(data["failed_checks"])))
    data["verification_guard_warned"] = False


def _activation_command(command, shell: str = "Bash") -> bool:
    """The helper is activated by its real PreToolUse payload, never shell env."""
    if not isinstance(command, str) or any(x in command for x in (";", "\n", "&&", "||", "|", "$(", "`")):
        return False
    tokens = command_tokens(command, shell)
    if not tokens:
        return False
    executable = tokens.pop(0).replace("\\", "/").rsplit("/", 1)[-1].lower()
    if executable == "py" and tokens[:1] == ["-3"]:
        tokens.pop(0)
    elif not re.fullmatch(r"python(?:[0-9]+(?:\.[0-9]+)*)?(?:\.exe)?", executable):
        return False
    if len(tokens) != 2 or tokens[1] != "--activate":
        return False
    try:
        return Path(tokens[0]).resolve() == Path(__file__).resolve()
    except (OSError, RuntimeError):
        return False


def _remember_impact(data: dict, payload: dict) -> None:
    if not data.get("active") or data.get("impact_estimate"):
        return
    estimate = first_impact_from_transcript(
        payload.get("transcript_path") or data.get("transcript_path"),
        start_offset=data["transcript_start_offset"],
        expected_identity=data.get("transcript_identity"),
    )
    if estimate:
        data["impact_estimate"] = estimate


def _identity_matches(data: dict, payload: dict) -> bool:
    prompt_id = payload.get("prompt_id")
    if isinstance(prompt_id, str) and prompt_id:
        return prompt_id in data.get("prompt_ids", [])
    turn_id = payload.get("turn_id")
    return isinstance(turn_id, str) and turn_id in data.get("turn_ids", [])


def _bound_state(data: dict) -> None:
    def size():
        return len(json.dumps(data, ensure_ascii=True, separators=(",", ":")).encode("utf-8"))
    if not data or size() <= MAX_TRACKING_BYTES:
        return
    # Preserve failures/task identities while dropping proof that no longer fits
    # a bounded store. Capacity loss must never turn into successful evidence.
    data["verification_tracking_incomplete"] = True
    data["verification_snapshot"] = None
    data["diff_snapshot"] = None
    data["verification_evidence"] = []
    for check in data.get("pending_checks", {}).values():
        if isinstance(check, dict):
            check["start_snapshot"] = {"available": False, "complete": False, "error": "state_size_limit"}
            check["argv"] = [str(value)[:200] for value in check.get("argv", [])[:32]]
    if size() > MAX_TRACKING_BYTES:
        baseline = data.get("baseline_snapshot") or {}
        data["baseline_snapshot"] = {"available": False, "complete": False, "root": baseline.get("root"), "error": "state_size_limit"}
    while size() > MAX_TRACKING_BYTES and data.get("native_files"):
        data["native_tracking_truncated"] = True
        data["native_files"].pop(next(iter(data["native_files"])))
        data["all_edited_files"] = list(data["native_files"])
    _set_status(data)


@contextmanager
def _tracking_transaction(payload: dict, *, recover: bool = False):
    with state_transaction(payload, recover=recover) as data:
        yield data
        _bound_state(data)


def _replace_task(data: dict, payload: dict, cwd: str, *, active: bool, recovered: bool = False) -> None:
    def history(field):
        values = data.get(field)
        return [value for value in values if isinstance(value, str)] if isinstance(values, list) else []
    retired_tools = history("retired_tool_ids")
    retired_tools.extend(history("seen_tool_ids"))
    retired_agents = history("retired_agent_ids")
    children = data.get("child_tasks")
    if isinstance(children, dict):
        retired_agents.extend(value for value in children if isinstance(value, str))
    data.clear()
    data.update(new_task_state(payload, cwd, active=active))
    data["retired_tool_ids"] = list(dict.fromkeys(retired_tools))[-512:]
    data["retired_agent_ids"] = list(dict.fromkeys(retired_agents))[-256:]
    if recovered:
        data["state_recovered_at"] = int(time.time())
        data["evidence_reset_reason"] = "malformed_state"


def _remember_tool(data: dict, tool_id) -> None:
    if isinstance(tool_id, str) and tool_id and tool_id not in data["seen_tool_ids"]:
        data["seen_tool_ids"] = (data["seen_tool_ids"] + [tool_id])[-512:]


def _check_command(command, cwd: str, shell: str, *, workdir=None) -> dict | None:
    reported_workdir = isinstance(workdir, str) and bool(workdir)
    effective_cwd = _normal_path(workdir, cwd) if reported_workdir else cwd
    check = classify_command(command, effective_cwd, shell=shell)
    if check is not None:
        check["command_digest"] = hashlib.sha256(command.encode("utf-8", "surrogatepass")).hexdigest()
        tokens = command_tokens(command, shell) or []
        cd_args = tokens[1:] if tokens[:1] == ["cd"] else []
        if cd_args[:1] == ["--"]:
            cd_args = cd_args[1:]
        absolute_cd = len(cd_args) >= 3 and cd_args[1] == "&&" and os.path.isabs(cd_args[0])
        # Codex's normalized unified-exec hook can omit effective workdir.
        # A session cwd alone cannot prove where that command actually ran.
        check["scope_proven"] = HOST_KIND != "codex" or reported_workdir or absolute_cd
    return check


def _diff_covers_snapshot(check: dict, current: dict, baseline: dict) -> bool:
    """A valid patch command must cover the snapshot credited to that review."""
    if not snapshot_complete(current) or not snapshot_complete(baseline):
        return False
    root = Path(current["root"])
    files = set(current["files"])
    try:
        for raw in current.get("native_files", {}):
            files.add(Path(raw).relative_to(root).as_posix())
        def git(*args):
            return subprocess.run(["git", *args], cwd=root, capture_output=True, timeout=0.5, check=False)
        head = git("rev-parse", "--verify", "HEAD")
        if head.returncode != 0 or head.stdout.decode("ascii", "ignore").strip() != baseline["base_ref"]:
            return False
        # Git patches do not contain ignored/untracked file bodies. Do not
        # credit a whole snapshot when those files require a separate review.
        if files and git("ls-files", "--error-unmatch", "--", *sorted(files)).returncode != 0:
            return False
        scope = check.get("diff_scope")
        if scope == "head":
            return True
        if scope == "worktree":
            return git("diff", "--cached", "--quiet", baseline["base_ref"], "--").returncode == 0
        if scope == "index":
            return git("diff", "--quiet", "--").returncode == 0
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return False
    return False


def process(payload: dict) -> None:
    event = payload.get("hook_event_name")
    if event not in {"UserPromptSubmit", "PreToolUse", "PostToolUse", "PostToolUseFailure", "SubagentStart"}:
        return
    cwd = payload.get("cwd") if isinstance(payload.get("cwd"), str) else "."
    prompt = payload.get("prompt") or payload.get("user_prompt") or ""
    prompt = prompt if isinstance(prompt, str) else ""
    tool_name = payload.get("tool_name")
    tool_input = payload.get("tool_input")
    tool_id = payload.get("tool_use_id")
    agent_id = payload.get("agent_id")
    is_child = isinstance(agent_id, str) and bool(agent_id)

    # Only causally linked child tool events can affect an existing live parent.
    # Child prompts, Stop, and unlinked/late events never create or reset it.
    if is_child and event == "UserPromptSubmit":
        return
    store_payload = dict(payload)
    if is_child:
        store_payload.pop("agent_id", None)
        store_payload.pop("agent_type", None)

    with _tracking_transaction(store_payload, recover=event == "UserPromptSubmit") as data:
        if is_child:
            if data.get("schema_version") != SCHEMA_VERSION or data.get("active") is not True or data.get("task_completed") is not False:
                return
            _validate_state(data)
            binding = data["child_tasks"].get(agent_id)
            linked = isinstance(binding, dict) and binding.get("task_id") == data["task_id"]
            if not linked:
                current_origin = _identity_matches(data, payload)
                if not current_origin:
                    return
                if agent_id in data["retired_agent_ids"] and not (event == "SubagentStart" and current_origin):
                    return
                data["child_tasks"][agent_id] = {"task_id": data["task_id"]}
            if event == "SubagentStart":
                return
            if isinstance(tool_id, str):
                tool_id = "agent:" + agent_id + ":" + tool_id
            payload = dict(payload, transcript_path=data.get("transcript_path"))
        elif event == "SubagentStart":
            return
        elif data.get("schema_version") != SCHEMA_VERSION:
            old_active = data.get("active") is True
            _replace_task(data, payload, cwd,
                          active=active_prompt(prompt) if event == "UserPromptSubmit" else old_active,
                          recovered=data.get("state_recovered") is True)
        else:
            try:
                _validate_state(data)
            except ValueError:
                if event != "UserPromptSubmit":
                    raise
                _replace_task(data, payload, cwd, active=active_prompt(prompt), recovered=True)

        if event == "UserPromptSubmit":
            if data["task_completed"]:
                _replace_task(data, payload, cwd, active=active_prompt(prompt))
            # Codex Stop continuations and Claude internal notifications can
            # deliver UserPromptSubmit. Preserve unfinished task evidence.
            if active_prompt(prompt):
                data["active"] = True
                data["activation_reason"] = data.get("activation_reason") or "explicit_prompt"
            _remember_identity(data, payload)
            data["updated_at"] = int(time.time())
            return

        if data["task_completed"] or (isinstance(tool_id, str) and tool_id in data["retired_tool_ids"]):
            return
        supplied_origin = any(isinstance(payload.get(field), str) and payload[field] for field in ("prompt_id", "turn_id"))
        if not is_child and supplied_origin and (data["prompt_ids"] or data["turn_ids"]) and not _identity_matches(data, payload):
            return
        if event == "PreToolUse":
            if not is_child:
                _remember_identity(data, payload)
            _remember_tool(data, tool_id)
            if tool_name == "Skill" and active_skill(tool_input):
                data["active"] = True
                data["activation_reason"] = "skill_invocation"
            if tool_name in SHELL_TOOLS and isinstance(tool_input, dict) and _activation_command(tool_input.get("command"), tool_name):
                data["active"] = True
                data["activation_reason"] = "activation_helper"
            if tool_name in NATIVE_TOOLS:
                _track_native(data, tool_name, tool_input, cwd, before=True)
                if isinstance(tool_id, str) and tool_id:
                    data["pending_mutations"][tool_id] = {"task_id": data["task_id"], "paths": extract_paths(tool_name, tool_input, cwd)}
            if data["active"] and tool_name in SHELL_TOOLS and isinstance(tool_input, dict):
                check = _check_command(tool_input.get("command"), cwd, tool_name, workdir=tool_input.get("workdir"))
                if check and isinstance(tool_id, str) and tool_id:
                    if len(data["pending_checks"]) >= MAX_PENDING_CHECKS and tool_id not in data["pending_checks"]:
                        data["verification_tracking_incomplete"] = True
                    else:
                        # Never replace an earlier invocation's start snapshot.
                        data["pending_checks"].setdefault(tool_id, {
                            **check,
                            "task_id": data["task_id"],
                            "source_agent_id": agent_id if is_child else None,
                            "status": "running",
                            "start_snapshot": capture(data, check["cwd"]),
                            "run_in_background": tool_input.get("run_in_background") is True,
                        })
                    _set_status(data)
            _remember_impact(data, payload)
            return

        if tool_name in NATIVE_TOOLS:
            pending_edit = data["pending_mutations"].pop(tool_id, None) if isinstance(tool_id, str) else None
            paired = isinstance(pending_edit, dict) and pending_edit.get("task_id") == data["task_id"]
            if paired or _identity_matches(data, payload):
                # Without a Pre record, retain an explicitly current-task edit
                # as unknown-baseline evidence; old task IDs/prompts are ignored.
                _track_native(data, tool_name, tool_input, cwd, before=False)
                _remember_tool(data, tool_id)
        # Skill activation occurs in PreToolUse. A delayed old Skill completion
        # cannot activate a new task after the original state was closed.
        if not data["active"]:
            return

        if tool_name == "TaskStop" and isinstance(tool_input, dict):
            task_id = tool_input.get("task_id") or tool_input.get("shell_id")
            response = payload.get("tool_response")
            if event != "PostToolUse" or not isinstance(response, dict) or response.get("task_id") != task_id:
                return
            for pending_id, check in list(data["pending_checks"].items()):
                if task_id and check.get("background_task_id") == task_id and check.get("task_id") == data["task_id"]:
                    data["pending_checks"].pop(pending_id)
                    if check["kind"] == "verification":
                        _record_failure(data, pending_id, check, {"status": "cancelled", "reason": "background_task_stopped"})
            _set_status(data)
            return

        if tool_name not in SHELL_TOOLS or not isinstance(tool_id, str):
            _remember_impact(data, payload)
            return
        actual = _check_command(tool_input.get("command") if isinstance(tool_input, dict) else None, cwd, tool_name,
                                workdir=tool_input.get("workdir") if isinstance(tool_input, dict) else None)
        check = data["pending_checks"].get(tool_id)
        result = result_status(payload, HOST_KIND)
        if not isinstance(check, dict) or check.get("task_id") != data["task_id"]:
            # A known current-task failure still invalidates earlier success,
            # but unpaired successful results never create fresh evidence.
            if actual and actual["kind"] == "verification" and _identity_matches(data, payload) and result["status"] in {"failed", "cancelled"}:
                _record_failure(data, tool_id, actual, result)
                _set_status(data)
            return
        if not actual or any(actual.get(field) != check.get(field) for field in ("argv", "cwd", "shell", "command_digest")):
            return
        if check.get("run_in_background") and result["status"] == "passed" and not check.get("background_task_id") and result.get("reason") == "successful_synchronous_post_tool_use":
            result = {"status": "pending", "reason": "background_completion_not_observed"}
        if result["status"] == "pending":
            check["status"] = "pending"
            if result.get("background_task_id"):
                check["background_task_id"] = result["background_task_id"]
            _set_status(data)
            return

        data["pending_checks"].pop(tool_id)
        current = capture(data, check["cwd"])
        baseline_root = data["baseline_snapshot"].get("root")
        stable = snapshots_equal(check["start_snapshot"], current) and current.get("root") == baseline_root
        if result["status"] == "passed" and not check.get("scope_proven"):
            result = {"status": "unverified", "reason": "execution_workdir_unavailable"}
        elif result["status"] == "passed" and not stable:
            result = {"status": "unverified", "reason": "snapshot_changed_or_incomplete_during_check"}
        if check["kind"] == "verification":
            if result["status"] == "passed":
                data["failed_checks"].pop(_command_key(check), None)
                data["verification_snapshot"] = current
                data["verification_commands"] = (data["verification_commands"] + [check["command"][:300]])[-8:]
                data["verification_evidence"] = (data["verification_evidence"] + [{
                    "task_id": data["task_id"], "tool_use_id": tool_id,
                    "source_agent_id": check.get("source_agent_id"),
                    "argv": check["argv"], "cwd": check["cwd"], "shell": check["shell"],
                    "status": "passed", "completion_reason": result.get("reason"),
                    "exit_code": result.get("exit_code"),
                    "scope": "recorded command; coverage is not inferred",
                }])[-8:]
                data["verification_guard_warned"] = False
            elif result["status"] in {"failed", "cancelled"}:
                _record_failure(data, tool_id, check, result)
            else:
                data["verification_snapshot"] = None
                data["last_unverified_reason"] = result.get("reason")
        elif check["kind"] == "diff":
            covered = result["status"] == "passed" and _diff_covers_snapshot(check, current, data["baseline_snapshot"])
            data["diff_snapshot"] = current if covered else None
            data["diff_guard_warned"] = False
        _set_status(data)
        _remember_impact(data, payload)
        data["updated_at"] = int(time.time())


def main() -> int:
    if sys.argv[1:] == ["--activate"]:
        print("High Agency activation requested through the host PreToolUse hook.")
        return 0
    try:
        payload = json.load(getattr(sys.stdin, "buffer", sys.stdin))
    except (ValueError, OSError):
        return 0
    if isinstance(payload, dict):
        process(payload)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        # Advisory tracking must not break a user's host session.
        if os.environ.get("HIGH_AGENCY_HOOK_DEBUG") == "1":
            traceback.print_exc()
        raise SystemExit(0)
