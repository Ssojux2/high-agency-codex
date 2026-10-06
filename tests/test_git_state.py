import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

HOOKS = Path(__file__).resolve().parents[1] / "plugins" / "high-agency" / "hooks"
sys.path.insert(0, str(HOOKS))

import git_state  # noqa: E402
from git_state import (delta_files, file_fingerprint, fingerprint_complete,
                       snapshot, snapshot_complete, snapshots_equal)  # noqa: E402


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

    @unittest.skipIf(os.name == "nt", "POSIX executable mode is required")
    def test_mode_change_invalidates_verification_even_when_content_is_unchanged(self):
        temp, root = self.make_repo()
        self.addCleanup(temp.cleanup)
        run(root, "git", "config", "core.filemode", "true")
        path = root / "app.py"
        path.write_text("value = 2\n", encoding="utf-8")
        verified = snapshot(root)
        path.chmod(path.stat().st_mode | 0o111)
        current = snapshot(root, base_ref=verified["base_ref"])
        self.assertEqual(delta_files(verified, current), ["app.py"])
        self.assertFalse(snapshots_equal(verified, current))

    def test_changing_rename_source_invalidates_verification(self):
        temp, root = self.make_repo()
        self.addCleanup(temp.cleanup)
        (root / "copy.py").write_bytes((root / "app.py").read_bytes())
        run(root, "git", "add", "copy.py")
        run(root, "git", "commit", "-qm", "duplicate source")
        run(root, "git", "mv", "app.py", "renamed.py")
        verified = snapshot(root)
        run(root, "git", "restore", "--source=HEAD", "--staged", "--worktree", "app.py")
        run(root, "git", "rm", "copy.py")
        current = snapshot(root, base_ref=verified["base_ref"])
        self.assertEqual(verified["files"]["renamed.py"], current["files"]["renamed.py"])
        self.assertIn("app.py", verified["files"])
        self.assertIn("copy.py", current["files"])
        self.assertEqual(delta_files(verified, current), ["app.py", "copy.py"])
        self.assertFalse(snapshots_equal(verified, current))

    def test_identical_commits_in_different_repositories_are_not_equal(self):
        temp, root = self.make_repo()
        self.addCleanup(temp.cleanup)
        clone_temp = tempfile.TemporaryDirectory()
        self.addCleanup(clone_temp.cleanup)
        clone = Path(clone_temp.name) / "clone"
        run(root, "git", "clone", "-q", str(root), str(clone))
        left, right = snapshot(root), snapshot(clone)
        self.assertEqual(left["base_ref"], right["base_ref"])
        self.assertFalse(snapshots_equal(left, right))
        self.assertEqual(delta_files(left, right), [])

    def test_git_nonzero_and_timeout_are_incomplete_not_clean(self):
        temp, root = self.make_repo()
        self.addCleanup(temp.cleanup)
        original = git_state._run
        for failure in ("nonzero", "timeout", "partial_output"):
            def failing(cwd, args, **kwargs):
                if args[0] == "diff":
                    if failure == "timeout":
                        raise subprocess.TimeoutExpired("git", 1)
                    return subprocess.CompletedProcess(
                        ["git", *args], 128 if failure == "nonzero" else 0,
                        stdout=b"" if failure == "nonzero" else b"app.py", stderr=b"",
                    )
                return original(cwd, args, **kwargs)
            with self.subTest(failure=failure), mock.patch.object(git_state, "_run", side_effect=failing):
                current = snapshot(root)
                self.assertFalse(current["available"])
                self.assertFalse(snapshot_complete(current))
                self.assertFalse(snapshots_equal(current, current))

    def test_untracked_listing_failure_preserves_known_paths_but_not_validity(self):
        temp, root = self.make_repo()
        self.addCleanup(temp.cleanup)
        (root / "app.py").write_text("value = 2\n", encoding="utf-8")
        original = git_state._run
        def failing(cwd, args, **kwargs):
            if args[0] == "ls-files":
                return subprocess.CompletedProcess(["git", *args], 1, stdout=b"", stderr=b"")
            return original(cwd, args, **kwargs)
        with mock.patch.object(git_state, "_run", side_effect=failing):
            current = snapshot(root)
        self.assertIn("app.py", current["files"])
        self.assertEqual(current["error"], "git_untracked_failed")
        self.assertFalse(snapshots_equal(current, current))

    def test_truncated_snapshots_never_prove_equality(self):
        temp, root = self.make_repo()
        self.addCleanup(temp.cleanup)
        (root / "one.py").write_text("1\n", encoding="utf-8")
        (root / "two.py").write_text("2\n", encoding="utf-8")
        with mock.patch.object(git_state, "MAX_PATHS", 1):
            current = snapshot(root)
        self.assertTrue(current["truncated"])
        self.assertEqual(len(current["files"]), 1)
        self.assertFalse(current["available"])
        self.assertFalse(snapshots_equal(current, current))

    def test_fingerprint_errors_are_not_stable_evidence(self):
        temp, root = self.make_repo()
        self.addCleanup(temp.cleanup)
        (root / "app.py").write_text("value = 2\n", encoding="utf-8")
        with mock.patch.object(git_state, "file_fingerprint", return_value="error:PermissionError"):
            current = snapshot(root)
        self.assertEqual(current["error"], "fingerprint_incomplete")
        self.assertFalse(snapshots_equal(current, current))
        self.assertFalse(fingerprint_complete("error:PermissionError"))
        with mock.patch.object(Path, "lstat", side_effect=PermissionError):
            self.assertFalse(fingerprint_complete(file_fingerprint(root, "app.py")))

    def test_broken_symlink_is_fingerprinted_without_following_its_target(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            link = root / "link"
            try:
                link.symlink_to("absent-a")
            except (OSError, NotImplementedError):
                self.skipTest("symlink creation is not supported")
            first = file_fingerprint(root, "link")
            self.assertTrue(fingerprint_complete(first))
            self.assertTrue(first.startswith("symlink:"))
            (root / "absent-a").write_text("new target", encoding="utf-8")
            self.assertEqual(first, file_fingerprint(root, "link"))
            link.unlink()
            link.symlink_to("absent-b")
            self.assertNotEqual(first, file_fingerprint(root, "link"))

    def test_special_file_is_incomplete_without_opening_it(self):
        if not hasattr(os, "mkfifo"):
            self.skipTest("FIFO is not supported")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            os.mkfifo(root / "pipe")
            self.assertEqual(file_fingerprint(root, "pipe"), "error:unsupported_file_type")

    def test_oversized_file_is_incomplete_without_reading_gigabytes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / "large.bin"
            with path.open("wb") as handle:
                handle.truncate(git_state.MAX_FILE_BYTES + 1)
            with mock.patch.object(os, "open", side_effect=AssertionError("oversized file should not be opened")):
                self.assertEqual(file_fingerprint(root, path.name), "error:fingerprint_byte_limit")

    def test_expired_fingerprint_deadline_is_incomplete(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "file.py").write_text("value = 1\n", encoding="utf-8")
            self.assertEqual(file_fingerprint(root, "file.py", deadline=time.monotonic() - 1),
                             "error:fingerprint_time_limit")

    def test_snapshot_has_a_shared_hash_byte_budget(self):
        temp, root = self.make_repo()
        self.addCleanup(temp.cleanup)
        (root / "one.py").write_text("11", encoding="utf-8")
        (root / "two.py").write_text("22", encoding="utf-8")
        with mock.patch.object(git_state, "MAX_SNAPSHOT_BYTES", 3):
            current = snapshot(root)
        self.assertEqual(set(current["files"]), {"one.py", "two.py"})
        self.assertFalse(snapshot_complete(current))
        self.assertIn("error:fingerprint_byte_limit", current["files"].values())

    def test_path_and_fd_change_times_may_differ_without_invalidating_a_file(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / "file.py"
            path.write_text("initial\n", encoding="utf-8")
            path.write_text("rewritten content\n", encoding="utf-8")
            expected = file_fingerprint(root, path.name)
            self.assertTrue(fingerprint_complete(expected))
            original = os.fstat
            def windows_fstat(fd):
                info = original(fd)
                fields = {key: getattr(info, key) for key in
                          ("st_dev", "st_ino", "st_mode", "st_size", "st_mtime_ns", "st_ctime_ns")}
                fields["st_ctime_ns"] += 123456
                return SimpleNamespace(**fields)
            with mock.patch.object(os, "fstat", side_effect=windows_fstat):
                self.assertEqual(file_fingerprint(root, path.name), expected)

    def test_native_fingerprints_participate_in_snapshot_validity_and_equality(self):
        temp, root = self.make_repo()
        self.addCleanup(temp.cleanup)
        current = snapshot(root)
        native = str(root / "ignored.py")
        before = {**current, "native_files": {native: "missing"}}
        after = {**current, "native_files": {native: file_fingerprint(root, "app.py")}}
        self.assertFalse(snapshots_equal(before, after))
        self.assertTrue(snapshots_equal(after, after))
        failed = {**current, "native_files": {native: "error:PermissionError"}}
        self.assertFalse(snapshots_equal(failed, failed))

    def test_legacy_complete_flag_is_optional_but_identity_and_completeness_are_not(self):
        temp, root = self.make_repo()
        self.addCleanup(temp.cleanup)
        legacy = snapshot(root)
        legacy.pop("complete")
        self.assertTrue(snapshots_equal(legacy, legacy))
        for changes in ({"complete": False}, {"truncated": True}, {"root": None}):
            incomplete = {**legacy, **changes}
            self.assertFalse(snapshots_equal(incomplete, incomplete))


if __name__ == "__main__":
    unittest.main()
