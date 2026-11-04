"""Run a declared legacy generator batch with explicit cache semantics."""

import argparse
import os
import subprocess
from pathlib import Path
from uuid import uuid4

import yaml

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pipeline")
    parser.add_argument("--refresh", choices=["0", "1"], default="0")
    args = parser.parse_args()
    pipelines = yaml.safe_load(
        (ROOT / "shared/analysis/pipelines.yaml").read_text()
    )
    pipeline = pipelines[args.pipeline]
    refresh = args.refresh == "1"
    run_id = os.environ.get("RXP_REFRESH_RUN_ID") or uuid4().hex
    if refresh and pipeline.get("refresh_error"):
        parser.exit(1, pipeline["refresh_error"] + "\n")
    commands = (
        pipeline.get("refresh_commands", pipeline["commands"])
        if refresh
        else pipeline["commands"]
    )
    # Shared batches have one log owner, declared by the first paragraph ID.
    owners = sorted(
        path.parent
        for path in (ROOT / "targets").glob("*/target.yaml")
        if yaml.safe_load(path.read_text()).get("pipeline") == args.pipeline
    )
    log = owners[0] / "outputs/build" / (args.pipeline + ".log")
    log.parent.mkdir(parents=True, exist_ok=True)
    print(
        (
            f"{'Refreshing' if refresh else 'Reproducing cached'} "
            f"{args.pipeline}"
            + (f"; run: {run_id}" if refresh else "")
            + f"; log: {log.relative_to(ROOT)}"
        ),
        flush=True,
    )
    environment = os.environ.copy()
    if refresh:
        environment["RXP_REFRESH_RUN_ID"] = run_id
    with log.open("w") as stream:
        for command in commands:
            argv = [
                "make",
                "--no-print-directory",
                *command,
                "CACHED=" + ("0" if refresh else "1"),
            ]
            stream.write(" ".join(argv) + "\n")
            stream.flush()
            result = subprocess.run(
                argv,
                check=False,
                cwd=ROOT,
                env=environment,
                stdout=stream,
                stderr=subprocess.STDOUT,
            )
            if result.returncode:
                stream.flush()
                tail = "\n".join(log.read_text().splitlines()[-25:])
                parser.exit(
                    result.returncode,
                    tail
                    + (
                        "\nPipeline "
                        f"{args.pipeline}"
                        " stopped. No automatic refresh was attemp"
                        "ted. Inspect "
                        f"{log.relative_to(ROOT)}"
                        " and the owning target README before usin"
                        "g REFRESH=1.\n"
                    ),
                )


if __name__ == "__main__":
    main()
