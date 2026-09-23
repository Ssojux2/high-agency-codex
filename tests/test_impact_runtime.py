import json
import os
import subprocess
import tempfile
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOKS = ROOT / "plugins/high-agency/hooks"
VERIFY = HOOKS / "verification_state.py"
STOP = HOOKS / "stop_loop.py"


def run_hook(script, payload, *, cwd, plugin_data):
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


class CodexImpactRuntimeTests(unittest.TestCase):
    def test_major_scope_drift_blocks_once(self):
        with tempfile.TemporaryDirectory() as temp, tempfile.TemporaryDirectory() as state:
            root = Path(temp)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "High Agency Test"], cwd=root, check=True)
            (root / "src/auth").mkdir(parents=True)
            (root / "src/payments").mkdir(parents=True)
            (root / "src/auth/a.py").write_text("value = 1\n", encoding="utf-8")
            (root / "src/payments/b.py").write_text("value = 1\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=root, check=True)
            subprocess.run(["git", "commit", "-qm", "initial"], cwd=root, check=True)

            transcript = root / "transcript.jsonl"
            transcript.write_text(
                json.dumps({
                    "message": {
                        "role": "assistant",
                        "content": [{"type": "text", "text": "Impact: local | files<=1 | modules<=1 | boundary=private"}],
                    }
                }) + "\n",
                encoding="utf-8",
            )

            turn_id = "impact-" + uuid.uuid4().hex
            submit = run_hook(
                VERIFY,
                {
                    "hook_event_name": "UserPromptSubmit",
                    "turn_id": turn_id,
                    "cwd": str(root),
                    "prompt": "$high-agency-coding update both areas",
                    "transcript_path": str(transcript),
                },
                cwd=root,
                plugin_data=Path(state),
            )
            self.assertEqual(submit.returncode, 0)

            (root / "src/auth/a.py").write_text("value = 2\n", encoding="utf-8")
            (root / "src/payments/b.py").write_text("value = 2\n", encoding="utf-8")

            verify = run_hook(
                VERIFY,
                {
                    "hook_event_name": "PostToolUse",
                    "turn_id": turn_id,
                    "cwd": str(root),
                    "transcript_path": str(transcript),
                    "tool_name": "Bash",
                    "tool_input": {"command": "python -m pytest tests/test_scope.py"},
                },
                cwd=root,
                plugin_data=Path(state),
            )
            self.assertEqual(verify.returncode, 0)

            stop = run_hook(
                STOP,
                {
                    "hook_event_name": "Stop",
                    "turn_id": turn_id,
                    "cwd": str(root),
                    "transcript_path": str(transcript),
                    "last_assistant_message": "Done.",
                },
                cwd=root,
                plugin_data=Path(state),
            )
            self.assertEqual(stop.returncode, 0)
            result = json.loads(stop.stdout)
            self.assertEqual(result.get("decision"), "block")
            self.assertIn("impact calibration", result.get("reason", "").lower())
            self.assertIn("major scope drift", result.get("reason", "").lower())


if __name__ == "__main__":
    unittest.main()
