#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import os
import stat
import subprocess
import time
from pathlib import Path

MAX_PATHS = 512
GIT_TIMEOUT = 1.0
HASH_CHUNK = 1024 * 1024
MAX_FILE_BYTES = 64 * 1024 * 1024
MAX_SNAPSHOT_BYTES = 128 * 1024 * 1024
FILE_HASH_TIMEOUT = 0.5
SNAPSHOT_TIMEOUT = 1.5


class SnapshotError(Exception):
    """An incomplete Git read, with any paths already discovered."""

    def __init__(self, reason: str, paths=()):
        super().__init__(reason)
        self.reason = reason
        self.paths = sorted(set(paths))


def _run(cwd: Path, args: list[str], *, deadline: float | None = None) -> subprocess.CompletedProcess:
    timeout = GIT_TIMEOUT if deadline is None else min(GIT_TIMEOUT, deadline - time.monotonic())
    if timeout <= 0:
        raise subprocess.TimeoutExpired("git", 0)
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        text=False,
        capture_output=True,
        timeout=timeout,
        check=False,
    )


def _decode_z(data: bytes) -> list[str]:
    if data and not data.endswith(b"\0"):
        raise ValueError("incomplete NUL-delimited Git output")
    return [
        part.decode("utf-8", "surrogateescape")
        for part in data.split(b"\0")
        if part
    ]


def repo_root(cwd: Path, *, deadline: float | None = None) -> Path | None:
    try:
        cp = _run(cwd, ["rev-parse", "--show-toplevel"], deadline=deadline)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if cp.returncode != 0:
        return None
    try:
        value = cp.stdout.decode("utf-8", "surrogateescape").rstrip("\r\n")
        return Path(value).resolve() if value else None
    except Exception:
        return None


def head_ref(root: Path, *, deadline: float | None = None) -> str | None:
    try:
        cp = _run(root, ["rev-parse", "HEAD"], deadline=deadline)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if cp.returncode != 0:
        return None
    value = cp.stdout.decode("ascii", "ignore").strip()
    return value or None


def changed_paths(root: Path, base_ref: str, *, deadline: float | None = None) -> tuple[list[str], bool]:
    paths: set[str] = set()
    try:
        # Rename detection emits only destinations in --name-only output. Keep
        # both source deletions and destinations in the state fingerprint.
        tracked = _run(root, ["diff", "--no-renames", "--name-only", "-z", base_ref, "--"], deadline=deadline)
        if tracked.returncode != 0:
            raise SnapshotError("git_diff_failed", paths)
        paths.update(_decode_z(tracked.stdout))
        untracked = _run(root, ["ls-files", "--others", "--exclude-standard", "-z"], deadline=deadline)
        if untracked.returncode != 0:
            raise SnapshotError("git_untracked_failed", paths)
        paths.update(_decode_z(untracked.stdout))
    except subprocess.TimeoutExpired as exc:
        raise SnapshotError("git_timeout", paths) from exc
    except OSError as exc:
        raise SnapshotError("git_io_error", paths) from exc
    except ValueError as exc:
        raise SnapshotError("git_output_incomplete", paths) from exc

    ordered = sorted(paths)
    truncated = len(ordered) > MAX_PATHS
    return ordered[:MAX_PATHS], truncated


def _stat_identity(value: os.stat_result, *, change_time: bool = True) -> tuple:
    identity = (value.st_dev, value.st_ino, value.st_mode, value.st_size, value.st_mtime_ns)
    # Windows versions can report birth time via path stat and change time via
    # fstat. Compare ctime only within the same source, never path against fd.
    return identity + (value.st_ctime_ns,) if change_time else identity


def file_fingerprint(
    root: Path, relative: str, *, deadline: float | None = None, max_bytes: int | None = None,
) -> str:
    """Fingerprint the entry itself, including its mode, without following links.

    Missing is a known state. Read errors and a path changing during the read are
    explicitly incomplete evidence, never stable fingerprints.
    """
    path = root / relative
    before = None
    if max_bytes is not None and (type(max_bytes) is not int or max_bytes < 0):
        return "error:invalid_byte_limit"
    limit = MAX_FILE_BYTES if max_bytes is None else min(MAX_FILE_BYTES, max_bytes)
    if type(limit) is not int or limit < 0:
        return "error:invalid_byte_limit"
    own_deadline = time.monotonic() + FILE_HASH_TIMEOUT
    deadline = own_deadline if deadline is None else min(deadline, own_deadline)
    try:
        if time.monotonic() >= deadline:
            return "error:fingerprint_time_limit"
        before = path.lstat()
        if stat.S_ISLNK(before.st_mode):
            target = os.readlink(path)
            if _stat_identity(before) != _stat_identity(path.lstat()):
                return "error:path_changed_during_read"
            return f"symlink:{before.st_mode:o}:{target}"
        if not stat.S_ISREG(before.st_mode):
            # A directory/submodule or special device cannot be proved unchanged
            # by hashing metadata alone. Do not open a FIFO and hang the hook.
            return "error:unsupported_file_type"
        if before.st_size > limit:
            return "error:fingerprint_byte_limit"

        digest = hashlib.sha256()
        flags = (os.O_RDONLY | getattr(os, "O_BINARY", 0)
                 | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
        descriptor = os.open(path, flags)
        with os.fdopen(descriptor, "rb") as handle:
            opened = os.fstat(handle.fileno())
            if _stat_identity(before, change_time=False) != _stat_identity(opened, change_time=False):
                return "error:path_changed_during_read"
            consumed = 0
            while True:
                if time.monotonic() >= deadline:
                    return "error:fingerprint_time_limit"
                chunk = handle.read(HASH_CHUNK)
                if not chunk:
                    break
                consumed += len(chunk)
                if consumed > limit:
                    return "error:fingerprint_byte_limit"
                digest.update(chunk)
            if _stat_identity(opened) != _stat_identity(os.fstat(handle.fileno())):
                return "error:path_changed_during_read"
        if _stat_identity(before) != _stat_identity(path.lstat()):
            return "error:path_changed_during_read"
        return f"file:{before.st_mode:o}:sha256:{digest.hexdigest()}"
    except FileNotFoundError:
        # Only an entry already absent at the initial lstat is a known deletion.
        return "error:path_changed_during_read" if before is not None else "missing"
    except OSError as exc:
        return "error:" + type(exc).__name__


def fingerprint_complete(value) -> bool:
    return isinstance(value, str) and bool(value) and not value.startswith("error:")


def snapshot_complete(value: dict | None) -> bool:
    """Whether this snapshot can prove equality, including native edit evidence.

    Older complete snapshots have no `complete` field; retain compatibility only
    when their required identity and fingerprints are present and not truncated.
    """
    if (not isinstance(value, dict) or value.get("available") is not True
            or ("complete" in value and value["complete"] is not True) or value.get("truncated")
            or not isinstance(value.get("root"), str) or not value["root"]
            or not isinstance(value.get("base_ref"), str) or not value["base_ref"]
            or not isinstance(value.get("files"), dict) or value.get("error")):
        return False
    for field in ("files", "native_files"):
        files = value.get(field, {})
        if not isinstance(files, dict) or not all(fingerprint_complete(item) for item in files.values()):
            return False
    return True


def snapshot(cwd: str | Path, base_ref: str | None = None) -> dict:
    deadline = time.monotonic() + SNAPSHOT_TIMEOUT
    try:
        cwd_path = Path(cwd).resolve()
    except (OSError, RuntimeError, ValueError):
        return {"available": False, "complete": False, "error": "cwd_unavailable"}
    root = repo_root(cwd_path, deadline=deadline)
    if root is None:
        return {"available": False, "complete": False, "error": "repository_unavailable"}

    ref = base_ref or head_ref(root, deadline=deadline)
    if not ref:
        # Unborn repositories fall back to native edit tracking.
        return {"available": False, "complete": False, "root": str(root), "error": "head_unavailable"}

    error = None
    try:
        paths, truncated = changed_paths(root, ref, deadline=deadline)
    except SnapshotError as exc:
        paths, truncated = exc.paths[:MAX_PATHS], len(exc.paths) > MAX_PATHS
        error = exc.reason
    files = {}
    remaining = MAX_SNAPSHOT_BYTES
    for path in paths:
        try:
            info = (root / path).lstat()
            size = info.st_size if stat.S_ISREG(info.st_mode) else 0
        except OSError:
            size = 0  # file_fingerprint records the specific incomplete state.
        files[path] = file_fingerprint(root, path, deadline=deadline, max_bytes=remaining)
        remaining = max(0, remaining - size)
    if truncated:
        error = error or "path_limit_exceeded"
    if not all(fingerprint_complete(value) for value in files.values()):
        error = error or "fingerprint_incomplete"
    return {
        "available": error is None,
        "complete": error is None,
        "root": str(root),
        "base_ref": ref,
        "files": files,
        "truncated": truncated,
        **({"error": error} if error else {}),
    }


def delta_files(before: dict | None, after: dict | None) -> list[str]:
    if not snapshot_complete(before) or not snapshot_complete(after):
        return []
    if before.get("root") != after.get("root") or before.get("base_ref") != after.get("base_ref"):
        return []

    left = before.get("files") or {}
    right = after.get("files") or {}
    return sorted(
        path
        for path in set(left) | set(right)
        if left.get(path) != right.get(path)
    )


def snapshots_equal(left: dict | None, right: dict | None) -> bool:
    if not snapshot_complete(left) or not snapshot_complete(right):
        return False
    return (
        left.get("root") == right.get("root")
        and left.get("base_ref") == right.get("base_ref")
        and left.get("files") == right.get("files")
        and left.get("native_files", {}) == right.get("native_files", {})
    )
