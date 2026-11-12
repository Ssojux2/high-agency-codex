import unittest

from test_unit_skill import DELEGATE, DIRECTION, AUTONOMY, UNIT

FLOW = DIRECTION.parent / "references/branch-and-pr.md"


class BranchAndPrTests(unittest.TestCase):
    def test_direction_links_flow_and_branches_before_activation(self):
        text = DIRECTION.read_text(encoding="utf-8")
        self.assertIn("references/branch-and-pr.md", text)
        self.assertLess(text.index("## Feature branch and PR"), text.index("## Activate verification"))
        finish = text[text.index("## Finish"):]
        self.assertIn("branch-and-pr", finish)
        self.assertIn("PR URL", finish)

    def test_flow_keeps_git_actions_safe(self):
        text = FLOW.read_text(encoding="utf-8")
        for required in (
            "before `verification_state.py --activate`",
            "Never `git add -A`",
            "Never push to the default branch",
            "--no-verify",
            "--draft",
            "Do not merge",
            "## Why",
            "## Verification",
        ):
            self.assertIn(required, text)
        self.assertIn("Do not stash, reset, or discard them", text)

    def test_only_the_main_thread_runs_git(self):
        self.assertIn("never switches branches, commits, pushes, or opens a PR", UNIT.read_text(encoding="utf-8"))
        delegate = DELEGATE.read_text(encoding="utf-8")
        self.assertRegex(delegate, r"[Dd]o not switch branches, commit, push")

    def test_bounded_autonomy_commits_per_pass_and_opens_pr_once(self):
        text = AUTONOMY.read_text(encoding="utf-8")
        self.assertIn("commit the verified unit", text)
        self.assertIn("open the PR only once", text)


if __name__ == "__main__":
    unittest.main()
