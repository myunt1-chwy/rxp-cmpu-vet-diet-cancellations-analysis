"""REFNUM 14: count first-order lines using the certified shipment/line view."""
from datetime import datetime, timezone, timedelta, date
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import click
from jinja2 import Environment, StrictUndefined
import pandas as pd

from src.python import create_cmpu_prescription_first_order_status as legacy
from src.python.markdown_tables import markdown_table, table_layout
from src.python.markdown_tables import write_text

ROOT = legacy.ROOT
NAME = 'cmpu-first-order-line-status'
TEMPLATE = ROOT / 'src/sql/cmpu_first_order_line_status.sql'
UPLOAD_FOLLOWUP_DAYS = 11
KEYS = ['matched_order_id', 'matched_order_line_id']
DIMENSIONS = ['channel', 'order_group', 'order_status_group', 'cancel_reason',
              'cancellation_reason_group', 'block_reason', 'upload_group']


def non_d(frame):
    """Known final line statuses other than D; unknown is not evidence of non-D."""
    return frame.order_group.ne('D') & frame.order_group.ne('[Unknown line status]')


def render_sql(start, end, upload_start):
    legacy.render_sql(start, end, upload_start)  # Shared date validation.
    return Environment(undefined=StrictUndefined).from_string(TEMPLATE.read_text()).render(
        start_date=start, end_date=end, upload_start_date=upload_start,
        upload_end_date=(date.fromisoformat(end) + timedelta(days=UPLOAD_FOLLOWUP_DAYS)).isoformat())


def summarize(frame):
    frame = frame.rename(columns=str.lower).copy()
    if (frame.line_source_rows.isna().any() or frame.line_source_rows.lt(0).any()
            or frame.line_source_rows.mod(1).ne(0).any()):
        raise ValueError('invalid order-line source counts')
    matched = frame.line_source_rows.gt(0)
    if matched.ne(frame[KEYS].notna().all(axis=1)).any():
        raise ValueError('line match and key evidence disagree')
    for col in ['order_status_variants', 'line_status_variants', 'block_reason_variants', 'cancel_reason_variants']:
        if not frame.loc[matched, col].eq(1).all():
            raise ValueError('conflicting status/reason across shipment rows')
    if not frame.loc[matched, 'duplicate_shipment_rows'].eq(0).all():
        raise ValueError('duplicate shipment/order-line source keys')
    if ((frame.loc[matched, 'matched_order_id'] != frame.loc[matched, 'first_order_id']).any()
            or (frame.loc[matched, 'matched_order_line_id'] != frame.loc[matched, 'first_order_line_id']).any()):
        raise ValueError('order-line join keys disagree')
    # Reuse established prescription/upload validation, then classify raw line status.
    validation = frame.copy()
    validation['order_source_rows'] = matched.astype(int)
    associations, _, audits = legacy.summarize(validation)
    associations = legacy.validate_accepted_uploads(associations)
    associations['upload_group'] = associations.upload_count.gt(0).map({True:'Has matching accepted upload',False:'No matching accepted upload'})
    associations['order_group'] = (frame.order_line_status.astype('string').str.strip().str.upper()
                                   .replace('', pd.NA).fillna('[Unknown line status]'))
    associations['order_status_group'] = (frame.order_status.astype('string').str.strip().str.upper()
                                          .replace('', pd.NA).fillna('[Unknown order status]'))
    associations['block_reason'] = (frame.order_item_block_reason.astype('string').str.strip()
                                     .replace('', pd.NA).fillna('[No block reason recorded]'))
    associations['cancel_reason'] = (frame.order_cancel_reason.astype('string').str.strip()
                                      .replace('', pd.NA).fillna('[No cancellation reason recorded]'))
    recorded = frame.order_cancel_reason.astype('string').str.strip().replace('', pd.NA).notna()
    associations['cancellation_reason_group'] = recorded.map(
        {True: 'With cancellation reason', False: 'No cancellation reason'})
    associations.loc[associations.order_group.eq('D'), 'block_reason'] = '[Not applicable: status D]'
    associations.loc[associations.order_group.eq('[Unknown line status]'), 'block_reason'] = '[Not applicable: unknown line status]'
    for col in ['order_placed_utc', 'order_placed_eastern']:
        associations[col] = pd.to_datetime(associations[col], utc=True, errors='raise')
    if not frame.loc[matched, 'placement_variants'].eq(1).all():
        raise ValueError('conflicting order placement timestamps')
    local = associations.order_placed_utc.dt.tz_convert('America/New_York').dt.tz_localize(None)
    companion = associations.order_placed_eastern.dt.tz_localize(None)
    if ((local - companion).abs().gt(pd.Timedelta(seconds=1))).any():
        raise ValueError('UTC/Eastern order placement disagreement')
    associations['accepted_elapsed_hours'] = (associations.upload_state_changed_at_utc - associations.order_placed_utc).dt.total_seconds()/3600
    associations['missing_placement'] = associations.order_placed_utc.isna()
    associations['negative_accepted_duration'] = associations.accepted_elapsed_hours.lt(0)
    associations['line_match'] = 'Matched'
    associations.loc[~matched, 'line_match'] = 'First order line not found'
    associations.loc[frame.first_order_line_id.isna(), 'line_match'] = 'Missing or invalid first order item ID'
    associations.loc[frame.first_order_id.isna(), 'line_match'] = 'No first order ID'
    lines = associations.loc[matched].copy()
    if not lines.empty:
        # Do not choose one prescription arbitrarily if a line has conflicting attributes.
        conflicts = lines.groupby(KEYS)[DIMENSIONS].nunique(dropna=False)
        if conflicts.gt(1).any().any():
            raise ValueError('shared order line has conflicting channel/upload/status/block classifications')
        lines['associated_prescriptions'] = lines.groupby(KEYS).rx_id.transform('size')
        lines = lines.drop_duplicates(KEYS).copy()
    else:
        lines['associated_prescriptions'] = pd.Series(dtype='int64')
    groups = lines.groupby(DIMENSIONS).size().reset_index(name='order_lines')
    groups['percent_of_cohort'] = 100 * groups.order_lines / len(lines) if len(lines) else 0.
    audits = {f'prescription_{key}': value for key, value in audits.items()}
    for key in ['accepted_window_upload_rows','excluded_window_upload_rows']:
        if key in frame:
            audits['prescription_'+key] = int(frame[key].iloc[0]) if len(frame) and pd.notna(frame[key].iloc[0]) else 0
    audits.update(cohort_prescriptions=len(frame), matched_prescriptions=int(matched.sum()),
                  missing_first_order_id=int(frame.first_order_id.isna().sum()),
                  missing_or_invalid_first_order_item_id=int((frame.first_order_id.notna()
                                                            & frame.first_order_line_id.isna()).sum()),
                  unmatched_first_order_line=int((frame.first_order_id.notna() & frame.first_order_line_id.notna()
                                                 & ~matched).sum()),
                  distinct_order_lines=len(lines),
                  repeated_prescription_line_associations=int(matched.sum())-len(lines),
                  shipment_source_rows=int(lines.line_source_rows.sum()),
                  extra_shipment_rows_collapsed=int(lines.line_source_rows.sum())-len(lines),
                  order_lines_with_upload=int(lines.upload_count.gt(0).sum()),
                  order_lines_without_recorded_block_reason=int(lines.order_item_block_reason.astype('string').str.strip().replace('', pd.NA).isna().sum()),
                  canceled_lines_on_uncanceled_orders=int((lines.order_line_status.astype('string').str.strip().str.upper().eq('X')
                      & ~lines.order_status.astype('string').str.strip().str.upper().eq('X')).sum()))
    audits.update(missing_accepted_state_change=int(lines.missing_accepted_state_change.sum()),
                  missing_placement=int(lines.missing_placement.sum()),
                  negative_accepted_duration=int(lines.negative_accepted_duration.sum()))
    if (audits['matched_prescriptions'] + audits['missing_first_order_id']
            + audits['missing_or_invalid_first_order_item_id'] + audits['unmatched_first_order_line'] != len(frame)
            or groups.order_lines.sum() != len(lines)):
        raise ValueError('line eligibility/counts do not reconcile')
    return associations, lines, groups, audits


def flows_for_rendering(groups):
    """Keep block reasons in grouped data, outside the displayed stages."""
    groups = groups.assign(upload_node=groups.cancellation_reason_group + ' / ' + groups.upload_group)
    stages = [('channel', 'Channel: '), ('order_group', 'First order line status: '),
              ('cancel_reason', 'First order cancel reason: '),
              ('upload_node', 'Accepted upload: ')]
    rows = []
    for transition, ((source, source_label), (target, target_label)) in enumerate(zip(stages, stages[1:]), 1):
        for (left, right), count in groups.groupby([source, target]).order_lines.sum().items():
            rows.append((transition, source_label+left, target_label+right, int(count)))
    # The shared renderer uses "prescriptions" internally; each observation here is a line.
    flows = pd.DataFrame(rows, columns=['transition', 'source', 'target', 'prescriptions'])
    total = int(groups.order_lines.sum())
    flows['percent_of_cohort'] = 100 * flows.prescriptions / total if total else 0.
    if not flows.empty:
        if not flows.groupby('transition').prescriptions.sum().eq(total).all():
            raise ValueError('invalid Sankey transition totals')
        incoming = flows.groupby('target').prescriptions.sum()
        outgoing = flows.groupby('source').prescriptions.sum()
        internal = incoming.index.intersection(outgoing.index)
        if not incoming.loc[internal].equals(outgoing.loc[internal]):
            raise ValueError('unbalanced Sankey intermediate nodes')
    flows.attrs['node_alignment'] = 'left'
    flows.attrs['columns'] = [(prefix, heading) for (_, prefix), heading in zip(stages,
        ['Approval channel', 'Order line status', 'Cancellation reason', 'Accepted upload'])]
    nodes = set(flows.source) | set(flows.target)
    flows.attrs['node_colors'] = {node: '#AF7AA1' for node in nodes if node.startswith('First order cancel reason: ')}
    return flows


def write_outputs(frame, metadata, diagram_dir, table_dir, source_dir=None, table_prefix='', data_dir=None):
    associations, lines, groups, audit = summarize(frame)
    start, end, upload_start = map(pd.Timestamp, [metadata['start_date'], metadata['end_date_exclusive'],
                                                 metadata['upload_start_date']])
    if (associations.rx_creation_datetime.isna().any()
            or not associations.rx_creation_datetime.between(start, end, inclusive='left').all()):
        raise ValueError('prescription outside cohort window')
    upload_end = end + pd.Timedelta(days=UPLOAD_FOLLOWUP_DAYS)
    upload_start_utc = upload_start.tz_localize('UTC')
    upload_end_utc = upload_end.tz_localize('UTC')
    if not associations.first_upload_at_utc.dropna().between(upload_start_utc, upload_end_utc, inclusive='left').all():
        raise ValueError('upload outside search window')
    diagram_dir.mkdir(parents=True, exist_ok=True)
    source_dir = source_dir if source_dir is not None else diagram_dir
    source_dir.mkdir(parents=True, exist_ok=True)
    table_dir.mkdir(parents=True, exist_ok=True)
    field = 'ORDER_ORDER_LINE_STATUS'
    note = ('Only current ACCEPTED entities qualify. Select earliest entity creation, with UPLOAD_ID ties; ' f"Prescription creation {metadata['start_date']} inclusive to {metadata['end_date_exclusive']} exclusive UTC; "
            f"uploads {metadata['upload_start_date']} inclusive to {upload_end.date()} exclusive UTC. "
            f"Extracted {metadata['extracted_at_utc']}.\n\n"
            'Source: EDLDB.BT_HCA_HCDM.ORDER_LINE_COST_MEASURES_RXP. Join FIRST_ORDER_ID = ORDER_ID AND '
            'numeric FIRST_ORDERITEM_ID = ORDER_LINE_ID; no RX_ID join to the order-line view. '
            'Each matched (ORDER_ID, ORDER_LINE_ID) is counted once, collapsing shipment rows. '
            'Prescriptions without usable first-order keys or without a matching line are excluded from '
            'the Sankey denominators and reported in the audit. '
            f'The status stage uses the latest raw {field} codes directly; blank/null statuses are explicit. '
            'ORDER_ITEM_BLOCK_REASON is retained in data and tables but omitted from diagrams. '
            'Its grouped classification is populated for known non-D statuses, with explicit not-applicable values for D/unknown. Blank/null reasons are labeled '
            '[No block reason recorded], which does not independently establish an unblocked item. '
            'All figures show line status followed by raw ORDER_CANCEL_REASON; order status is retained only in data. '
            'Blank/null cancellation reasons are labeled [No cancellation reason recorded]; this does not establish '
            'whether the overall order was canceled. '
            'Multiple prescriptions sharing a line are counted once; conflicting classifications fail validation. '
            'Accepted-entity matching retains the DIET_PRESCRIPTION expanded RX_ID + numeric CUSTOMER_ID rules, '
            'without file/association flags, prescription-status/deletion filters or upload-after-creation requirement. '
            'A matching entity does not verify file presence. Approval channel → line status → '
            'cancellation reason → upload presence is a categorical breakdown, not a chronological journey. Full percentages use all matched distinct lines; focused '
            'percentages use matched distinct CUSTOMER_UPLOAD lines. The separate non-D figure uses only '
            'known non-D CUSTOMER_UPLOAD lines as its denominator. Upload endpoints separate lines with a '
            'recorded cancellation reason from lines without one, each split into has/no matching accepted upload. '
            'Blank/null/whitespace reasons mean no recorded reason, not proof of an uncanceled order. '
            'All three figures include the explicit line-status column. '
            'Column headers identify stages; visible node labels omit repeated stage prefixes. '
            'Percentages retain the whole-figure denominator.\n\n')
    non_d_lines = lines.loc[non_d(lines) & lines.channel.eq('CUSTOMER_UPLOAD')]
    audit.update(non_d_order_lines=int(non_d(lines).sum()),
                 customer_upload_non_d_order_lines=len(non_d_lines),
                 d_order_lines=int(lines.order_group.eq('D').sum()),
                 unknown_line_statuses=int(lines.order_group.eq('[Unknown line status]').sum()))
    outputs = [('associations', associations), ('order-lines', lines), ('distribution', groups),
               ('audit', pd.DataFrame(audit.items(), columns=['measure', 'count']))]
    for scope, selected in [('all', lines), ('customer-upload', lines.loc[lines.channel.eq('CUSTOMER_UPLOAD')]),
                            ('non-d', non_d_lines)]:
        selected_groups = selected.groupby(DIMENSIONS).size().reset_index(name='order_lines')
        n = len(selected)
        selected_groups['percent_of_cohort'] = 100 * selected_groups.order_lines / n if n else 0.
        flows = flows_for_rendering(selected_groups)
        exported_flows = flows.rename(columns={'prescriptions': 'order_lines'})
        prefix = '' if scope == 'all' else f'{scope}-'
        outputs.extend([(prefix+'flows', exported_flows)])
        if scope != 'all':
            outputs.append((prefix+'distribution', selected_groups))
        last = (date.fromisoformat(metadata['end_date_exclusive'])-timedelta(days=1)).isoformat()
        scope_title = {'all': 'All approval channels', 'customer-upload': 'CUSTOMER_UPLOAD only',
                       'non-d': 'CUSTOMER_UPLOAD only · non-D line statuses'}[scope]
        stages = 'line status → cancellation reason → upload presence by reason recorded/missing'
        title = (f"CMPU vet-diet first-order lines | {scope_title} | "
                 f"Rx: {metadata['start_date']}–{last}; uploads: {metadata['upload_start_date']}–{(upload_end - pd.Timedelta(days=1)).date()} | "
                 f"Denominator: {n:,} order lines; {stages}")
        stem = (f"cmpu-first-order-lines_{scope}_uploads-{metadata['upload_start_date']}_"
                f"{(upload_end - pd.Timedelta(days=1)).date()}_{legacy.TIMING_VARIANT}_sankey")
        legacy.render_sankey(flows, source_dir / f'{stem}.mmd', diagram_dir / f'{stem}.png', title)
    # Compare order-level and line-level statuses from the same line population.
    comparison = lines.groupby(['order_status', 'order_line_status'], dropna=False).size().reset_index(name='order_lines')
    outputs.append(('order-vs-line-status', comparison))
    outputs.append(('block-reasons', non_d_lines.groupby('block_reason').size().reset_index(name='order_lines')))
    outputs.append(('non-d-order-lines', non_d_lines))
    for name, data in outputs:
        write_text(table_dir / (table_prefix + f'{name}.md'), f'# {name.title()}\n\n'+note+markdown_table(data)+'\n')
    write_text(table_dir / (table_prefix + 'summary.md'), '# First-order lines\n\n'+note+markdown_table(
        pd.DataFrame(audit.items(), columns=['measure', 'count']))+'\n\n'+markdown_table(groups)+'\n')
    image_prefix = (f"cmpu-first-order-lines_{{scope}}_uploads-{metadata['upload_start_date']}_"
                    f"{(upload_end - pd.Timedelta(days=1)).date()}_{legacy.TIMING_VARIANT}_sankey.png")
    write_text(diagram_dir / 'cmpu-first-order-lines.md', '# REFNUM 14: first-order lines\n\n'+note+
        (f'![All channels]({image_prefix.format(scope="all")})\n\n' if len(lines) else 'No matched order lines.\n\n')+
        (f'![CUSTOMER_UPLOAD]({image_prefix.format(scope="customer-upload")})\n' if lines.channel.eq('CUSTOMER_UPLOAD').any()
         else 'No matched CUSTOMER_UPLOAD order lines.\n')+
        (f'\n![CUSTOMER_UPLOAD non-D line statuses]({image_prefix.format(scope="non-d")})\n' if len(non_d_lines)
         else '\nNo matched known non-D CUSTOMER_UPLOAD order lines.\n'))
    if data_dir is not None:
        data_dir.mkdir(parents=True, exist_ok=True)
        exported = {'associations':associations,'lines':lines,'distribution':groups,
                    'audit':pd.DataFrame(audit.items(),columns=['measure','count'])}
        for name,data in exported.items():
            data.to_parquet(data_dir/f'{name}.parquet',index=False)
        write_text(data_dir/'exports.json',json.dumps({
            'source_sha256':metadata['parquet_sha256'],
            'files':{f'{name}.parquet':legacy.digest(data_dir/f'{name}.parquet') for name in exported}},indent=2)+'\n')
    return audit


@click.command()
@click.option('--start-date', default='2026-08-15', show_default=True)
@click.option('--end-date', default='2026-10-15', show_default=True,
              help='Exclusive prescription end; uploads extend 11 days beyond this date.')
@click.option('--upload-start-date', default='2026-08-01', show_default=True)
@click.option('--cached', is_flag=True)
@click.option('--print-sql', is_flag=True)
def main(start_date, end_date, upload_start_date, cached, print_sql):
    try:
        sql = render_sql(start_date, end_date, upload_start_date)
        if print_sql:
            click.echo(sql)
            return
        upload_end = (date.fromisoformat(end_date) + timedelta(days=UPLOAD_FOLLOWUP_DAYS)).isoformat()
        period = legacy.period_name(start_date, end_date, upload_start_date) + f'_uploads-end-{upload_end}'
        period += '_' + legacy.TIMING_VARIANT
        directory = ROOT / 'data' / NAME / (period+'_block-reasons')
        parquet, manifest = directory / 'source.parquet', directory / 'source.json'
        if cached:
            metadata = json.loads(manifest.read_text())
            if (metadata.get('sql') != sql or metadata.get('parquet_sha256') != legacy.digest(parquet)
                    or [metadata.get(k) for k in ['start_date', 'end_date_exclusive', 'upload_start_date']]
                    != [start_date, end_date, upload_start_date]):
                raise ValueError('cached SQL, dates or fingerprint differs; refresh extract')
            frame = pd.read_parquet(parquet).rename(columns=str.lower)
        else:
            directory.mkdir(parents=True, exist_ok=True)
            sql_dir = ROOT / 'src/autogenerated' / NAME / period
            sql_dir.mkdir(parents=True, exist_ok=True)
            query = sql_dir / 'cmpu_first_order_line_status.sql'
            write_text(query, sql+'\n')
            manifest.unlink(missing_ok=True)
            subprocess.run([sys.executable, str(legacy.RUNNER), str(query), '--output-parquet', str(parquet.relative_to(ROOT)),
                            '--sql-log-dir', str((sql_dir/'sql-history').relative_to(ROOT))], cwd=ROOT, check=True)
            frame = pd.read_parquet(parquet).rename(columns=str.lower)
            summarize(frame)
            metadata = dict(sql=sql, sql_sha256=hashlib.sha256(sql.encode()).hexdigest(),
                parquet_sha256=legacy.digest(parquet), start_date=start_date, end_date_exclusive=end_date,
                upload_start_date=upload_start_date, upload_end_date_exclusive=upload_end,
                upload_followup_days=UPLOAD_FOLLOWUP_DAYS, extracted_at_utc=datetime.now(timezone.utc).isoformat(),
                source_extracted_at=frame.extracted_at_session_time.unique().tolist(),
                warehouse=frame.extraction_warehouse.unique().tolist())
            write_text(manifest, json.dumps(metadata, indent=2)+'\n')
        metadata = dict(metadata, status_field='ORDER_ORDER_LINE_STATUS', block_reason_field='ORDER_ITEM_BLOCK_REASON')
        scope = period+'_line-status-non-d-block-reasons'
        date_range = f'{start_date}_{date.fromisoformat(end_date) - timedelta(days=1)}'
        source_dir = ROOT / 'src/diagrams' / date_range
        diagram_dir = ROOT / 'outputs/diagrams' / date_range
        table_dir, table_prefix = table_layout(ROOT, NAME, scope)
        audit = write_outputs(frame, metadata, diagram_dir,
                              table_dir, source_dir=source_dir, table_prefix=table_prefix, data_dir=directory)
        click.echo(f'Mermaid sources: {source_dir}\nSankey figures: {diagram_dir}')
        click.echo(json.dumps(audit, indent=2))
    except (ValueError, OSError, KeyError, subprocess.CalledProcessError) as error:
        raise click.ClickException(str(error)) from error


if __name__ == '__main__':
    main()
