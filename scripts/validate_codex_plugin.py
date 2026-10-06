#!/usr/bin/env python3
"""Install the local marketplace into an isolated Codex home without inference."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def native_cli(executable: str) -> Path | None:
    located = shutil.which(executable)
    if not located:
        return None
    path = Path(located).resolve()
    if os.name != "nt" or path.suffix.lower() not in {".cmd", ".bat"}:
        return path
    # Avoid cmd.exe quoting entirely for npm's Windows launcher.
    for node_modules in (path.parent / "node_modules", path.parent.parent):
        for package in ("codex-win32-x64", "codex-win32-arm64", "codex"):
            vendor = node_modules / "@openai" / package / "vendor"
            if vendor.is_dir():
                matches = list(vendor.rglob("codex.exe"))
                if len(matches) == 1:
                    return matches[0]
    return None


def validate(executable: str, root: Path) -> dict:
    binary = native_cli(executable)
    if not binary:
        return {"passed": False, "error": "Pass --codex with a native Codex executable"}
    report = {"passed": False, "inference_run": False, "checks": []}
    expected = json.loads((root / "plugins/high-agency/.codex-plugin/plugin.json").read_text())["version"]
    # Some Codex builds intentionally refuse to create helper aliases below /tmp.
    # This private temporary home remains outside the repository and is removed.
    with tempfile.TemporaryDirectory(prefix="high-agency-codex-cli-", dir=root.parent) as temporary:
        home = Path(temporary)
        env = {"HOME": str(home), "PATH": os.environ.get("PATH", os.defpath),
               "LANG": "C.UTF-8", "TERM": "dumb", "NO_COLOR": "1"}
        if os.name == "nt":
            for name in ("SystemRoot", "WINDIR", "COMSPEC", "PATHEXT", "ProgramFiles", "ProgramFiles(x86)"):
                if name in os.environ:
                    env[name] = os.environ[name]
            env.update({"USERPROFILE": str(home), "APPDATA": str(home / "appdata"),
                        "LOCALAPPDATA": str(home / "localappdata")})

        def run(name: str, command: list[str]) -> dict | None:
            try:
                process = subprocess.run(command, cwd=home, env=env,
                                         stdin=subprocess.DEVNULL, capture_output=True,
                                         text=True, encoding="utf-8", errors="replace", timeout=30)
                item = {"name": name, "exit_code": process.returncode,
                        "stdout": process.stdout[-8000:], "stderr": process.stderr[-4000:]}
                report["checks"].append(item)
                if process.returncode:
                    return None
                if name == "version":
                    return {"version": process.stdout.strip()}
                return json.loads(process.stdout)
            except (OSError, subprocess.TimeoutExpired, ValueError) as error:
                report["checks"].append({"name": name, "error": type(error).__name__})
                return None

        version = run("version", [str(binary), "--version"])
        if version is None:
            return report
        report["cli_version"] = version["version"]
        marketplace = run("marketplace", [str(binary), "plugin", "marketplace", "add", str(root), "--json"])
        if not marketplace or marketplace.get("marketplaceName") != "high-agency":
            return report
        installed = run("install", [str(binary), "plugin", "add", "high-agency@high-agency", "--json"])
        if not installed or installed.get("version") != expected:
            return report
        listing = run("list", [str(binary), "plugin", "list", "--marketplace", "high-agency", "--json"])
        if not listing:
            return report
        report["installed"] = any(
            item.get("pluginId") == "high-agency@high-agency"
            and item.get("version") == expected and item.get("enabled") is True
            for item in listing.get("installed", []) if isinstance(item, dict)
        )
        helper = root / "plugins/high-agency/scripts/model_catalog.py"
        catalog = run("catalog", [sys.executable, str(helper), "--codex-bin", str(binary), "--timeout", "8"])
        if catalog is None:
            return report
        report["catalog_query_status"] = catalog.get("query_status")
        report["catalog_selection_status"] = catalog.get("selection_status")
        report["catalog_freshness_status"] = catalog.get("freshness_status")
        report["passed"] = report["installed"] and catalog.get("query_status") == "succeeded"
        report["scope"] = "local marketplace installation and metadata-only catalog query; hook trust and inference not exercised"
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codex", default="codex")
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    result = validate(arguments.codex, Path(__file__).resolve().parents[1])
    output = json.dumps(result, indent=2) + "\n"
    if arguments.output:
        arguments.output.write_text(output, encoding="utf-8")
    print(output, end="")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
