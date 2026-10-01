#!/usr/bin/env python3
"""Resolve role models from Codex's current model/list, never a bundled ID list.

Only initialize, initialized and model/list are sent. No inference, thread,
configuration writes, credential scraping, external SDK or persistent cache.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
from queue import Empty, Queue
import re
import subprocess
import sys
from threading import Thread
import time
from typing import Any

# Family preferences are policy; version numbers come exclusively from runtime.
ROLES = {
    "CHEAP DELEGATE": (("luna", "terra", "sol"), "low"),
    "BROAD MAP": (("sol", "terra"), "medium"),
    "WORKHORSE": (("sol",), "medium"),
    "STRONG REASONING": (("astra", "sol"), "high"),
}
EFFORTS = ("none", "minimal", "low", "medium", "high", "xhigh", "max")
MODEL = re.compile(r"^gpt-(\d+(?:\.\d+)*)-(luna|terra|sol|astra)(?:-(\d{4}-\d{2}-\d{2}))?$")


def models_from_page(page: Any) -> list[dict[str, Any]]:
    if not isinstance(page, dict) or not isinstance(page.get("data"), list):
        raise ValueError("invalid model/list response")
    return [item for item in page["data"] if isinstance(item, dict)]


def supported_effort(model: dict[str, Any], requested: str) -> str | None:
    """Never pass an effort absent from the runtime's advertised capabilities."""
    options = model.get("supportedReasoningEfforts", [])
    supported = [option.get("reasoningEffort") for option in options
                 if isinstance(option, dict) and isinstance(option.get("reasoningEffort"), str)] if isinstance(options, list) else []
    if requested in supported:
        return requested
    if requested in EFFORTS:
        lower = [value for value in EFFORTS[:EFFORTS.index(requested)] if value in supported]
        if lower:
            return lower[-1]
    default = model.get("defaultReasoningEffort")
    if isinstance(default, str) and default in supported:
        return default
    # An unfamiliar future effort is not guessed; omit the override instead.
    return next((value for value in EFFORTS if value in supported), None)


def resolve(models: list[dict[str, Any]], excluded: tuple[str, ...] = ()) -> dict[str, Any]:
    families: dict[str, list[tuple[Any, dict[str, Any]]]] = {}
    for item in models:
        name = item.get("model")
        if (not isinstance(name, str) or item.get("hidden") is True
                or item.get("available") is False or item.get("disabled") is True
                or item.get("preview") is True or item.get("deprecated") is True
                or name in excluded):
            continue
        match = MODEL.fullmatch(name)
        if not match:
            continue
        version = tuple(int(part) for part in match[1].split("."))
        # 6 and 6.0 compare as the same version, without lexicographic 6.9 > 6.10.
        while len(version) > 1 and version[-1] == 0:
            version = version[:-1]
        rank = (version, match[3] or "", item.get("isDefault") is True, name)
        families.setdefault(match[2], []).append((rank, item))
    latest = {family: max(items, key=lambda pair: pair[0])[1] for family, items in families.items()}
    routes = {}
    for route, (preferences, effort) in ROLES.items():
        family = next((candidate for candidate in preferences if candidate in latest), None)
        if family is None:
            routes[route] = {"model": None, "reasoning_effort": None, "fallback": "current main model"}
            continue
        item = latest[family]
        routes[route] = {
            "model": item["model"],
            "reasoning_effort": supported_effort(item, effort),
            "supported_reasoning_efforts": [entry["reasoningEffort"]
                for entry in (item.get("supportedReasoningEfforts") if isinstance(item.get("supportedReasoningEfforts"), list) else [])
                if isinstance(entry, dict) and isinstance(entry.get("reasoningEffort"), str)],
            "fallback": None if family == preferences[0] else f"preferred {preferences[0]} unavailable",
        }
    return routes


def read_live(command: list[str], timeout: float = 8.0) -> list[dict[str, Any]]:
    """Read every catalog page over stdio with one total time budget."""
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("timeout must be positive and finite")
    deadline = time.monotonic() + timeout
    proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, text=True, encoding="utf-8")
    inbox: Queue[Any] = Queue(maxsize=256)

    def receive() -> None:
        try:
            for line in proc.stdout:
                try:
                    inbox.put(json.loads(line), timeout=max(0.01, deadline - time.monotonic()))
                except json.JSONDecodeError:
                    continue
        except Exception:
            pass
        finally:
            try:
                inbox.put(None, timeout=0.1)
            except Exception:
                pass

    reader = Thread(target=receive, daemon=True)
    reader.start()

    def send(message: dict[str, Any]) -> None:
        proc.stdin.write(json.dumps(message) + "\n")
        proc.stdin.flush()

    def request(method: str, request_id: int, params: dict[str, Any]) -> dict[str, Any]:
        send({"method": method, "id": request_id, "params": params})
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("model catalog lookup timed out")
            try:
                message = inbox.get(timeout=remaining)
            except Empty as exc:
                raise TimeoutError("model catalog lookup timed out") from exc
            if message is None:
                raise ValueError("model catalog connection closed")
            if not isinstance(message, dict) or message.get("id") != request_id:
                continue
            if "error" in message:
                # Do not echo a server error that could contain configuration/secrets.
                raise ValueError("model catalog request rejected")
            result = message.get("result")
            if not isinstance(result, dict):
                raise ValueError("invalid model catalog result")
            return result

    try:
        request("initialize", 1, {"clientInfo": {"name": "high_agency_model_catalog", "version": "0.11.0"}})
        send({"method": "initialized", "params": {}})
        models, seen = [], set()
        cursor = None
        for request_id in range(2, 102):
            params = {"limit": 100, "includeHidden": False}
            if cursor is not None:
                params["cursor"] = cursor
            page = request("model/list", request_id, params)
            models.extend(models_from_page(page))
            cursor = page.get("nextCursor")
            if cursor is None:
                return models
            if not isinstance(cursor, str) or not cursor or cursor in seen:
                raise ValueError("invalid/repeated catalog cursor")
            seen.add(cursor)
        raise ValueError("model catalog page limit exceeded")
    finally:
        if proc.poll() is None:
            proc.terminate()
        try:
            proc.wait(timeout=1)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=1)
        reader.join(timeout=0.2)
        proc.stdin.close()
        proc.stdout.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", help="complete current model/list JSON; '-' reads stdin (no live lookup)")
    parser.add_argument("--codex-bin", default="codex")
    parser.add_argument("--exclude-model", action="append", default=[], help="exclude a rejected model ID for one refreshed fallback")
    parser.add_argument("--timeout", type=float, default=8.0)
    args = parser.parse_args()
    try:
        if args.catalog:
            text = sys.stdin.read() if args.catalog == "-" else Path(args.catalog).read_text(encoding="utf-8")
            page = json.loads(text)
            if isinstance(page, dict) and "result" in page:
                page = page["result"]
            models = models_from_page(page)
            if page.get("nextCursor") is not None:
                raise ValueError("incomplete catalog: fetch remaining pages")
        else:
            models = read_live([args.codex_bin, "app-server"], args.timeout)
        print(json.dumps({"source": "supplied model/list" if args.catalog else "codex app-server model/list",
                          "resolved_at": datetime.now(timezone.utc).isoformat(),
                          "freshness": "caller-supplied; not independently verified" if args.catalog else "runtime query",
                          "routes": resolve(models, tuple(args.exclude_model))}, indent=2))
        return 0
    except (OSError, ValueError, TimeoutError, subprocess.SubprocessError):
        print(json.dumps({"source": "unavailable", "routes": resolve([]),
                          "warning": "Catalog unavailable or incomplete; keep the current main model. Latest availability is unverified."}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
