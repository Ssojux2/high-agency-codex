#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

VERIFY_RE = re.compile(
    r"(?:\bpytest\b|python\s+-m\s+pytest|\bjest\b|\bvitest\b|playwright\s+test|"
    r"cypress\s+run|cargo\s+(?:test|check)|go\s+test|dotnet\s+test|mvnw?\b.*\btest\b|"
    r"gradlew?\b.*\btest\b|\brspec\b|swift\s+test|xcodebuild\b.*\btest\b|"
    r"\b(?:npm|pnpm|yarn|bun)\b.*\b(?:test|lint|typecheck|check|build)\b|"
    r"\btsc\b|\beslint\b|\bruff\b|\bmypy\b|\bpyright\b)",
    re.IGNORECASE,
)
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
    p = prompt.lower()
    return "high-agency" in p or "high agency" in p or "bounded-autonomy" in p

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

def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    event = str(payload.get("hook_event_name") or "")
    path = path_for(payload)

    if event == "UserPromptSubmit":
        prompt = str(payload.get("prompt") or payload.get("user_prompt") or "")
        save(path, {
            "active": active_prompt(prompt),
            "edited_files": [],
            "verification_seen": False,
            "verification_commands": [],
            "guard_warned": False,
        })
        return 0

    if event != "PostToolUse":
        return 0

    data = load(path)
    if not data.get("active"):
        return 0

    tool_name = str(payload.get("tool_name") or "")
    tool_input = payload.get("tool_input")
    edited = list(data.get("edited_files") or [])

    if tool_name in {"Edit", "Write", "NotebookEdit", "apply_patch"}:
        for item in extract_paths(tool_name, tool_input):
            if item not in edited:
                edited.append(item)
        data["edited_files"] = edited[:64]

    if tool_name == "Bash" and isinstance(tool_input, dict):
        command = tool_input.get("command")
        if isinstance(command, str) and VERIFY_RE.search(command):
            data["verification_seen"] = True
            commands = list(data.get("verification_commands") or [])
            commands.append(command[:300])
            data["verification_commands"] = commands[-8:]

    save(path, data)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
