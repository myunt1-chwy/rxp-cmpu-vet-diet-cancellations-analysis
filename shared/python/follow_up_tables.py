"""Reusable follow up tables helpers; no analysis CLI."""

import re

from shared.python.paths import repository_root

ROOT = repository_root()


SOURCES = [
    (
        "All aged customers",
        "financial_opportunity_follow_up_same_part_pet.tex",
    ),
    (
        "First CUSTOMER_UPLOAD vet-diet order aged",
        "financial_opportunity_new_upload_follow_up_same_part_pet.tex",
    ),
    (
        "First vet-diet order aged",
        "financial_opportunity_new_vet_diet_follow_up_same_part_pet.tex",
    ),
]


def read_table(path):
    text = path.read_text()
    body = text.split(r"\midrule", 1)[1].split(r"\bottomrule", 1)[0]
    rows = [
        line.strip().removesuffix(r"\\").strip().split(" & ")
        for line in body.splitlines()
        if re.match(r"^\d+ & ", line.strip())
    ]
    if not rows or any(len(row) != 5 for row in rows):
        raise ValueError(f"Expected five-column follow-up rows in {path}")
    days = [int(row[0]) for row in rows]
    if days != sorted(set(days)):
        raise ValueError(f"Duplicate or unordered follow-up days in {path}")
    denominator = re.search(
        r"(?:cohort of|denominator of) (\d+(?:,\d{3})*)", text
    )
    period = re.search(
        r"from\s+(\w+ \d+, \d{4}) through (\w+ \d+, \d{4}), inclusive, UTC",
        text,
    )
    cutoff = re.search(r"\d{4}-\d{2}-\d{2} 00:00 UTC", text)
    if not all((denominator, period, cutoff)):
        raise ValueError(f"Missing cohort/window metadata in {path}")
    return rows, denominator[1], period.groups(), cutoff[0]
