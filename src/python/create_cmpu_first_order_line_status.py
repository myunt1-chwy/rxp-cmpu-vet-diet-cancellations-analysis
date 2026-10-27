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
from src.python.markdown_tables import markdown_table

ROOT = legacy.ROOT
NAME = 'cmpu-first-order-line-status'
TEMPLATE = ROOT / 'src/sql/cmpu_first_order_line_status.sql'
UPLOAD_FOLLOWUP_DAYS = 11
KEYS = ['matched_order_id', 'matched_order_line_id']


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
    associations['order_group'] = (frame.order_line_status.astype('string').str.strip().str.upper()
                                   .replace('', pd.NA).fillna('[Unknown line status]'))
    associations['block_reason'] = (frame.order_item_block_reason.astype('string').str.strip()
                                     .replace('', pd.NA).fillna('[No block reason recorded]'))
    associations['cancel_reason'] = (frame.order_cancel_reason.astype('string').str.strip()
                                      .replace('', pd.NA).fillna('[No cancellation reason recorded]'))
    associations.loc[associations.order_group.eq('D'), 'block_reason'] = '[Not applicable: status D]'
    associations.loc[associations.order_group.eq('[Unknown line status]'), 'block_reason'] = '[Not applicable: unknown line status]'
    associations['line_match'] = 'Matched'
    associations.loc[~matched, 'line_match'] = 'First order line not found'
    associations.loc[frame.first_order_line_id.isna(), 'line_match'] = 'Missing or invalid first order item ID'
    associations.loc[frame.first_order_id.isna(), 'line_match'] = 'No first order ID'
    lines = associations.loc[matched].copy()
    if not lines.empty:
        # Do not choose one prescription arbitrarily if a line has conflicting attributes.
        conflicts = lines.groupby(KEYS)[['channel', 'cancel_reason', 'order_group', 'block_reason', 'upload_group']].nunique(dropna=False)
        if conflicts.gt(1).any().any():
            raise ValueError('shared order line has conflicting channel/upload/status/block classifications')
        lines['associated_prescriptions'] = lines.groupby(KEYS).rx_id.transform('size')
        lines = lines.drop_duplicates(KEYS).copy()
    else:
        lines['associated_prescriptions'] = pd.Series(dtype='int64')
    groups = lines.groupby(['channel', 'cancel_reason', 'order_group', 'block_reason', 'upload_group']).size().reset_index(name='order_lines')
    groups['percent_of_cohort'] = 100 * groups.order_lines / len(lines) if len(lines) else 0.
    audits = {f'prescription_{key}': value for key, value in audits.items()}
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
    if (audits['matched_prescriptions'] + audits['missing_first_order_id']
            + audits['missing_or_invalid_first_order_item_id'] + audits['unmatched_first_order_line'] != len(frame)
            or groups.order_lines.sum() != len(lines)):
        raise ValueError('line eligibility/counts do not reconcile')
    return associations, lines, groups, audits


def flows_for_rendering(groups, show_line_status=True):
    """Channel → cancel reason → line status → item block → upload presence."""
    groups = groups.assign(block_node=groups.order_group + ' / ' + groups.block_reason,
                           upload_node=groups.order_group + ' / ' + groups.upload_group)
    stages = [('channel', 'Channel: '), ('cancel_reason', 'First order cancel reason: '),
              ('order_group', 'First order line status: '), ('block_node', 'Item block reason: '),
              ('upload_node', 'Matching upload: ')]
    if not show_line_status:
        stages = [stage for stage in stages if stage[0] != 'order_group']
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
    return flows


def write_outputs(frame, metadata, diagram_dir, table_dir, source_dir=None):
    associations, lines, groups, audit = summarize(frame)
    start, end, upload_start = map(pd.Timestamp, [metadata['start_date'], metadata['end_date_exclusive'],
                                                 metadata['upload_start_date']])
    if (associations.rx_creation_datetime.isna().any()
            or not associations.rx_creation_datetime.between(start, end, inclusive='left').all()):
        raise ValueError('prescription outside cohort window')
    upload_end = end + pd.Timedelta(days=UPLOAD_FOLLOWUP_DAYS)
    if not associations.first_upload_at_utc.dropna().between(upload_start, upload_end, inclusive='left').all():
        raise ValueError('upload outside search window')
    diagram_dir.mkdir(parents=True, exist_ok=True)
    source_dir = source_dir if source_dir is not None else diagram_dir
    source_dir.mkdir(parents=True, exist_ok=True)
    table_dir.mkdir(parents=True, exist_ok=True)
    field = 'ORDER_ORDER_LINE_STATUS'
    note = (f"Prescription creation {metadata['start_date']} inclusive to {metadata['end_date_exclusive']} exclusive UTC; "
            f"uploads {metadata['upload_start_date']} inclusive to {upload_end.date()} exclusive UTC. "
            f"Extracted {metadata['extracted_at_utc']}.\n\n"
            'Source: EDLDB.BT_HCA_HCDM.ORDER_LINE_COST_MEASURES_RXP. Join FIRST_ORDER_ID = ORDER_ID AND '
            'numeric FIRST_ORDERITEM_ID = ORDER_LINE_ID; no RX_ID join to the order-line view. '
            'Each matched (ORDER_ID, ORDER_LINE_ID) is counted once, collapsing shipment rows. '
            'Prescriptions without usable first-order keys or without a matching line are excluded from '
            'the Sankey denominators and reported in the audit. '
            f'The status stage uses the latest raw {field} codes directly; blank/null statuses are explicit. '
            'Actual ORDER_ITEM_BLOCK_REASON is shown only for known non-D statuses. D and unknown statuses '
            'use explicit not-applicable nodes so all lines continue to upload presence. Blank/null reasons are labeled '
            '[No block reason recorded], which does not independently establish an unblocked item. '
            'All figures show raw ORDER_CANCEL_REASON between channel and line status. '
            'Blank/null cancellation reasons are labeled [No cancellation reason recorded]; this does not establish '
            'whether the overall order was canceled. '
            'Multiple prescriptions sharing a line are counted once; conflicting classifications fail validation. '
            'Upload matching retains the DIET_PRESCRIPTION expanded RX_ID + numeric CUSTOMER_ID rules, '
            'without file/association flags, prescription-status/deletion filters or upload-after-creation requirement. '
            'A matching entity does not verify file presence. Approval channel → first-order cancel reason → '
            'line status → item block reason → upload presence is a categorical breakdown. Full percentages use all matched distinct lines; focused '
            'percentages use matched distinct CUSTOMER_UPLOAD lines. The separate non-D figure uses only '
            'known non-D CUSTOMER_UPLOAD lines as its denominator. Item-block and upload nodes retain their '
            'line-status identity, so X, D and other statuses have separate upload/no-upload endpoints even '
            'when they share the same block reason. The non-D figure omits the explicit line-status column, '
            'while retaining all non-D statuses and their labels on block/upload nodes. '
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
        dimensions = ['channel', 'cancel_reason', 'order_group', 'block_reason', 'upload_group']
        selected_groups = selected.groupby(dimensions).size().reset_index(name='order_lines')
        n = len(selected)
        selected_groups['percent_of_cohort'] = 100 * selected_groups.order_lines / n if n else 0.
        flows = flows_for_rendering(selected_groups, show_line_status=scope != 'non-d')
        if scope == 'non-d':
            flows.attrs['columns'] = [
                ('Channel: ', 'Approval channel'),
                ('First order cancel reason: ', 'First-order cancel reason'),
                ('Item block reason: ', 'Item block reason'),
                ('Matching upload: ', 'Matching upload'),
            ]
            nodes = set(flows.source) | set(flows.target)
            flows.attrs['node_colors'] = {
                node: '#AF7AA1' if node.startswith('First order cancel reason: ') else '#8CC9EE'
                for node in nodes if node.startswith(('First order cancel reason: ', 'Item block reason: '))
            }
        exported_flows = flows.rename(columns={'prescriptions': 'order_lines'})
        prefix = '' if scope == 'all' else f'{scope}-'
        outputs.extend([(prefix+'flows', exported_flows)])
        if scope != 'all':
            outputs.append((prefix+'distribution', selected_groups))
        last = (date.fromisoformat(metadata['end_date_exclusive'])-timedelta(days=1)).isoformat()
        scope_title = {'all': 'All approval channels', 'customer-upload': 'CUSTOMER_UPLOAD only',
                       'non-d': 'CUSTOMER_UPLOAD only · non-D line statuses'}[scope]
        stages = ('cancel reason → item block → upload presence' if scope == 'non-d'
                  else 'cancel reason → line status → item block → upload presence')
        title = (f"CMPU vet-diet first-order lines | {scope_title} | "
                 f"Rx: {metadata['start_date']}–{last}; uploads: {metadata['upload_start_date']}–{(upload_end - pd.Timedelta(days=1)).date()} | "
                 f"Denominator: {n:,} order lines; {stages}")
        stem = (f"cmpu-first-order-lines_{scope}_uploads-{metadata['upload_start_date']}_"
                f"{(upload_end - pd.Timedelta(days=1)).date()}_sankey")
        legacy.render_sankey(flows, source_dir / f'{stem}.mmd', diagram_dir / f'{stem}.png', title)
    # Compare order-level and line-level statuses from the same line population.
    comparison = lines.groupby(['order_status', 'order_line_status'], dropna=False).size().reset_index(name='order_lines')
    outputs.append(('order-vs-line-status', comparison))
    outputs.append(('block-reasons', non_d_lines.groupby('block_reason').size().reset_index(name='order_lines')))
    outputs.append(('non-d-order-lines', non_d_lines))
    for name, data in outputs:
        (table_dir / f'{name}.md').write_text(f'# {name.title()}\n\n'+note+markdown_table(data)+'\n')
    (table_dir / 'summary.md').write_text('# First-order lines\n\n'+note+markdown_table(
        pd.DataFrame(audit.items(), columns=['measure', 'count']))+'\n\n'+markdown_table(groups)+'\n')
    image_prefix = (f"cmpu-first-order-lines_{{scope}}_uploads-{metadata['upload_start_date']}_"
                    f"{(upload_end - pd.Timedelta(days=1)).date()}_sankey.png")
    (diagram_dir / 'cmpu-first-order-lines.md').write_text('# REFNUM 14: first-order lines\n\n'+note+
        (f'![All channels]({image_prefix.format(scope="all")})\n\n' if len(lines) else 'No matched order lines.\n\n')+
        (f'![CUSTOMER_UPLOAD]({image_prefix.format(scope="customer-upload")})\n' if lines.channel.eq('CUSTOMER_UPLOAD').any()
         else 'No matched CUSTOMER_UPLOAD order lines.\n')+
        (f'\n![CUSTOMER_UPLOAD non-D line statuses]({image_prefix.format(scope="non-d")})\n' if len(non_d_lines)
         else '\nNo matched known non-D CUSTOMER_UPLOAD order lines.\n'))
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
            query.write_text(sql+'\n')
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
            manifest.write_text(json.dumps(metadata, indent=2)+'\n')
        metadata = dict(metadata, status_field='ORDER_ORDER_LINE_STATUS', block_reason_field='ORDER_ITEM_BLOCK_REASON')
        scope = period+'_line-status-non-d-block-reasons'
        date_range = f'{start_date}_{date.fromisoformat(end_date) - timedelta(days=1)}'
        source_dir = ROOT / 'src/diagrams' / date_range
        diagram_dir = ROOT / 'outputs/diagrams' / date_range
        audit = write_outputs(frame, metadata, diagram_dir,
                              ROOT/'outputs/tables'/NAME/scope, source_dir=source_dir)
        click.echo(f'Mermaid sources: {source_dir}\nSankey figures: {diagram_dir}')
        click.echo(json.dumps(audit, indent=2))
    except (ValueError, OSError, KeyError, subprocess.CalledProcessError) as error:
        raise click.ClickException(str(error)) from error


if __name__ == '__main__':
    main()
