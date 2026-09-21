import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "plugins/high-agency/skills/high-agency-coding/SKILL.md"
ROUTING = ROOT / "plugins/high-agency/skills/high-agency-coding/references/model-routing.md"


class RoutingPolicyTests(unittest.TestCase):
    def test_core_is_single_agent_first_and_progressive(self):
        text = SKILL.read_text(encoding="utf-8")
        self.assertIn("Start single-agent with the current model", text)
        self.assertIn("read `references/model-routing.md`", text)

    def test_openai_model_tiers_are_present(self):
        text = ROUTING.read_text(encoding="utf-8")
        for model in (
            "gpt-6-astra",
            "gpt-5.6-sol",
            "gpt-5.6-terra",
            "gpt-5.6-luna",
        ):
            self.assertIn(model, text)

    def test_reasoning_tiers_are_present(self):
        text = ROUTING.read_text(encoding="utf-8")
        for effort in ("low", "medium", "high", "xhigh", "max"):
            self.assertRegex(text, rf"\b{re.escape(effort)}\b")

    def test_nested_codex_exec_is_discouraged(self):
        text = ROUTING.read_text(encoding="utf-8")
        self.assertIn("Do **not** launch nested `codex exec`", text)


if __name__ == "__main__":
    unittest.main()
