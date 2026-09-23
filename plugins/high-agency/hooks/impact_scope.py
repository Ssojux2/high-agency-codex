#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import re
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
    files = max(1, int(match.group(2)))
    modules = max(1, int(match.group(3)))
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


def _assistant_texts(node):
    if isinstance(node, dict):
        if str(node.get("role") or "").lower() == "assistant":
            text = _content_text(node.get("content"))
            if text:
                yield text
        message = node.get("message")
        if isinstance(message, dict) and str(message.get("role") or "").lower() == "assistant":
            text = _content_text(message.get("content"))
            if text:
                yield text
        for key, value in node.items():
            if key != "message":
                yield from _assistant_texts(value)
    elif isinstance(node, list):
        for item in node:
            yield from _assistant_texts(item)


def first_impact_from_transcript(raw_path) -> dict | None:
    if not isinstance(raw_path, str) or not raw_path:
        return None
    path = Path(raw_path)
    try:
        with path.open("rb") as handle:
            data = handle.read(MAX_TRANSCRIPT_BYTES)
    except OSError:
        return None

    text = data.decode("utf-8", "replace")
    for line in text.splitlines():
        try:
            entry = json.loads(line)
        except Exception:
            continue
        for assistant_text in _assistant_texts(entry):
            estimate = parse_impact(assistant_text)
            if estimate:
                return estimate
    return None


def module_key(raw: str) -> str:
    value = raw.replace("\\", "/").lstrip("./")
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
