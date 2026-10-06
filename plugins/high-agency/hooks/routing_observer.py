#!/usr/bin/env python3
"""Observe native delegation metadata; never dispatch agents or query a provider.

Only allowlisted identity/model fields are persisted. Prompts, answers, errors,
credentials, transcript bodies and the common hook's parent model are ignored.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys

from state_store import HOST_KIND, data_root, identity_key, load_json, locked_json

MAX_RECORDS = 64
SAFE_VALUE = re.compile(r"^[A-Za-z0-9_.:/+\-]{1,160}$")
ROLE_NAMES = {"high-agency-" + name for name in
              ("scout", "verifier", "builder", "planner", "advisor", "deep-critic")}
EFFORTS = {"none", "minimal", "low", "medium", "high", "xhigh", "max", "ultra"}


def safe_value(value):
    return value if isinstance(value, str) and SAFE_VALUE.fullmatch(value) else None


def capabilities() -> dict:
    return {
        "request_observation": "supported",
        "dispatch_observation": "supported",
        "resolved_model_metadata": "conditional" if HOST_KIND == "claude" else "unsupported",
        "models_used_metadata": "conditional" if HOST_KIND == "claude" else "unsupported",
        "served_effort_metadata": "unsupported",
        "source": "documented native hook/tool contract; installed host not probed",
    }


def role_defaults(role: str | None) -> dict:
    """Read only our own scalar role defaults, never user settings or a path from input."""
    name = role.rsplit(":", 1)[-1] if role else ""
    if HOST_KIND != "claude" or name not in ROLE_NAMES:
        return {}
    try:
        text = (Path(__file__).resolve().parents[1] / "agents" / (name + ".md")).read_text(encoding="utf-8")
    except OSError:
        return {}
    match = re.match(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|$)", text, re.S)
    if not match:
        return {}
    return {key: value for key, value in re.findall(r"^(model|effort):\s*([A-Za-z0-9_.:/+\-]+)\s*$",
                                                   match[1], re.M)}


def response_object(value) -> dict:
    # Codex can expose its model-facing response as a JSON string. Do not search
    # content blocks or prose for metadata: that would trust an agent's answer.
    if HOST_KIND == "codex" and isinstance(value, str) and len(value) <= 65536:
        try:
            value = json.loads(value)
        except ValueError:
            return {}
    return value if isinstance(value, dict) else {}


def build_record(payload: dict) -> dict | None:
    if not isinstance(payload, dict):
        return None
    event, tool = payload.get("hook_event_name"), payload.get("tool_name")
    tools = {"Agent", "Task"} if HOST_KIND == "claude" else {"Agent", "spawn_agent"}
    if not isinstance(event, str) or not isinstance(tool, str):
        return None
    if event not in {"PostToolUse", "PostToolUseFailure"} or tool not in tools:
        return None
    args = payload.get("tool_input")
    args = args if isinstance(args, dict) else {}
    response = response_object(payload.get("tool_response"))
    failed = event == "PostToolUseFailure"
    role = safe_value(args.get("subagent_type") or args.get("agent_type"))
    defaults = role_defaults(role)
    requested = safe_value(args.get("model"))
    requested_source = "tool_input.model" if requested else "unverified"
    if not requested and safe_value(defaults.get("model")):
        requested, requested_source = defaults["model"], "bundled_role_frontmatter"
    effort = args.get("reasoning_effort") if HOST_KIND == "codex" else defaults.get("effort")
    effort = effort if isinstance(effort, str) and effort in EFFORTS else None
    effort_source = ("tool_input.reasoning_effort" if HOST_KIND == "codex" else "bundled_role_frontmatter") if effort else "unverified"

    resolved, used = None, []
    child_id = safe_value((response.get("agentId") or response.get("taskId")) if HOST_KIND == "claude"
                          else response.get("agent_id") or response.get("task_name"))
    status = "failed" if failed else "response_observed"
    if not failed and HOST_KIND == "claude":
        raw_status = response.get("status")
        if isinstance(raw_status, str) and raw_status in {"completed", "async_launched", "remote_launched"} and child_id:
            status = raw_status
        if status in {"completed", "async_launched"}:
            resolved = safe_value(response.get("resolvedModel"))
            raw_used = response.get("modelsUsed")
            if isinstance(raw_used, list):
                used = list(dict.fromkeys(value for value in raw_used[:32] if safe_value(value)))
    elif not failed and child_id:
        status = "launched"

    fallback = "unverified"
    if len(used) > 1:
        fallback = "multiple_models_observed"
    elif requested and resolved:
        if requested in {"haiku", "sonnet", "opus", "fable"}:
            same = bool(re.search(r"(?:^|[-.:/])" + re.escape(requested) + r"(?:[-.:/]|$)", resolved))
        else:
            same = requested == resolved
        fallback = "none_observed" if same else "model_difference_observed"

    return {
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "source": "native_hook.tool_input/tool_response",
        "tool": tool,
        "tool_use_id": safe_value(payload.get("tool_use_id")),
        "child_id": child_id,
        "requested": {"model": requested, "model_source": requested_source, "role": role,
                      "effort": effort, "effort_source": effort_source},
        "resolvedModel": resolved,
        "modelsUsed": used,
        "resolution_status": "host_reported" if resolved else "unverified",
        "served_model_status": "host_reported" if used else "unverified",
        "effort_status": "unverified",
        "dispatch_status": status,
        "fallback_status": fallback,
        "fallback_reason": None,
        "query_status": "not_observed",
        "freshness_status": "unverified",
        "entitlement_status": "observed_for_completed_dispatch" if status == "completed" and used else "unverified",
    }


def observation_path(payload: dict, directory: Path | None = None) -> Path:
    if directory is None:
        if HOST_KIND == "codex" and not os.environ.get("PLUGIN_DATA"):
            raise ValueError("PLUGIN_DATA is unavailable")
        directory = data_root() / "routing"
    digest = hashlib.sha256(identity_key(payload).encode("utf-8", "surrogatepass")).hexdigest()[:32]
    return directory / (digest + ".json")


def observe(payload: dict) -> None:
    record = build_record(payload)
    if record is None:
        return
    path = observation_path(payload)
    with locked_json(path) as state:
        records = state.get("records")
        records = records if isinstance(records, list) else []
        state.clear()
        state.update({"schema_version": 1, "host": HOST_KIND, "records": (records + [record])[-MAX_RECORDS:]})


def report(session_id: str | None = None, agent_id: str | None = None,
           directory: Path | None = None) -> dict:
    result = {"schema_version": 1, "host": HOST_KIND, "capabilities": capabilities(),
              "scope": "session" if session_id else "unspecified", "observation_status": "unverified", "records": []}
    if not session_id:
        result["warning"] = "Pass the current host's session ID to inspect its observations; no other session is selected automatically."
        return result
    try:
        state = load_json(observation_path({"session_id": session_id, "agent_id": agent_id}, directory))
    except ValueError:
        result["warning"] = "Plugin state location unavailable; pass its known routing directory with --state-dir."
        return result
    if state.get("host") == HOST_KIND and isinstance(state.get("records"), list):
        result["records"] = state["records"][-MAX_RECORDS:]
        if result["records"]:
            result["observation_status"] = "observed"
    if not result["records"]:
        result["warning"] = "No recorded native delegation for this session; hook trust or missing events remain unverified."
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", action="store_true", help="read only; report capabilities and an explicitly identified session")
    parser.add_argument("--session-id")
    parser.add_argument("--agent-id", help="parent subagent scope, if inspecting delegation from a child")
    parser.add_argument("--state-dir", type=Path, help="known routing-state directory for read-only reporting")
    args = parser.parse_args()
    if args.report:
        print(json.dumps(report(args.session_id, args.agent_id, args.state_dir), indent=2))
        return 0
    try:
        observe(json.load(getattr(sys.stdin, "buffer", sys.stdin)))
    except Exception:
        # Observation is advisory. Never interrupt an authorized tool or print
        # payloads/errors that might contain user content or credentials.
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
