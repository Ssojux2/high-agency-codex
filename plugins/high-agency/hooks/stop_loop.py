#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

from git_state import delta_files, snapshot, snapshots_equal

MARKER_RE = re.compile(
    r"<!--\s*high-agency:continue(?:\s+max=(\d+))?\s*-->\s*$",
    re.IGNORECASE | re.DOTALL,
)
DEFAULT_MAX = 3
HARD_CAP = 12
STATE_TTL_SECONDS = 7 * 24 * 60 * 60
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


def data_root() -> Path:
    return Path(os.environ.get("PLUGIN_DATA") or ".").resolve()


def bounded_path(turn_id: str) -> Path:
    digest = hashlib.sha256(turn_id.encode("utf-8", "replace")).hexdigest()[:24]
    return data_root() / "bounded-autonomy" / f"{digest}.json"


def verification_path(payload: dict) -> Path:
    raw = str(payload.get("turn_id") or payload.get("session_id") or "default")
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", raw)[:120]
    return data_root() / "verification" / f"{safe}.json"


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


def clear(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def cleanup(directory: Path) -> None:
    if not directory.exists():
        return
    cutoff = time.time() - STATE_TTL_SECONDS
    for path in directory.glob("*.json"):
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink(missing_ok=True)
        except OSError:
            pass


def code_files(files: list[str]) -> list[str]:
    result = []
    for raw in files:
        path = Path(raw)
        name = path.name
        if name.upper() in DOC_NAMES or name.startswith("README"):
            continue
        if path.suffix.lower() in DOC_EXTS:
            continue
        result.append(raw)
    return result


def rel(raw: str, cwd: Path) -> str:
    path = Path(raw)
    try:
        if path.is_absolute():
            return path.resolve().relative_to(cwd.resolve()).as_posix()
    except Exception:
        pass
    return path.as_posix().lstrip("./")


def current_snapshot(vdata: dict, cwd: Path) -> dict:
    baseline = vdata.get("baseline_snapshot") or {}
    base_ref = baseline.get("base_ref") if baseline.get("available") else None
    return snapshot(cwd, base_ref=base_ref)


def task_files(vdata: dict, current: dict) -> list[str]:
    baseline = vdata.get("baseline_snapshot") or {}
    files = delta_files(baseline, current)
    if files:
        return files
    if not baseline.get("available") or not current.get("available"):
        return list(vdata.get("all_edited_files") or [])
    return []


def git_stats(cwd: Path, files: list[str], base_ref: str | None) -> tuple[int, str]:
    if not files or not base_ref:
        return 0, ""
    try:
        numstat = subprocess.run(
            ["git", "diff", "--numstat", base_ref, "--", *files],
            cwd=cwd,
            text=True,
            capture_output=True,
            timeout=0.8,
            check=False,
        )
        total = 0
        if numstat.returncode == 0:
            for line in numstat.stdout.splitlines():
                parts = line.split("\t")
                if len(parts) >= 2:
                    add, delete = parts[0], parts[1]
                    if add.isdigit():
                        total += int(add)
                    if delete.isdigit():
                        total += int(delete)

        check = subprocess.run(
            ["git", "diff", "--check", base_ref, "--", *files],
            cwd=cwd,
            text=True,
            capture_output=True,
            timeout=0.8,
            check=False,
        )
        issue = (check.stdout + check.stderr).strip()[:1200] if check.returncode else ""
        return total, issue
    except Exception:
        return 0, ""


def diff_reasons(vdata: dict, current: dict, files: list[str], cwd: Path) -> tuple[list[str], list[str], str]:
    relevant = code_files(files)
    reasons = []
    if current.get("truncated"):
        reasons.append("changed-file snapshot exceeded tracking limit")
    if len(relevant) >= 3:
        reasons.append(f"{len(relevant)} code/config files changed")

    relative = [rel(path, cwd) for path in relevant]
    top_levels = {path.split("/")[0] if "/" in path else "." for path in relative}
    if len(relevant) >= 2 and len(top_levels) >= 2:
        reasons.append("change crosses module boundaries")
    if any(RISK_RE.search(path) for path in relative):
        reasons.append("high-impact/shared path changed")

    baseline = vdata.get("baseline_snapshot") or {}
    lines, check = git_stats(cwd, relevant, baseline.get("base_ref"))
    if lines >= LARGE_DIFF_LINES:
        reasons.append(f"large diff ({lines} changed lines)")
    return reasons, relevant, check


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        emit({})
        return 0

    turn_id = str(payload.get("turn_id") or "")
    message = payload.get("last_assistant_message")
    cwd = Path(payload.get("cwd") or ".").resolve()
    if not turn_id or not isinstance(message, str):
        emit({})
        return 0

    cleanup(data_root() / "bounded-autonomy")
    cleanup(data_root() / "verification")

    bpath = bounded_path(turn_id)
    vpath = verification_path(payload)
    vdata = load(vpath)
    marker = MARKER_RE.search(message)

    current = current_snapshot(vdata, cwd) if vdata.get("active") else {"available": False}
    changed = task_files(vdata, current)
    relevant = code_files(changed)

    verification = vdata.get("verification_snapshot")
    git_dirty_after_verify = (
        bool(relevant)
        and current.get("available")
        and not snapshots_equal(verification, current)
    )
    fallback_dirty = (
        bool(relevant)
        and not current.get("available")
        and bool(vdata.get("native_dirty"))
    )

    if (
        vdata.get("active")
        and (git_dirty_after_verify or fallback_dirty)
        and not vdata.get("verification_guard_warned")
    ):
        vdata["verification_guard_warned"] = True
        save(vpath, vdata)
        suffix = ""
        if marker:
            requested = int(marker.group(1)) if marker.group(1) else DEFAULT_MAX
            limit = min(max(requested, 1), HARD_CAP)
            suffix = (
                f" If more work remains after verification, preserve "
                f"<!-- high-agency:continue max={limit} -->."
            )
        emit(
            {
                "decision": "block",
                "reason": (
                    "High Agency verification guard: the Git working-tree snapshot changed after "
                    "the last valid verification (including changes made by shell scripts or generators). "
                    "Run the narrowest relevant targeted/affected check. Do not run the full suite unless "
                    "risk justifies it." + suffix
                ),
            }
        )
        return 0

    diff_valid = (
        current.get("available")
        and snapshots_equal(vdata.get("diff_snapshot"), current)
    )
    if (
        not marker
        and vdata.get("active")
        and not diff_valid
        and not vdata.get("diff_guard_warned")
    ):
        reasons, diff_files, check = diff_reasons(vdata, current, changed, cwd)
        if reasons:
            vdata["diff_guard_warned"] = True
            save(vpath, vdata)
            preview = ", ".join(rel(path, cwd) for path in diff_files[:8])
            extra = (" git diff --check also reported: " + check) if check else ""
            emit(
                {
                    "decision": "block",
                    "reason": (
                        "High Agency conditional diff review: "
                        + "; ".join(reasons)
                        + ". Inspect only the focused final diff for touched files ("
                        + preview
                        + "), confirm no unrelated changes/API drift, then finish. "
                        "Do not launch a reviewer subagent or broad branch review unless requested."
                        + extra
                    ),
                }
            )
            return 0

    if not marker:
        clear(bpath)
        clear(vpath)
        emit({})
        return 0

    requested = int(marker.group(1)) if marker.group(1) else DEFAULT_MAX
    limit = min(max(requested, 1), HARD_CAP)
    bdata = load(bpath)
    count = max(0, int(bdata.get("continuations", 0)))
    if count >= limit:
        clear(bpath)
        clear(vpath)
        emit({})
        return 0

    count += 1
    save(bpath, {"continuations": count, "limit": limit, "updated_at": int(time.time())})
    vdata["verification_guard_warned"] = False
    vdata["native_dirty"] = False
    save(vpath, vdata)

    if count == limit:
        reason = (
            f"Final bounded-autonomy continuation {count}/{limit}. Make the highest-value "
            "remaining progress, verify only the touched/affected scope unless risk requires "
            "broader checks, do not emit another continuation marker, and report the evidence "
            "or blocker."
        )
    else:
        reason = (
            f"Bounded-autonomy continuation {count}/{limit}. Continue from current repository "
            "state. Use an independently verifiable step and targeted/affected verification. "
            "Request another pass only after meaningful new progress; if needed end with "
            f"<!-- high-agency:continue max={limit} -->."
        )

    emit({"decision": "block", "reason": reason})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
