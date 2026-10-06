"""Stop runtime regressions shared by the Claude and Codex plugins."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
HOOKS = ROOT / "plugins" / "high-agency" / "hooks"
sys.path.insert(0, str(HOOKS))
import state_store  # noqa: E402
from git_state import file_fingerprint, snapshot  # noqa: E402
from stop_loop import MAX_TRANSCRIPT_BYTES, current_snapshot, rel, task_files  # noqa: E402

STOP = HOOKS / "stop_loop.py"
MARKER = "<!-- high-agency:continue max=2 -->"


class StopRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.state_root = self.root / "state"
        self.state_root.mkdir()
        self.env = {
            **os.environ,
            "TMPDIR": str(self.state_root),
            "TEMP": str(self.state_root),
            "TMP": str(self.state_root),
            "PLUGIN_DATA": str(self.state_root),
        }
        self.env.pop("HIGH_AGENCY_HOOK_DEBUG", None)
        self.transcript = self.root / "transcript.jsonl"
        self.transcript.write_text("", encoding="utf-8")
        self.payload = {
            "hook_event_name": "Stop",
            "session_id": "stop-session",
            "turn_id": "turn-1",
            "cwd": str(self.repo),
            "transcript_path": str(self.transcript),
            "last_assistant_message": "Done.",
        }
        self.git("init", "-q")
        self.git("config", "user.email", "test@example.com")
        self.git("config", "user.name", "High Agency Test")
        (self.repo / "src").mkdir()
        (self.repo / "src/app.py").write_text("value = 1\n", encoding="utf-8")
        (self.repo / ".github/workflows").mkdir(parents=True)
        (self.repo / ".github/workflows/ci.yml").write_text("name: old\n", encoding="utf-8")
        (self.repo / ".gitignore").write_text("ignored.py\n", encoding="utf-8")
        self.git("add", ".")
        self.git("commit", "-qm", "initial")

    def git(self, *args):
        return subprocess.run(
            ["git", *args], cwd=self.repo, text=True, capture_output=True, check=True
        )

    def state_path(self, payload=None):
        data_dir = self.state_root / (
            "high-agency-claude-code-verification"
            if state_store.HOST_KIND == "claude" else "verification"
        )
        with patch.object(state_store, "data_root", return_value=data_dir):
            return state_store.verification_path(payload or self.payload)

    def save_state(self, data, payload=None):
        path = self.state_path(payload)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding="utf-8")

    def read_state(self, payload=None):
        path = self.state_path(payload)
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}

    def active_state(self):
        return {
            "active": True,
            "task_id": "task-1",
            "task_completed": False,
            "baseline_snapshot": snapshot(self.repo),
            "verification_snapshot": None,
            "verification_status": "unverified",
            "verification_failure": None,
            "pending_checks": {},
            "native_files": {},
            "all_edited_files": [],
            "prompt_ids": [],
            "transcript_start_offset": 0,
        }

    def stop(self, payload=None, *, raw=None, debug=False):
        env = dict(self.env)
        if debug:
            env["HIGH_AGENCY_HOOK_DEBUG"] = "1"
        result = subprocess.run(
            [sys.executable, str(STOP)],
            input=json.dumps(payload if payload is not None else self.payload) if raw is None else raw,
            cwd=self.repo, env=env, text=True, capture_output=True,
            timeout=10, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        if not debug:
            self.assertEqual(result.stderr, "")
        self.assertIsInstance(json.loads(result.stdout), dict)
        return json.loads(result.stdout), result.stderr

    def append_message(self, role, content):
        with self.transcript.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"message": {"role": role, "content": content}}) + "\n")

    def test_authoritative_done_ignores_stale_transcript_marker(self):
        self.append_message("assistant", MARKER)
        self.assertEqual(self.stop()[0], {})

    def test_authoritative_empty_message_ignores_stale_marker(self):
        self.append_message("assistant", MARKER)
        self.assertEqual(self.stop({**self.payload, "last_assistant_message": ""})[0], {})

    def test_current_marker_works_without_transcript(self):
        payload = {**self.payload, "last_assistant_message": MARKER}
        payload.pop("transcript_path")
        result, _ = self.stop(payload)
        self.assertEqual(result.get("decision"), "block")
        self.assertIn("1/2", result["reason"])

    def test_missing_field_uses_transcript_fallback(self):
        self.append_message("assistant", MARKER)
        payload = dict(self.payload)
        payload.pop("last_assistant_message")
        self.assertEqual(self.stop(payload)[0].get("decision"), "block")

    def test_malformed_present_field_never_falls_back(self):
        self.append_message("assistant", MARKER)
        for invalid in (None, 3, {}, ["text"]):
            with self.subTest(invalid=invalid):
                self.assertEqual(self.stop({**self.payload, "last_assistant_message": invalid})[0], {})

    def test_fallback_ignores_non_string_content_type(self):
        self.append_message("assistant", MARKER)
        self.append_message("assistant", [{"type": [], "text": MARKER}])
        payload = dict(self.payload)
        payload.pop("last_assistant_message")
        self.assertEqual(self.stop(payload)[0], {})

    def test_fallback_rejects_fifo_without_waiting_for_a_writer(self):
        if not hasattr(os, "mkfifo"):
            self.skipTest("Named pipes are unavailable on this platform")
        fifo = self.root / "transcript-pipe"
        os.mkfifo(fifo)
        payload = {**self.payload, "transcript_path": str(fifo)}
        payload.pop("last_assistant_message")
        self.assertEqual(self.stop(payload)[0], {})

    def test_fallback_uses_bounded_tail_and_skips_malformed_entries(self):
        self.append_message("assistant", MARKER)
        with self.transcript.open("a", encoding="utf-8") as handle:
            handle.write("x" * (MAX_TRANSCRIPT_BYTES + 32) + "\n")
            handle.write("[]\nnull\n{broken\n")
        self.append_message("assistant", "Done.")
        payload = dict(self.payload)
        payload.pop("last_assistant_message")
        self.assertEqual(self.stop(payload)[0], {})

    def test_empty_assistant_or_new_user_supersedes_fallback_marker(self):
        payload = dict(self.payload)
        payload.pop("last_assistant_message")
        for role, content in (("assistant", []), ("user", "A new request")):
            with self.subTest(role=role):
                self.transcript.write_text("", encoding="utf-8")
                self.append_message("assistant", MARKER)
                self.append_message(role, content)
                self.assertEqual(self.stop(payload)[0], {})

    def test_codex_response_item_transcript_fallback(self):
        self.transcript.write_text(json.dumps({
            "type": "response_item",
            "payload": {
                "type": "message", "role": "assistant",
                "content": [{"type": "output_text", "text": MARKER}],
            },
        }) + "\n", encoding="utf-8")
        payload = dict(self.payload)
        payload.pop("last_assistant_message")
        self.assertEqual(self.stop(payload)[0].get("decision"), "block")

    def test_fallback_does_not_reuse_marker_when_last_record_is_incomplete(self):
        self.append_message("assistant", MARKER)
        with self.transcript.open("a", encoding="utf-8") as handle:
            handle.write('{"message":{"role":"assistant","content":"still being written')
        payload = dict(self.payload)
        payload.pop("last_assistant_message")
        self.assertEqual(self.stop(payload)[0], {})

    def test_malformed_payload_fails_open_with_valid_json_output(self):
        for raw in ("{", "[]", "null", '"text"', "3"):
            with self.subTest(raw=raw):
                self.assertEqual(self.stop(raw=raw)[0], {})

    def test_corrupt_state_fails_open_and_debug_is_opt_in(self):
        path = self.state_path()
        path.parent.mkdir(parents=True)
        path.write_text("[1]", encoding="utf-8")
        payload = {**self.payload, "last_assistant_message": MARKER}
        self.assertEqual(self.stop(payload)[0], {})
        result, diagnostics = self.stop(payload, debug=True)
        self.assertEqual(result, {})
        self.assertIn("Hook state cannot be read safely", diagnostics)
        self.assertEqual(path.read_text(encoding="utf-8"), "[1]")

    def test_malformed_counter_fails_open_without_resetting_budget(self):
        for count in ("bad", True, -1, {}, 100):
            with self.subTest(count=count):
                data = {
                    "active": False, "task_id": "task-1",
                    "continuation": {"task_id": "task-1", "continuations": count, "limit": 2},
                }
                self.save_state(data)
                self.assertEqual(self.stop({**self.payload, "last_assistant_message": MARKER})[0], {})
                self.assertEqual(self.read_state(), data)

    def test_malformed_state_collections_fail_open_without_rewriting_state(self):
        for field, value in (("baseline_snapshot", []), ("native_files", []),
                             ("pending_checks", "bad"), ("task_completed", "false"),
                             ("continuation", None), ("verification_snapshot", [])):
            with self.subTest(field=field):
                data = self.active_state()
                data[field] = value
                self.save_state(data)
                self.assertEqual(self.stop()[0], {})
                self.assertEqual(self.read_state(), data)

    def test_budget_survives_turn_changes_using_transcript_identity(self):
        payload = {**self.payload, "last_assistant_message": MARKER}
        payload.pop("session_id")
        first = self.stop({**payload, "turn_id": "turn-1"})[0]
        second = self.stop({**payload, "turn_id": "turn-2"})[0]
        third = self.stop({**payload, "turn_id": "turn-3"})[0]
        self.assertIn("1/2", first["reason"])
        self.assertIn("2/2", second["reason"])
        self.assertEqual(third, {})
        state = self.read_state(payload)
        self.assertTrue(state["task_completed"])
        self.assertEqual(state["completion_reason"], "budget_exhausted")
        self.assertEqual(state["continuation"]["continuations"], 2)
        self.assertEqual(self.stop({**payload, "turn_id": "turn-4"})[0], {})

    def test_later_marker_cannot_extend_the_task_budget(self):
        first = {**self.payload, "last_assistant_message": "<!-- high-agency:continue max=1 -->"}
        self.assertIn("1/1", self.stop(first)[0]["reason"])
        second = {**self.payload, "last_assistant_message": "<!-- high-agency:continue max=12 -->"}
        self.assertEqual(self.stop(second)[0], {})

    def test_marker_only_task_survives_later_lifecycle_hook(self):
        payload = {**self.payload, "last_assistant_message": MARKER}
        self.assertIn("1/2", self.stop(payload)[0]["reason"])
        before = self.read_state()
        result = subprocess.run(
            [sys.executable, str(HOOKS / "verification_state.py")],
            input=json.dumps({**self.payload, "hook_event_name": "UserPromptSubmit",
                              "prompt": "Background work has reported completion."}),
            cwd=self.repo, env=self.env, text=True, capture_output=True,
            timeout=10, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.read_state()["task_id"], before["task_id"])
        self.assertIn("2/2", self.stop(payload)[0]["reason"])
        self.assertEqual(self.stop(payload)[0], {})

    def test_huge_requested_max_is_clamped_without_integer_conversion_failure(self):
        marker = "<!-- high-agency:continue max=" + "9" * 5000 + " -->"
        self.assertIn("1/12", self.stop({**self.payload, "last_assistant_message": marker})[0]["reason"])

    def test_concurrent_stops_share_one_bounded_counter(self):
        payload = {**self.payload, "last_assistant_message": "<!-- high-agency:continue max=3 -->"}
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: self.stop(payload)[0], range(8)))
        self.assertEqual(sum(result.get("decision") == "block" for result in results), 3)
        state = self.read_state()
        self.assertEqual(state["continuation"]["continuations"], 3)
        self.assertTrue(state["task_completed"])

    def test_unverified_scope_warns_once_then_completes_truthfully(self):
        data = self.active_state()
        (self.repo / "src/app.py").write_text("value = 2\n", encoding="utf-8")
        self.save_state(data)
        result = self.stop()[0]
        self.assertIn("UNVERIFIED", result["reason"])
        self.assertEqual(self.stop()[0], {})
        state = self.read_state()
        self.assertTrue(state["task_completed"])
        self.assertFalse(state["active"])
        self.assertEqual(state["verification_status"], "unverified")

    def test_failed_pending_and_cancelled_checks_are_reported_once(self):
        for status, expected in (("failed", "failed"), ("pending", "PENDING"), ("cancelled", "cancelled")):
            with self.subTest(status=status):
                data = self.active_state()
                data["verification_status"] = status
                if status == "pending":
                    data["pending_checks"] = {"check-1": {"status": "pending"}}
                else:
                    data["verification_failure"] = {"reason": status}
                self.save_state(data)
                self.assertIn(expected, self.stop()[0]["reason"])
                self.assertEqual(self.stop()[0], {})
                self.assertEqual(self.read_state()["verification_status"], status)

    def test_legacy_flag_reset_does_not_repeat_the_task_warning(self):
        data = self.active_state()
        (self.repo / "src/app.py").write_text("value = 2\n", encoding="utf-8")
        self.save_state(data)
        self.assertIn("verification guard", self.stop()[0]["reason"])
        data = self.read_state()
        data["verification_guard_warned"] = False
        self.save_state(data)
        self.assertEqual(self.stop()[0], {})

    def test_guard_pass_does_not_reset_marker_budget(self):
        data = self.active_state()
        data["verification_status"] = "failed"
        self.save_state(data)
        payload = {**self.payload, "last_assistant_message": "<!-- high-agency:continue max=1 -->"}
        self.assertIn("failed", self.stop(payload)[0]["reason"])
        self.assertIn("1/1", self.stop(payload)[0]["reason"])
        self.assertEqual(self.stop(payload)[0], {})
        self.assertEqual(self.read_state()["continuation"]["continuations"], 1)

    def test_incomplete_snapshot_is_unverified_and_guards_still_exit(self):
        data = self.active_state()
        data["baseline_snapshot"]["base_ref"] = "missing-ref-for-test"
        data["verification_status"] = "passed"
        data["verification_snapshot"] = dict(data["baseline_snapshot"])
        self.save_state(data)
        first = self.stop()[0]
        self.assertIn("incomplete", first["reason"])
        self.assertIn("UNVERIFIED", first["reason"])
        # At most one verification warning and one focused-diff warning.
        for _ in range(3):
            result = self.stop()[0]
            if result == {}:
                break
        self.assertEqual(result, {})
        self.assertTrue(self.read_state()["task_completed"])
        self.assertEqual(self.read_state()["verification_status"], "unverified")

    def test_git_delta_and_ignored_native_edits_are_unioned(self):
        ignored = self.repo / "ignored.py"
        ignored.write_text("old\n", encoding="utf-8")
        before = file_fingerprint(self.repo, "ignored.py")
        data = self.active_state()
        data["native_files"] = {str(ignored): {"before": before, "current": before}}
        ignored.write_text("new\n", encoding="utf-8")
        (self.repo / "src/app.py").write_text("value = 2\n", encoding="utf-8")
        current = current_snapshot(data, self.repo)
        self.assertEqual(task_files(data, current, self.repo), ["ignored.py", "src/app.py"])

    def test_ignored_file_changed_after_verification_invalidates_evidence(self):
        ignored = self.repo / "ignored.py"
        ignored.write_text("old\n", encoding="utf-8")
        before = file_fingerprint(self.repo, "ignored.py")
        data = self.active_state()
        ignored.write_text("checked\n", encoding="utf-8")
        data["native_files"] = {str(ignored): {"before": before, "current": file_fingerprint(self.repo, "ignored.py")}}
        data["verification_snapshot"] = current_snapshot(data, self.repo)
        data["verification_status"] = "passed"
        self.save_state(data)
        ignored.write_text("changed again\n", encoding="utf-8")
        self.assertIn("verification guard", self.stop()[0]["reason"])
        self.assertEqual(self.read_state()["verification_status"], "unverified")

    def test_successful_matching_native_and_git_snapshot_allows_completion(self):
        ignored = self.repo / "ignored.py"
        ignored.write_text("old\n", encoding="utf-8")
        before = file_fingerprint(self.repo, "ignored.py")
        data = self.active_state()
        ignored.write_text("checked\n", encoding="utf-8")
        data["native_files"] = {str(ignored): {"before": before, "current": file_fingerprint(self.repo, "ignored.py")}}
        data["verification_snapshot"] = current_snapshot(data, self.repo)
        data["verification_status"] = "passed"
        self.save_state(data)
        self.assertEqual(self.stop()[0], {})

    def test_native_symlink_fingerprint_tracks_the_link_without_following_it(self):
        first = self.root / "first.py"
        second = self.root / "second.py"
        first.write_text("same contents\n", encoding="utf-8")
        second.write_text("same contents\n", encoding="utf-8")
        link = self.repo / "ignored.py"
        try:
            link.symlink_to(first)
        except (OSError, NotImplementedError) as exc:
            self.skipTest("Symlink creation unavailable: " + type(exc).__name__)
        before = file_fingerprint(self.repo, "ignored.py")
        data = self.active_state()
        data["native_files"] = {str(link): {"before": before, "current": before}}
        link.unlink()
        link.symlink_to(second)
        current = current_snapshot(data, self.repo)
        self.assertIn("symlink:", next(iter(current["native_files"].values())))
        self.assertEqual(task_files(data, current, self.repo), ["ignored.py"])

    def test_reverting_a_preexisting_dirty_file_remains_a_task_change(self):
        app = self.repo / "src/app.py"
        app.write_text("value = 9\n", encoding="utf-8")
        data = self.active_state()
        app.write_text("value = 1\n", encoding="utf-8")
        current = current_snapshot(data, self.repo)
        self.assertEqual(task_files(data, current, self.repo), ["src/app.py"])
        self.save_state(data)
        self.assertIn("verification guard", self.stop()[0]["reason"])

    def test_native_return_to_task_baseline_is_not_a_spurious_change(self):
        app = self.repo / "src/app.py"
        before = file_fingerprint(self.repo, "src/app.py")
        data = self.active_state()
        data["native_files"] = {str(app): {"before": before, "current": "outdated-after-edit"}}
        current = current_snapshot(data, self.repo)
        self.assertEqual(task_files(data, current, self.repo), [])
        self.save_state(data)
        self.assertEqual(self.stop()[0], {})

    def test_dot_github_workflow_keeps_high_impact_classification(self):
        self.assertEqual(rel(".github/workflows/ci.yml", self.repo), ".github/workflows/ci.yml")
        data = self.active_state()
        (self.repo / ".github/workflows/ci.yml").write_text("name: new\n", encoding="utf-8")
        data["verification_snapshot"] = current_snapshot(data, self.repo)
        data["verification_status"] = "passed"
        self.save_state(data)
        self.assertIn("high-impact/shared path", self.stop()[0]["reason"])

    def test_subagent_stop_cannot_complete_or_reset_parent(self):
        self.save_state(self.active_state())
        before = self.state_path().read_bytes()
        payload = {**self.payload, "agent_id": "late-child", "last_assistant_message": MARKER}
        self.assertEqual(self.stop(payload)[0], {})
        self.assertEqual(self.state_path().read_bytes(), before)

    def test_stop_from_unknown_prompt_cannot_complete_parent_task(self):
        data = self.active_state()
        data["prompt_ids"] = ["current-prompt"]
        self.save_state(data)
        before = self.state_path().read_bytes()
        self.assertEqual(self.stop({**self.payload, "prompt_id": "old-prompt"})[0], {})
        self.assertEqual(self.state_path().read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
