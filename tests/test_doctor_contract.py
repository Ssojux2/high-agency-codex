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
        for fragment in ("Luna", "Terra", "Sol", "Astra", "current main model"):
            self.assertIn(fragment, text)
        self.assertIn("Explicit fallback chains", text)
        self.assertIn("current catalog", text)

    def test_catalog_lookup_is_not_a_model_probe(self):
        text = DOCTOR.read_text(encoding="utf-8")
        self.assertIn("model_catalog.py", text)
        self.assertIn("metadata query, not an inference/model probe", text)
        self.assertIn("failed lookup is **UNVERIFIED**", text)

    def test_doctor_separates_catalog_and_dispatch_evidence(self):
        text = DOCTOR.read_text(encoding="utf-8")
        for field in ("query_status", "freshness_status", "entitlement_status", "dispatch_status", "selection_status"):
            self.assertIn(field, text)
        self.assertIn("routing_observer.py --report --session-id", text)
        self.assertIn("common hook `model` describes the parent", text)
        self.assertIn("unsupported", text)
        self.assertIn("Python 3.10+", text)


if __name__ == "__main__":
    unittest.main()
