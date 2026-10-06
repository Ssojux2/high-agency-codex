"""Resolve npm-installed native binaries without invoking package managers."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/validate_codex_plugin.py"
SPEC = importlib.util.spec_from_file_location("validate_codex_plugin", SCRIPT)
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


class NativeCliTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="codex launcher & %PATH%! ")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def make_binary(self, package_root, target="x86_64-pc-windows-msvc"):
        binary = package_root / "vendor" / target / "bin/codex.exe"
        binary.parent.mkdir(parents=True)
        binary.touch()
        return binary

    def resolve(self, shim):
        with mock.patch.object(validator.shutil, "which", return_value=str(shim)):
            return validator.native_cli("codex", windows=True)

    def test_npm_global_and_local_dependency_layouts(self):
        cases = (
            ("global", "nested", "codex-win32-x64"),
            ("global", "nested", "codex-win32-arm64"),
            ("global", "hoisted", "codex-win32-x64"),
            ("global", "bundled", "codex"),
            ("local", "nested", "codex-win32-x64"),
            ("local", "hoisted", "codex-win32-x64"),
        )
        for index, (installation, layout, package) in enumerate(cases):
            with self.subTest(installation=installation, layout=layout, package=package):
                prefix = self.root / str(index)
                modules = prefix / "node_modules"
                shim = (prefix / "codex.cmd" if installation == "global"
                        else modules / ".bin/codex.cmd")
                shim.parent.mkdir(parents=True, exist_ok=True)
                shim.touch()
                if layout == "nested":
                    modules = modules / "@openai/codex/node_modules"
                target = ("aarch64-pc-windows-msvc" if package.endswith("arm64")
                          else "x86_64-pc-windows-msvc")
                binary = self.make_binary(modules / "@openai" / package, target)
                self.assertEqual(self.resolve(shim), binary.resolve())

    def test_nested_dependency_precedes_a_hoisted_version(self):
        shim = self.root / "codex.cmd"
        shim.touch()
        modules = self.root / "node_modules"
        expected = self.make_binary(modules / "@openai/codex/node_modules/@openai/codex-win32-x64")
        self.make_binary(modules / "@openai/codex-win32-x64")
        self.assertEqual(self.resolve(shim), expected.resolve())

    def test_missing_platform_dependency_does_not_execute_the_shim(self):
        shim = self.root / "codex.cmd"
        shim.touch()
        self.assertIsNone(self.resolve(shim))

    def test_explicit_native_executable_is_retained(self):
        binary = self.root / "codex.exe"
        binary.touch()
        self.assertEqual(self.resolve(binary), binary.resolve())


if __name__ == "__main__":
    unittest.main()
