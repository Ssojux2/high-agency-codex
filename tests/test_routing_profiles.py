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

    def test_unified_preflight_drives_route_and_model(self):
        text = SKILL.read_text(encoding="utf-8")
        self.assertIn("## Unified preflight", text)
        self.assertIn("before the first code/config mutation", text)
        self.assertIn("write exactly one compact five-line preflight block", text)
        for field in ("Preflight:", "Complexity:", "Route:", "Model:", "Impact:"):
            self.assertIn(field, text)
        self.assertIn("Derive all five lines from the **same inspection**", text)
        self.assertIn("Do not summarize first and then independently reconsider routing", text)
        for route in ("DIRECT", "CHEAP DELEGATE", "BROAD MAP", "WORKHORSE", "STRONG REASONING"):
            self.assertIn(route, text)
        for model in ("gpt-5.6-luna", "gpt-5.6-terra", "gpt-5.6-sol", "gpt-6-astra"):
            self.assertIn(model, text)

    def test_routing_requires_native_dispatch_matching_preflight(self):
        skill = SKILL.read_text(encoding="utf-8")
        routing = ROUTING.read_text(encoding="utf-8")
        self.assertIn("spawn the selected native Codex subagent", skill)
        self.assertIn("actual spawn request must match the preflight `Model:` line", skill)
        self.assertIn("Merely saying that Astra/Sol/Terra/Luna should be used is not execution", skill)
        self.assertIn("counts as executed only when the delegated subagent was actually spawned", routing)

    def test_original_impact_line_remains_immutable(self):
        text = SKILL.read_text(encoding="utf-8")
        self.assertIn("The first `Impact:` line is immutable", text)
        self.assertIn("do not emit a replacement preflight", text)

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

    def test_delegation_is_shallow_and_bounded(self):
        text = ROUTING.read_text(encoding="utf-8")
        self.assertIn("at most 2 concurrent delegated agents", text)
        self.assertIn("Child agents should not recursively spawn", text)

    def test_handoff_packet_is_compact(self):
        text = ROUTING.read_text(encoding="utf-8")
        for field in ("Goal", "Relevant evidence", "Constraints", "Expected return", "Stop condition"):
            self.assertIn(field, text)


if __name__ == "__main__":
    unittest.main()
