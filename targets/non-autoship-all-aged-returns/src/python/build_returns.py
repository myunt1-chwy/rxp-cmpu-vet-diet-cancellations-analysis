"""Extract once and present the three cohort paragraphs."""

import argparse

from shared.python.non_autoship_returns import run

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", choices=["0", "1"], default="0")
    run(parser.parse_args().refresh == "1")
