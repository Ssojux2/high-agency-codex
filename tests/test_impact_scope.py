import json
import sys
import tempfile
import unittest
from pathlib import Path

HOOKS = Path(__file__).resolve().parents[1] / "plugins" / "high-agency" / "hooks"
sys.path.insert(0, str(HOOKS))

from impact_scope import classify_drift, first_impact_from_transcript, parse_impact, scope_metrics  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
