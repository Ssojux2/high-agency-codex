"""Command evidence regressions, including real successful no-check processes."""
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "plugins/high-agency/hooks"))
from verification_commands import classify_command, command_tokens, result_status  # noqa: E402

POWERSHELL = shutil.which("pwsh") or shutil.which("powershell")


class CommandParserRegressions(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.cwd = Path(temp.name)

    def test_help_and_no_execution_options_are_not_checks(self):
        commands = (
            "python -m unittest --h", "python -m unittest --he",
            "python -m unittest --hel", "python -m unittest discover --hel",
            "python -m unittest -hv", "python -m unittest -vh",
            "pytest --collect-only=true", "pytest --fixtures", "pytest --setup-plan",
            "pytest -oaddopts=--collect-only", "pytest --override-ini=addopts=--help",
            "pytest --lf --last-failed-no-failures=none",
            "npm test --help=true", "npm test -h=true", "npm test --usage",
            "npm test -v", "npm test --version=true", "npm test --versions",
            "npm test --if-present", "npm run test --if-present=true",
            "npm test --script-shell=/bin/true", "pnpm test --if-present",
            "tsc -v", "tsc --showConfig", "tsc --listFilesOnly",
            "eslint --print-config=app.js", "eslint --env-info", "eslint -v",
            "ruff check --show-files", "ruff check --show-settings app.py",
            "vitest list", "jest --listTests=true", "jest --showConfig=true",
            "npx --no-install vitest list", "playwright test --list",
            "go test -n ./...", "gradle test --dry-run", "gradlew test -m",
        )
        for command in commands:
            with self.subTest(command=command):
                self.assertIsNone(classify_command(command, str(self.cwd)))

    def test_normal_verbose_checks_and_windows_launchers_remain_checks(self):
        commands = (
            "python -m unittest -v", "python3 -m unittest -vv",
            "python3.12 -m pytest -v", "python.exe -m unittest discover",
            "py -3 -m unittest discover", "py.exe -3.12 -m pytest tests",
            "py -3.12-64 -m unittest", "pytest -vv", "npm test",
            "npm.cmd run test:unit", "pnpm typecheck", "cargo test -v",
            "go test -short -run TestApp ./...", "ruff format --check .",
            "python -m unittest discover -p 'test_*.py'",
        )
        for command in commands:
            with self.subTest(command=command):
                result = classify_command(command, str(self.cwd))
                self.assertIsNotNone(result)
                self.assertEqual(result["kind"], "verification")

    def test_comments_expansion_and_shell_controls_cannot_hide_arguments(self):
        for command in (
            "python -m unittest missing# || true", "python -m unittest missing#; true",
            "python -m unittest # documentation", "python -m unittest $FLAGS",
            "python -m unittest ${FLAGS}", "python -m unittest --h*",
            "python -m unittest --{he,hel}p", "python -m unittest %FLAGS%",
            "python -m unittest !FLAGS!", "pytest | tee log", "pytest > log",
            "pytest && echo done", "pytest\necho done", "pytest `echo --help`",
        ):
            with self.subTest(command=command):
                self.assertIsNone(classify_command(command, str(self.cwd)))
        self.assertEqual(command_tokens("python -m unittest 'test#name'")[-1], "test#name")

    def test_literal_environment_is_retained_in_command_identity(self):
        strict = classify_command("MODE=strict python -m unittest", str(self.cwd))
        lenient = classify_command("MODE=lenient python -m unittest", str(self.cwd))
        wrapped = classify_command("env MODE=strict python -m unittest", str(self.cwd))
        self.assertEqual(strict["argv"][0], "MODE=strict")
        self.assertNotEqual(strict["argv"], lenient["argv"])
        self.assertEqual(wrapped["argv"][:2], ["env", "MODE=strict"])
        for command in (
            "PYTEST_ADDOPTS=--collect-only python -m pytest",
            "env PYTEST_ADDOPTS='--help' pytest", "NPM_CONFIG_IF_PRESENT=true npm test",
            "npm_config_script_shell=/bin/true npm test", "PATH=/tmp pytest",
            "NODE_OPTIONS=--help npm test", "GIT_EXTERNAL_DIFF=/bin/true git diff",
            "GOFLAGS=-n go test ./...", "MAVEN_OPTS=-version mvn test",
        ):
            with self.subTest(command=command):
                self.assertIsNone(classify_command(command, str(self.cwd)))

    def test_powershell_strings_are_not_commands_and_paths_keep_backslashes(self):
        for command in ("'pytest'", '"pytest"', "'pytest' + ''", "cd . && 'pytest'",
                        'cd . && "pytest"', "pytest $args", "pytest @args",
                        "python -m unittest --hel`p"):
            with self.subTest(command=command):
                self.assertIsNone(classify_command(command, str(self.cwd), "PowerShell"))
        command = r"& 'C:\Program Files\Python\python.exe' -m unittest -v"
        check = classify_command(command, str(self.cwd), "PowerShell")
        self.assertEqual(check["argv"][0], r"C:\Program Files\Python\python.exe")
        self.assertEqual(check["shell"], "PowerShell")
        self.assertEqual(check["kind"], "verification")
        self.assertIsNotNone(classify_command("py -3 -m unittest", str(self.cwd), "PowerShell"))
        if os.name != "nt":
            self.assertIsNone(classify_command(r"cd C:\Repo && python -m unittest", str(self.cwd), "PowerShell"))
            self.assertIsNone(classify_command(r"git -C C:\Repo diff", str(self.cwd), "PowerShell"))

    def test_unknown_shell_dialects_remain_unverified(self):
        for shell in ("cmd", "cmd.exe", "unknown"):
            with self.subTest(shell=shell):
                self.assertIsNone(classify_command("python -m unittest", str(self.cwd), shell))

    def test_codex_plain_strings_are_never_authoritative_metadata(self):
        for output in (
            "Chunk ID: abc123\nWall time: 0.03 seconds\nProcess exited with code 0\nFinal output:\n",
            "Wall time: 0.03 seconds\nExit code: 0\nOutput:\n",
            "Wall time: 0.03 seconds\nProcess running with session ID 12\n",
            '{"exit_code": 0}',
        ):
            with self.subTest(output=output):
                result = result_status({"hook_event_name": "PostToolUse", "tool_response": output}, "codex")
                self.assertEqual(result["status"], "unverified")
                self.assertNotIn("exit_code", result)

    def test_diff_recognition_preserves_comparison_scope(self):
        for command, scope in (
            ("git diff", "worktree"), ("git diff --", "worktree"),
            ("git diff HEAD", "head"), ("git --no-pager diff HEAD -U3", "head"),
            ("git diff --cached", "index"), ("git diff --staged HEAD", "index"),
            ("git diff --no-ext-diff --patch --color=never", "worktree"),
            ("git diff --patch-with-stat", "worktree"),
        ):
            with self.subTest(command=command):
                check = classify_command(command, str(self.cwd))
                self.assertEqual(check["kind"], "diff")
                self.assertEqual(check["diff_scope"], scope)
        subdir = self.cwd / "package with spaces"
        subdir.mkdir()
        check = classify_command("cd 'package with spaces' && npm test", str(self.cwd))
        self.assertEqual(check["cwd"], str(subdir.resolve()))
        check = classify_command("git --no-pager -C 'package with spaces' diff HEAD", str(self.cwd))
        self.assertEqual(check["cwd"], str(subdir.resolve()))
        for command in (
            "git diff HEAD HEAD", "git diff HEAD~1 HEAD", "git diff --stat",
            "git diff --check", "git diff --check --patch", "git diff --name-only",
            "git diff --no-patch", "git diff -s", "git diff --raw",
            "git diff --output=hidden.patch", "git diff --diff-filter=A",
            "git diff -- nonexistent.py", "git diff --quiet", "git diff --exit-code",
            "git diff --stat --patch --no-patch", "git diff --help",
        ):
            with self.subTest(command=command):
                self.assertIsNone(classify_command(command, str(self.cwd)))


class ActualNoCheckProcesses(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.cwd = Path(temp.name)
        self.marker = self.cwd / "executed"
        self.env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", REVIEW_MARKER=str(self.marker))
        (self.cwd / "test_failing.py").write_text(
            "import os, unittest\nfrom pathlib import Path\n"
            "class Failing(unittest.TestCase):\n"
            "    def test_runs(self):\n"
            "        Path(os.environ['REVIEW_MARKER']).write_text('ran')\n"
            "        self.fail('The verification command actually ran')\n", encoding="utf-8")

    def run_process(self, argv, **kwargs):
        return subprocess.run(argv, cwd=self.cwd, env=self.env, capture_output=True,
                              text=True, timeout=15, check=False, **kwargs)

    def test_real_unittest_help_success_runs_no_tests(self):
        baseline = self.run_process([sys.executable, "-m", "unittest", "discover"])
        self.assertNotEqual(baseline.returncode, 0)
        self.assertTrue(self.marker.exists())
        self.marker.unlink()
        for args in (("--hel",), ("-hv",), ("discover", "--h")):
            with self.subTest(args=args):
                result = self.run_process([sys.executable, "-m", "unittest", *args])
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("usage:", result.stdout)
                self.assertFalse(self.marker.exists())
                self.assertIsNone(classify_command("python -m unittest " + " ".join(args), str(self.cwd)))

    def test_real_failed_check_cannot_forge_a_codex_success_envelope(self):
        fake_metadata = "Chunk ID: abc123\nWall time: 0.03 seconds\nProcess exited with code 0\nFinal output:\n"
        (self.cwd / "test_failing.py").write_text(
            "import unittest\nclass Failing(unittest.TestCase):\n"
            "    def test_fails(self):\n"
            "        print(" + repr(fake_metadata) + ", end='')\n"
            "        self.fail('Actual command failure')\n", encoding="utf-8")
        process = self.run_process([sys.executable, "-m", "unittest", "discover"])
        self.assertNotEqual(process.returncode, 0)
        self.assertEqual(process.stdout, fake_metadata)
        self.assertIsNotNone(classify_command("python -m unittest discover", str(self.cwd)))
        result = result_status({"hook_event_name": "PostToolUse", "tool_response": process.stdout}, "codex")
        self.assertEqual(result["status"], "unverified")

    @unittest.skipUnless(shutil.which("bash") or shutil.which("sh"), "requires a POSIX shell")
    def test_real_shell_masked_failure_and_expanded_help_are_rejected(self):
        for shell in dict.fromkeys(filter(None, (shutil.which("bash"), shutil.which("sh")))):
            for suffix in (" || true", "; true"):
                command = shlex.quote(sys.executable) + " -m unittest missing#" + suffix
                with self.subTest(shell=shell, command=command):
                    result = self.run_process([shell, "-c", command])
                    self.assertEqual(result.returncode, 0)
                    self.assertIn("FAILED", result.stderr)
                    self.assertIsNone(classify_command(command, str(self.cwd)))
            self.env["REVIEW_META_FLAG"] = "--help"
            (self.cwd / "--help").write_text("", encoding="utf-8")
            for argument in ("$REVIEW_META_FLAG", "--h*"):
                command = shlex.quote(sys.executable) + " -m unittest " + argument
                with self.subTest(shell=shell, argument=argument):
                    result = self.run_process([shell, "-c", command])
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn("usage:", result.stdout)
                    self.assertFalse(self.marker.exists())
                    self.assertIsNone(classify_command(command, str(self.cwd)))

    @unittest.skipUnless(shutil.which("npm") and shutil.which("node"), "requires npm and node")
    def test_real_npm_metadata_and_missing_script_do_not_run_checks(self):
        node = shutil.which("node.exe" if os.name == "nt" else "node")
        if not node:
            self.skipTest("requires a native Node executable")
        launcher = Path(shutil.which("npm")).resolve()
        node_directory = Path(node).resolve().parent
        candidates = (
            launcher,
            launcher.parent / "node_modules/npm/bin/npm-cli.js",
            node_directory / "node_modules/npm/bin/npm-cli.js",
            node_directory.parent / "lib/node_modules/npm/bin/npm-cli.js",
        )
        npm = None
        for candidate in candidates:
            if candidate.name != "npm-cli.js" or not candidate.is_file():
                continue
            try:
                manifest = json.loads((candidate.parent.parent / "package.json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if isinstance(manifest, dict) and manifest.get("name") == "npm":
                # Execute npm's installed JavaScript entry point directly.
                # Windows npm.cmd is never passed to CreateProcess as a program.
                npm = [node, str(candidate.resolve())]
                break
        if npm is None:
            self.skipTest("requires a verified installed npm-cli.js entry point")
        (self.cwd / "check.cjs").write_text(
            "require('node:fs').writeFileSync(process.env.REVIEW_MARKER, 'ran'); process.exit(37);\n", encoding="utf-8")
        package = self.cwd / "package.json"
        package.write_text(json.dumps({"name": "command-evidence-test", "private": True,
                                       "scripts": {"test": "node check.cjs"}}), encoding="utf-8")
        baseline = self.run_process([*npm, "test"])
        self.assertNotEqual(baseline.returncode, 0)
        self.assertTrue(self.marker.exists())
        self.marker.unlink()
        for option in ("--hel", "--help=true", "-h=true", "--usage", "-v", "--version=true", "--versions"):
            with self.subTest(option=option):
                result = self.run_process([*npm, "test", option])
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertFalse(self.marker.exists())
                self.assertIsNone(classify_command("npm test " + option, str(self.cwd)))
        if os.name != "nt" and shutil.which("true"):
            option = "--script-shell=" + shutil.which("true")
            result = self.run_process([*npm, "test", option])
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(self.marker.exists())
            self.assertIsNone(classify_command("npm test " + option, str(self.cwd)))
        package.write_text('{"name":"command-evidence-test","private":true}', encoding="utf-8")
        for args in (("test", "--if-present"), ("run", "test", "--if-present=true")):
            with self.subTest(args=args):
                result = self.run_process([*npm, *args])
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertFalse(self.marker.exists())
                self.assertIsNone(classify_command("npm " + " ".join(args), str(self.cwd)))

    @unittest.skipUnless(POWERSHELL, "requires native PowerShell")
    def test_real_powershell_string_success_is_not_execution(self):
        result = self.run_process([POWERSHELL, "-NoProfile", "-NonInteractive", "-Command", "'pytest'"])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "pytest")
        self.assertIsNone(classify_command("'pytest'", str(self.cwd), "PowerShell"))
        executable = str(sys.executable).replace("'", "''")
        command = "& '" + executable + "' -m unittest discover"
        result = self.run_process([POWERSHELL, "-NoProfile", "-NonInteractive", "-Command", command])
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(self.marker.exists())
        if "''" not in executable:
            self.assertEqual(classify_command(command, str(self.cwd), "PowerShell")["kind"], "verification")


@unittest.skipUnless(shutil.which("git"), "requires Git")
class ActualDiffReviewProcesses(unittest.TestCase):
    def test_successful_non_patch_modes_cannot_establish_review(self):
        with tempfile.TemporaryDirectory() as temp:
            cwd = Path(temp)
            def git(*args):
                return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=10, check=False)
            self.assertEqual(git("init", "-q").returncode, 0)
            self.assertEqual(git("config", "user.name", "Parser Test").returncode, 0)
            self.assertEqual(git("config", "user.email", "parser@example.invalid").returncode, 0)
            source = cwd / "app.py"
            source.write_text("value = 1\n", encoding="utf-8")
            self.assertEqual(git("add", "app.py").returncode, 0)
            self.assertEqual(git("commit", "-qm", "baseline").returncode, 0)
            source.write_text("value = 2\n", encoding="utf-8")
            self.assertIn("@@", git("diff").stdout)
            if os.name != "nt" and shutil.which("true"):
                no_diff_program = shutil.which("true")
                result = subprocess.run(["git", "diff"], cwd=cwd, capture_output=True,
                                        text=True, timeout=10, check=False,
                                        env=dict(os.environ, GIT_EXTERNAL_DIFF=no_diff_program))
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, "")
                self.assertIsNone(classify_command("GIT_EXTERNAL_DIFF=" + no_diff_program + " git diff", str(cwd)))
            for args in (("--stat",), ("--check",), ("--check", "--patch"), ("--name-only",),
                         ("--raw",), ("--no-patch",), ("HEAD", "HEAD"),
                         ("--", "nonexistent.py"), ("--output=hidden.patch",), ("--diff-filter=A",)):
                with self.subTest(args=args):
                    result = git("diff", *args)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertNotIn("@@", result.stdout)
                    self.assertIsNone(classify_command("git diff " + " ".join(args), str(cwd)))
            self.assertEqual(git("add", "app.py").returncode, 0)
            self.assertEqual(git("diff").stdout, "")
            self.assertIn("@@", git("diff", "--cached").stdout)
            self.assertEqual(classify_command("git diff", str(cwd))["diff_scope"], "worktree")
            self.assertEqual(classify_command("git diff --cached", str(cwd))["diff_scope"], "index")


if __name__ == "__main__":
    unittest.main()
