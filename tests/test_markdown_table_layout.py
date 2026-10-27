from pathlib import Path

import pytest

from src.python.markdown_tables import table_layout


@pytest.mark.parametrize('period,folder', [
    ('2026-08-15_2026-10-15', '2026-08-15_2026-10-14'),
    ('2024-02-01_2024-03-01', '2024-02-01_2024-02-29'),
    ('2026-12-01_2027-01-01', '2026-12-01_2026-12-31')])
def test_flat_inclusive_date_folder(period, folder):
    directory, prefix = table_layout(Path('/repo'), 'analysis', period)
    assert directory == Path('/repo/outputs/tables') / folder
    assert prefix == 'analysis_'


def test_analysis_and_upload_variants_cannot_overwrite_each_other():
    variants = [
        ('first-order', '2026-08-15_2026-10-15_uploads-from-2026-08-01'),
        ('first-order', '2026-08-15_2026-10-15_uploads-from-2026-08-01_uploads-end-2026-10-26'),
        ('other-analysis', '2026-08-15_2026-10-15_uploads-from-2026-08-01')]
    outputs = [table_layout(Path('/repo'), analysis, period) for analysis, period in variants]
    assert len({directory for directory, _ in outputs}) == 1
    assert len({prefix for _, prefix in outputs}) == 3
    assert all('/' not in prefix for _, prefix in outputs)


@pytest.mark.parametrize('period', ['2026-10-15_2026-08-15', '2026-10-15_2026-10-15', 'bad-period'])
def test_invalid_date_ranges_rejected(period):
    with pytest.raises(ValueError):
        table_layout(Path('/repo'), 'analysis', period)
