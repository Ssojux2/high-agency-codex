#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

from git_state import snapshot

VERIFY_RE = re.compile(
    r"(?:\bpytest\b|python\s+-m\s+pytest|\bjest\b|\bvitest\b|playwright\s+test|"
    r"cypress\s+run|cargo\s+(?:test|check)|go\s+test|dotnet\s+test|mvnw?\b.*\btest\b|"
    r"gradlew?\b.*\btest\b|\brspec\b|swift\s+test|xcodebuild\b.*\btest\b|"
    r"\b(?:npm|pnpm|yarn|bun)\b.*\b(?:test|lint|typecheck|check|build)\b|"
    r"\btsc\b|\beslint\b|\bruff\b|\bmypy\b|\bpyright\b)",
    re.IGNORECASE,
)
DIFF_RE = re.compile(r"\bgit\s+(?:-C\s+\S+\s+)?diff\b", re.IGNORECASE)
PATCH_PATH_RE = re.compile(r"^\*\*\* (?:Update|Add|Delete) File:\s*(.+?)\s*$", re.MULTILINE)


def state_dir() -> Path:
    return Path(os.environ.get("PLUGIN_DATA") or ".").resolve() / "verification"


def key(payload: dict) -> str:
    return str(payload.get("turn_id") or payload.get("session_id") or "default")


def path_for(payload: dict) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", key(payload))[:120]
    return state_dir() / f"{safe}.json"


def load(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
    tmp.replace(path)


def active_prompt(prompt: str) -> bool:
    value = prompt.lower()
    return (
        "high-agency" in value
        or "high agency" in value
        or "bounded-autonomy" in value
    )


def extract_paths(tool_name: str, tool_input) -> list[str]:
    if not isinstance(tool_input, dict):
        return []
    found = []
    for field in ("file_path", "path", "notebook_path"):
        value = tool_input.get(field)
        if isinstance(value, str) and value:
            found.append(value)
    if tool_name == "apply_patch":
        command = tool_input.get("command")
        if isinstance(command, str):
            found.extend(PATCH_PATH_RE.findall(command))
    return found


def capture(data: dict, cwd: str) -> dict:
    baseline = data.get("baseline_snapshot") or {}
    base_ref = baseline.get("base_ref") if baseline.get("available") else None
    return snapshot(cwd, base_ref=base_ref)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    event = str(payload.get("hook_event_name") or "")
    path = path_for(payload)
    cwd = str(payload.get("cwd") or ".")

    if event == "UserPromptSubmit":
        prompt = str(payload.get("prompt") or payload.get("user_prompt") or "")
        active = active_prompt(prompt)
        baseline = snapshot(cwd) if active else {"available": False}
        save(
            path,
            {
                "active": active,
                "baseline_snapshot": baseline,
                "verification_snapshot": None,
                "diff_snapshot": None,
                "native_dirty": False,
                "all_edited_files": [],
                "verification_commands": [],
                "verification_guard_warned": False,
                "diff_guard_warned": False,
            },
        )
        return 0

    if event != "PostToolUse":
        return 0

    data = load(path)
    if not data.get("active"):
        return 0

    tool_name = str(payload.get("tool_name") or "")
    tool_input = payload.get("tool_input")

    if tool_name in {"Edit", "Write", "NotebookEdit", "apply_patch"}:
        paths = extract_paths(tool_name, tool_input)
        if paths:
            edited = list(data.get("all_edited_files") or [])
            for item in paths:
                if item not in edited:
                    edited.append(item)
            data["all_edited_files"] = edited[:128]
            data["native_dirty"] = True
            data["verification_guard_warned"] = False
            data["diff_guard_warned"] = False

    if tool_name == "Bash" and isinstance(tool_input, dict):
        command = tool_input.get("command")
        if isinstance(command, str):
            if VERIFY_RE.search(command):
                data["verification_snapshot"] = capture(data, cwd)
                data["native_dirty"] = False
                commands = list(data.get("verification_commands") or [])
                commands.append(command[:300])
                data["verification_commands"] = commands[-8:]
                data["verification_guard_warned"] = False
            if DIFF_RE.search(command):
                data["diff_snapshot"] = capture(data, cwd)
                data["diff_guard_warned"] = False

    save(path, data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
