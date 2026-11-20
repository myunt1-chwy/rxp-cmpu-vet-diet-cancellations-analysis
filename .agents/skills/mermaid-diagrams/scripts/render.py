"""Render a Mermaid source with Docker; no third-party Python dependencies."""

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Mermaid source file")
    parser.add_argument("-o", "--output", type=Path, help="PNG, SVG, or PDF destination")
    args = parser.parse_args(argv)
    source = args.input.resolve()
    output = (args.output or Path("outputs/diagrams") / f"{source.stem}.png").resolve()

    if shutil.which("docker") is None:
        print("Error: Docker is required but was not found on PATH. Install Docker before rendering.", file=sys.stderr)
        return 1
    if not source.is_file():
        print(f"Error: input file does not exist: {source}", file=sys.stderr)
        return 1
    if output.suffix.lower() not in {".png", ".svg", ".pdf"}:
        print("Error: output must end in .png, .svg, or .pdf.", file=sys.stderr)
        return 1
    if source == output:
        print("Error: input and output must be different files.", file=sys.stderr)
        return 1

    try:
        check = subprocess.run(["docker", "info"], capture_output=True, text=True)
        if check.returncode:
            print("Error: Docker daemon is unavailable or inaccessible. Start Docker or check access permissions.", file=sys.stderr)
            print(check.stderr.strip(), file=sys.stderr)
            return check.returncode

        output.parent.mkdir(parents=True, exist_ok=True)
        # Stage the render so errors cannot overwrite a previously good diagram.
        with tempfile.TemporaryDirectory(prefix=".mermaid-", dir=output.parent) as directory:
            staged = Path(directory) / f"diagram{output.suffix.lower()}"
            command = [
                "docker", "run", "--rm",
                "--user", f"{os.getuid()}:{os.getgid()}",
                "--env", "HOME=/tmp",
                "--env", "XDG_CONFIG_HOME=/tmp",
                "--env", "XDG_CACHE_HOME=/tmp",
                "-v", f"{source.parent}:/input:ro",
                "-v", f"{directory}:/output",
                "minlag/mermaid-cli:latest",
                "-i", f"/input/{source.name}",
                "-o", f"/output/{staged.name}",
                "-b", "transparent",
            ]
            result = subprocess.run(command)
            if result.returncode:
                print("Error: Mermaid rendering failed; see Docker output above.", file=sys.stderr)
                return result.returncode
            if not staged.is_file() or staged.stat().st_size == 0:
                print("Error: Mermaid did not produce a nonempty output file.", file=sys.stderr)
                return 1
            staged.replace(output)
    except OSError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
