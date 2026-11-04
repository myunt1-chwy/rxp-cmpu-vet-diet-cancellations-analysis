from shared.python import opportunity_report_tables as a


def test_interleaved_cohorts_exclude_frequency_and_rerun_idempotently(
    tmp_path,
):
    order = []
    for study in a.STUDIES:
        order.extend(
            [a.WHOLE_FILES[study], a.UPLOAD_FILES[study], a.VET_FILES[study]]
        )
    order.extend([a.CHEWY, a.UPLOAD_CHEWY, a.VET_CHEWY])
    for name in order + [
        a.FREQUENCY,
        a.LEGACY_WHOLE,
        a.LEGACY_UPLOAD,
        a.LEGACY_VET,
    ]:
        (tmp_path / (name + ".tex")).write_text("Table\n")
    parent = tmp_path / "financial_opportunity.tex"
    old = "\n".join("\\input{appendix/" + name + "}" for name in a.KNOWN_FILES)
    parent.write_text("Baseline table\n" + old + "\n")
    a.update_follow_up_inputs(parent)
    first = parent.read_text()
    a.update_follow_up_inputs(parent)
    assert parent.read_text() == first
    inputs = ["\\input{appendix/" + name + "}" for name in order]
    assert all(first.count(include) == 1 for include in inputs)
    assert [first.index(include) for include in inputs] == sorted(
        first.index(include) for include in inputs
    )
    assert first.rstrip().endswith(inputs[-1])
    for legacy in [a.LEGACY_WHOLE, a.LEGACY_UPLOAD, a.LEGACY_VET]:
        assert "\\input{appendix/" + legacy + "}" not in first
    assert "\\input{appendix/" + a.FREQUENCY + "}" not in first
    assert "Baseline table" in first and "SQL" not in first
