#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path

MAX_PATHS = 512
GIT_TIMEOUT = 1.0
HASH_CHUNK = 1024 * 1024


def _run(cwd: Path, args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        text=False,
        capture_output=True,
        timeout=GIT_TIMEOUT,
        check=False,
    )


def _decode_z(data: bytes) -> list[str]:
    return [
        part.decode("utf-8", "surrogateescape")
        for part in data.split(b"\0")
        if part
    ]


def repo_root(cwd: Path) -> Path | None:
    try:
        cp = _run(cwd, ["rev-parse", "--show-toplevel"])
    except (OSError, subprocess.TimeoutExpired):
        return None
    if cp.returncode != 0:
        return None
    try:
        return Path(cp.stdout.decode("utf-8", "surrogateescape").strip()).resolve()
    except Exception:
        return None


def head_ref(root: Path) -> str | None:
    try:
        cp = _run(root, ["rev-parse", "HEAD"])
    except (OSError, subprocess.TimeoutExpired):
        return None
    if cp.returncode != 0:
        return None
    value = cp.stdout.decode("ascii", "ignore").strip()
    return value or None


def changed_paths(root: Path, base_ref: str) -> tuple[list[str], bool]:
    paths: set[str] = set()
    try:
        tracked = _run(root, ["diff", "--name-only", "-z", base_ref, "--"])
        if tracked.returncode == 0:
            paths.update(_decode_z(tracked.stdout))
        untracked = _run(root, ["ls-files", "--others", "--exclude-standard", "-z"])
        if untracked.returncode == 0:
            paths.update(_decode_z(untracked.stdout))
    except (OSError, subprocess.TimeoutExpired):
        return [], False

    ordered = sorted(paths)
    truncated = len(ordered) > MAX_PATHS
    return ordered[:MAX_PATHS], truncated


def file_fingerprint(root: Path, relative: str) -> str:
    path = root / relative
    try:
        if path.is_symlink():
            return "symlink:" + os.readlink(path)
        if not path.exists():
            return "missing"
        if not path.is_file():
            stat = path.stat()
            return f"other:{stat.st_mode}:{stat.st_size}:{stat.st_mtime_ns}"

        digest = hashlib.sha256()
        with path.open("rb") as handle:
            while True:
                chunk = handle.read(HASH_CHUNK)
                if not chunk:
                    break
                digest.update(chunk)
        return "sha256:" + digest.hexdigest()
    except OSError as exc:
        return "error:" + type(exc).__name__


def snapshot(cwd: str | Path, base_ref: str | None = None) -> dict:
    cwd_path = Path(cwd).resolve()
    root = repo_root(cwd_path)
    if root is None:
        return {"available": False}

    ref = base_ref or head_ref(root)
    if not ref:
        # Unborn repositories fall back to native edit tracking.
        return {"available": False, "root": str(root)}

    paths, truncated = changed_paths(root, ref)
    files = {path: file_fingerprint(root, path) for path in paths}
    return {
        "available": True,
        "root": str(root),
        "base_ref": ref,
        "files": files,
        "truncated": truncated,
    }


def delta_files(before: dict | None, after: dict | None) -> list[str]:
    if not before or not after:
        return []
    if not before.get("available") or not after.get("available"):
        return []
    if before.get("base_ref") != after.get("base_ref"):
        return []

    left = before.get("files") or {}
    right = after.get("files") or {}
    return sorted(
        path
        for path in set(left) | set(right)
        if left.get(path) != right.get(path)
    )


def snapshots_equal(left: dict | None, right: dict | None) -> bool:
    if not left or not right:
        return False
    if not left.get("available") or not right.get("available"):
        return False
    return (
        left.get("base_ref") == right.get("base_ref")
        and left.get("files") == right.get("files")
        and bool(left.get("truncated")) == bool(right.get("truncated"))
    )
