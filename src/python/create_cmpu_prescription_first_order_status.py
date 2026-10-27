"""REFNUM 14: prescription-level approval/channel/order/upload Sankey."""
import csv
from datetime import date, datetime, timedelta, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import xml.etree.ElementTree as ET

import click
from jinja2 import Environment, StrictUndefined
import pandas as pd

from src.python.markdown_tables import markdown_table

ROOT = Path(__file__).resolve().parents[2]
NAME = 'cmpu-prescription-first-order-status'
TEMPLATE = ROOT / 'src/sql/cmpu_prescription_first_order_status.sql'
RUNNER = ROOT / '.agents/skills/rxp-sql/scripts/run_snowflake_query.py'
RENDERER = ROOT / '.agents/skills/mermaid-diagrams/scripts/render.py'
SVG_RASTERIZER = ROOT / 'scripts/render_sankey_svg.cjs'
AUDIT_COLUMNS = ['window_upload_rows', 'invalid_upload_source_rows', 'uploads_missing_customer',
                 'uploads_invalid_customer', 'upload_rows_missing_rx', 'upload_rows_malformed_rx']
REASONS = {'aged order': 'Aged Order',
           'customer initiated cancellation': 'Customer Initiated Cancellation',
           'customer request': 'Customer Request'}
TEXT_SCALE = 1.2
NODE_FONT_SIZE = 21  # An additional 25% over the previous 16.8px labels.


def render_sql(start, end, upload_start=None):
    start, end = date.fromisoformat(start), date.fromisoformat(end)
    upload_start = date.fromisoformat(upload_start) if upload_start else start
    if start >= end:
        raise ValueError('start date must precede exclusive end date')
    if upload_start > start:
        raise ValueError('upload start date must be on or before prescription start date')
    return Environment(undefined=StrictUndefined).from_string(TEMPLATE.read_text()).render(
        start_date=start.isoformat(), end_date=end.isoformat(), upload_start_date=upload_start.isoformat())


def period_name(start, end, upload_start=None):
    period = f'{start}_{end}'
    return f'{period}_uploads-from-{upload_start}' if upload_start and upload_start != start else period


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def summarize(frame):
    frame = frame.rename(columns=str.lower).copy()
    if frame.rx_id.isna().any() or frame.rx_id.duplicated().any() or not frame.rx_source_rows.eq(1).all():
        raise ValueError('missing or duplicate prescription source IDs')
    if not frame.order_source_rows.isin([0, 1]).all():
        raise ValueError('duplicate order source records')
    if frame.upload_count.isna().any() or frame.upload_count.lt(0).any() or frame.upload_count.mod(1).ne(0).any():
        raise ValueError('invalid upload counts')
    if frame.upload_count.gt(0).ne(frame.first_upload_at_utc.notna()).any():
        raise ValueError('upload count/timestamp evidence disagrees')
    if (frame.cohort_window_upload_count.isna().any() or frame.cohort_window_upload_count.lt(0).any()
            or frame.cohort_window_upload_count.mod(1).ne(0).any()
            or frame.cohort_window_upload_count.gt(frame.upload_count).any()):
        raise ValueError('invalid prescription-window upload counts')
    if (frame.first_order_id.isna() & frame.order_source_rows.ne(0)).any():
        raise ValueError('order match without a first order ID')
    audits = {}
    for column in AUDIT_COLUMNS:
        if frame[column].nunique(dropna=False) > 1 or frame[column].isna().any():
            raise ValueError('inconsistent upload audits')
        audits[column] = int(frame[column].iloc[0]) if len(frame) else None
    if audits['invalid_upload_source_rows']:
        raise ValueError('missing or duplicate upload source IDs')
    frame['channel'] = frame.approval_channel.astype('string').str.strip().replace('', pd.NA).fillna('[Unknown approval channel]')
    status = frame.order_status.astype('string').str.strip().str.upper().replace('', pd.NA)
    reason = frame.order_cancel_reason.astype('string').str.strip().str.lower().replace('', pd.NA)
    frame['order_group'] = 'Not canceled'
    canceled = status.eq('X').fillna(False)
    frame.loc[canceled, 'order_group'] = reason[canceled].map(REASONS).fillna('Other cancellation reason')
    frame.loc[canceled & reason.isna(), 'order_group'] = 'Canceled - missing reason'
    frame.loc[status.isna(), 'order_group'] = 'Unknown order status'
    frame.loc[frame.order_source_rows.eq(0), 'order_group'] = 'First order not found'
    frame.loc[frame.first_order_id.isna(), 'order_group'] = 'No first order ID'
    frame['upload_group'] = frame.upload_count.gt(0).map({True: 'Has matching upload', False: 'No matching upload'})
    groups = frame.groupby(['channel', 'upload_group', 'order_group']).size().reset_index(name='prescriptions')
    groups['percent_of_cohort'] = 100 * groups.prescriptions / len(frame) if len(frame) else 0.
    if int(groups.prescriptions.sum()) != len(frame):
        raise ValueError('group counts do not conserve the cohort')
    audits.update(cohort_prescriptions=len(frame),
                  prescriptions_with_upload=int(frame.upload_count.gt(0).sum()),
                  prescriptions_matched_only_by_earlier_uploads=int((frame.upload_count.gt(0) & frame.cohort_window_upload_count.eq(0)).sum()),
                  prescriptions_missing_customer=int(frame.customer_id.isna().sum()))
    return frame, groups, audits


def make_flows(groups):
    """Channel-specific middle nodes preserve the complete three-way split."""
    rows = []
    for (channel, upload), subset in groups.groupby(['channel', 'upload_group'], sort=True):
        source, middle = f'Channel: {channel}', f'{channel} / {upload}'
        rows.append((1, source, middle, int(subset.prescriptions.sum())))
        rows.extend((2, middle, f'First order: {row.order_group}', int(row.prescriptions))
                    for row in subset.itertuples(index=False) if row.prescriptions > 0)
    flows = pd.DataFrame(rows, columns=['transition', 'source', 'target', 'prescriptions'])
    total = int(groups.prescriptions.sum())
    flows['percent_of_cohort'] = 100 * flows.prescriptions / total if total else 0.
    if not flows.empty:
        if flows.prescriptions.le(0).any() or not flows.groupby('transition').prescriptions.sum().eq(total).all():
            raise ValueError('invalid Sankey transition totals')
        incoming = flows.loc[flows.transition.eq(1)].set_index('target').prescriptions
        outgoing = flows.loc[flows.transition.eq(2)].groupby('source').prescriptions.sum()
        if not incoming.sort_index().equals(outgoing.sort_index()):
            raise ValueError('unbalanced Sankey intermediate nodes')
    return flows


def mermaid_source(flows, title=None):
    denominator = int(flows.loc[flows.transition.eq(1)].prescriptions.sum())
    totals = flows.loc[flows.transition.eq(1)].groupby('source').prescriptions.sum().to_dict()
    totals.update(flows.groupby('target').prescriptions.sum().to_dict())
    labels = {node: f'{node} ({count:,}; {100 * count / denominator:.2f}%)'
              for node, count in totals.items()}
    # Keep category colors consistent between the full and focused diagrams.
    palette = {
        'Channel: CUSTOMER_UPLOAD': '#4E79A7', 'Channel: VERBAL': '#AF7AA1',
        'Channel: CUSTOMER_EMAIL': '#FF9DA7', 'Channel: FAX': '#F28E2C',
        'Channel: CLINIC_EMAIL': '#BAB0AB', 'Channel: PH': '#8CC9EE',
        'Channel: SNAIL_MAIL': '#B6A7D8', 'Channel: PARTNER': '#E15759',
        'First order: Aged Order': '#AF7AA1',
        'First order: Customer Initiated Cancellation': '#FF9DA7',
        'First order: Customer Request': '#E15759',
        'First order: Not canceled': '#4E79A7',
        'First order: Other cancellation reason': '#BAB0AB',
        'First order: No first order ID': '#AEB9C3',
        'First order line status: X': '#E15759',
        'First order line status: D': '#4E79A7',
        'First order line status: S': '#8CC9EE',
        'First order line status: C': '#AF7AA1',
        'First order line status: R': '#F28E2C',
    }
    palette.update(flows.attrs.get('node_colors', {}))
    node_colors = {
        label: ('#8CC9EE' if ' / No matching upload' in node or node == 'Matching upload: No matching upload'
                else '#F28E2C' if ' / Has matching upload' in node or node == 'Matching upload: Has matching upload'
                else palette.get(node, '#BAB0AB'))
        for node, label in labels.items()
    }
    buffer = io.StringIO()
    # Quote every label so commas and embedded quotes remain valid Sankey CSV.
    writer = csv.writer(buffer, lineterminator='\n', quoting=csv.QUOTE_NONNUMERIC)
    for row in flows.itertuples(index=False):
        writer.writerow([labels[row.source], labels[row.target], row.prescriptions])
    height = int(max(1000, 55 * max(flows.groupby('transition').source.nunique().max(),
                                   flows.groupby('transition').target.nunique().max())))
    config = {'theme': 'base', 'themeVariables': {'fontFamily': 'Arial', 'fontSize': f'{18 * TEXT_SCALE:g}px'},
              'themeCSS': (f'.node-labels, .node-labels text {{ font-size: {NODE_FONT_SIZE:g}px; font-weight: bold; }} '
                           '.links { stroke-opacity: 0.75; } .link { mix-blend-mode: normal !important; } '
                           f'[class$="TitleText"] {{ font-size: {24 * TEXT_SCALE:g}px; '
                           'paint-order: stroke; stroke: white; stroke-width: 3px; stroke-linejoin: round; }'),
              'sankey': {'width': 1200 * int(flows.transition.max()), 'height': height, 'linkColor': 'source',
                         'nodeColors': node_colors,
                         'nodeAlignment': flows.attrs.get('node_alignment', 'justify'), 'showValues': False,
                         'useMaxWidth': False, 'nodePadding': 32, 'labelStyle': 'outlined'}}
    heading = 'title: ' + json.dumps(title) + '\n' if title else ''
    return '---\n' + heading + 'config: ' + json.dumps(config) + '\n---\nsankey-beta\n' + buffer.getvalue()


def add_title(svg, title, columns=None):
    """Mermaid's Sankey renderer ignores visible frontmatter titles."""
    namespace = 'http://www.w3.org/2000/svg'
    ET.register_namespace('', namespace)
    try:
        diagram = ET.fromstring(svg)
    except ET.ParseError as error:
        raise ValueError('Mermaid produced invalid SVG') from error
    _, _, width, height = map(float, diagram.attrib['viewBox'].split())
    header_height = 96 * TEXT_SCALE + (64 if columns else 0)
    wrapper = ET.Element(f'{{{namespace}}}svg', width=str(width), height=str(height + header_height),
                         viewBox=f'0 0 {width} {height + header_height}', role='img',
                         attrib={'aria-label': title})
    ET.SubElement(wrapper, f'{{{namespace}}}title').text = title
    parts = title.split(' | ', 2)
    heading, subtitle = ' | '.join(parts[:2]), parts[2] if len(parts) > 2 else ''
    for text, y, size, weight in [(heading, 34, 28, 'bold'), (subtitle, 65, 18, 'normal')]:
        label = ET.SubElement(wrapper, f'{{{namespace}}}text', x=str(width / 2), y=str(y * TEXT_SCALE),
            attrib={'text-anchor': 'middle', 'font-family': 'Arial, sans-serif', 'font-size': f'{size * TEXT_SCALE:g}',
                    'font-weight': weight, 'fill': '#222222', 'stroke': 'white', 'stroke-width': '3',
                    'paint-order': 'stroke', 'stroke-linejoin': 'round'})
        label.text = text
    if columns:
        # Column headings act as swimlanes; retain full node IDs in Mermaid/flow data.
        node_x = sorted({float(g.attrib['x']) for g in diagram.findall(
            f'.//{{{namespace}}}g[@class="node"]') if 'x' in g.attrib})
        if len(node_x) != len(columns):
            node_x = [width * i / len(columns) for i in range(len(columns))]
        headings = ET.SubElement(wrapper, f'{{{namespace}}}g', attrib={'class': 'stage-headings'})
        for (prefix, heading), x in zip(columns, node_x):
            label = ET.SubElement(headings, f'{{{namespace}}}text', x=str(x + 12),
                y=str(header_height - 22), attrib={'font-family': 'Arial, sans-serif',
                'font-size': '26', 'font-weight': 'bold', 'fill': '#222222', 'stroke': 'white',
                'stroke-width': '3', 'paint-order': 'stroke'})
            label.text = heading
        for group in diagram.findall(f'.//{{{namespace}}}g[@class="node-labels"]'):
            for label in group:
                for prefix, _ in columns:
                    if label.text and label.text.startswith(prefix):
                        label.text = label.text.removeprefix(prefix)
                        break
    # Also override Mermaid's hard-coded 14px label attribute in the SVG export.
    for group in diagram.findall(f'.//{{{namespace}}}g[@class="node-labels"]'):
        group.set('font-size', f'{NODE_FONT_SIZE:g}')
        group.set('font-weight', 'bold')
    # Normal blending preserves the blue palette across SVG rasterizers.
    for group in diagram.findall(f'.//{{{namespace}}}g[@class="link"]'):
        group.set('style', 'mix-blend-mode: normal;')
    for group in diagram.findall(f'.//{{{namespace}}}g[@class="links"]'):
        group.set('stroke-opacity', '0.75')
    # Mermaid places its label group before the links, so links paint over text.
    # Keep both outlined text layers above every flow without changing geometry.
    for parent in diagram.iter():
        for child in list(parent):
            if child.attrib.get('class') == 'node-labels':
                parent.remove(child)
                parent.append(child)
    diagram.set('x', '0')
    diagram.set('y', str(header_height))
    diagram.set('width', str(width))
    diagram.set('height', str(height))
    wrapper.append(diagram)
    return ET.tostring(wrapper, encoding='unicode')


def render_sankey(flows, source, png, title):
    svg = png.with_suffix('.svg')
    if flows.empty:
        source.unlink(missing_ok=True)
        png.unlink(missing_ok=True)
        svg.unlink(missing_ok=True)
        return 'Empty prescription cohort; no Sankey generated.'
    source.write_text(mermaid_source(flows, title))
    # Stage both formats so rendering/conversion errors preserve the prior PNG.
    with TemporaryDirectory(prefix='.title-', dir=source.parent) as directory:
        staged_svg, staged_png = Path(directory) / 'diagram.svg', Path(directory) / 'diagram.png'
        subprocess.run([sys.executable, str(RENDERER), str(source), '-o', str(staged_svg)], cwd=ROOT, check=True)
        titled_svg = add_title(staged_svg.read_text(), title, flows.attrs.get('columns'))
        staged_svg.write_text(titled_svg)
        subprocess.run([
            'docker', 'run', '--rm', '--user', f'{os.getuid()}:{os.getgid()}',
            '--env', 'HOME=/tmp', '--env', 'XDG_CACHE_HOME=/tmp',
            '-v', f'{SVG_RASTERIZER.parent}:/scripts:ro',
            '-v', f'{Path(directory).resolve()}:/work',
            '--entrypoint', 'node', 'minlag/mermaid-cli:latest',
            '/scripts/render_sankey_svg.cjs', '/work/diagram.svg', '/work/diagram.png',
        ], cwd=ROOT, check=True)
        if not staged_png.is_file() or staged_png.stat().st_size == 0:
            raise ValueError('browser export did not produce a nonempty PNG')
        staged_svg.replace(svg)
        staged_png.replace(png)
    return f'Diagram: {png.relative_to(ROOT)}. Mermaid source: {source.relative_to(ROOT)}.'


def write_outputs(frame, metadata, diagram_dir, table_dir):
    prescriptions, groups, audits = summarize(frame)
    upload_start = metadata.get('upload_start_date', metadata['start_date'])
    start, end, upload_start_time = map(pd.Timestamp, [metadata['start_date'], metadata['end_date_exclusive'], upload_start])
    if (prescriptions.rx_creation_datetime.lt(start) | prescriptions.rx_creation_datetime.ge(end)).any():
        raise ValueError('prescription creation timestamp outside cohort window')
    uploaded = prescriptions.first_upload_at_utc.dropna()
    if (uploaded.lt(upload_start_time) | uploaded.ge(end)).any():
        raise ValueError('matched upload timestamp outside upload search window')
    flows = make_flows(groups)
    diagram_dir.mkdir(parents=True, exist_ok=True)
    table_dir.mkdir(parents=True, exist_ok=True)
    source, png = diagram_dir / 'sankey.mmd', diagram_dir / 'sankey.png'
    note = (f"Prescription creation: {metadata['start_date']} inclusive to {metadata['end_date_exclusive']} exclusive, UTC. "
            f"Upload search: {upload_start} inclusive to {metadata['end_date_exclusive']} exclusive, UTC. "
            f"Extracted: {metadata['extracted_at_utc']}.\n\n"
            'Count each CMPU vet-diet prescription once. First order means FIRST_ORDER_ID only, '
            'regardless of placement date. Status/reason is the latest snapshot; X means canceled. '
            'No deletion or prescription-status filter is applied. Match DIET_PRESCRIPTION upload '
            'entities by expanded RX_ID and numeric CUSTOMER_ID, within the upload search window; file and '
            'association flags are not filters. Matching upload entity does not verify file presence. '
            'The Sankey shows approval channel, then upload presence, then first-order status/reason. '
            'It is a categorical breakdown, not a chronological sequence. Upload middle nodes retain '
            'approval-channel identity. Node and flow percentages use the full prescription cohort '
            'for the main diagram, and only CUSTOMER_UPLOAD prescriptions for the focused diagram. '
            'They are rounded to two decimals in node labels, not percentages of the parent node. '
            'Missing/invalid upload-key audits describe the entire upload window.\n\n')
    for name, table in [('distribution', groups), ('flows', flows), ('prescriptions', prescriptions),
                        ('audit', pd.DataFrame(audits.items(), columns=['measure', 'count']))]:
        (table_dir / f'{name}.md').write_text(f'# {name.title()}\n\n' + note + markdown_table(table) + '\n')
    data_dir = ROOT / 'data' / NAME / period_name(metadata['start_date'], metadata['end_date_exclusive'], upload_start)
    prescriptions.to_parquet(data_dir / 'prescriptions.parquet', index=False)
    period = (f"{metadata['start_date']} through "
              f"{(date.fromisoformat(metadata['end_date_exclusive']) - timedelta(days=1)).isoformat()}")
    if upload_start != metadata['start_date']:
        period = (f"Rx: {period}; uploads: {upload_start} through "
                  f"{(date.fromisoformat(metadata['end_date_exclusive']) - timedelta(days=1)).isoformat()}")
    title = f'CMPU vet-diet prescriptions | All approval channels | {period} | Denominator: {len(prescriptions):,}'
    diagram_note = render_sankey(flows, source, png, title)
    focused = groups.loc[groups.channel.eq('CUSTOMER_UPLOAD')].copy()
    focused_total = int(focused.prescriptions.sum())
    focused['percent_of_cohort'] = 100 * focused.prescriptions / focused_total if focused_total else 0.
    focused_flows = make_flows(focused)
    focused_title = f'CMPU vet-diet prescriptions | CUSTOMER_UPLOAD only | {period} | Denominator: {focused_total:,}'
    focused_note = render_sankey(focused_flows, diagram_dir / 'sankey-customer-upload.mmd',
                                 diagram_dir / 'sankey-customer-upload.png', focused_title)
    for name, table in [('customer-upload-distribution', focused), ('customer-upload-flows', focused_flows)]:
        (table_dir / f'{name}.md').write_text(f'# {name.title()}\n\n' + note
            + 'Approval channel CUSTOMER_UPLOAD only. Percentages use this channel as the denominator.\n\n'
            + markdown_table(table) + '\n')
    (table_dir / 'customer-upload-summary.md').write_text('# CUSTOMER_UPLOAD first-order status\n\n'
        + note + f'Approval channel CUSTOMER_UPLOAD only: **{focused_total:,} prescriptions**. '
        'Percentages use this channel as the denominator.\n\n' + markdown_table(focused)
        + '\n\n' + focused_note + '\n')
    (table_dir / 'summary.md').write_text('# CMPU prescriptions: first order and uploads\n\n' + note
        + markdown_table(pd.DataFrame(audits.items(), columns=['measure', 'count']))
        + '\n\n' + markdown_table(groups) + '\n\n' + diagram_note + '\n')
    (diagram_dir / 'README.md').write_text('# CMPU first-order status\n\n' + note +
        f'Full-diagram percentage denominator: **{len(prescriptions):,} prescriptions**.\n\n' +
        ('![Prescription Sankey](sankey.png)\n' if len(flows) else diagram_note + '\n')
        + '\n## CUSTOMER_UPLOAD only\n\n'
        + f'Focused-diagram percentage denominator: **{focused_total:,} CUSTOMER_UPLOAD prescriptions**.\n\n'
        + ('![CUSTOMER_UPLOAD Sankey](sankey-customer-upload.png)\n' if focused_total else focused_note + '\n'))
    return audits


@click.command()
@click.option('--start-date', default='2026-08-15', show_default=True)
@click.option('--end-date', default='2026-10-15', show_default=True, help='Exclusive end date')
@click.option('--upload-start-date', default='2026-08-01', show_default=True, help='Inclusive upload search start')
@click.option('--cached', is_flag=True)
@click.option('--print-sql', is_flag=True)
def main(start_date, end_date, upload_start_date, cached, print_sql):
    try:
        sql = render_sql(start_date, end_date, upload_start_date)
        if print_sql:
            click.echo(sql)
            return
        period = period_name(start_date, end_date, upload_start_date)
        directory = ROOT / 'data' / NAME / period
        parquet, manifest = directory / 'source.parquet', directory / 'source.json'
        if cached:
            metadata = json.loads(manifest.read_text())
            if (metadata.get('sql') != sql or metadata.get('start_date') != start_date
                    or metadata.get('end_date_exclusive') != end_date
                    or metadata.get('upload_start_date', start_date) != upload_start_date
                    or metadata.get('parquet_sha256') != digest(parquet)):
                raise ValueError('cached SQL, dates or extract fingerprint differs; refresh extract')
            frame = pd.read_parquet(parquet).rename(columns=str.lower)
        else:
            directory.mkdir(parents=True, exist_ok=True)
            query = directory / 'source.sql'
            query.write_text(sql + '\n')
            manifest.unlink(missing_ok=True)
            subprocess.run([sys.executable, str(RUNNER), str(query), '--output-parquet', str(parquet.relative_to(ROOT)),
                            '--sql-log-dir', str((directory / 'sql-history').relative_to(ROOT))], cwd=ROOT, check=True)
            frame = pd.read_parquet(parquet).rename(columns=str.lower)
            summarize(frame)
            metadata = dict(sql=sql, sql_sha256=hashlib.sha256(sql.encode()).hexdigest(),
                            parquet_sha256=digest(parquet), start_date=start_date, end_date_exclusive=end_date,
                            upload_start_date=upload_start_date,
                            extracted_at_utc=datetime.now(timezone.utc).isoformat(),
                            source_extracted_at_session_time=frame.extracted_at_session_time.unique().tolist(),
                            warehouse=frame.extraction_warehouse.unique().tolist())
            manifest.write_text(json.dumps(metadata, indent=2) + '\n')
        audits = write_outputs(frame, metadata, ROOT / 'outputs/diagrams' / NAME / period,
                               ROOT / 'outputs/tables' / NAME / period)
        click.echo(json.dumps(audits, indent=2))
    except (ValueError, OSError, KeyError, subprocess.CalledProcessError) as error:
        raise click.ClickException(str(error)) from error


if __name__ == '__main__':
    main()
