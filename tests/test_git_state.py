import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HOOKS = Path(__file__).resolve().parents[1] / "plugins" / "high-agency" / "hooks"
sys.path.insert(0, str(HOOKS))

from git_state import delta_files, snapshot, snapshots_equal  # noqa: E402


def run(cwd: Path, *args: str) -> None:
    subprocess.run(args, cwd=cwd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


class GitStateTests(unittest.TestCase):
    def make_repo(self):
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        run(root, "git", "init", "-q")
        run(root, "git", "config", "user.email", "test@example.com")
        run(root, "git", "config", "user.name", "High Agency Test")
        (root / "app.py").write_text("value = 1\n", encoding="utf-8")
        run(root, "git", "add", "app.py")
        run(root, "git", "commit", "-qm", "initial")
        return temp, root

    def test_shell_edit_is_detected(self):
        temp, root = self.make_repo()
        self.addCleanup(temp.cleanup)

        baseline = snapshot(root)
        (root / "app.py").write_text("value = 2\n", encoding="utf-8")
        current = snapshot(root, base_ref=baseline["base_ref"])

        self.assertEqual(delta_files(baseline, current), ["app.py"])

    def test_preexisting_dirty_file_detects_additional_edit(self):
        temp, root = self.make_repo()
        self.addCleanup(temp.cleanup)

        (root / "app.py").write_text("value = 2\n", encoding="utf-8")
        baseline = snapshot(root)
        (root / "app.py").write_text("value = 3\n", encoding="utf-8")
        current = snapshot(root, base_ref=baseline["base_ref"])

        self.assertEqual(delta_files(baseline, current), ["app.py"])

    def test_untracked_generator_output_is_detected(self):
        temp, root = self.make_repo()
        self.addCleanup(temp.cleanup)

        baseline = snapshot(root)
        (root / "generated.py").write_text("generated = True\n", encoding="utf-8")
        current = snapshot(root, base_ref=baseline["base_ref"])

        self.assertEqual(delta_files(baseline, current), ["generated.py"])

    def test_verification_snapshot_becomes_stale_after_shell_edit(self):
        temp, root = self.make_repo()
        self.addCleanup(temp.cleanup)

        baseline = snapshot(root)
        (root / "app.py").write_text("value = 2\n", encoding="utf-8")
        verified = snapshot(root, base_ref=baseline["base_ref"])
        self.assertTrue(snapshots_equal(verified, verified))

        (root / "app.py").write_text("value = 3\n", encoding="utf-8")
        current = snapshot(root, base_ref=baseline["base_ref"])

        self.assertFalse(snapshots_equal(verified, current))


if __name__ == "__main__":
    unittest.main()
