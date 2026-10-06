#!/usr/bin/env python3
"""Small, process-safe JSON state store for advisory hook state."""
from __future__ import annotations

import hashlib
import json
import os
import stat
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

HOST_KIND = "codex"
LOCK_TIMEOUT_SECONDS = 3.0
MAX_STATE_BYTES = 4 * 1024 * 1024


def data_root() -> Path:
    if HOST_KIND == "claude":
        return Path(tempfile.gettempdir()) / "high-agency-claude-code-verification"
    return Path(os.environ.get("PLUGIN_DATA") or ".").resolve() / "verification"


def identity_key(payload: dict) -> str:
    identity = payload.get("session_id") or payload.get("transcript_path") or payload.get("turn_id")
    if not isinstance(identity, str) or not identity:
        raise ValueError("Hook state needs a session, turn, or transcript identity")
    agent = payload.get("agent_id")
    return json.dumps([identity, agent if isinstance(agent, str) else ""], separators=(",", ":"))


def verification_path(payload: dict) -> Path:
    digest = hashlib.sha256(identity_key(payload).encode("utf-8", "surrogatepass")).hexdigest()[:32]
    return data_root() / (digest + ".json")


def load_json(path: Path, *, strict: bool = False) -> dict:
    try:
        path = Path(path)
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_STATE_BYTES:
            raise ValueError("Hook state must be a bounded regular file")
        flags = os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path, flags)
        with os.fdopen(descriptor, "rb") as handle:
            opened = os.fstat(handle.fileno())
            if not stat.S_ISREG(opened.st_mode) or opened.st_size > MAX_STATE_BYTES:
                raise ValueError("Hook state must be a bounded regular file")
            raw = handle.read(MAX_STATE_BYTES + 1)
        if len(raw) > MAX_STATE_BYTES:
            raise ValueError("Hook state size exceeded limit")
        value = json.loads(raw.decode("utf-8"))
        if not isinstance(value, dict):
            raise ValueError("Hook state must be a JSON object")
        return value
    except FileNotFoundError:
        return {}
    except (OSError, ValueError, TypeError) as exc:
        if strict:
            raise ValueError("Hook state cannot be read safely") from exc
        return {}


def atomic_json_write(path: Path, data: dict) -> None:
    path = Path(path)
    encoded = json.dumps(data, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    if len(encoded) > MAX_STATE_BYTES:
        raise ValueError("Hook state size exceeded limit")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, raw_temp = tempfile.mkstemp(prefix="." + path.name + ".", suffix=".tmp", dir=path.parent)
    temporary = Path(raw_temp)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


@contextmanager
def locked_json(path: Path, *, recover: bool = False):
    """Lock the complete read/modify/write transaction, including absent files."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_suffix(path.suffix + ".lock")
    try:
        if not stat.S_ISREG(lock_path.lstat().st_mode):
            raise ValueError("Hook lock must be a regular file")
    except FileNotFoundError:
        pass
    descriptor = os.open(str(lock_path), os.O_CREAT | os.O_RDWR | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_NOFOLLOW", 0), 0o600)
    if not stat.S_ISREG(os.fstat(descriptor).st_mode):
        os.close(descriptor)
        raise ValueError("Hook lock must be a regular file")
    handle = os.fdopen(descriptor, "r+b")
    acquired = False
    unlock = None
    try:
        deadline = time.monotonic() + LOCK_TIMEOUT_SECONDS
        if os.name == "nt":
            import msvcrt
            # Windows permits locking a range beyond EOF. Never read or
            # initialize byte zero before acquiring it: another process's
            # byte-range lock denies reads and writes as well as other locks.
            def acquire():
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            def release():
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            def acquire():
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            def release():
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        unlock = release
        while not acquired:
            try:
                acquire()
                acquired = True
            except (BlockingIOError, OSError):
                if time.monotonic() >= deadline:
                    raise TimeoutError("Hook state lock timed out")
                time.sleep(0.025)
        try:
            data = load_json(path, strict=True)
        except ValueError:
            if not recover:
                raise
            data = {"state_recovered": True}
        original = json.dumps(data, sort_keys=True, separators=(",", ":"))
        yield data
        if json.dumps(data, sort_keys=True, separators=(",", ":")) != original:
            atomic_json_write(path, data)
    finally:
        if acquired and unlock is not None:
            unlock()
        handle.close()


def load_state(payload: dict) -> dict:
    return load_json(verification_path(payload))


def state_transaction(payload: dict, *, recover: bool = False):
    return locked_json(verification_path(payload), recover=recover)
