#!/usr/bin/env python3
"""Bounded Stop decisions from current task evidence, never a verification claim."""
from __future__ import annotations

import json
import os
import re
import stat
import subprocess
import sys
import time
import traceback
import uuid
from pathlib import Path

from git_state import (
    delta_files,
    file_fingerprint,
    fingerprint_complete,
    snapshot,
    snapshot_complete,
    snapshots_equal,
)
from impact_scope import classify_drift, first_impact_from_transcript
from state_store import state_transaction
from verification_state import new_task_state

MARKER_RE = re.compile(
    r"<!--\s*high-agency:continue(?:\s+max=(\d+))?\s*-->\s*$",
    re.IGNORECASE | re.DOTALL,
)
DEFAULT_MAX = 3
HARD_CAP = 12
MAX_TRANSCRIPT_BYTES = 1024 * 1024
LARGE_DIFF_LINES = 120
DOC_EXTS = {".md", ".mdx", ".txt", ".rst", ".adoc", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico"}
DOC_NAMES = {"LICENSE", "README", "CHANGELOG", "CONTRIBUTING", "CODE_OF_CONDUCT"}
RISK_RE = re.compile(
    r"(^|/)(migrations?|schema|auth|security|permissions?|policies?|\.github/workflows)(/|$)|"
    r"(^|/)(package\.json|pyproject\.toml|cargo\.toml|go\.mod|go\.sum|pom\.xml|"
    r"dockerfile|docker-compose\.(?:yml|yaml)|[^/]*lock[^/]*)$",
    re.IGNORECASE,
)


def emit(payload: dict) -> None:
    sys.stdout.write(json.dumps(payload, separators=(",", ":")) + "\n")


def debug(message: str) -> None:
    if os.environ.get("HIGH_AGENCY_HOOK_DEBUG") == "1":
        print("High Agency Stop: " + message, file=sys.stderr)


def mapping(value) -> dict:
    return value if isinstance(value, dict) else {}


def string_list(value) -> list[str]:
    return [item for item in value if isinstance(item, str) and item] if isinstance(value, list) else []


def content_text(content) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    return "\n".join(
        item["text"]
        for item in content
        if isinstance(item, dict)
        and item.get("type") in ("text", "output_text")
        and isinstance(item.get("text"), str)
    )


def transcript_message(raw_path) -> str | None:
    """Read a bounded tail only for older hosts that omit the latest-text field."""
    if not isinstance(raw_path, str) or not raw_path:
        return None
    path = Path(raw_path)
    try:
        if not stat.S_ISREG(path.lstat().st_mode):
            return None
        flags = (os.O_RDONLY | getattr(os, "O_BINARY", 0)
                 | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
        descriptor = os.open(path, flags)
        with os.fdopen(descriptor, "rb") as handle:
            before = os.fstat(handle.fileno())
            if not stat.S_ISREG(before.st_mode):
                return None
            start = max(0, before.st_size - MAX_TRANSCRIPT_BYTES)
            remaining = MAX_TRANSCRIPT_BYTES
            handle.seek(start)
            if start:
                handle.seek(start - 1)
                if handle.read(1) != b"\n":
                    skipped = handle.readline(remaining)
                    remaining -= len(skipped)
                    if not skipped.endswith(b"\n"):
                        return None
            data = handle.read(remaining)
            after = os.fstat(handle.fileno())
            current = path.lstat()
            identity = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
            if any(
                (item.st_dev, item.st_ino, item.st_size, item.st_mtime_ns) != identity
                for item in (after, current)
            ):
                return None
    except (OSError, ValueError):
        return None

    if data and not data.endswith(b"\n"):
        # An in-flight final record is not a trustworthy older-host stop message.
        return None
    latest = None
    for line in data.decode("utf-8", "replace").splitlines():
        try:
            entry = json.loads(line)
        except (ValueError, TypeError):
            continue
        if not isinstance(entry, dict):
            continue
        message = entry.get("message")
        if not isinstance(message, dict):
            message = entry.get("payload")
        if not isinstance(message, dict):
            message = entry
        role = message.get("role")
        if role == "user":
            # Do not reuse a marker from the task before the latest user boundary.
            latest = ""
        elif role == "assistant":
            # Empty assistant output also supersedes an older continuation marker.
            latest = content_text(message.get("content"))
    return latest


def latest_message(payload: dict) -> str | None:
    if "last_assistant_message" in payload:
        value = payload["last_assistant_message"]
        if not isinstance(value, str):
            debug("last_assistant_message is not text; ignoring the malformed event")
            return None
        return value
    return transcript_message(payload.get("transcript_path"))


def code_files(files: list[str]) -> list[str]:
    result = []
    for raw in files:
        path = Path(raw)
        name = path.name
        if name.upper() in DOC_NAMES or name.upper().startswith("README"):
            continue
        if path.suffix.lower() in DOC_EXTS:
            continue
        result.append(raw)
    return result


def rel(raw: str, cwd: Path) -> str:
    path = Path(raw)
    try:
        if path.is_absolute():
            return native_path(raw, cwd).relative_to(native_path(str(cwd), cwd)).as_posix()
    except (OSError, ValueError):
        pass
    # lstrip("./") also strips the leading dot from .github and other real names.
    return path.as_posix()


def native_path(raw: str, cwd: Path) -> Path:
    """Normalize Windows drives/case without following a file's symlink."""
    path = Path(raw)
    if not path.is_absolute():
        path = cwd / path
    return Path(os.path.normcase(os.path.abspath(path)))


def current_snapshot(data: dict, cwd: Path) -> dict:
    baseline = mapping(data.get("baseline_snapshot"))
    base_ref = baseline.get("base_ref")
    current = snapshot(cwd, base_ref=base_ref if isinstance(base_ref, str) else None)
    native = {}
    deadline = time.monotonic() + 1.0
    for raw, entry in mapping(data.get("native_files")).items():
        if not isinstance(raw, str) or not raw:
            continue
        path = native_path(raw, cwd)
        fingerprint = file_fingerprint(path.parent, path.name, deadline=deadline)
        if isinstance(entry, dict):
            entry["current"] = fingerprint
        if mapping(entry).get("before") != fingerprint or not fingerprint_complete(fingerprint):
            native[str(path)] = fingerprint
    current["native_files"] = native
    if data.get("native_tracking_truncated"):
        current["available"] = False
        current["complete"] = False
        current["truncated"] = True
    if data.get("verification_tracking_incomplete"):
        current.update(available=False, complete=False, error="verification_tracking_limit_exceeded")
    return current


def scope_root(current: dict, cwd: Path) -> Path:
    value = current.get("root")
    return Path(value) if isinstance(value, str) and value else cwd


def task_files(data: dict, current: dict, cwd: Path | None = None) -> list[str]:
    """Union Git changes and native edits, including ignored and external files."""
    root = scope_root(current, cwd or Path(".").resolve())
    baseline = mapping(data.get("baseline_snapshot"))
    files = {rel(path, root) for path in delta_files(baseline, current)}
    if not snapshot_complete(baseline) or not snapshot_complete(current):
        # Keep known paths when discovery is incomplete. Absence is not a clean tree.
        for source in (mapping(baseline.get("files")), mapping(current.get("files"))):
            files.update(rel(path, root) for path in source if isinstance(path, str))

    native = mapping(data.get("native_files"))
    now = mapping(current.get("native_files"))
    tracked = set()
    for raw, entry in native.items():
        if not isinstance(raw, str) or not raw:
            continue
        normalized = rel(raw, root)
        tracked.add(normalized)
        before = mapping(entry).get("before")
        actual = now.get(str(native_path(raw, cwd or root)))
        if actual is None:
            actual = mapping(entry).get("current")
        # A known return to the task's starting bytes needs no extra native delta.
        if not fingerprint_complete(before) or not fingerprint_complete(actual) or before != actual:
            files.add(normalized)

    # Older/missing PreToolUse evidence must not make a native edit disappear merely
    # because there are also ordinary Git changes.
    for raw in string_list(data.get("all_edited_files")):
        normalized = rel(raw, root)
        if normalized not in tracked:
            files.add(normalized)
    return sorted(files)


def git_stats(cwd: Path, files: list[str], base_ref: str | None) -> tuple[int, str]:
    if not files or not base_ref:
        return 0, ""
    try:
        numstat = subprocess.run(
            ["git", "diff", "--numstat", base_ref, "--", *files],
            cwd=cwd, text=True, capture_output=True, timeout=0.8, check=False,
        )
        total = 0
        if numstat.returncode == 0:
            for line in numstat.stdout.splitlines():
                parts = line.split("\t")
                if len(parts) >= 2:
                    total += sum(int(part) for part in parts[:2] if part.isdigit())
        check = subprocess.run(
            ["git", "diff", "--check", base_ref, "--", *files],
            cwd=cwd, text=True, capture_output=True, timeout=0.8, check=False,
        )
        issue = (check.stdout + check.stderr).strip()[:1200] if check.returncode else ""
        return total, issue
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return 0, ""


def diff_reasons(data: dict, current: dict, files: list[str], cwd: Path, estimate=None) -> tuple[list[str], list[str], str]:
    relevant = code_files(files)
    reasons = []
    if not snapshot_complete(current):
        reasons.append("changed-file tracking is incomplete")
    relative = [rel(path, cwd) for path in relevant]
    if not estimate:
        if len(relevant) >= 3:
            reasons.append(f"{len(relevant)} code/config files changed")
        top_levels = {path.split("/")[0] if "/" in path else "." for path in relative}
        if len(relevant) >= 2 and len(top_levels) >= 2:
            reasons.append("change crosses module boundaries")
    if any(RISK_RE.search(path) for path in relative):
        reasons.append("high-impact/shared path changed")
    baseline = mapping(data.get("baseline_snapshot"))
    lines, check = git_stats(cwd, relevant, baseline.get("base_ref"))
    if lines >= LARGE_DIFF_LINES:
        reasons.append(f"large diff ({lines} changed lines)")
    if check:
        reasons.append("git diff --check reported an issue")
    return reasons, relevant, check


def impact_drift(data: dict, payload: dict, current: dict, files: list[str], cwd: Path) -> tuple[dict | None, dict]:
    estimate = data.get("impact_estimate")
    if not isinstance(estimate, dict):
        estimate = first_impact_from_transcript(
            payload.get("transcript_path"),
            start_offset=data.get("transcript_start_offset", 0),
            expected_identity=data.get("transcript_identity"),
        )
        if estimate:
            data["impact_estimate"] = estimate
    relative = [rel(path, cwd) for path in files]
    drift = classify_drift(
        estimate, relative,
        high_impact=any(RISK_RE.search(path) for path in relative),
        truncated=bool(current.get("truncated")),
    )
    return estimate, drift


def requested_limit(marker) -> int:
    value = marker.group(1)
    if value is None:
        return DEFAULT_MAX
    value = value.lstrip("0") or "0"
    return HARD_CAP if len(value) > 2 else min(max(int(value), 1), HARD_CAP)


def continuation_state(data: dict, marker) -> dict:
    previous = data.get("continuation")
    if previous is not None and not isinstance(previous, dict):
        raise ValueError("Invalid continuation state")
    previous = previous or {}
    if previous.get("task_id") not in {None, data.get("task_id")}:
        previous = {}
    count = previous.get("continuations", 0)
    limit = previous.get("limit", requested_limit(marker))
    if type(count) is not int or not 0 <= count <= HARD_CAP:
        raise ValueError("Invalid continuation count")
    if type(limit) is not int or not 1 <= limit <= HARD_CAP:
        raise ValueError("Invalid continuation limit")
    # A later model-generated marker may tighten a budget, never extend it.
    result = {
        "task_id": data.get("task_id"),
        "continuations": count,
        "limit": min(limit, requested_limit(marker)),
    }
    data["continuation"] = result
    return result


def complete(data: dict, reason: str) -> dict:
    data.update({
        "active": False,
        "task_completed": True,
        "continuing_stop": False,
        "completion_reason": reason,
        "completed_at": int(time.time()),
    })
    return {}


def block(data: dict, reason: str) -> dict:
    data["continuing_stop"] = True
    return {"decision": "block", "reason": reason}


def warn_once(data: dict, name: str, legacy_flag: str) -> bool:
    warnings = data.get("stop_guard_warnings", [])
    if not isinstance(warnings, list):
        raise ValueError("Invalid Stop warning state")
    if name in warnings or data.get(legacy_flag) is True:
        return False
    data["stop_guard_warnings"] = string_list(warnings) + [name]
    data[legacy_flag] = True
    return True


def verification_problem(data: dict, current: dict, relevant: list[str]) -> str | None:
    status = data.get("verification_status")
    failure = mapping(data.get("verification_failure"))
    if status in {"failed", "cancelled"} or failure.get("status") in {"failed", "cancelled"}:
        label = "was cancelled" if status == "cancelled" else "failed"
        return (
            f"the latest relevant verification {label}. Make a focused correction and rerun "
            "only the affected check when useful, or report the failure/blocker honestly."
        )
    pending = any(
        mapping(check).get("kind") == "verification"
        for check in mapping(data.get("pending_checks")).values()
    )
    if status == "pending" or pending:
        return (
            "a verification check is still pending. Observe that existing check's completion "
            "or report it as PENDING; do not start duplicate checks merely to clear this guard."
        )
    if failure:
        return (
            "verification evidence is incomplete or unavailable. Report the affected scope "
            "as UNVERIFIED and explain the limitation instead of claiming a successful check."
        )
    if not snapshot_complete(current) or not snapshot_complete(data.get("baseline_snapshot")):
        return (
            "changed-file tracking is incomplete, so verification of the current scope is "
            "UNVERIFIED. Inspect the known touched scope and report the tracking limitation; "
            "an incomplete snapshot is not proof that nothing changed."
        )
    unknown_reason = data.get("last_unverified_reason")
    if status != "passed" and unknown_reason in (
        "missing_authoritative_completion", "execution_workdir_unavailable"
    ):
        missing = (
            "execution-directory evidence" if unknown_reason == "execution_workdir_unavailable"
            else "authoritative completion metadata"
        )
        return (
            f"the host hook did not provide {missing} for the "
            "verification command. Automatic verification is UNVERIFIED. Report the "
            "command's observed result and this host limitation; rerunning the same "
            "command solely to satisfy this guard cannot supply missing hook metadata."
        )
    if relevant and not (
        status == "passed" and snapshots_equal(data.get("verification_snapshot"), current)
    ):
        return (
            "the current code/config changes have no successful verification evidence for "
            "this exact Git and native-file snapshot. Run the narrowest relevant targeted "
            "check, or report the remaining scope as UNVERIFIED."
        )
    return None


def invalidate_stale_evidence(data: dict, current: dict) -> None:
    if data.get("verification_status") != "passed":
        return
    if (
        not snapshot_complete(data.get("baseline_snapshot"))
        or not snapshots_equal(data.get("verification_snapshot"), current)
    ):
        # Preserve historical command evidence, but never label today's unknown
        # or changed snapshot as passed, including at the continuation budget cap.
        data["verification_status"] = "unverified"
        data["verification_snapshot"] = None
        data["last_unverified_reason"] = "snapshot_changed_or_incomplete_at_stop"


def validate_stop_state(data: dict) -> None:
    for name in ("active", "task_completed", "continuing_stop", "native_tracking_truncated",
                 "verification_tracking_incomplete",
                 "verification_guard_warned", "impact_drift_warned", "diff_guard_warned"):
        if name in data and type(data[name]) is not bool:
            raise ValueError("Invalid Stop state flag")
    for name in ("baseline_snapshot", "native_files", "pending_checks", "continuation"):
        if name in data and not isinstance(data[name], dict):
            raise ValueError("Invalid Stop state collection")
    for name in ("verification_snapshot", "diff_snapshot", "impact_estimate", "verification_failure"):
        if data.get(name) is not None and not isinstance(data[name], dict):
            raise ValueError("Invalid Stop evidence record")
    for name in ("prompt_ids", "all_edited_files", "stop_guard_warnings"):
        if name in data and not isinstance(data[name], list):
            raise ValueError("Invalid Stop state history")
    if "task_id" in data and (not isinstance(data["task_id"], str) or not data["task_id"]):
        raise ValueError("Invalid Stop task identity")
    if "verification_status" in data and not isinstance(data["verification_status"], str):
        raise ValueError("Invalid Stop evidence status")


def process_stop(payload: dict) -> dict:
    if payload.get("hook_event_name") not in {None, "", "Stop"}:
        return {}
    # A late subagent event must never finish, reset, or consume its parent's budget.
    if payload.get("agent_id"):
        return {}
    message = latest_message(payload)
    if message is None:
        return {}
    cwd_value = payload.get("cwd", ".")
    if not isinstance(cwd_value, str) or not cwd_value:
        raise ValueError("Invalid hook working directory")
    cwd = Path(cwd_value).resolve()
    marker = MARKER_RE.search(message)

    with state_transaction(payload) as data:
        validate_stop_state(data)
        if not data and marker:
            # Preserve the budget through later PreToolUse/UserPromptSubmit events,
            # even when this hook was enabled after the task's original prompt.
            data.update(new_task_state(payload, str(cwd), active=False))
        prompt_id = payload.get("prompt_id")
        known_prompts = string_list(data.get("prompt_ids"))
        if isinstance(prompt_id, str) and known_prompts and prompt_id not in known_prompts:
            debug("ignoring a Stop event outside the active task's known prompts")
            return {}
        if data.get("task_completed") is True:
            return {}
        active = data.get("active") is True
        if not active and not marker:
            return complete(data, "done") if data else {}
        if not isinstance(data.get("task_id"), str) or not data["task_id"]:
            data["task_id"] = uuid.uuid4().hex

        bounded = continuation_state(data, marker) if marker else mapping(data.get("continuation"))
        current = current_snapshot(data, cwd) if active else {}
        if active:
            invalidate_stale_evidence(data, current)
        if marker and bounded["continuations"] >= bounded["limit"]:
            return complete(data, "budget_exhausted")
        root = scope_root(current, cwd)
        changed = task_files(data, current, cwd) if active else []
        relevant = code_files(changed)

        if active:
            problem = verification_problem(data, current, relevant)
            if problem and warn_once(data, "verification", "verification_guard_warned"):
                suffix = ""
                if marker:
                    suffix = f" Preserve <!-- high-agency:continue max={bounded['limit']} --> only if useful work remains."
                return block(
                    data,
                    "High Agency verification guard: " + problem
                    + " Do not claim checks passed without evidence or repeat an unavailable check indefinitely."
                    + suffix,
                )

        estimate, drift = impact_drift(data, payload, current, relevant, root) if active else (None, {})
        if (
            active and estimate and drift.get("severity") in {"minor", "major"}
            and warn_once(data, "impact", "impact_drift_warned")
        ):
            severity = drift["severity"]
            actual = f"{drift.get('file_count', 0)} files / {drift.get('module_count', 0)} modules"
            reasons = "; ".join(string_list(drift.get("reasons")))
            if severity == "major":
                data["diff_guard_warned"] = True
                action = (
                    "Major scope drift. Inspect the focused final diff and the expanded semantic "
                    "boundary. Extend verification only for the newly affected risk surface."
                )
            else:
                action = (
                    "Minor scope drift. Extend verification to the newly affected surface; "
                    "a full suite or extra reviewer needs an additional risk signal."
                )
            return block(
                data,
                "High Agency impact calibration: initial " + str(estimate.get("raw") or "")
                + "; actual " + actual + ". " + reasons + ". " + action
                + " Keep the original estimate immutable and report any remaining failed, pending, "
                "or unverified checks honestly.",
            )

        if active and not marker and not snapshots_equal(data.get("diff_snapshot"), current):
            reasons, diff_files, check = diff_reasons(data, current, changed, root, estimate)
            if reasons and warn_once(data, "diff", "diff_guard_warned"):
                preview = ", ".join(rel(path, root) for path in diff_files[:8]) or "known touched files"
                extra = (" git diff --check also reported: " + check) if check else ""
                return block(
                    data,
                    "High Agency conditional diff review: " + "; ".join(reasons)
                    + ". Inspect the focused final diff (" + preview
                    + "), confirm the intended scope, then finish with truthful evidence or limitations."
                    + " Do not launch a broad review or repeat unavailable checks just to clear this guard."
                    + extra,
                )

        if not marker:
            return complete(data, "done")

        bounded["continuations"] += 1
        bounded["updated_at"] = int(time.time())
        count, limit = bounded["continuations"], bounded["limit"]
        if count == limit:
            reason = (
                f"Final bounded-autonomy continuation {count}/{limit}. Make the highest-value "
                "remaining progress, verify only the touched/affected scope when possible, "
                "do not emit another continuation marker, and report evidence, failed/pending/"
                "unverified checks, or the blocker honestly."
            )
        else:
            reason = (
                f"Bounded-autonomy continuation {count}/{limit}. Continue from the current "
                "repository state with an independently verifiable step and targeted checks. "
                "Request another pass only after meaningful progress; if useful, end with "
                f"<!-- high-agency:continue max={limit} -->."
            )
        return block(data, reason)


def main() -> int:
    try:
        payload = json.load(getattr(sys.stdin, "buffer", sys.stdin))
        if not isinstance(payload, dict):
            debug("hook payload is not an object")
            emit({})
            return 0
        result = process_stop(payload)
    except Exception:
        # Stop guards are advisory. State, input, filesystem, or Git failures must
        # not interrupt the host session; diagnostics are explicitly opt-in.
        if os.environ.get("HIGH_AGENCY_HOOK_DEBUG") == "1":
            traceback.print_exc(file=sys.stderr)
        result = {}
    emit(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
