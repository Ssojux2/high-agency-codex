import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCTOR = ROOT / "plugins/high-agency/skills/high-agency-doctor/SKILL.md"
ROUTING = ROOT / "plugins/high-agency/skills/high-agency-coding/references/model-routing.md"


class CodexDoctorContractTests(unittest.TestCase):
    def test_doctor_is_read_only_and_safe(self):
        text = DOCTOR.read_text(encoding="utf-8")
        self.assertIn("Do not edit project files", text)
        self.assertIn("Do **not** print the full config file", text)
        self.assertIn("UNVERIFIED", text)

    def test_doctor_checks_routing_blockers(self):
        text = DOCTOR.read_text(encoding="utf-8")
        self.assertIn("agents.enabled", text)
        self.assertIn("allow_managed_hooks_only", text)
        self.assertIn("default_subagent_model", text)
        self.assertIn("hook trust", text)

    def test_model_probes_are_opt_in(self):
        text = DOCTOR.read_text(encoding="utf-8")
        self.assertIn("Only if the user explicitly asks to probe models", text)

    def test_explicit_fallbacks_exist(self):
        text = ROUTING.read_text(encoding="utf-8")
        for fragment in (
            "gpt-5.6-luna",
            "gpt-5.6-terra",
            "gpt-5.6-sol",
            "gpt-6-astra",
            "current main model",
        ):
            self.assertIn(fragment, text)
        self.assertIn("Explicit fallback chains", text)


if __name__ == "__main__":
    unittest.main()
