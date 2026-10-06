"""Execute configured hook launchers with synthetic payloads on the actual OS.

This tests the checked-in command/args and shell quoting contracts, including a
plugin path containing spaces and shell metacharacters. It does not start either
agent host, exercise plugin trust, invoke a model, or prove host event delivery.
The separate CI CLI-loading checks cover registration.

Claude exec form:
https://code.claude.com/docs/en/hooks#command-hook-fields
Codex selected-shell execution and discovery substitution, pinned reference:
https://github.com/openai/codex/blob/rust-v0.160.1/codex-rs/hooks/src/engine/command_runner.rs
https://github.com/openai/codex/blob/rust-v0.160.1/codex-rs/hooks/src/discovery.rs
https://github.com/openai/codex/blob/rust-v0.160.1/codex-rs/core/src/shell.rs
"""
import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


class ConfiguredHookLaunchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="high-agency-launch-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.plugin = self.base / "플러그인 cache with spaces & $HA_TEST_NAME %PATH% ! `"
        shutil.copytree(
            ROOT / "plugins/high-agency", self.plugin,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
        self.config = json.loads((self.plugin / "hooks/hooks.json").read_text(encoding="utf-8"))
        self.home = self.base / "isolated home"
        self.temp_root = self.base / "temporary state"
        self.plugin_data = self.base / "plugin data"
        self.repo = self.base / "작업 tree with spaces"
        self.empty_template = self.base / "empty git template"
        for directory in (self.home, self.temp_root, self.plugin_data, self.repo, self.empty_template):
            directory.mkdir()
        self.transcript = self.base / "transcript.jsonl"
        self.transcript.write_text("", encoding="utf-8")
        self.source_env = {
            "PLUGIN_ROOT": str(self.plugin),
            "PLUGIN_DATA": str(self.plugin_data),
            "CLAUDE_PLUGIN_ROOT": str(self.plugin),
            "CLAUDE_PLUGIN_DATA": str(self.plugin_data),
        }
        # Only child processes receive the isolated home/configuration.
        self.env = {
            **os.environ, **self.source_env,
            "HOME": str(self.home), "USERPROFILE": str(self.home),
            "XDG_CONFIG_HOME": str(self.home / "config"),
            "TMPDIR": str(self.temp_root), "TEMP": str(self.temp_root), "TMP": str(self.temp_root),
            "GIT_CONFIG_GLOBAL": str(self.home / "empty.gitconfig"),
            "GIT_CONFIG_NOSYSTEM": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "HA_TEST_NAME": "this value must not replace the literal folder name",
        }
        for name in (
            "HIGH_AGENCY_HOOK_DEBUG", "GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR",
            "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES",
        ):
            self.env.pop(name, None)
        (self.home / "empty.gitconfig").write_text("", encoding="utf-8")
        self.git("init", "-q", "--template=" + str(self.empty_template))
        self.git("config", "user.email", "test@example.com")
        self.git("config", "user.name", "High Agency Launch Test")
        (self.repo / "fixture.py").write_text("value = 1\n", encoding="utf-8")
        # A -c launcher must not import project code through implicit cwd when
        # runpy imports pkgutil. Direct script execution never did this.
        (self.repo / "pkgutil.py").write_text(
            "raise RuntimeError('launcher imported project-local pkgutil.py')\n",
            encoding="utf-8",
        )
        self.git("add", ".")
        self.git("commit", "-qm", "launcher fixture")

        # Use the copied plugin's public state API; only its storage root is
        # patched for this test process, since child tempfile configuration is
        # deliberately independent of Python's already-cached parent tempdir.
        spec = importlib.util.spec_from_file_location(
            "high_agency_launch_fixture_store", self.plugin / "hooks/state_store.py"
        )
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        self.store = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.store)
        self.host = self.store.HOST_KIND

    def git(self, *args):
        result = subprocess.run(
            ["git", *args], cwd=self.repo, env=self.env, text=True,
            capture_output=True, timeout=15, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def backends(self):
        if self.host == "claude":
            return [("exec", None)]
        if os.name == "nt":
            powershell = shutil.which("pwsh.exe") or shutil.which("powershell.exe")
            self.assertIsNotNone(powershell, "Native Windows launch coverage requires PowerShell")
            command_prompt = os.environ.get("COMSPEC") or shutil.which("cmd.exe")
            self.assertTrue(command_prompt, "Native Windows launch coverage requires cmd.exe")
            return [("powershell", powershell), ("cmd", command_prompt)]
        shell = os.environ.get("SHELL") or "/bin/sh"
        self.assertTrue(Path(shell).is_file(), "The configured POSIX shell must exist")
        return [("posix", shell)]

    def payload(self, backend, event):
        return {
            "hook_event_name": event,
            "session_id": "launcher-" + backend,
            "turn_id": "launcher-turn-" + backend,
            "prompt_id": "launcher-prompt-" + backend,
            "cwd": str(self.repo),
            "transcript_path": str(self.transcript),
        }

    def render(self, value):
        # Codex discovery replaces source.env placeholders before shell dispatch;
        # Claude exec form substitutes each argument as a plain string.
        for key, replacement in self.source_env.items():
            value = value.replace("$" + "{" + key + "}", replacement)
        return value

    def dispatch(self, backend, program, event, payload):
        hooks = [
            hook
            for group in self.config["hooks"][event]
            for hook in group["hooks"]
            if hook["type"] == "command"
        ]
        self.assertEqual(len(hooks), 1, "Update this fixture if the event gains another command hook")
        hook = hooks[0]
        kwargs = {}
        if self.host == "claude":
            self.assertEqual(backend, "exec")
            self.assertIsInstance(hook.get("args"), list)
            # Do not replace the configured interpreter with sys.executable:
            # this must prove that the documented 'python' PATH entry works.
            command = [self.render(hook["command"]), *(self.render(arg) for arg in hook["args"])]
            self.assertIsNotNone(
                shutil.which(command[0], path=self.env.get("PATH")),
                "Configured hook interpreter is missing from PATH",
            )
        else:
            field = "commandWindows" if os.name == "nt" else "command"
            command_line = self.render(hook[field])
            if backend == "cmd":
                # The Codex runner uses raw_arg around the command for /c.
                # A Python argv list would apply CRT quoting to this last
                # argument, which is a different contract from cmd parsing.
                command = subprocess.list2cmdline([program, "/c"]) + ' "' + command_line + '"'
                kwargs["executable"] = program
            elif backend == "powershell":
                command = [program, "-NoProfile", "-Command", command_line]
            else:
                # The current TurnEnvironment supplies derive_exec_args(false):
                # a non-login -c, not the runner's no-shell-supplied -lc fallback.
                command = [program, "-c", command_line]
        result = subprocess.run(
            command, input=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            cwd=self.repo, env=self.env, capture_output=True, shell=False,
            timeout=hook.get("timeout", 12) + 3, check=False, **kwargs,
        )
        self.assertEqual(
            result.returncode, 0,
            f"{self.host}/{backend} {event} launcher failed: {result.stderr.decode('utf-8', errors='replace')}",
        )
        self.assertEqual(result.stderr, b"")
        return json.loads(result.stdout) if result.stdout.strip() else {}

    def read_state(self, payload):
        directory = (
            self.temp_root / "high-agency-claude-code-verification"
            if self.host == "claude" else self.plugin_data / "verification"
        )
        with patch.object(self.store, "data_root", return_value=directory):
            state_path = self.store.verification_path(payload)
            self.assertTrue(state_path.is_file(), "The configured launcher did not create hook state")
            return self.store.load_state(payload)

    def test_configured_user_prompt_launcher_creates_active_v2_state(self):
        for backend, program in self.backends():
            with self.subTest(host=self.host, backend=backend):
                payload = {
                    **self.payload(backend, "UserPromptSubmit"),
                    "prompt": "Use high-agency-coding for this fixture",
                }
                self.assertEqual(self.dispatch(backend, program, "UserPromptSubmit", payload), {})
                state = self.read_state(payload)
                self.assertEqual(state["schema_version"], 2)
                self.assertTrue(state["active"])
                self.assertEqual(state["session_id"], payload["session_id"])
                self.assertIn(payload["prompt_id"], state["prompt_ids"])
                self.assertIn(payload["turn_id"], state["turn_ids"])
                self.assertEqual(Path(state["cwd"]), Path(os.path.normcase(str(self.repo))))
                self.assertTrue(state["baseline_snapshot"]["available"])

    def test_configured_stop_launcher_reads_task_state_and_returns_bounded_json(self):
        for backend, program in self.backends():
            with self.subTest(host=self.host, backend=backend):
                submit = {
                    **self.payload(backend, "UserPromptSubmit"),
                    "prompt": "Use bounded-autonomy for this fixture",
                }
                self.dispatch(backend, program, "UserPromptSubmit", submit)
                original = self.read_state(submit)
                stop = {
                    **self.payload(backend, "Stop"),
                    "last_assistant_message": "<!-- high-agency:continue max=1 -->",
                    "stop_hook_active": False,
                }
                response = self.dispatch(backend, program, "Stop", stop)
                self.assertEqual(response["decision"], "block")
                self.assertIn("1/1", response["reason"])
                current = self.read_state(stop)
                self.assertEqual(current["task_id"], original["task_id"])
                self.assertEqual(current["continuation"]["continuations"], 1)
                self.assertTrue(current["continuing_stop"])
                stop["stop_hook_active"] = True
                self.assertEqual(self.dispatch(backend, program, "Stop", stop), {})
                self.assertEqual(self.read_state(stop)["completion_reason"], "budget_exhausted")


if __name__ == "__main__":
    unittest.main()
