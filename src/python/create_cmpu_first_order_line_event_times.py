"""REFNUM 20: audited first-order-line event times; no survival outcomes."""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json
import subprocess
import sys

import click
from jinja2 import Environment, StrictUndefined
import pandas as pd

from src.python.create_cmpu_prescription_first_order_status import ROOT, RUNNER, TIMING_VARIANT, AUDIT_COLUMNS, digest
from src.python.markdown_tables import markdown_table, table_layout
from src.python.markdown_tables import write_text

NAME = 'cmpu-first-order-line-event-times'
TEMPLATE = ROOT / 'src/sql/cmpu_first_order_line_event_times.sql'
TIMES = ['line_created_utc', 'line_created_eastern', 'actual_upload_created_time', 'order_placed_utc', 'order_placed_eastern', 'order_cancel_time',
         'min_approved_denied_datetime', 'actual_upload_time', 'estimated_upload_time',
         'candidate_upload_time', 'event_time']
ASSOCIATION_COLUMNS = ['rx_id', 'customer_id', 'rx_creation_datetime', 'approval_channel',
                       'first_order_id', 'first_orderitem_id', 'first_order_line_id',
                       'rx_source_rows', 'upload_count', 'association_upload_time', 'association_upload_created_time',
                       'association_upload_id', 'association_upload_state']
QUALITY = ['missing_placement', 'missing_event', 'missing_estimate',
           'negative_duration', 'negative_approval_interval']
STATES = ['Missing order ID', 'Missing line ID', 'Invalid line ID', 'Unmatched line', 'Matched']


def render_sql(start, end, upload_start):
    start, end, upload_start = map(date.fromisoformat, [start, end, upload_start])
    if not upload_start <= start < end:
        raise ValueError('require upload start <= start < exclusive end')
    return Environment(undefined=StrictUndefined).from_string(TEMPLATE.read_text()).render(
        start_date=start.isoformat(), end_date=end.isoformat(), upload_start_date=upload_start.isoformat(),
        upload_end_date=(end + timedelta(days=11)).isoformat())


def expected_estimate(created, approved):
    """Independent integer/Decimal check, avoiding floating-point timestamp arithmetic."""
    if pd.isna(created) or pd.isna(approved):
        return pd.NaT
    delta = approved.value - created.value
    offset = int((Decimal(delta) * Decimal('0.96')).quantize(Decimal(1), rounding=ROUND_HALF_UP))
    return pd.Timestamp(created.value + offset, tz='UTC')


def validate(frame, start, end, upload_start):
    render_sql(start, end, upload_start)  # Validate date options in direct callers too.
    frame = frame.rename(columns=str.lower).copy()
    for col in ['rx_creation_datetime', 'association_upload_time', 'association_upload_created_time', *TIMES]:
        frame[col] = pd.to_datetime(frame[col], utc=True, format='mixed', errors='raise').astype('datetime64[ns, UTC]')
    if frame.rx_id.isna().any() or frame.rx_id.duplicated().any() or not frame.rx_source_rows.eq(1).all():
        raise ValueError('missing or duplicate prescription IDs')
    if not frame.approval_channel.eq('CUSTOMER_UPLOAD').all():
        raise ValueError('unexpected approval channel')
    if frame.rx_creation_datetime.isna().any() or not frame.rx_creation_datetime.between(
            pd.Timestamp(start, tz='UTC'), pd.Timestamp(end, tz='UTC'), inclusive='left').all():
        raise ValueError('prescription outside cohort window')
    for col in AUDIT_COLUMNS:
        if frame[col].isna().any() or frame[col].nunique() > 1:
            raise ValueError('inconsistent upload source audit')
    if len(frame) and frame.invalid_upload_source_rows.iloc[0] != 0:
        raise ValueError('missing or duplicate upload source IDs')
    if (frame.upload_count.isna().any() or frame.upload_count.lt(0).any()
            or frame.upload_count.mod(1).ne(0).any()
            or frame.upload_count.gt(0).ne(frame.association_upload_created_time.notna()).any()):
        raise ValueError('invalid upload counts or timestamps')
    upload_end = pd.Timestamp(end, tz='UTC') + pd.Timedelta(days=11)
    if not frame.association_upload_created_time.dropna().between(
            pd.Timestamp(upload_start, tz='UTC'), upload_end, inclusive='left').all():
        raise ValueError('upload outside search window')
    present = frame.upload_count.gt(0)
    if (present & (frame.association_upload_id.isna() | frame.association_upload_state.ne('ACCEPTED').fillna(True))).any():
        raise ValueError('invalid selected accepted entity')
    if (~present & (frame.association_upload_time.notna() | frame.association_upload_id.notna())).any():
        raise ValueError('accepted entity evidence disagrees')
    numeric = frame.first_orderitem_id.astype('string').str.strip().str.fullmatch(r'[0-9]+').fillna(False)
    for row, valid in zip(frame.itertuples(), numeric):
        parsed = int(str(row.first_orderitem_id).strip()) if valid else None
        if (parsed is None) != pd.isna(row.first_order_line_id) or (
                parsed is not None and parsed != row.first_order_line_id):
            raise ValueError('numeric first-order line key disagrees')
    matched = frame.order_id.notna()
    if matched.ne(frame.order_line_id.notna()).any() or (matched & (
            frame.first_order_id.ne(frame.order_id) | frame.first_order_line_id.ne(frame.order_line_id))).any():
        raise ValueError('first-order keys disagree')
    for col in ['line_status_variants', 'is_deleted_variants', 'is_refill_variants', 'order_placed_utc_variants']:
        if not frame.loc[matched, col].eq(1).all():
            raise ValueError('conflicting line status, flags or placement timestamps')
    if frame.loc[matched, ['cancellation_variants', 'eastern_variants']].gt(1).any().any():
        raise ValueError('conflicting populated cancellation or Eastern timestamps')
    blank = frame.first_orderitem_id.astype('string').str.strip().fillna('').eq('')
    frame['association_state'] = 'Matched'
    for mask, label in reversed(list(zip([
            frame.first_order_id.isna(), blank, frame.first_order_line_id.isna(), ~matched], STATES))):
        frame.loc[mask, 'association_state'] = label
    # SQL event fields must be identical across repeated prescription associations.
    line_columns = [c for c in frame if c not in ASSOCIATION_COLUMNS + AUDIT_COLUMNS +
                    ['association_state', 'extracted_at_session_time', 'extraction_warehouse']]
    repeated = frame.loc[matched, line_columns]
    if repeated.groupby(['order_id', 'order_line_id']).nunique(dropna=False).gt(1).any().any():
        raise ValueError('inconsistent repeated line associations')
    lines = repeated.drop_duplicates(['order_id', 'order_line_id']).copy()
    if (lines.shipment_rows.isna().any() or lines.shipment_rows.lt(1).any()
            or lines.shipment_rows.mod(1).ne(0).any()):
        raise ValueError('invalid shipment row counts')
    eastern = lines.order_placed_utc.dt.tz_convert('America/New_York').dt.tz_localize(None)
    companion = lines.order_placed_eastern.dt.tz_localize(None)
    lines['timezone_checked'] = eastern.notna() & companion.notna()
    if (lines.timezone_checked & (eastern - companion).abs().gt(pd.Timedelta(seconds=1))).any():
        raise ValueError('UTC/Eastern placement timestamp disagreement')
    lines['missing_accepted_state_change'] = lines.actual_upload_id.notna() & lines.actual_upload_time.isna()
    associations = frame[ASSOCIATION_COLUMNS + ['order_id', 'order_line_id', 'association_state']].copy()
    chosen = frame.loc[matched].sort_values(['association_upload_created_time', 'association_upload_id'], na_position='last').drop_duplicates(['order_id','order_line_id']).set_index(['order_id','order_line_id'])
    counts = frame.loc[matched].groupby(['order_id', 'order_line_id']).size()
    for row in lines.itertuples():
        key = (row.order_id, row.order_line_id)
        def same(actual, expected, name):
            if hasattr(expected, 'item'):
                expected = expected.item()
            if pd.isna(actual) or pd.isna(expected):
                agrees = pd.isna(actual) and pd.isna(expected)
            else:
                agrees = actual == expected
            if not agrees:
                raise ValueError(f'{name} disagrees for line {key}')
        same(row.actual_upload_time, chosen.loc[key, 'association_upload_time'], 'selected accepted state change')
        same(row.actual_upload_created_time, chosen.loc[key, 'association_upload_created_time'], 'selected entity creation')
        same(row.actual_upload_id, chosen.loc[key, 'association_upload_id'], 'selected entity ID')
        same(row.prescription_associations, counts.loc[key], 'association count')
        estimate = expected_estimate(row.order_placed_utc, row.min_approved_denied_datetime)
        same(row.estimated_upload_time, estimate, '0.96 estimate')
        candidate = row.actual_upload_time if pd.notna(row.actual_upload_time) else estimate
        candidate_source = ('actual_upload' if pd.notna(row.actual_upload_time) else
                            'estimated_upload' if pd.notna(estimate) else 'missing')
        same(row.candidate_upload_time, candidate, 'candidate upload')
        same(row.candidate_upload_source, candidate_source, 'candidate source')
        populated = [t for t in [candidate, row.order_cancel_time] if pd.notna(t)]
        event = min(populated) if populated else pd.NaT
        source = ('missing' if not populated else 'tie' if pd.notna(candidate) and candidate == row.order_cancel_time
                  else 'order_cancellation' if pd.notna(row.order_cancel_time) and event == row.order_cancel_time
                  else candidate_source)
        same(row.event_time, event, 'event time')
        same(row.event_time_source, source, 'event source')
        elapsed = (event.value - row.order_placed_utc.value) / 3_600_000_000_000 if (
            pd.notna(event) and pd.notna(row.order_placed_utc)) else None
        if elapsed is None:
            same(row.elapsed_hours, None, 'elapsed hours')
        elif pd.isna(row.elapsed_hours) or abs(float(row.elapsed_hours) - elapsed) > 1e-9:
            raise ValueError('elapsed hours disagree')
        for col, expected in zip(QUALITY, [pd.isna(row.order_placed_utc), pd.isna(event), pd.isna(estimate),
                event < row.order_placed_utc if elapsed is not None else None,
                row.min_approved_denied_datetime < row.order_placed_utc if pd.notna(row.min_approved_denied_datetime)
                and pd.notna(row.order_placed_utc) else None]):
            same(getattr(row, col), expected, col)
    audit = [('associations', 'Cohort', len(associations))]
    audit += [('associations', state, int(associations.association_state.eq(state).sum())) for state in STATES]
    audit += [('lines', 'Distinct matched lines', len(lines)),
              ('lines', 'Shipment rows', int(lines.shipment_rows.sum())),
              ('lines', 'Repeated associations', int(matched.sum() - len(lines))),
              ('lines', 'UTC/Eastern pairs checked', int(lines.timezone_checked.sum()))]
    for col in ['event_time_source', 'candidate_upload_source', 'line_status', 'is_deleted', 'is_refill']:
        distribution = lines[col].astype('object').fillna('[NULL]').value_counts()
        if col.endswith('_source'):
            categories = ['actual_upload', 'estimated_upload', 'missing']
            if col == 'event_time_source':
                categories = ['actual_upload', 'estimated_upload', 'order_cancellation', 'tie', 'missing']
            if not distribution.index.isin(categories).all() or distribution.sum() != len(lines):
                raise ValueError('event source counts do not reconcile')
            distribution = distribution.reindex(categories, fill_value=0)
        audit += [(col, str(value), int(n)) for value, n in distribution.items()]
    audit += [('quality', 'missing_accepted_state_change', int(lines.missing_accepted_state_change.sum()))]
    audit += [('quality', col, int(lines[col].fillna(False).sum())) for col in QUALITY]
    audit += [('quality', 'Missing Eastern companion rows', int(lines.missing_eastern_rows.sum())),
              ('quality', 'Missing approval shipment rows', int(lines.missing_approval_rows.sum())),
              ('quality', 'Multiple populated approval minima', int(lines.approval_variants.gt(1).sum()))]
    audit += [('upload source', col, int(frame[col].iloc[0]) if len(frame) else None) for col in AUDIT_COLUMNS]
    audit += [('upload source',key,int(frame[key].iloc[0]) if len(frame) and pd.notna(frame[key].iloc[0]) else 0)
              for key in ['accepted_window_upload_rows','excluded_window_upload_rows'] if key in frame]
    if len(associations) != sum(associations.association_state.eq(s).sum() for s in STATES):
        raise ValueError('association counts do not reconcile')
    return associations, lines, pd.DataFrame(audit, columns=['grain', 'measure', 'count'])


def load_source(start, end, upload_start, cached=False):
    sql = render_sql(start, end, upload_start)
    upload_end = (date.fromisoformat(end) + timedelta(days=11)).isoformat()
    period = f'{start}_{end}_uploads-{upload_start}_{upload_end}_{TIMING_VARIANT}'
    directory = ROOT / 'data' / NAME / period
    parquet, manifest = directory / 'source.parquet', directory / 'source.json'
    options = dict(timing_variant=TIMING_VARIANT, timing_origin='ORDER_PLACED_DTTM',
                   upload_timing_field='STATE_CHANGED_TS_UTC', upload_state_filter='ACCEPTED',
                   estimate_multiplier='0.96', start_date=start, end_date_exclusive=end, upload_start_date=upload_start,
                   upload_end_date_exclusive=upload_end)
    if cached:
        metadata = json.loads(manifest.read_text())
        if (metadata.get('sql') != sql or metadata.get('sql_sha256') != hashlib.sha256(sql.encode()).hexdigest()
                or metadata.get('parquet_sha256') != digest(parquet)
                or any(metadata.get(k) != v for k, v in options.items())):
            raise ValueError('cached SQL, dates or fingerprint differs; refresh extract')
        frame = pd.read_parquet(parquet)
    else:
        directory.mkdir(parents=True, exist_ok=True)
        generated = ROOT / 'src/autogenerated' / NAME / period
        generated.mkdir(parents=True, exist_ok=True)
        query = generated / 'cmpu_first_order_line_event_times.sql'
        write_text(query, sql + '\n')
        manifest.unlink(missing_ok=True)
        subprocess.run([sys.executable, str(RUNNER), str(query), '--output-parquet',
                        str(parquet.relative_to(ROOT)), '--sql-log-dir',
                        str((generated / 'sql-history').relative_to(ROOT))], cwd=ROOT, check=True)
        frame = pd.read_parquet(parquet).rename(columns=str.lower)
        validate(frame, start, end, upload_start)
        metadata = dict(options, sql=sql, sql_sha256=hashlib.sha256(sql.encode()).hexdigest(),
                        parquet_sha256=digest(parquet), extracted_at_utc=datetime.now(timezone.utc).isoformat(),
                        warehouse=frame.extraction_warehouse.unique().tolist(),
                        source_extracted_at=frame.extracted_at_session_time.unique().tolist())
        write_text(manifest, json.dumps(metadata, indent=2) + '\n')
    return frame, metadata, period


def write_outputs(frame, metadata, period):
    associations, lines, audit = validate(frame, metadata['start_date'], metadata['end_date_exclusive'],
                                         metadata['upload_start_date'])
    directory, prefix = table_layout(ROOT, NAME, period)
    directory.mkdir(parents=True, exist_ok=True)
    notes = (f"Prescriptions UTC [{metadata['start_date']}, {metadata['end_date_exclusive']}); "
             f"uploads UTC [{metadata['upload_start_date']}, {metadata['upload_end_date_exclusive']}).\n\n"
             'Distinct order/order-line pairs; all statuses and nullable flags retained. '
             'Estimate = order placement + round(0.96 × approval/denial elapsed nanoseconds), no intercept. '
             'Accepted-entity STATE_CHANGED_TS_UTC supplies the observed endpoint. The fixed 0.96 coefficient is retained pending recalibration. '
             'Actual upload takes precedence over estimate; populated cancellation caps either. '
             'ORDER_CANCEL_DTTM uses the UTC interpretation checked against its Eastern companion '
             'in REFNUM 5; this view has no cancellation Eastern companion. '
             'Null and negative durations remain. No survival outcomes or censoring rules assigned.\n\n')
    for kind, data in [('associations', associations), ('lines', lines), ('audit', audit)]:
        write_text(directory / f'{prefix}{kind}.md',
            f'# CMPU first-order-line event times: {kind}\n\n' + notes + markdown_table(data) + '\n')
    # Machine-readable validated datasets and fingerprints stay under data/.
    directory_data = ROOT / 'data' / NAME / period
    for kind, data in [('associations', associations), ('lines', lines), ('audit', audit)]:
        path = directory_data / f'{kind}.parquet'
        data.to_parquet(path, index=False)
    write_text(directory_data / 'exports.json', json.dumps({
        'source_sha256': metadata['parquet_sha256'],
        'files': {f'{k}.parquet': digest(directory_data / f'{k}.parquet')
                  for k in ['associations', 'lines', 'audit']}}, indent=2) + '\n')
    return audit, directory


@click.command()
@click.option('--start-date', default='2026-08-15', show_default=True)
@click.option('--end-date', default='2026-10-15', show_default=True, help='Exclusive prescription end; uploads end 11 days later.')
@click.option('--upload-start-date', default='2026-08-01', show_default=True)
@click.option('--cached', is_flag=True)
@click.option('--print-sql', is_flag=True)
def main(start_date, end_date, upload_start_date, cached, print_sql):
    try:
        if print_sql:
            click.echo(render_sql(start_date, end_date, upload_start_date))
            return
        frame, metadata, period = load_source(start_date, end_date, upload_start_date, cached)
        audit, directory = write_outputs(frame, metadata, period)
        click.echo(audit.to_string(index=False))
        click.echo(f'Tables: {directory}')
    except (ValueError, OSError, KeyError, subprocess.CalledProcessError) as error:
        raise click.ClickException(str(error)) from error


if __name__ == '__main__':
    main()
