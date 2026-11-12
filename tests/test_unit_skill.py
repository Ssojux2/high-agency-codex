import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "plugins/high-agency/skills"
UNIT = SKILLS / "high-agency-unit/SKILL.md"
DIRECTION = SKILLS / "high-agency-coding/SKILL.md"
AUTONOMY = SKILLS / "bounded-autonomy/SKILL.md"
ROUTING = SKILLS / "high-agency-coding/references/model-routing.md"
REPORT_FIELDS = ("Unit:", "Files:", "Check:", "Cut:", "Open:")


def frontmatter(path: Path) -> dict[str, str]:
    match = re.match(r"---\n(.*?)\n---\n", path.read_text(encoding="utf-8"), re.S)
    if not match:
        raise AssertionError(f"missing frontmatter: {path}")
    return dict(
        (key.strip(), value.strip())
        for key, value in (line.split(":", 1) for line in match.group(1).splitlines() if ":" in line)
    )


class UnitSkillTests(unittest.TestCase):
    def test_every_skill_has_matching_name_and_description(self):
        for path in SKILLS.glob("*/SKILL.md"):
            data = frontmatter(path)
            self.assertEqual(data.get("name"), path.parent.name)
            self.assertTrue(data.get("description"))

    def test_unit_skill_stays_compact_and_complete(self):
        text = UNIT.read_text(encoding="utf-8")
        self.assertLessEqual(len(text.splitlines()), 150)
        for heading in ("### Feature", "### Bug fix", "### Refactor", "## Boundaries",
                        "## Over-implementation checklist", "## Unit report"):
            self.assertIn(heading, text)
        for item in ("no current caller sets", "one caller or one implementation",
                     "inside trusted internal code", "Compatibility shim", "nobody requested",
                     "narrates", "private helper"):
            self.assertIn(item, text)
        for field in REPORT_FIELDS:
            self.assertIn(field, text)

    def test_unit_skill_defers_to_direction_budgets(self):
        text = UNIT.read_text(encoding="utf-8")
        self.assertIn("adds no plan document, mandatory TDD cycle, subagent fan-out, or review stage", text)
        self.assertIn("Run once, retest once, vary the data", text)
        self.assertIn("never widens outcome, budget, or verification scope", text)
        self.assertNotIn("Run once, retest once, vary the data", text.split("## Playbooks", 1)[1])

    def test_direction_links_to_unit_and_keeps_its_own_rules(self):
        text = DIRECTION.read_text(encoding="utf-8")
        self.assertIn("(../high-agency-unit/SKILL.md)", text)
        self.assertIn("## Direction and unit handoff", text)
        self.assertIn("Acceptance criteria", text)
        self.assertIn("ask one focused question", text)
        self.assertIn("### Run once, retest once, vary the data", text)
        self.assertNotIn("## Coding discipline", text)
        self.assertLess(len(text.splitlines()), 195)

    def test_markdown_links_between_layers_resolve(self):
        for path in (UNIT, DIRECTION, UNIT.parent / "references/unit-craft.md",
                     DIRECTION.parent / "references/coding-principles.md"):
            for target in re.findall(r"\]\((?!https?:|#)([^)#]+)", path.read_text(encoding="utf-8")):
                self.assertTrue((path.parent / target).exists(), f"{path}: {target}")

    def test_bounded_autonomy_composes_with_unit(self):
        self.assertIn("`high-agency-unit`", AUTONOMY.read_text(encoding="utf-8"))

    def test_delegated_writer_follows_unit_skill(self):
        self.assertIn("`high-agency-unit`", ROUTING.read_text(encoding="utf-8"))
        text = DELEGATE.read_text(encoding="utf-8")
        self.assertIn("high-agency-unit", text)
        self.assertIn("over-implementation checklist", text)
        for field in DELEGATE_FIELDS:
            self.assertIn(field, text)


DELEGATE = ROUTING
DELEGATE_FIELDS = ("Outcome:", "Budget:", "Scope of proof:", "Unit / Files / Check / Cut / Open")

if __name__ == "__main__":
    unittest.main()
