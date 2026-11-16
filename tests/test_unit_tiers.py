import unittest

from test_unit_skill import DELEGATE, DIRECTION, ROUTING, UNIT


class UnitTierTests(unittest.TestCase):
    def test_unit_skill_defines_four_tiers_and_names_them_in_the_report(self):
        text = UNIT.read_text(encoding="utf-8")
        for tier in ("T1 mechanical", "T2 standard", "T3 hard", "T4 frontier"):
            self.assertIn(tier, text)
        self.assertLess(text.index("## Difficulty tier"), text.index("## Playbooks"))
        self.assertIn("Unit: <one line: what changed> [T1–T4]", text)
        self.assertIn("stays on the main thread whatever its tier", text)

    def test_routing_maps_tiers_to_codex_families_and_existing_routes(self):
        text = ROUTING.read_text(encoding="utf-8")
        section = text[text.index("### Unit tiers"):text.index("### Testing / verification")]
        for needle in ("Luna / low", "Sol / medium", "Sol / high", "Astra / high–xhigh",
                       "`reasoning_effort`", "Astra never writes code", "unrouted"):
            self.assertIn(needle, section)
        for route in ("CHEAP DELEGATE", "WORKHORSE", "STRONG REASONING"):
            self.assertIn(route, section)
        self.assertIn("Never run two tiers on the same question", section)
        for claude_only in ("Sonnet", "Opus", "Fable", "Haiku"):
            self.assertNotIn(claude_only, section)

    def test_direction_and_delegate_brief_reference_tiers(self):
        self.assertIn("Unit tiers", DIRECTION.read_text(encoding="utf-8"))
        brief = DELEGATE.read_text(encoding="utf-8")
        self.assertIn("Tier: <T1–T4>", brief)
        self.assertIn("harder than its tier", brief)


if __name__ == "__main__":
    unittest.main()
