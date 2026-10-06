import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HOOKS = Path(__file__).resolve().parents[1] / "plugins" / "high-agency" / "hooks"
sys.path.insert(0, str(HOOKS))

import impact_scope  # noqa: E402
from impact_scope import (classify_drift, first_impact_from_transcript, module_key,
                          parse_impact, scope_metrics)  # noqa: E402


class ImpactScopeTests(unittest.TestCase):
    def test_parse_machine_readable_estimate(self):
        estimate = parse_impact(
            "Impact: local | files<=2 | modules<=1 | boundary=private"
        )

        self.assertEqual(
            estimate,
            {
                "tier": "local",
                "files_max": 2,
                "modules_max": 1,
                "boundary": "private",
                "raw": "Impact: local | files<=2 | modules<=1 | boundary=private",
            },
        )

    def test_oversized_numeric_fields_are_bounded_without_huge_integer_conversion(self):
        estimate = parse_impact("Impact: local | files<=" + "9" * 5000
                                + " | modules<=" + "0" * 5000 + "1 | boundary=private")
        self.assertEqual(estimate["files_max"], 999)
        self.assertEqual(estimate["modules_max"], 1)

    def test_first_estimate_is_immutable_baseline(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "transcript.jsonl"
            entries = [
                {
                    "message": {
                        "role": "assistant",
                        "content": [
                            {
                                "type": "text",
                                "text": "Impact: local | files<=2 | modules<=1 | boundary=private",
                            }
                        ],
                    }
                },
                {
                    "message": {
                        "role": "assistant",
                        "content": [
                            {
                                "type": "text",
                                "text": "Impact: high | files<=10 | modules<=4 | boundary=high-impact",
                            }
                        ],
                    }
                },
            ]
            path.write_text(
                "\n".join(json.dumps(entry) for entry in entries) + "\n",
                encoding="utf-8",
            )
            estimate = first_impact_from_transcript(str(path))
            self.assertEqual(estimate["tier"], "local")
            self.assertEqual(estimate["files_max"], 2)

    def test_generic_source_roots_measure_submodules(self):
        metrics = scope_metrics(["src/auth/token.py", "src/payments/api.py"])
        self.assertEqual(metrics["file_count"], 2)
        self.assertEqual(metrics["module_count"], 2)

    def test_dot_directories_are_not_normalized_into_different_modules(self):
        self.assertEqual(module_key(".github/workflows/ci.yml"), ".github")
        self.assertEqual(module_key("./.github/workflows/ci.yml"), ".github")
        self.assertEqual(module_key(".\\.github\\workflows\\ci.yml"), ".github")
        self.assertEqual(scope_metrics([".github/a.yml", "github/a.py"])["module_count"], 2)

    def test_latest_user_task_has_its_own_immutable_first_estimate(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "transcript.jsonl"
            entries = [
                {"role": "user", "content": "first task"},
                {"role": "assistant", "content": "Impact: high | files<=9 | modules<=4 | boundary=high-impact"},
                {"message": {"role": "user", "content": "second task"}},
                {"message": {"role": "assistant", "content": "Impact: local | files<=1 | modules<=1 | boundary=private"}},
                {"message": {"role": "user", "content": [{"type": "tool_result", "content": "test passed"}]}},
                {"message": {"role": "assistant", "content": "Impact: high | files<=8 | modules<=3 | boundary=high-impact"}},
            ]
            path.write_text("".join(json.dumps(item) + "\n" for item in entries), encoding="utf-8")
            estimate = first_impact_from_transcript(str(path))
            self.assertEqual(estimate["files_max"], 1)

    def test_byte_cursor_skips_prior_unicode_task_and_does_not_reuse_old_estimate(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "transcript.jsonl"
            old = json.dumps({"role": "assistant", "content": "이전 작업\nImpact: high | files<=9 | modules<=4 | boundary=high-impact"}, ensure_ascii=False) + "\n"
            path.write_bytes(old.encode("utf-8"))
            offset = path.stat().st_size
            self.assertGreater(offset, len(old))
            self.assertIsNone(first_impact_from_transcript(str(path), start_offset=offset))
            current = {"role": "assistant", "content": "Impact: local | files<=2 | modules<=1 | boundary=private"}
            with path.open("ab") as handle:
                handle.write((json.dumps(current) + "\n").encode("utf-8"))
            self.assertEqual(first_impact_from_transcript(str(path), start_offset=offset)["files_max"], 2)

    def test_explicit_task_cursor_keeps_first_estimate_across_user_continuations(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "transcript.jsonl"
            entries = [
                {"role": "user", "content": "current task"},
                {"role": "assistant", "content": "Impact: local | files<=1 | modules<=1 | boundary=private"},
                {"role": "user", "content": "Continue from the Stop hook."},
                {"role": "assistant", "content": "Impact: high | files<=100 | modules<=10 | boundary=high-impact"},
            ]
            path.write_text("".join(json.dumps(item) + "\n" for item in entries), encoding="utf-8")
            self.assertEqual(first_impact_from_transcript(str(path), start_offset=0)["files_max"], 1)
            self.assertEqual(first_impact_from_transcript(str(path))["files_max"], 100)

    def test_invalid_or_truncated_cursor_is_unknown(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "transcript.jsonl"
            path.write_text(json.dumps({"role": "assistant", "content": "Impact: local | files<=1 | modules<=1 | boundary=private"}) + "\n", encoding="utf-8")
            for offset in (-1, True, 1.5, "0", path.stat().st_size + 1):
                with self.subTest(offset=offset):
                    self.assertIsNone(first_impact_from_transcript(str(path), start_offset=offset))

    def test_cursor_inside_record_skips_to_next_complete_line(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "transcript.jsonl"
            entries = [
                {"role": "assistant", "content": "Impact: high | files<=9 | modules<=4 | boundary=high-impact"},
                {"role": "assistant", "content": "Impact: local | files<=2 | modules<=1 | boundary=private"},
            ]
            path.write_text("".join(json.dumps(item) + "\n" for item in entries), encoding="utf-8")
            self.assertEqual(first_impact_from_transcript(str(path), start_offset=1)["files_max"], 2)

    def test_rotation_identity_rejects_a_replacement_transcript(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "transcript.jsonl"
            path.write_text("old transcript\n", encoding="utf-8")
            info = path.stat()
            identity = {"device": info.st_dev, "inode": info.st_ino}
            path.rename(path.with_suffix(".old"))
            path.write_text(json.dumps({"role": "assistant", "content": "Impact: local | files<=1 | modules<=1 | boundary=private"}) + "\n", encoding="utf-8")
            self.assertIsNone(first_impact_from_transcript(str(path), start_offset=0, expected_identity=identity))

    def test_unfinished_jsonl_record_is_not_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "transcript.jsonl"
            text = json.dumps({"role": "assistant", "content": "Impact: local | files<=1 | modules<=1 | boundary=private"})
            path.write_text(text, encoding="utf-8")
            self.assertIsNone(first_impact_from_transcript(str(path), start_offset=0))
            with path.open("a", encoding="utf-8") as handle:
                handle.write("\n")
            self.assertEqual(first_impact_from_transcript(str(path), start_offset=0)["files_max"], 1)

    def test_capped_tail_needs_a_current_user_boundary_without_a_cursor(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "transcript.jsonl"
            filler = json.dumps({"role": "assistant", "content": "x" * 1024}) + "\n"
            impact = json.dumps({"role": "assistant", "content": "Impact: local | files<=1 | modules<=1 | boundary=private"}) + "\n"
            path.write_text(filler + impact, encoding="utf-8")
            with mock.patch.object(impact_scope, "MAX_TRANSCRIPT_BYTES", 512):
                self.assertIsNone(first_impact_from_transcript(str(path)))
                self.assertEqual(first_impact_from_transcript(str(path), start_offset=len(filler.encode("utf-8")))["files_max"], 1)
                prompt = json.dumps({"role": "user", "content": "current task"}) + "\n"
                path.write_text(filler + prompt + impact, encoding="utf-8")
                self.assertEqual(first_impact_from_transcript(str(path))["files_max"], 1)

    def test_prompt_marker_must_match_current_human_prompt(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "transcript.jsonl"
            entries = [
                {"uuid": "current-prompt", "message": {"role": "user", "content": "fix this"}},
                {"role": "assistant", "content": "Impact: local | files<=2 | modules<=1 | boundary=private"},
            ]
            path.write_text("".join(json.dumps(item) + "\n" for item in entries), encoding="utf-8")
            for marker in ("current-prompt", "fix this"):
                self.assertEqual(first_impact_from_transcript(str(path), prompt_marker=marker)["files_max"], 2)
            self.assertIsNone(first_impact_from_transcript(str(path), prompt_marker="previous-prompt"))

    def test_codex_envelope_is_supported_but_nested_tool_output_is_not_an_assistant(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "transcript.jsonl"
            entries = [
                {"type": "event_msg", "payload": {"type": "user_message", "message": "current task"}},
                {"type": "tool_result", "content": {"role": "assistant", "content": "Impact: high | files<=9 | modules<=4 | boundary=high-impact"}},
                {"type": "response_item", "payload": {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "Impact: local | files<=2 | modules<=1 | boundary=private"}]}},
            ]
            path.write_text("".join(json.dumps(item) + "\n" for item in entries), encoding="utf-8")
            self.assertEqual(first_impact_from_transcript(str(path))["files_max"], 2)

    def test_malformed_role_and_content_types_do_not_disrupt_valid_later_records(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "transcript.jsonl"
            entries = [
                {"message": {"role": [], "content": "bad role"}},
                {"role": "user", "content": [{"type": [], "text": "bad content"}]},
                {"role": "assistant", "content": "Impact: local | files<=2 | modules<=1 | boundary=private"},
            ]
            path.write_text("".join(json.dumps(item) + "\n" for item in entries), encoding="utf-8")
            self.assertEqual(first_impact_from_transcript(str(path))["files_max"], 2)

    def test_nonregular_transcript_is_rejected_before_open(self):
        if not hasattr(os, "mkfifo"):
            self.skipTest("FIFO is not supported")
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "pipe"
            os.mkfifo(path)
            with mock.patch.object(os, "open", side_effect=AssertionError("FIFO should not be opened")):
                self.assertIsNone(first_impact_from_transcript(str(path)))

    def test_minor_file_drift(self):
        estimate = parse_impact(
            "Impact: local | files<=2 | modules<=1 | boundary=private"
        )
        drift = classify_drift(
            estimate,
            ["src/auth/a.py", "src/auth/b.py", "src/auth/c.py"],
        )
        self.assertEqual(drift["severity"], "minor")

    def test_cross_module_underestimate_is_major(self):
        estimate = parse_impact(
            "Impact: local | files<=1 | modules<=1 | boundary=private"
        )
        drift = classify_drift(
            estimate,
            ["src/auth/a.py", "src/payments/b.py"],
        )
        self.assertEqual(drift["severity"], "major")
        self.assertTrue(any("modules" in reason for reason in drift["reasons"]))

    def test_unexpected_high_impact_boundary_is_major(self):
        estimate = parse_impact(
            "Impact: local | files<=2 | modules<=1 | boundary=private"
        )
        drift = classify_drift(
            estimate,
            ["src/auth/a.py"],
            high_impact=True,
        )
        self.assertEqual(drift["severity"], "major")
        self.assertTrue(any("boundary" in reason for reason in drift["reasons"]))

    def test_match_has_no_drift(self):
        estimate = parse_impact(
            "Impact: propagating | files<=4 | modules<=2 | boundary=shared-api"
        )
        drift = classify_drift(
            estimate,
            ["src/auth/a.py", "src/auth/b.py"],
        )
        self.assertEqual(drift["severity"], "none")


    def test_parse_impact_inside_unified_preflight(self):
        estimate = parse_impact(
            "Preflight: trace unfamiliar dependency path\n"
            "Complexity: medium\n"
            "Route: BROAD MAP\n"
            "Model: gpt-5.6-terra medium\n"
            "Impact: propagating | files<=4 | modules<=2 | boundary=private"
        )
        self.assertIsNotNone(estimate)
        self.assertEqual(estimate["tier"], "propagating")
        self.assertEqual(estimate["files_max"], 4)
        self.assertEqual(estimate["modules_max"], 2)
        self.assertEqual(estimate["boundary"], "private")


if __name__ == "__main__":
    unittest.main()
