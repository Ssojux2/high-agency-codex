#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import os
import re
import stat
from pathlib import Path

MAX_TRANSCRIPT_BYTES = 8 * 1024 * 1024
GENERIC_ROOTS = {"src", "lib", "app", "apps", "packages", "services", "crates", "modules", "pkg"}

IMPACT_RE = re.compile(
    r"^\s*Impact:\s*(local|propagating|high)\s*\|\s*"
    r"files\s*(?:<=|≤)\s*(\d+)\s*\|\s*"
    r"modules\s*(?:<=|≤)\s*(\d+)\s*\|\s*"
    r"boundary\s*=\s*(private|shared-api|high-impact)\s*$",
    re.IGNORECASE | re.MULTILINE,
)


def parse_impact(text: str) -> dict | None:
    if not isinstance(text, str):
        return None
    match = IMPACT_RE.search(text)
    if not match:
        return None
    def bounded_count(value: str) -> int:
        digits = value.lstrip("0") or "0"
        return 999 if len(digits) > 3 else max(1, int(digits))
    files = bounded_count(match.group(2))
    modules = bounded_count(match.group(3))
    return {
        "tier": match.group(1).lower(),
        "files_max": min(files, 999),
        "modules_max": min(modules, 999),
        "boundary": match.group(4).lower(),
        "raw": match.group(0).strip(),
    }


def _content_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                value = item.get("text")
                if isinstance(value, str):
                    parts.append(value)
                elif isinstance(item.get("content"), str):
                    parts.append(item["content"])
        return "\n".join(parts)
    if isinstance(content, dict):
        value = content.get("text")
        return value if isinstance(value, str) else ""
    return ""


def _message_record(entry):
    """Read host message envelopes, not arbitrary nested tool-result content."""
    if not isinstance(entry, dict) or entry.get("isSidechain") or entry.get("isMeta"):
        return None
    if entry.get("role") in ("assistant", "user"):
        return entry
    for key in ("message", "payload"):
        value = entry.get(key)
        if isinstance(value, dict) and value.get("role") in ("assistant", "user"):
            return value
    payload = entry.get("payload")
    if (entry.get("type") == "event_msg" and isinstance(payload, dict)
            and payload.get("type") == "user_message" and isinstance(payload.get("message"), str)):
        return {"role": "user", "content": payload["message"]}
    return None


def _assistant_texts(entry):
    message = _message_record(entry)
    if message and message.get("role") == "assistant":
        text = _content_text(message.get("content"))
        if text:
            yield text


def _user_prompt(entry) -> str | None:
    message = _message_record(entry)
    if not message or message.get("role") != "user":
        return None
    content = message.get("content")
    # Claude records tool results as user messages. They are not new tasks.
    if isinstance(content, list):
        content = [item for item in content if isinstance(item, str)
                   or (isinstance(item, dict) and item.get("type") in ("text", "input_text"))]
    text = _content_text(content)
    return text if text else None


def first_impact_from_transcript(
    raw_path, start_offset: int | None = None, *, prompt_marker: str | None = None,
    expected_identity: dict | None = None,
) -> dict | None:
    """Return the first estimate for this task, bounded by a byte cursor.

    Capture `start_offset` at UserPromptSubmit. A matching device/inode identity
    additionally rejects rotated transcripts. Without a cursor, only the latest
    visible human prompt is used; a capped tail lacking that boundary is unknown.
    A marker can be the human prompt's exact text or its host UUID/id/turn_id.
    """
    if not isinstance(raw_path, str) or not raw_path:
        return None
    if start_offset is not None and (type(start_offset) is not int or start_offset < 0):
        return None
    if prompt_marker is not None and (not isinstance(prompt_marker, str) or not prompt_marker):
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
            if expected_identity is not None:
                if (not isinstance(expected_identity, dict)
                        or expected_identity.get("device") != before.st_dev
                        or expected_identity.get("inode") != before.st_ino):
                    return None
            if start_offset is not None and start_offset > before.st_size:
                return None
            offset = start_offset if start_offset is not None else max(0, before.st_size - MAX_TRANSCRIPT_BYTES)
            remaining = MAX_TRANSCRIPT_BYTES
            handle.seek(offset)
            if offset:
                handle.seek(offset - 1)
                if handle.read(1) != b"\n":
                    # A stale/partial-line cursor must not parse its remainder as
                    # a complete new message. Limit this skip to the same budget.
                    skipped = handle.readline(remaining)
                    remaining -= len(skipped)
                    if not skipped.endswith(b"\n"):
                        return None
            data = handle.read(remaining)
            after = os.fstat(handle.fileno())
            current = path.stat()
            if (after.st_size < before.st_size or current.st_size < after.st_size
                    or (current.st_dev, current.st_ino) != (before.st_dev, before.st_ino)):
                return None
    except (OSError, ValueError):
        return None

    estimate = None
    boundary_seen = False
    marker_seen = prompt_marker is None
    # JSONL writers can still be appending the last line; wait for its newline.
    for line in data.split(b"\n")[:-1]:
        try:
            entry = json.loads(line.decode("utf-8"))
        except Exception:
            continue
        prompt = _user_prompt(entry)
        if prompt is not None:
            boundary_seen = True
            if start_offset is not None and prompt_marker is None:
                # The lifecycle hook already chose this task's boundary. Later
                # Stop continuations/tool notifications must not rewrite it.
                continue
            estimate = None
            if prompt_marker is not None:
                message = _message_record(entry) or {}
                marker_seen = prompt_marker == prompt or any(
                    prompt_marker == node.get(key)
                    for node in (entry, message)
                    for key in ("uuid", "id", "turn_id")
                )
            continue
        if not marker_seen or estimate is not None:
            continue
        for assistant_text in _assistant_texts(entry):
            estimate = parse_impact(assistant_text)
            if estimate:
                break
    if start_offset is None and offset > 0 and not boundary_seen:
        return None
    return estimate if marker_seen else None


def module_key(raw: str) -> str:
    value = raw.replace("\\", "/")
    while value.startswith("./"):
        value = value[2:]
    parts = [part for part in value.split("/") if part]
    if len(parts) <= 1:
        return "."
    if parts[0].lower() in GENERIC_ROOTS and len(parts) >= 2:
        return "/".join(parts[:2])
    return parts[0]


def scope_metrics(files: list[str]) -> dict:
    unique = sorted(set(files))
    modules = sorted({module_key(path) for path in unique})
    return {
        "file_count": len(unique),
        "module_count": len(modules),
        "modules": modules,
    }


def classify_drift(
    estimate: dict | None,
    files: list[str],
    *,
    high_impact: bool = False,
    truncated: bool = False,
) -> dict:
    metrics = scope_metrics(files)
    result = {
        "severity": "none",
        "reasons": [],
        **metrics,
    }
    if not estimate:
        return result

    major = []
    minor = []

    if truncated:
        major.append("changed-file snapshot exceeded tracking limit")

    if high_impact and estimate.get("boundary") != "high-impact":
        major.append(
            f"boundary expanded from {estimate.get('boundary')} to a high-impact path"
        )

    file_limit = max(1, int(estimate.get("files_max") or 1))
    module_limit = max(1, int(estimate.get("modules_max") or 1))

    file_count = metrics["file_count"]
    module_count = metrics["module_count"]

    if file_count > file_limit:
        major_threshold = max(file_limit + 2, math.ceil(file_limit * 1.5))
        target = major if file_count >= major_threshold else minor
        target.append(f"files {file_count} exceeded estimate <={file_limit}")

    if module_count > module_limit:
        major_threshold = max(module_limit + 1, math.ceil(module_limit * 1.5))
        target = major if module_count >= major_threshold else minor
        target.append(f"modules {module_count} exceeded estimate <={module_limit}")

    if major:
        result["severity"] = "major"
        result["reasons"] = major + minor
    elif minor:
        result["severity"] = "minor"
        result["reasons"] = minor

    return result
