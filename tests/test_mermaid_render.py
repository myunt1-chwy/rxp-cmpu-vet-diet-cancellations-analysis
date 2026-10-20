import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location(
    "mermaid_render",
    Path(__file__).resolve().parents[1] / ".agents/skills/mermaid-diagrams/scripts/render.py",
)
render = importlib.util.module_from_spec(spec)
spec.loader.exec_module(render)


class RenderTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="mermaid test ")
        self.addCleanup(directory.cleanup)
        previous = Path.cwd()
        os.chdir(directory.name)
        self.addCleanup(os.chdir, previous)
        self.source = Path("source file.mmd")
        self.source.write_text("flowchart LR\n A --> B\n")
        docker = patch.object(render.shutil, "which", return_value="docker")
        self.which = docker.start()
        self.addCleanup(docker.stop)

    def test_missing_docker(self):
        self.which.return_value = None
        with patch.object(render.subprocess, "run") as run:
            self.assertEqual(render.main([str(self.source)]), 1)
            run.assert_not_called()

    def test_missing_input_and_invalid_extension(self):
        with patch.object(render.subprocess, "run") as run:
            self.assertEqual(render.main(["missing.mmd"]), 1)
            self.assertEqual(render.main([str(self.source), "-o", "bad.txt"]), 1)
            run.assert_not_called()

    def test_daemon_unavailable(self):
        with patch.object(render.subprocess, "run", return_value=subprocess.CompletedProcess([], 1, "", "cannot connect")) as run:
            self.assertEqual(render.main([str(self.source)]), 1)
            self.assertEqual(run.call_count, 1)

    def test_render_failure_preserves_existing_output(self):
        output = Path("existing.png")
        output.write_bytes(b"previous image")
        with patch.object(render.subprocess, "run", side_effect=[
            subprocess.CompletedProcess([], 0, "", ""),
            subprocess.CompletedProcess([], 7),
        ]):
            self.assertEqual(render.main([str(self.source), "-o", str(output)]), 7)
        self.assertEqual(output.read_bytes(), b"previous image")

    def test_empty_output_is_failure(self):
        with patch.object(render.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "", "")):
            self.assertEqual(render.main([str(self.source)]), 1)

    def test_success_defaults_spaces_and_formats(self):
        def run(command, **kwargs):
            if command[1] == "run":
                self.assertIn(f"{Path.cwd()}:/input:ro", command)
                self.assertIn("/input/source file.mmd", command)
                self.assertEqual(command[-2:], ["-b", "transparent"])
                mount = next(value for value in command if value.endswith(":/output"))
                destination = Path(mount.removesuffix(":/output")) / Path(command[command.index("-o") + 1]).name
                destination.write_bytes(b"rendered diagram")
            return subprocess.CompletedProcess(command, 0, "", "")

        for extension in ("png", "svg", "pdf"):
            with self.subTest(extension=extension), patch.object(render.subprocess, "run", side_effect=run):
                args = [str(self.source)]
                output = Path("outputs/diagrams/source file.png")
                if extension != "png":
                    output = Path(f"custom folder/custom file.{extension}")
                    args += ["-o", str(output)]
                self.assertEqual(render.main(args), 0)
                self.assertEqual(output.read_bytes(), b"rendered diagram")


if __name__ == "__main__":
    unittest.main()
