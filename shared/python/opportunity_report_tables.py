"""Keep published financial follow-up tables grouped by study."""

from shared.python.markdown_tables import write_text
from shared.python.paths import latex_fragment_path

STUDIES = ["same-part-pet", "same-pet-different-part", "any-vet-diet"]
WHOLE_FILES = {
    study: "financial_opportunity_follow_up_" + study.replace("-", "_")
    for study in STUDIES
}
UPLOAD_FILES = {
    study: "financial_opportunity_new_upload_follow_up_"
    + study.replace("-", "_")
    for study in STUDIES
}
VET_FILES = {
    study: "financial_opportunity_new_vet_diet_follow_up_"
    + study.replace("-", "_")
    for study in STUDIES
}
CHEWY_FIRST_FILES = {
    study: "financial_opportunity_new_chewy_follow_up_"
    + study.replace("-", "_")
    for study in STUDIES
}
FREQUENCY = "financial_opportunity_customer_order_frequency"
CHEWY = "financial_opportunity_chewy_follow_up"
UPLOAD_CHEWY = "financial_opportunity_new_upload_chewy_follow_up"
VET_CHEWY = "financial_opportunity_new_vet_diet_chewy_follow_up"
LEGACY_VET = "financial_opportunity_new_vet_diet_follow_up"
LEGACY_WHOLE = "financial_opportunity_reorders"
LEGACY_UPLOAD = "financial_opportunity_new_upload_follow_up"
COMBINED_SAME_PART = "financial_opportunity_same_part_pet_comparison"
COMBINED_DIFFERENT_PART = (
    "financial_opportunity_same_pet_different_part_comparison"
)
COMBINED_ANY_VET_DIET = "financial_opportunity_any_vet_diet_comparison"
COMBINED_ALL_CHEWY = "financial_opportunity_all_chewy_comparison"
SQL_LISTINGS = "financial_opportunity_sql"
REPRODUCTION = "reproduction_financial"
KNOWN_FILES = (
    list(WHOLE_FILES.values())
    + list(UPLOAD_FILES.values())
    + list(VET_FILES.values())
    + list(CHEWY_FIRST_FILES.values())
    + [
        VET_CHEWY,
        "financial_opportunity_new_chewy_follow_up",
        LEGACY_VET,
        FREQUENCY,
        CHEWY,
        UPLOAD_CHEWY,
        LEGACY_WHOLE,
        LEGACY_UPLOAD,
        COMBINED_SAME_PART,
        COMBINED_DIFFERENT_PART,
        COMBINED_ANY_VET_DIET,
        COMBINED_ALL_CHEWY,
        SQL_LISTINGS,
        REPRODUCTION,
    ]
)


def follow_up_inputs(root):
    """
    Use per-study fragments; allow older aggregate-only outputs as
    fallback.
    """
    names = []
    whole_fragments = any(
        (latex_fragment_path(name + ".tex", root=root)).exists()
        for name in WHOLE_FILES.values()
    )
    upload_fragments = any(
        (latex_fragment_path(name + ".tex", root=root)).exists()
        for name in UPLOAD_FILES.values()
    )
    vet_fragments = any(
        (latex_fragment_path(name + ".tex", root=root)).exists()
        for name in VET_FILES.values()
    )
    for index, study in enumerate(STUDIES):
        combined = {
            "same-part-pet": COMBINED_SAME_PART,
            "same-pet-different-part": COMBINED_DIFFERENT_PART,
            "any-vet-diet": COMBINED_ANY_VET_DIET,
        }.get(study)
        if (
            combined
            and (latex_fragment_path(combined + ".tex", root=root)).exists()
        ):
            names.append(combined)
            continue
        for available, fragments, legacy in [
            (WHOLE_FILES, whole_fragments, LEGACY_WHOLE),
            (UPLOAD_FILES, upload_fragments, LEGACY_UPLOAD),
            (VET_FILES, vet_fragments, LEGACY_VET),
        ]:
            name = (
                available[study]
                if fragments
                else (legacy if index == 0 else None)
            )
            if (
                name
                and (latex_fragment_path(name + ".tex", root=root)).exists()
            ):
                names.append(name)
    # Frequency remains a computed/exported analysis, outside the published
    # report.
    chewy_files = (
        [COMBINED_ALL_CHEWY]
        if (
            latex_fragment_path(COMBINED_ALL_CHEWY + ".tex", root=root)
        ).exists()
        else [CHEWY, UPLOAD_CHEWY, VET_CHEWY]
    )
    for name in chewy_files:
        if (latex_fragment_path(name + ".tex", root=root)).exists():
            names.append(name)
    # Keep SQL files available for inspection, outside the published report.
    if (latex_fragment_path(REPRODUCTION + ".tex", root=root)).exists():
        names.append(REPRODUCTION)
    return "\n".join("\\input{appendix/" + name + "}" for name in names)


def update_follow_up_inputs(root):
    parent = latex_fragment_path("financial_opportunity.tex", root=root)
    if not parent.exists():
        return
    text = parent.read_text()
    for name in KNOWN_FILES:
        text = text.replace("\\input{appendix/" + name + "}", "")
    block = follow_up_inputs(root)
    text = text.rstrip() + "\n\n" + block + "\n"
    write_text(parent, text)
