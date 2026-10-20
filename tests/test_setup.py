import importlib.util
import io
import os
from pathlib import Path
import subprocess
import tempfile
import tomllib
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location("project_setup", Path(__file__).resolve().parents[1] / "scripts/setup.py")
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)


class SetupTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="setup-test-")
        self.addCleanup(self.directory.cleanup)
        previous = Path.cwd()
        os.chdir(self.directory.name)
        self.addCleanup(os.chdir, previous)
        self.addCleanup(patch.stopall)
        patch.object(setup.shutil, "which", return_value="uv").start()
        self.sync = patch.object(setup.subprocess, "run").start()
        patch("sys.stdout", new_callable=io.StringIO).start()
        patch("sys.stderr", new_callable=io.StringIO).start()

    def run_setup(self, answers, argv=None):
        with patch("builtins.input", side_effect=answers):
            return setup.main(argv or [])

    def configuration(self):
        return tomllib.loads(Path("pyproject.toml").read_text())

    def test_defaults(self):
        self.assertEqual(self.run_setup(["", ""]), 0)
        project = self.configuration()["project"]
        self.assertEqual(project["name"], Path.cwd().name)
        self.assertEqual(project["description"], "Add your description here")
        self.assertEqual(project["version"], "0.1.0")
        self.assertEqual(project["requires-python"], ">=3.12")
        self.assertEqual(project["readme"], "README.md")
        self.assertEqual(project["dependencies"], [
            "altair>=6.3.0",
            "click>=8.5.0",
            "duckdb>=1.5.5",
            "jinja2>=3.1.6",
            "pandas>=3.0.5",
            "pyarrow>=25.0.1",
            "pyyaml",
            "scipy>=1.18.1",
            "snowflake-connector-python[secure-local-storage]>=4.7.5",
            "sqlparse>=0.6.0",
            "statsmodels>=0.15.0",
        ])
        self.assertEqual(self.configuration()["dependency-groups"]["dev"], setup.DEVELOPMENT_DEPENDENCIES)
        self.sync.assert_called_once_with(["uv", "sync", "--python", "3.12", "--group", "dev"], check=True)

    def test_custom_metadata_and_escaping(self):
        description = 'Quotes " and backslash \\ with café 🐾\t'
        self.assertEqual(self.run_setup(["my.project-1_x", description]), 0)
        project = self.configuration()["project"]
        self.assertEqual(project["name"], "my.project-1_x")
        self.assertEqual(project["description"], description.strip())

    def test_invalid_names_are_reprompted(self):
        self.assertEqual(self.run_setup(["bad name", "-bad", "bad/thing", "bad.", "valid", ""]), 0)
        self.assertEqual(self.configuration()["project"]["name"], "valid")

    def test_interrupted_prompts_do_not_write(self):
        for answers in ([EOFError], [KeyboardInterrupt], ["valid", EOFError], ["valid", KeyboardInterrupt]):
            with self.subTest(answers=answers):
                self.assertEqual(self.run_setup(answers), 1)
                self.assertFalse(Path("pyproject.toml").exists())
        self.sync.assert_not_called()

    def test_repeat_run_preserves_bytes_without_input(self):
        original = b'# custom metadata\n[project]\nname = "existing"\n'
        Path("pyproject.toml").write_bytes(original)
        self.assertEqual(self.run_setup([AssertionError("Must not prompt")]), 0)
        self.assertEqual(Path("pyproject.toml").read_bytes(), original)
        self.sync.assert_called_once()

    def test_sync_failure_preserves_configuration(self):
        self.run_setup(["valid", ""])
        original = Path("pyproject.toml").read_bytes()
        self.sync.side_effect = subprocess.CalledProcessError(1, "uv")
        self.assertEqual(self.run_setup([]), 1)
        self.assertEqual(Path("pyproject.toml").read_bytes(), original)

    def test_missing_uv_does_not_prompt_or_write(self):
        with patch.object(setup.shutil, "which", return_value=None):
            self.assertEqual(self.run_setup([]), 1)
        self.assertFalse(Path("pyproject.toml").exists())
        self.sync.assert_not_called()

    def test_init_preserves_custom_configuration_and_formatting(self):
        original = (
            '# Keep this comment\n[project]\nname = "old"\n'
            'description = "Old description"\nversion = "2.3.4"\n'
            'requires-python = ">=3.12"\n'
            'dependencies = [\n    "click==8.5.0", # pinned\n]\n'
            '\n[dependency-groups]\ndev = ["pytest"]\n'
            '\n[tool.custom]\nsetting = true\n'
        )
        Path("pyproject.toml").write_text(original)
        self.assertEqual(self.run_setup(["new-project", "New description"], ["--init"]), 0)
        self.assertEqual(
            Path("pyproject.toml").read_text(),
            original.replace('"old"', '"new-project"').replace('"Old description"', '"New description"'),
        )
        self.sync.assert_called_once()

    def test_init_defaults_and_repeated_initialization(self):
        self.run_setup(["old", "Existing description"])
        self.assertEqual(self.run_setup(["", ""], ["--init"]), 0)
        self.assertEqual(self.configuration()["project"]["name"], Path.cwd().name)
        self.assertEqual(self.configuration()["project"]["description"], "Existing description")
        self.assertEqual(self.run_setup(["bad name", "new-name", 'Quotes " café \\'], ["--init"]), 0)
        self.assertEqual(self.configuration()["project"]["name"], "new-name")
        self.assertEqual(self.configuration()["project"]["description"], 'Quotes " café \\')

    def test_init_cancellation_preserves_existing_bytes(self):
        self.run_setup(["old", "Existing description"])
        original = Path("pyproject.toml").read_bytes()
        self.sync.reset_mock()
        for answers in ([EOFError], [KeyboardInterrupt], ["new", EOFError], ["new", KeyboardInterrupt]):
            with self.subTest(answers=answers):
                self.assertEqual(self.run_setup(answers, ["--init"]), 1)
                self.assertEqual(Path("pyproject.toml").read_bytes(), original)
        self.sync.assert_not_called()

    def test_init_sync_failure_retains_new_metadata(self):
        self.run_setup(["old", "Existing description"])
        self.sync.side_effect = subprocess.CalledProcessError(1, "uv")
        self.assertEqual(self.run_setup(["new-name", "New description"], ["--init"]), 1)
        self.assertEqual(self.configuration()["project"]["name"], "new-name")

    def test_init_without_configuration(self):
        self.assertEqual(self.run_setup(["new-name", ""], ["--init"]), 0)
        self.assertEqual(self.configuration()["project"]["name"], "new-name")


if __name__ == "__main__":
    unittest.main()
