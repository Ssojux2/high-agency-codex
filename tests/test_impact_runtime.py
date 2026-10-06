import json
import os
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
HOOKS = ROOT / "plugins/high-agency/hooks"
sys.path.insert(0, str(HOOKS))
import state_store  # noqa: E402

VERIFY = HOOKS / "verification_state.py"
STOP = HOOKS / "stop_loop.py"


class ImpactRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "repo"
        self.root.mkdir()
        self.state = self.base / "state"
        self.state.mkdir()
        self.transcript = self.state / "transcript.jsonl"
        self.transcript.write_text("", encoding="utf-8")
        self.env = {
            **os.environ, "TMPDIR": str(self.state), "TEMP": str(self.state),
            "TMP": str(self.state), "PLUGIN_DATA": str(self.state),
        }
        self.env.pop("HIGH_AGENCY_HOOK_DEBUG", None)
        identity = "impact-" + uuid.uuid4().hex
        self.common = {
            "cwd": str(self.root),
            "transcript_path": str(self.transcript),
            **({"session_id": identity, "prompt_id": "prompt-1"}
               if state_store.HOST_KIND == "claude" else {"turn_id": identity}),
        }
        self.git("init", "-q")
        self.git("config", "user.email", "test@example.com")
        self.git("config", "user.name", "High Agency Test")
        for path in ("src/auth/a.py", "src/payments/b.py", "src/view/c.py"):
            target = self.root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("value = 1\n", encoding="utf-8")
        self.git("add", ".")
        self.git("commit", "-qm", "initial")

    def git(self, *args):
        return subprocess.run(
            ["git", *args], cwd=self.root, text=True, capture_output=True, check=True
        )

    def run_hook(self, script, **payload):
        result = subprocess.run(
            [sys.executable, str(script)], input=json.dumps({**self.common, **payload}),
            text=True, capture_output=True, cwd=self.root, env=self.env,
            timeout=10, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        return json.loads(result.stdout) if result.stdout.strip() else {}

    def append(self, text):
        with self.transcript.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({
                "message": {"role": "assistant", "content": [{"type": "text", "text": text}]}
            }) + "\n")

    def submit(self, prompt="Use high-agency-coding to update both areas"):
        self.run_hook(VERIFY, hook_event_name="UserPromptSubmit", prompt=prompt)

    def verify(self, tool_id="scope-check"):
        tool = {
            "tool_name": "Bash", "tool_use_id": tool_id,
            "tool_input": {"command": "python -m pytest tests/test_scope.py"},
        }
        if state_store.HOST_KIND == "codex":
            # This fixture models an adapter that supplies structured completion
            # and execution cwd. Native Codex exec stdout alone stays unverified.
            tool["tool_input"]["workdir"] = str(self.root)
        self.run_hook(VERIFY, hook_event_name="PreToolUse", **tool)
        response = (
            {"stdout": "1 passed", "stderr": "", "interrupted": False}
            if state_store.HOST_KIND == "claude"
            else {"exit_code": 0, "stdout": "1 passed", "stderr": ""}
        )
        self.run_hook(VERIFY, hook_event_name="PostToolUse", tool_response=response, **tool)

    def stop(self, text="Done."):
        return self.run_hook(STOP, hook_event_name="Stop", last_assistant_message=text)

    def read_state(self):
        directory = self.state / (
            "high-agency-claude-code-verification"
            if state_store.HOST_KIND == "claude" else "verification"
        )
        with patch.object(state_store, "data_root", return_value=directory):
            path = state_store.verification_path(self.common)
        return json.loads(path.read_text(encoding="utf-8"))

    def edit_both_areas(self):
        for path in ("src/auth/a.py", "src/payments/b.py"):
            (self.root / path).write_text("value = 2\n", encoding="utf-8")

    def test_major_scope_drift_blocks_once_after_real_paired_success_metadata(self):
        self.submit()
        self.append("Impact: local | files<=1 | modules<=1 | boundary=private")
        self.edit_both_areas()
        self.verify()
        self.assertEqual(self.read_state()["verification_status"], "passed")
        self.append("Done.")
        result = self.stop()
        self.assertEqual(result.get("decision"), "block")
        self.assertIn("impact calibration", result.get("reason", "").lower())
        self.assertIn("major scope drift", result.get("reason", "").lower())
        self.assertEqual(self.stop(), {})
        self.assertTrue(self.read_state()["task_completed"])

    def test_prior_task_estimate_is_not_reused_and_current_estimate_is_immutable(self):
        self.append("Impact: high | files<=99 | modules<=99 | boundary=high-impact")
        self.append("Previous task done.")
        self.submit()
        original = "Impact: local | files<=1 | modules<=1 | boundary=private"
        self.append(original)
        self.edit_both_areas()
        self.verify()
        self.append("Impact: high | files<=99 | modules<=99 | boundary=high-impact")
        result = self.stop()
        self.assertIn("major scope drift", result.get("reason", "").lower())
        self.assertEqual(self.read_state()["impact_estimate"]["raw"], original)

    def test_completed_task_allows_a_fresh_estimate_on_next_submit(self):
        self.submit()
        self.append("Impact: local | files<=1 | modules<=1 | boundary=private")
        self.edit_both_areas()
        self.verify()
        old_id = self.read_state()["task_id"]
        self.assertIn("major scope drift", self.stop()["reason"].lower())
        self.assertEqual(self.stop(), {})

        if state_store.HOST_KIND == "claude":
            self.common["prompt_id"] = "prompt-2"
        else:
            self.common["turn_id"] = "next-turn"
        self.submit("Use high-agency-coding for the view change")
        self.append("Impact: local | files<=1 | modules<=1 | boundary=private")
        (self.root / "src/view/c.py").write_text("value = 2\n", encoding="utf-8")
        self.verify("next-check")
        self.assertNotEqual(self.read_state()["task_id"], old_id)
        self.assertEqual(self.stop(), {})

    def test_internal_submit_preserves_active_task_baseline_estimate_and_budget(self):
        self.submit()
        self.append("Impact: local | files<=1 | modules<=1 | boundary=private")
        self.verify()
        marker = "<!-- high-agency:continue max=2 -->"
        first = self.stop(marker)
        self.assertIn("1/2", first["reason"])
        before = self.read_state()
        if state_store.HOST_KIND == "claude":
            self.common["prompt_id"] = "internal-report"
        else:
            self.common["turn_id"] = "internal-report"
        self.submit("Background work has reported completion.")
        current = self.read_state()
        self.assertTrue(current["active"])
        self.assertEqual(current["task_id"], before["task_id"])
        self.assertEqual(current["baseline_snapshot"], before["baseline_snapshot"])
        self.assertEqual(current["impact_estimate"], before["impact_estimate"])
        self.assertIn("2/2", self.stop(marker)["reason"])
        self.assertEqual(self.stop(marker), {})


if __name__ == "__main__":
    unittest.main()
