#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

MARKER_RE = re.compile(
    r"<!--\s*high-agency:continue(?:\s+max=(\d+))?\s*-->\s*$",
    re.IGNORECASE | re.DOTALL,
)
DEFAULT_MAX = 3
HARD_CAP = 12
STATE_TTL_SECONDS = 7 * 24 * 60 * 60

def emit(payload: dict) -> None:
    sys.stdout.write(json.dumps(payload, separators=(",", ":")) + "\n")

def state_path(plugin_data: Path, turn_id: str) -> Path:
    digest = hashlib.sha256(turn_id.encode("utf-8", "replace")).hexdigest()[:24]
    return plugin_data / "bounded-autonomy" / f"{digest}.json"

def cleanup_old_states(directory: Path) -> None:
    if not directory.exists():
        return
    cutoff = time.time() - STATE_TTL_SECONDS
    for path in directory.glob("*.json"):
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink(missing_ok=True)
        except OSError:
            pass

def load_count(path: Path) -> int:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return max(0, int(data.get("continuations", 0)))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return 0

def save_count(path: Path, count: int, limit: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(
            {"continuations": count, "limit": limit, "updated_at": int(time.time())},
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    tmp.replace(path)

def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError):
        emit({})
        return 0

    turn_id = str(payload.get("turn_id") or "")
    message = payload.get("last_assistant_message")
    if not turn_id or not isinstance(message, str):
        emit({})
        return 0

    plugin_data = Path(os.environ.get("PLUGIN_DATA") or ".").resolve()
    state_dir = plugin_data / "bounded-autonomy"
    cleanup_old_states(state_dir)
    path = state_path(plugin_data, turn_id)

    match = MARKER_RE.search(message)
    if not match:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
        emit({})
        return 0

    requested = int(match.group(1)) if match.group(1) else DEFAULT_MAX
    limit = min(max(requested, 1), HARD_CAP)
    count = load_count(path)

    if count >= limit:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
        emit({})
        return 0

    count += 1
    save_count(path, count, limit)

    reason = (
        f"Bounded-autonomy continuation {count}/{limit}. Continue the same task from the "
        "current repository state. Work on the highest-value unresolved acceptance criterion. "
        "Use fresh evidence, do not repeat an unchanged failed approach, and run relevant "
        "verification before stopping. If more actionable work remains, end with exactly "
        f"<!-- high-agency:continue max={limit} -->. If complete or blocked, finish without "
        "a continuation marker and report the evidence or blocker."
    )
    emit({"decision": "block", "reason": reason})
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
