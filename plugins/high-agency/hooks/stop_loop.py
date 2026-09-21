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
DOC_EXTS = {".md", ".mdx", ".txt", ".rst", ".adoc", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico"}
DOC_NAMES = {"LICENSE", "README", "CHANGELOG", "CONTRIBUTING", "CODE_OF_CONDUCT"}

def emit(payload: dict) -> None:
    sys.stdout.write(json.dumps(payload, separators=(",", ":")) + "\n")

def data_root() -> Path:
    return Path(os.environ.get("PLUGIN_DATA") or ".").resolve()

def state_path(turn_id: str) -> Path:
    digest = hashlib.sha256(turn_id.encode("utf-8", "replace")).hexdigest()[:24]
    return data_root() / "bounded-autonomy" / f"{digest}.json"

def verification_path(payload: dict) -> Path:
    raw = str(payload.get("turn_id") or payload.get("session_id") or "default")
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", raw)[:120]
    return data_root() / "verification" / f"{safe}.json"

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

def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
    tmp.replace(path)

def clear(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass

def needs_verification(files: list[str]) -> bool:
    for raw in files:
        name = Path(raw).name
        if name.upper() in DOC_NAMES or name.startswith("README"):
            continue
        if Path(raw).suffix.lower() in DOC_EXTS:
            continue
        return True
    return False

def reset_pass(vpath: Path, data: dict) -> None:
    if not data.get("active"):
        return
    data["edited_files"] = []
    data["verification_seen"] = False
    data["verification_commands"] = []
    data["guard_warned"] = False
    save_json(vpath, data)

def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        emit({})
        return 0

    turn_id = str(payload.get("turn_id") or "")
    message = payload.get("last_assistant_message")
    if not turn_id or not isinstance(message, str):
        emit({})
        return 0

    cleanup_old_states(data_root() / "bounded-autonomy")
    cleanup_old_states(data_root() / "verification")

    bpath = state_path(turn_id)
    vpath = verification_path(payload)
    vdata = load_json(vpath)
    marker = MARKER_RE.search(message)

    edited_files = list(vdata.get("edited_files") or [])
    if (
        vdata.get("active")
        and needs_verification(edited_files)
        and not vdata.get("verification_seen")
        and not vdata.get("guard_warned")
    ):
        vdata["guard_warned"] = True
        save_json(vpath, vdata)
        suffix = ""
        if marker:
            requested = int(marker.group(1)) if marker.group(1) else DEFAULT_MAX
            limit = min(max(requested, 1), HARD_CAP)
            suffix = (
                f" If meaningful work still remains after verification, preserve the bounded-autonomy "
                f"contract and end with <!-- high-agency:continue max={limit} -->."
            )
        emit({
            "decision": "block",
            "reason": (
                "High Agency verification guard: code/config edits were detected but no verification "
                "command was observed in this pass. Run the narrowest relevant verification for the "
                "touched or affected scope first. Prefer related/affected tests, package/module checks, "
                "or a focused runtime probe. Do not run the full suite unless dependency or integration "
                "risk justifies it." + suffix
            )
        })
        return 0

    if not marker:
        clear(bpath)
        clear(vpath)
        emit({})
        return 0

    requested = int(marker.group(1)) if marker.group(1) else DEFAULT_MAX
    limit = min(max(requested, 1), HARD_CAP)
    bdata = load_json(bpath)
    count = max(0, int(bdata.get("continuations", 0)))

    if count >= limit:
        clear(bpath)
        clear(vpath)
        emit({})
        return 0

    count += 1
    save_json(bpath, {"continuations": count, "limit": limit, "updated_at": int(time.time())})
    reset_pass(vpath, vdata)

    if count == limit:
        reason = (
            f"Final bounded-autonomy continuation {count}/{limit}. Continue the same task from the "
            "current repository state. Make the highest-value remaining progress using an independently "
            "verifiable step. Verify the touched or affected scope first and broaden only if risk requires "
            "it. Do not weaken verification and do not emit another high-agency continuation marker. "
            "Finish by reporting what is verified, what remains incomplete, or what is blocked."
        )
    else:
        reason = (
            f"Bounded-autonomy continuation {count}/{limit}. Continue the same task from the current "
            "repository state. Work on the highest-value unresolved acceptance criterion using an "
            "independently verifiable step. Verify the touched or affected scope first; broaden only for "
            "dependency or integration risk. Request another continuation only if this pass produces "
            "meaningful new progress and more actionable work remains. If so, end with exactly "
            f"<!-- high-agency:continue max={limit} -->. Otherwise finish without a marker."
        )

    emit({"decision": "block", "reason": reason})
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
