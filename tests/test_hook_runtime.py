import json
import os
import subprocess
import tempfile
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOKS = ROOT / "plugins/high-agency/hooks"
VERIFY_HOOK = HOOKS / "verification_state.py"
STOP_HOOK = HOOKS / "stop_loop.py"


def run_hook(script: Path, payload, *, cwd: Path, plugin_data: Path):
    env = dict(os.environ)
    env["PLUGIN_DATA"] = str(plugin_data)
    return subprocess.run(
        ["python3", str(script)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        cwd=cwd,
        env=env,
        timeout=5,
        check=False,
    )


class CodexHookRuntimeTests(unittest.TestCase):
    def make_repo(self):
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True)
        subprocess.run(["git", "config", "user.name", "High Agency Test"], cwd=root, check=True)
        (root / "app.py").write_text("value = 1\n", encoding="utf-8")
        subprocess.run(["git", "add", "app.py"], cwd=root, check=True)
        subprocess.run(["git", "commit", "-qm", "initial"], cwd=root, check=True)
        return temp, root

    def test_inactive_bash_post_tool_use_is_silent(self):
        with tempfile.TemporaryDirectory() as state:
            payload = {
                "hook_event_name": "PostToolUse",
                "turn_id": "inactive-" + uuid.uuid4().hex,
                "cwd": str(ROOT),
                "tool_name": "Bash",
                "tool_input": {"command": "echo ok"},
            }
            result = run_hook(VERIFY_HOOK, payload, cwd=ROOT, plugin_data=Path(state))
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stderr, "")

    def test_active_prompt_then_bash_verification_is_silent(self):
        temp, root = self.make_repo()
        self.addCleanup(temp.cleanup)
        with tempfile.TemporaryDirectory() as state:
            turn_id = "active-" + uuid.uuid4().hex

            submit = run_hook(
                VERIFY_HOOK,
                {
                    "hook_event_name": "UserPromptSubmit",
                    "turn_id": turn_id,
                    "cwd": str(root),
                    "prompt": "$high-agency-coding fix this bug",
                },
                cwd=root,
                plugin_data=Path(state),
            )
            self.assertEqual(submit.returncode, 0)
            self.assertEqual(submit.stderr, "")

            post = run_hook(
                VERIFY_HOOK,
                {
                    "hook_event_name": "PostToolUse",
                    "turn_id": turn_id,
                    "cwd": str(root),
                    "tool_name": "Bash",
                    "tool_input": {"command": "python -m pytest tests/test_auth.py"},
                },
                cwd=root,
                plugin_data=Path(state),
            )
            self.assertEqual(post.returncode, 0)
            self.assertEqual(post.stderr, "")

    def test_malformed_verification_payload_fails_open(self):
        with tempfile.TemporaryDirectory() as state:
            env = dict(os.environ)
            env["PLUGIN_DATA"] = state
            result = subprocess.run(
                ["python3", str(VERIFY_HOOK)],
                input="{not-json",
                text=True,
                capture_output=True,
                cwd=ROOT,
                env=env,
                timeout=5,
                check=False,
            )
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stderr, "")

    def test_stop_hook_invalid_payload_fails_open(self):
        with tempfile.TemporaryDirectory() as state:
            env = dict(os.environ)
            env["PLUGIN_DATA"] = state
            result = subprocess.run(
                ["python3", str(STOP_HOOK)],
                input="{not-json",
                text=True,
                capture_output=True,
                cwd=ROOT,
                env=env,
                timeout=5,
                check=False,
            )
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stderr, "")

    def test_stop_hook_no_marker_is_silent(self):
        with tempfile.TemporaryDirectory() as state:
            payload = {
                "hook_event_name": "Stop",
                "turn_id": "stop-" + uuid.uuid4().hex,
                "cwd": str(ROOT),
                "last_assistant_message": "Task complete.",
            }
            result = run_hook(STOP_HOOK, payload, cwd=ROOT, plugin_data=Path(state))
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stderr, "")


if __name__ == "__main__":
    unittest.main()
