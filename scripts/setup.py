"""Initialize project metadata once, then synchronize the project environment."""

import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys


RUNTIME_DEPENDENCIES = [
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
]
DEVELOPMENT_DEPENDENCIES = ["pytest>=9.1.1", "tomlkit>=0.13.3"]


def project_configuration(name: str, description: str) -> str:
    return (
        "[project]\n"
        f"name = {json.dumps(name)}\n"
        'version = "0.1.0"\n'
        f"description = {json.dumps(description, ensure_ascii=False)}\n"
        'readme = "README.md"\n'
        'requires-python = ">=3.12"\n'
        f"dependencies = {json.dumps(RUNTIME_DEPENDENCIES)}\n"
        "\n[dependency-groups]\n"
        f"dev = {json.dumps(DEVELOPMENT_DEPENDENCIES)}\n"
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--init", action="store_true", help="Prompt for project metadata even when configuration exists.")
    args = parser.parse_args(argv)
    if shutil.which("uv") is None:
        print("Error: install uv from https://docs.astral.sh/uv/getting-started/installation/", file=sys.stderr)
        return 1

    configuration = Path("pyproject.toml")
    if args.init or not configuration.exists():
        document = None
        default_description = "Add your description here"
        if configuration.exists():
            import tomlkit

            try:
                document = tomlkit.parse(configuration.read_text(encoding="utf-8"))
                project = document["project"]
                default_description = project.get("description", default_description)
                if not isinstance(default_description, str):
                    raise ValueError("project.description must be a string")
            except (ValueError, KeyError, TypeError) as error:
                print(f"Cannot initialize project configuration: {error}", file=sys.stderr)
                return 1
        default_name = Path.cwd().name
        try:
            while True:
                name = input(f"Project name [{default_name}]: ").strip() or default_name
                if re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?", name):
                    break
                print("Use letters, digits, dots, underscores, or hyphens; start and end with a letter or digit.")
            description = input(f"Description [{default_description}]: ").strip() or default_description
        except (EOFError, KeyboardInterrupt):
            print("\nSetup cancelled; no project configuration was written.", file=sys.stderr)
            return 1

        if document is None:
            content = project_configuration(name, description)
        else:
            document["project"]["name"] = name
            document["project"]["description"] = description
            content = tomlkit.dumps(document)
        configuration.write_text(content, encoding="utf-8")

    try:
        subprocess.run(["uv", "sync", "--python", "3.12", "--group", "dev"], check=True)
    except subprocess.CalledProcessError as error:
        print("Dependency synchronization failed; version constraints were preserved. Resolve the error above and rerun make setup.", file=sys.stderr)
        return error.returncode
    return 0


if __name__ == "__main__":
    sys.exit(main())
