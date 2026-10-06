import hashlib
import json
import os
import shlex
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOKS = ROOT / "plugins/high-agency/hooks"
sys.path.insert(0, str(HOOKS))
from state_store import HOST_KIND, atomic_json_write, load_json  # noqa: E402
from verification_commands import classify_command, result_status  # noqa: E402

VERIFY = HOOKS / "verification_state.py"
CHECK = "python -m unittest discover -s tests"


class CommandEvidenceTests(unittest.TestCase):
    def test_only_actual_check_executable_is_recognized(self):
        for command in (
            "echo pytest", "printf pytest", "cat pytest.log",
            "python -c 'print(\"pytest\")'", "npm install test",
            "git log --grep=pytest", "pytest --help", "pytest --collect-only",
        ):
            with self.subTest(command=command):
                self.assertIsNone(classify_command(command, str(ROOT)))

    def test_unittest_and_common_checks_are_recognized(self):
        for command in (CHECK, "python3 -m pytest tests/test_one.py", "npm run test:unit",
                        "pnpm typecheck", "cargo test", "ruff check .", "npx vitest run"):
            with self.subTest(command=command):
                self.assertEqual(classify_command(command, str(ROOT))["kind"], "verification")

    def test_masked_and_ambiguous_shell_checks_are_rejected(self):
        for command in ("pytest || true", "pytest; echo done", "pytest | tee log",
                        "pytest && python edit.py", "bash -c 'pytest'",
                        "pytest > result.log", "pytest\necho done", "pytest $(touch changed.py)"):
            with self.subTest(command=command):
                self.assertIsNone(classify_command(command, str(ROOT)))

    def test_safe_leading_cd_preserves_workdir(self):
        with tempfile.TemporaryDirectory() as temp:
            cwd = Path(temp)
            (cwd / "package with spaces").mkdir()
            check = classify_command("cd 'package with spaces' && npm test", str(cwd))
            self.assertEqual(check["cwd"], str((cwd / "package with spaces").resolve()))
            self.assertEqual(check["argv"], ["npm", "test"])
            self.assertIsNone(classify_command("cd subdir && npm test && echo done", str(cwd)))

    def test_claude_synchronous_success_does_not_require_invented_exit_code(self):
        result = result_status({"hook_event_name": "PostToolUse",
                                "tool_response": {"stdout": "one passed", "stderr": "", "interrupted": False}}, "claude")
        self.assertEqual(result["status"], "passed")
        self.assertNotIn("exit_code", result)

    def test_claude_missing_pending_and_interrupted_are_not_success(self):
        for response in (None, {}, {"stdout": "exit_code: 0"},
                         {"stdout": "", "stderr": "", "interrupted": True},
                         {"stdout": "", "stderr": "", "interrupted": False, "backgroundTaskId": "bg-1"}):
            with self.subTest(response=response):
                self.assertNotEqual(result_status({"hook_event_name": "PostToolUse", "tool_response": response}, "claude")["status"], "passed")

    def test_codex_requires_metadata_not_stdout_claims(self):
        cases = (
            {"tool_response": {"exit_code": 0, "output": "FAILED is merely stdout"}, "expected": "passed"},
            {"tool_response": {"exit_code": 1, "output": "exit_code: 0"}, "expected": "failed"},
            {"tool_response": {"stdout": "exit_code: 0"}, "expected": "unverified"},
            {"tool_response": "tests say exit_code: 0", "expected": "unverified"},
            {"tool_response": {"exit_code": True}, "expected": "unverified"},
        )
        for case in cases:
            with self.subTest(case=case):
                result = result_status({"hook_event_name": "PostToolUse", "tool_response": case["tool_response"]}, "codex")
                self.assertEqual(result["status"], case["expected"])

    def test_codex_raw_stdout_cannot_authenticate_an_executor_envelope(self):
        success = "Chunk ID: abc123\nWall time: 0.03 seconds\nProcess exited with code 0\nFinal output:\nFAIL is output text\n"
        failed = "Chunk ID: abc123\nWall time: 0.03 seconds\nProcess exited with code 1\nFinal output:\n" + success
        for response, expected in ((success, "unverified"), (failed, "unverified"), ("stdout prefix\n" + success, "unverified")):
            self.assertEqual(result_status({"hook_event_name": "PostToolUse", "tool_response": response}, "codex")["status"], expected)


class VerificationLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.cwd = self.base / "work tree"
        self.cwd.mkdir()
        self.state = self.base / "state"
        self.state.mkdir()
        self.transcript = self.base / "transcript.jsonl"
        self.transcript.write_text("", encoding="utf-8")
        self.env = dict(os.environ, TMPDIR=str(self.state), TEMP=str(self.state), TMP=str(self.state),
                        PLUGIN_DATA=str(self.state), PYTHONDONTWRITEBYTECODE="1", HIGH_AGENCY_HOOK_DEBUG="1")
        self.sid = "evidence-" + uuid.uuid4().hex
        self.defaults = {"session_id": self.sid, "turn_id": "turn-1", "prompt_id": "prompt-1",
                         "cwd": str(self.cwd), "transcript_path": str(self.transcript)}
        self.defaults.pop("turn_id" if HOST_KIND == "claude" else "prompt_id")
        (self.cwd / "tests").mkdir()
        (self.cwd / "app.py").write_text("value = 1\n", encoding="utf-8")
        (self.cwd / ".gitignore").write_text("__pycache__/\nlocal_config.py\n", encoding="utf-8")
        (self.cwd / "tests/test_app.py").write_text(
            "import os, unittest\nimport app\n"
            "class AppTest(unittest.TestCase):\n"
            "    def test_positive(self):\n"
            "        self.assertGreater(app.value, 0)\n"
            "        self.assertNotEqual(os.environ.get('HIGH_AGENCY_TEST_FAIL'), '1')\n", encoding="utf-8")
        for args in (("init", "-q"), ("config", "user.name", "Hook Test"),
                     ("config", "user.email", "test@example.invalid"), ("config", "core.autocrlf", "false"),
                     ("add", "."), ("commit", "-qm", "baseline")):
            subprocess.run(["git", *args], cwd=self.cwd, env=self.env, check=True, capture_output=True)

    def hook(self, event, *, tool="Bash", command=None, tool_id="check-1", **kwargs):
        payload = dict(self.defaults, hook_event_name=event)
        if event in {"PreToolUse", "PostToolUse", "PostToolUseFailure"}:
            payload.update(tool_name=tool, tool_use_id=tool_id)
            if command is not None:
                payload["tool_input"] = {"command": command}
        payload.update(kwargs)
        # Exercise each documented host identity without assuming the other's
        # extension is present: Claude prompt_id, Codex turn_id.
        payload.pop("turn_id" if HOST_KIND == "claude" else "prompt_id", None)
        result = subprocess.run([sys.executable, str(VERIFY)], input=json.dumps(payload),
                                text=True, capture_output=True, cwd=self.cwd, env=self.env, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "", result.stderr)
        return result

    def files(self):
        directory = self.state / ("high-agency-claude-code-verification" if HOST_KIND == "claude" else "verification")
        return list(directory.glob("*.json"))

    def data(self):
        values = [(path, json.loads(path.read_text(encoding="utf-8"))) for path in self.files()]
        return next(value for path, value in values if not value.get("agent_id"))

    def replace_data(self, value):
        path = next(path for path in self.files() if not json.loads(path.read_text(encoding="utf-8")).get("agent_id"))
        atomic_json_write(path, value)

    def activate(self, prompt="Use high-agency-coding for this task"):
        self.hook("UserPromptSubmit", prompt=prompt)

    def append_assistant(self, text):
        with self.transcript.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"message": {"role": "assistant", "content": [{"type": "text", "text": text}]}}) + "\n")

    def actual_check(self, *, tool_id="check-1", fail=False, mutate=None):
        command = "cd " + shlex.quote(str(self.cwd)) + " && " + CHECK if HOST_KIND == "codex" else CHECK
        self.hook("PreToolUse", command=command, tool_id=tool_id)
        if mutate:
            mutate()
        env = dict(self.env)
        if fail:
            env["HIGH_AGENCY_TEST_FAIL"] = "1"
        cp = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests"],
                            cwd=self.cwd, env=env, capture_output=True, text=True, timeout=10)
        if HOST_KIND == "claude":
            event = "PostToolUse" if cp.returncode == 0 else "PostToolUseFailure"
            response = {"stdout": cp.stdout, "stderr": cp.stderr, "interrupted": False}
        else:
            event = "PostToolUse"
            response = {"exit_code": cp.returncode, "output": cp.stdout + cp.stderr}
        self.hook(event, command=command, tool_id=tool_id, tool_response=response)
        return cp

    def edit_native(self, path, content, *, tool_id="edit-1"):
        tool_input = {"file_path": str(path), "old_string": "", "new_string": content}
        self.hook("PreToolUse", tool="Edit", tool_id=tool_id, tool_input=tool_input)
        path.write_text(content, encoding="utf-8")
        self.hook("PostToolUse", tool="Edit", tool_id=tool_id, tool_input=tool_input, tool_response={})

    def test_ordinary_prompt_has_pre_mutation_baseline_and_skill_activates(self):
        self.activate("Fix the bug")
        before = self.data()
        self.assertFalse(before["active"])
        self.assertTrue(before["baseline_snapshot"]["available"])
        self.hook("PreToolUse", tool="Skill", tool_id="skill-1", tool_input={"skill": "high-agency:high-agency-coding"})
        self.assertTrue(self.data()["active"])
        self.assertEqual(before["baseline_snapshot"], self.data()["baseline_snapshot"])

    def test_direct_slash_and_bound_autonomy_activate(self):
        self.activate("/high-agency:bounded-autonomy fix it")
        self.assertTrue(self.data()["active"])

    def test_exact_activation_helper_uses_host_payload_identity(self):
        self.activate("Fix the bug")
        helper = shlex.join(["python", str(VERIFY), "--activate"])
        self.hook("PreToolUse", command="echo " + helper, tool_id="fake-activation")
        self.assertFalse(self.data()["active"])
        self.hook("PreToolUse", command=helper, tool_id="real-activation")
        self.assertTrue(self.data()["active"])
        self.assertEqual(self.data()["activation_reason"], "activation_helper")

    def test_actual_unittest_success_has_paired_fresh_evidence(self):
        self.activate()
        (self.cwd / "app.py").write_text("value = 2\n", encoding="utf-8")
        cp = self.actual_check()
        self.assertEqual(cp.returncode, 0, cp.stderr)
        data = self.data()
        self.assertEqual(data["verification_status"], "passed")
        self.assertEqual(data["verification_evidence"][-1]["tool_use_id"], "check-1")
        self.assertIsNotNone(data["verification_snapshot"])

    def test_actual_failure_invalidates_previous_success_without_source_change(self):
        self.activate()
        self.assertEqual(self.actual_check(tool_id="pass").returncode, 0)
        self.assertNotEqual(self.actual_check(tool_id="fail", fail=True).returncode, 0)
        data = self.data()
        self.assertEqual(data["verification_status"], "failed")
        self.assertIsNone(data["verification_snapshot"])
        self.assertEqual(data["verification_failure"]["tool_use_id"], "fail")
        self.assertEqual(self.actual_check(tool_id="recovered").returncode, 0)
        self.assertEqual(self.data()["verification_status"], "passed")

    def test_mutation_during_successful_check_is_not_verified(self):
        self.activate()
        cp = self.actual_check(mutate=lambda: (self.cwd / "app.py").write_text("value = 2\n", encoding="utf-8"))
        self.assertEqual(cp.returncode, 0)
        self.assertEqual(self.data()["verification_status"], "unverified")
        self.assertIsNone(self.data()["verification_snapshot"])

    def test_echo_pytest_and_masked_failure_never_create_pending_check(self):
        self.activate()
        for command in ("echo pytest", "python -m pytest || true"):
            self.hook("PreToolUse", command=command)
            self.hook("PostToolUse", command=command, tool_response={"exit_code": 0, "stdout": "pytest", "stderr": "", "interrupted": False})
        self.assertEqual(self.data()["pending_checks"], {})
        self.assertIsNone(self.data()["verification_snapshot"])

    def test_post_without_matching_pre_or_tool_id_is_not_evidence(self):
        self.activate()
        self.hook("PostToolUse", command=CHECK, tool_response={"exit_code": 0, "stdout": "", "stderr": "", "interrupted": False})
        self.assertIsNone(self.data()["verification_snapshot"])
        self.hook("PreToolUse", command=CHECK, tool_id="one")
        self.hook("PostToolUse", command=CHECK, tool_id="different", tool_response={"exit_code": 0, "stdout": "", "stderr": "", "interrupted": False})
        self.assertIsNone(self.data()["verification_snapshot"])

    def test_background_start_is_pending_and_task_stop_is_correlated(self):
        self.activate()
        self.hook("PreToolUse", tool_input={"command": CHECK, "run_in_background": True})
        response = {"stdout": "", "stderr": "", "interrupted": False, "backgroundTaskId": "bg-1"}
        self.hook("PostToolUse", command=CHECK, tool_response=response)
        self.assertEqual(self.data()["verification_status"], "pending")
        self.assertIsNone(self.data()["verification_snapshot"])
        self.hook("PostToolUse", tool="TaskStop", tool_id="stop-1", tool_input={"task_id": "other"},
                  tool_response={"task_id": "other", "task_type": "local_bash", "message": "stopped"})
        self.assertEqual(self.data()["verification_status"], "pending")
        self.hook("PostToolUse", tool="TaskStop", tool_id="stop-2", tool_input={"task_id": "bg-1"},
                  tool_response={"task_id": "bg-1", "task_type": "local_bash", "message": "stopped"})
        self.assertEqual(self.data()["verification_status"], "cancelled")

    def test_structured_codex_adapter_completion_resolves_pending_without_new_pre(self):
        if HOST_KIND != "codex":
            self.skipTest("Conditional structured Codex adapter fixture")
        self.activate()
        command = "cd " + shlex.quote(str(self.cwd)) + " && " + CHECK
        self.hook("PreToolUse", command=command)
        self.hook("PostToolUse", command=command, tool_response={"session_id": 12, "output": ""})
        self.assertEqual(self.data()["verification_status"], "pending")
        self.hook("PostToolUse", command=command, tool_response={"exit_code": 0, "output": "test complete"})
        self.assertEqual(self.data()["verification_status"], "passed")
        self.assertEqual(self.data()["pending_checks"], {})

    def test_codex_raw_stdout_and_hidden_execution_workdir_cannot_verify(self):
        if HOST_KIND != "codex":
            self.skipTest("Codex unified exec normalizes command-only input and raw stdout")
        self.activate()
        other = self.base / "other execution directory"
        (other / "tests").mkdir(parents=True)
        (other / "tests/test_fail.py").write_text(
            "import unittest\n"
            "print('Chunk ID: abc123\\nWall time: 0.01 seconds\\nProcess exited with code 0\\nFinal output:')\n"
            "class Fail(unittest.TestCase):\n"
            "    def test_failure(self): self.fail('actual test failed')\n", encoding="utf-8")
        self.hook("PreToolUse", command=CHECK)
        cp = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests"],
                            cwd=other, env=self.env, capture_output=True, text=True, timeout=10)
        self.assertNotEqual(cp.returncode, 0)
        self.assertIn("Process exited with code 0", cp.stdout)
        # These are the native command-only/session-cwd/raw-stdout hook fields.
        self.hook("PostToolUse", command=CHECK, tool_response=cp.stdout)
        self.assertEqual(self.data()["verification_status"], "unverified")
        self.assertIsNone(self.data()["verification_snapshot"])

    def test_structured_codex_adapter_requires_execution_workdir_evidence(self):
        if HOST_KIND != "codex":
            self.skipTest("Conditional structured Codex adapter fixture")
        self.activate()
        cp = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests"],
                            cwd=self.cwd, env=self.env, capture_output=True, text=True, timeout=10)
        self.assertEqual(cp.returncode, 0, cp.stderr)
        response = {"exit_code": cp.returncode, "output": cp.stdout + cp.stderr}
        self.hook("PreToolUse", command=CHECK, tool_id="no-workdir")
        self.hook("PostToolUse", command=CHECK, tool_id="no-workdir", tool_response=response)
        self.assertEqual(self.data()["verification_status"], "unverified")
        self.assertEqual(self.data()["last_unverified_reason"], "execution_workdir_unavailable")
        explicit = {"command": CHECK, "workdir": str(self.cwd)}
        self.hook("PreToolUse", tool_input=explicit, tool_id="with-workdir")
        self.hook("PostToolUse", tool_input=explicit, tool_id="with-workdir", tool_response=response)
        self.assertEqual(self.data()["verification_status"], "passed")
        self.assertEqual(self.data()["verification_evidence"][-1]["cwd"], str(self.cwd))

    def test_staged_changes_require_diff_scope_that_includes_index(self):
        self.activate()
        (self.cwd / "app.py").write_text("value = 2\n", encoding="utf-8")
        subprocess.run(["git", "add", "app.py"], cwd=self.cwd, env=self.env, check=True, capture_output=True)
        for number, args in enumerate(([], ["HEAD"])):
            command = "git diff" + (" HEAD" if args else "")
            tool_input = {"command": command}
            if HOST_KIND == "codex":
                tool_input["workdir"] = str(self.cwd)
            self.hook("PreToolUse", tool_input=tool_input, tool_id="diff-" + str(number))
            cp = subprocess.run(["git", "diff", *args], cwd=self.cwd, env=self.env, capture_output=True, text=True, timeout=10)
            response = ({"stdout": cp.stdout, "stderr": cp.stderr, "interrupted": False}
                        if HOST_KIND == "claude" else {"exit_code": cp.returncode, "output": cp.stdout + cp.stderr})
            self.hook("PostToolUse", tool_input=tool_input, tool_id="diff-" + str(number), tool_response=response)
            self.assertEqual(cp.returncode, 0)
            if args:
                self.assertIn("value = 2", cp.stdout)
                self.assertIsNotNone(self.data()["diff_snapshot"])
            else:
                self.assertEqual(cp.stdout, "")
                self.assertIsNone(self.data()["diff_snapshot"])

    def test_ignored_native_edits_are_fingerprinted_and_reversion_is_clean(self):
        path = self.cwd / "local_config.py"
        path.write_text("value = 1\n", encoding="utf-8")
        self.activate()
        self.edit_native(path, "value = 2\n")
        self.assertTrue(self.data()["native_dirty"])
        self.assertEqual(self.actual_check().returncode, 0)
        data = self.data()
        self.assertIn(os.path.normcase(os.path.abspath(path)), data["verification_snapshot"]["native_files"])
        self.edit_native(path, "value = 1\n", tool_id="revert")
        self.assertFalse(self.data()["native_dirty"])
        self.assertEqual(self.data()["all_edited_files"], [])

    def test_internal_prompt_preserves_task_baseline_and_success(self):
        self.activate()
        self.assertEqual(self.actual_check().returncode, 0)
        before = self.data()
        self.hook("UserPromptSubmit", prompt="The background task completed", prompt_id="notification-2", turn_id="turn-2")
        after = self.data()
        for field in ("task_id", "baseline_snapshot", "verification_snapshot", "transcript_start_offset"):
            self.assertEqual(before[field], after[field])
        self.assertTrue(after["active"])

    def test_completed_task_gets_new_epoch_and_old_completion_cannot_verify(self):
        self.activate()
        self.hook("PreToolUse", command=CHECK, tool_id="old-check")
        old = self.data()
        old["task_completed"] = True
        old["active"] = False
        self.replace_data(old)
        self.append_assistant("old task complete")
        self.hook("UserPromptSubmit", prompt="Use high-agency-coding on a new task", prompt_id="new-prompt", turn_id="turn-2")
        self.assertNotEqual(old["task_id"], self.data()["task_id"])
        self.hook("PostToolUse", command=CHECK, tool_id="old-check", tool_response={"exit_code": 0, "stdout": "", "stderr": "", "interrupted": False})
        self.assertIsNone(self.data()["verification_snapshot"])

    def test_impact_uses_current_task_offset(self):
        self.append_assistant("Impact: high | files<=100 | modules<=100 | boundary=high-impact")
        self.activate()
        self.append_assistant("Impact: local | files<=1 | modules<=1 | boundary=private")
        self.hook("PreToolUse", command=CHECK)
        self.assertEqual(self.data()["impact_estimate"]["files_max"], 1)
        self.assertGreater(self.data()["transcript_start_offset"], 0)

    def test_legacy_success_is_invalidated_on_migration(self):
        self.activate()
        old = self.data()
        self.replace_data({"active": True, "baseline_snapshot": old["baseline_snapshot"],
                           "verification_snapshot": old["baseline_snapshot"]})
        self.hook("PreToolUse", command="echo ok")
        self.assertEqual(self.data()["schema_version"], 2)
        self.assertIsNone(self.data()["verification_snapshot"])


    def test_late_native_and_skill_completion_do_not_contaminate_new_task(self):
        path = self.cwd / "local_config.py"
        path.write_text("value = 1\n", encoding="utf-8")
        self.activate()
        native = {"file_path": str(path)}
        self.hook("PreToolUse", tool="Write", tool_id="old-write", tool_input=native)
        self.hook("PreToolUse", tool="Skill", tool_id="old-skill", tool_input={"skill": "high-agency:high-agency-coding"})
        path.write_text("value = 2\n", encoding="utf-8")
        old = self.data()
        old.update(task_completed=True, active=False)
        self.replace_data(old)
        self.hook("UserPromptSubmit", prompt="A new ordinary task", prompt_id="prompt-2", turn_id="turn-2")
        current_task = self.data()["task_id"]
        self.hook("PostToolUse", tool="Write", tool_id="old-write", tool_input=native, tool_response={})
        self.hook("PostToolUse", tool="Skill", tool_id="old-skill", tool_input={"skill": "high-agency:high-agency-coding"}, tool_response={})
        after = self.data()
        self.assertEqual(after["task_id"], current_task)
        self.assertFalse(after["active"])
        self.assertFalse(after["native_dirty"])
        self.assertEqual(after["native_files"], {})

    def test_current_prompt_post_only_native_edit_remains_unknown_baseline(self):
        path = self.cwd / "local_config.py"
        self.activate()
        path.write_text("value = 2\n", encoding="utf-8")
        self.hook("PostToolUse", tool="Write", tool_id="current-unpaired", tool_input={"file_path": str(path)}, tool_response={})
        data = self.data()
        self.assertTrue(data["native_dirty"])
        self.assertEqual(next(iter(data["native_files"].values()))["before"], "unknown:missing_pre_tool_use")

    def test_child_ignored_edit_is_aggregated_and_parent_stop_warns(self):
        path = self.cwd / "local_config.py"
        path.write_text("value = 1\n", encoding="utf-8")
        self.activate()
        parent = self.data()
        self.hook("SubagentStart", agent_id="worker-1", agent_type="test-worker")
        native = {"file_path": str(path)}
        self.hook("PreToolUse", tool="Edit", tool_id="child-edit", tool_input=native, agent_id="worker-1")
        path.write_text("value = 2\n", encoding="utf-8")
        self.hook("PostToolUse", tool="Edit", tool_id="child-edit", tool_input=native, tool_response={}, agent_id="worker-1")
        after = self.data()
        self.assertEqual(after["task_id"], parent["task_id"])
        self.assertEqual(after["transcript_start_offset"], parent["transcript_start_offset"])
        self.assertTrue(after["native_dirty"])
        self.assertIsNone(after["agent_id"])
        self.assertIn("agent:worker-1:child-edit", after["seen_tool_ids"])
        payload = dict(self.defaults, hook_event_name="Stop", last_assistant_message="Done.", stop_hook_active=False)
        result = subprocess.run([sys.executable, str(HOOKS / "stop_loop.py")], input=json.dumps(payload),
                                cwd=self.cwd, env=self.env, capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["decision"], "block")

    def test_child_edit_with_current_prompt_can_link_without_start_replay(self):
        path = self.cwd / "local_config.py"
        self.activate()
        self.hook("PreToolUse", tool="Write", tool_id="child-edit", tool_input={"file_path": str(path)}, agent_id="worker-2")
        path.write_text("value = 2\n", encoding="utf-8")
        self.hook("PostToolUse", tool="Write", tool_id="child-edit", tool_input={"file_path": str(path)}, tool_response={}, agent_id="worker-2")
        self.assertTrue(self.data()["native_dirty"])

    def test_late_unseen_child_start_cannot_bind_to_new_task(self):
        self.activate()
        old = self.data()
        old.update(task_completed=True, active=False)
        self.replace_data(old)
        self.hook("UserPromptSubmit", prompt="high-agency new task", prompt_id="prompt-2", turn_id="turn-2")
        self.hook("SubagentStart", agent_id="late-old-child", agent_type="worker")
        self.assertNotIn("late-old-child", self.data()["child_tasks"])

    def test_delayed_first_pre_tool_from_old_origin_cannot_activate_new_task(self):
        self.activate()
        old = self.data()
        old.update(task_completed=True, active=False)
        self.replace_data(old)
        self.hook("UserPromptSubmit", prompt="A new ordinary task", prompt_id="prompt-2", turn_id="turn-2")
        current = self.data()
        self.hook("PreToolUse", tool="Skill", tool_id="unseen-old-pre",
                  tool_input={"skill": "high-agency:high-agency-coding"})
        after = self.data()
        self.assertFalse(after["active"])
        for field in ("task_id", "prompt_ids", "turn_ids", "seen_tool_ids"):
            self.assertEqual(after[field], current[field])

    def test_malformed_persisted_state_recovers_only_on_prompt(self):
        self.activate()
        path = self.files()[0]
        for malformed in ("{invalid", json.dumps({"schema_version": 2, "task_id": "broken"})):
            path.write_text(malformed, encoding="utf-8")
            self.hook("UserPromptSubmit", prompt="high-agency start fresh", prompt_id="recovery")
            data = self.data()
            self.assertIn("state_recovered_at", data)
            self.assertIsNone(data["verification_snapshot"])
            self.assertTrue(data["baseline_snapshot"]["available"])

    def test_malformed_nested_records_and_histories_recover(self):
        self.activate()
        for field, invalid in (("retired_tool_ids", 42), ("seen_tool_ids", 42),
                               ("retired_agent_ids", 42), ("failed_checks", {"bad": 42}),
                               ("native_files", {"bad": 42})):
            damaged = self.data()
            damaged[field] = invalid
            self.replace_data(damaged)
            self.hook("UserPromptSubmit", prompt="high-agency recover", prompt_id="recover-" + field)
            self.assertIn("state_recovered_at", self.data())
            self.assertIsNone(self.data()["verification_snapshot"])

    def test_pending_capacity_loss_cannot_become_passed(self):
        from unittest import mock
        import state_store
        import verification_state
        self.activate()
        directory = self.files()[0].parent
        with mock.patch.object(state_store, "data_root", return_value=directory), mock.patch.object(verification_state, "MAX_PENDING_CHECKS", 1):
            def replay(event, tool_id, response=None):
                payload = dict(self.defaults, hook_event_name=event, tool_name="Bash", tool_use_id=tool_id,
                               tool_input={"command": CHECK}, tool_response=response)
                verification_state.process(payload)
            replay("PreToolUse", "first")
            replay("PreToolUse", "overflow")
            replay("PostToolUse", "first", {"exit_code": 0, "stdout": "", "stderr": "", "interrupted": False})
            replay("PostToolUse" if HOST_KIND == "codex" else "PostToolUseFailure", "overflow",
                   {"exit_code": 1, "stdout": "", "stderr": "failed", "interrupted": False})
        data = self.data()
        self.assertTrue(data["verification_tracking_incomplete"])
        self.assertNotEqual(data["verification_status"], "passed")
        self.assertIsNone(data["verification_snapshot"])

    def test_state_size_budget_preserves_unverified_readable_state(self):
        import copy
        import verification_state
        from state_store import MAX_STATE_BYTES
        self.activate()
        self.hook("PreToolUse", command=CHECK)
        data = self.data()
        template = next(iter(data["pending_checks"].values()))
        for number in range(40):
            record = copy.deepcopy(template)
            record["start_snapshot"]["files"] = {"p%04d.py" % i: "file:100644:sha256:" + "a" * 64 for i in range(512)}
            record["start_snapshot"]["native_files"] = {"/native/p%04d.py" % i: "file:100644:sha256:" + "b" * 64 for i in range(512)}
            data["pending_checks"]["capacity-" + str(number)] = record
        self.assertGreater(len(json.dumps(data).encode()), MAX_STATE_BYTES)
        verification_state._bound_state(data)
        self.assertTrue(data["verification_tracking_incomplete"])
        self.assertIsNone(data["verification_snapshot"])
        self.assertLess(len(json.dumps(data).encode()), MAX_STATE_BYTES)
        self.replace_data(data)
        self.assertNotEqual(self.data()["verification_status"], "passed")



class StateStoreTests(unittest.TestCase):
    def test_non_dict_and_malformed_state_are_not_valid_transactions(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "state.json"
            for value in ("[]", "{invalid"):
                path.write_text(value, encoding="utf-8")
                self.assertEqual(load_json(path), {})
                with self.assertRaises(ValueError):
                    load_json(path, strict=True)

    def test_atomic_writes_leave_no_temp_files(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "state.json"
            atomic_json_write(path, {"x": 1})
            self.assertEqual(load_json(path), {"x": 1})
            self.assertEqual(list(Path(temp).glob("*.tmp")), [])

    def test_parallel_process_updates_are_not_lost(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "state.json"
            script = (
                "import sys; from pathlib import Path; sys.path.insert(0, sys.argv[1]); "
                "from state_store import locked_json; "
                "\nfor _ in range(12):"
                "\n with locked_json(Path(sys.argv[2])) as state:"
                "\n  state['count'] = state.get('count', 0) + 1\n"
            )
            children = [subprocess.Popen([sys.executable, "-c", script, str(HOOKS), str(path)],
                                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for _ in range(4)]
            for child in children:
                stdout, stderr = child.communicate(timeout=15)
                self.assertEqual(child.returncode, 0, stderr)
            self.assertEqual(load_json(path)["count"], 48)


if __name__ == "__main__":
    unittest.main()
