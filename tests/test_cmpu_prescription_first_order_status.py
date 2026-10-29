import csv
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

from click.testing import CliRunner
import pandas as pd

from src.python import create_cmpu_prescription_first_order_status as analysis

LEGACY_ARGS = ['--start-date', '2026-08-14', '--upload-start-date', '2026-08-14']


def fixture():
    specs = [('Aged Order', 'X', 1, 1), ('customer initiated cancellation', 'X', 2, 1),
             ('Customer Request', 'X', 3, 1), ('Payment Declined', 'X', 4, 1),
             (None, 'X', 5, 1), ('Aged Order', 'D', 6, 1),
             (None, None, None, 0), (None, None, 8, 0), (None, None, 9, 1)]
    rows = []
    for i, (reason, status, first_order, order_rows) in enumerate(specs):
        rows.append(dict(rx_id=f'RX{i}', customer_id=10, rx_source_rows=1,
            rx_creation_datetime=pd.Timestamp('2026-09-01'),
            approval_channel='CUSTOMER_UPLOAD' if i % 2 else None,
            first_order_id=first_order, order_source_rows=order_rows,
            order_status=status, order_status_description=None, order_cancel_reason=reason,
            upload_count=3 if i % 2 else 0,
            cohort_window_upload_count=3 if i % 2 else 0,
            first_upload_at_utc=pd.Timestamp('2026-09-02') if i % 2 else pd.NaT,
            **{column: 0 for column in analysis.AUDIT_COLUMNS}))
    return pd.DataFrame(rows)


def fake_render(command, **kwargs):
    if str(analysis.RENDERER) in command:
        destination = Path(command[command.index('-o') + 1])
        destination.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="2400" height="1000" '
                               'viewBox="0 0 2400 1000"><rect width="10" height="10"/>'
                               '<g class="node-labels" font-size="14"><text>Fixture</text></g></svg>')
    elif command[0] == 'docker':
        mount = next(value for value in command if value.endswith(':/work'))
        (Path(mount.removesuffix(':/work')) / 'diagram.png').write_bytes(b'fixture PNG')


class FirstOrderSankeyTests(unittest.TestCase):
    def test_column_headers_shorten_visible_labels_and_preserve_counts(self):
        svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 2400 1000">'
               '<g class="node-labels"><text>First order cancel reason: Aged Order (2; 40.00%)</text>'
               '<text>Item block reason: X / NEW_ITEM_AUTHORIZATION (3; 60.00%)</text></g></svg>')
        columns=[('First order cancel reason: ', 'First-order cancel reason'),
                 ('Item block reason: ', 'Item block reason')]
        result=ET.fromstring(analysis.add_title(svg,'Fixture',columns))
        headings=result.find('{http://www.w3.org/2000/svg}g[@class="stage-headings"]')
        self.assertEqual([' '.join(t.itertext()) for t in headings], ['First-order cancel reason','Item block reason'])
        labels=result.findall('.//{http://www.w3.org/2000/svg}g[@class="node-labels"]/{http://www.w3.org/2000/svg}text')
        self.assertEqual([' '.join(span.text for span in t.findall('{http://www.w3.org/2000/svg}tspan')) for t in labels],['Aged Order (2; 40.00%)','X / NEW_ITEM_AUTHORIZATION (3; 60.00%)'])

    def test_many_nodes_have_serializable_render_dimensions(self):
        groups = pd.DataFrame({'channel': ['CUSTOMER_UPLOAD']*21,
                               'upload_group': ['Has matching upload']*21,
                               'order_group': [f'Category {i}' for i in range(21)],
                               'prescriptions': [1]*21})
        source = analysis.mermaid_source(analysis.make_flows(groups))
        config = json.loads(source.split('config: ',1)[1].split('\n---',1)[0])
        self.assertEqual(config['sankey']['height'], 2688)

    def test_landscape_layout_wraps_labels_and_preserves_full_accessible_name(self):
        svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 5000 1400">'
               '<g class="node" x="0" y="0"><rect height="1400"/></g>'
               '<g class="node" x="840" y="0"><rect height="1400"/></g>'
               '<g class="node-labels"><text x="834" y="0" text-anchor="end">'
               'Reason: Customer Initiated Cancellation (1,234; 25.00%)</text></g></svg>')
        result = ET.fromstring(analysis.add_title(svg, 'A long title | Scope | ' + 'date notes; '*30,
                                                 [('Reason: ', 'Cancellation reason')]))
        ns = {'s': 'http://www.w3.org/2000/svg'}
        self.assertLess(float(result.attrib['width']), 5000)
        label = result.find('.//s:g[@class="node-labels"]/s:text', ns)
        self.assertEqual([t.text for t in label.findall('s:tspan', ns)],
                         ['Customer Initiated', 'Cancellation', '(1,234; 25.00%)'])
        self.assertEqual(label.attrib['text-anchor'], 'start')
        self.assertEqual(label.find('s:title', ns).text,
                         'Reason: Customer Initiated Cancellation (1,234; 25.00%)')
        self.assertGreater(len(result.findall('s:text', ns)[1].findall('s:tspan', ns)), 1)

    def test_upload_labels_render_above_links(self):
        # Mermaid emits labels before links; the later opaque links cover this text.
        svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 2400 1000">'
               '<g class="nodes"/><g class="node-labels">'
               '<text class="sankey-label-bg">Has matching upload</text>'
               '<text class="sankey-label-fg">Has matching upload</text></g>'
               '<g class="links"><path d="M0 0 L100 100"/></g></svg>')
        result = ET.fromstring(analysis.add_title(svg, 'Fixture'))
        inner = result.find('{http://www.w3.org/2000/svg}svg')
        classes = [child.attrib.get('class') for child in inner]
        self.assertGreater(classes.index('node-labels'), classes.index('links'))

    def test_prescription_grain_and_all_order_groups(self):
        frame, groups, audit = analysis.summarize(fixture())
        self.assertEqual(len(frame), 9)
        self.assertEqual(groups.prescriptions.sum(), 9)
        self.assertEqual(audit['prescriptions_with_upload'], 4)
        self.assertEqual(frame.order_group.tolist(), [
            'Aged Order', 'Customer Initiated Cancellation', 'Customer Request',
            'Other cancellation reason', 'Canceled - missing reason', 'Not canceled',
            'No first order ID', 'First order not found', 'Unknown order status'])
        self.assertEqual(frame.iloc[0].channel, '[Unknown approval channel]')
        # A stale cancellation reason must not turn a non-X order into canceled.
        self.assertEqual(frame.iloc[5].order_group, 'Not canceled')

    def test_duplicates_and_inconsistent_evidence_fail(self):
        for column, value in [('rx_source_rows', 2), ('order_source_rows', 2),
                              ('invalid_upload_source_rows', 1), ('upload_count', -1),
                              ('upload_count', 1.5)]:
            frame = fixture()
            frame[column] = value
            with self.subTest(column=column, value=value), self.assertRaises(ValueError):
                analysis.summarize(frame)
        with self.assertRaises(ValueError):
            analysis.summarize(pd.concat([fixture(), fixture().iloc[:1]]))
        frame = fixture()
        frame.loc[0, 'upload_count'] = 1
        with self.assertRaises(ValueError):
            analysis.summarize(frame)

    def test_flow_conservation_and_channel_identity(self):
        frame = fixture()
        frame.loc[0, 'upload_count'] = 3
        frame.loc[0, 'first_upload_at_utc'] = pd.Timestamp('2026-09-02')
        _, groups, _ = analysis.summarize(frame)
        flows = analysis.make_flows(groups)
        self.assertTrue(flows.groupby('transition').prescriptions.sum().eq(9).all())
        uploaded = flows.loc[flows.transition.eq(1) & flows.target.str.endswith('/ Has matching upload')]
        self.assertEqual(len(uploaded), 2)
        self.assertEqual(uploaded.target.nunique(), 2)
        self.assertTrue(flows.loc[flows.transition.eq(1)].target.str.contains('matching upload').all())
        self.assertTrue(flows.loc[flows.transition.eq(2)].target.str.startswith('First order: ').all())
        self.assertFalse(flows.loc[flows.transition.eq(1)].target.str.contains('Aged Order').any())
        self.assertTrue(flows.prescriptions.gt(0).all())
        for total in flows.groupby('transition').percent_of_cohort.sum():
            self.assertAlmostEqual(total, 100)

    def test_mermaid_csv_escaping_and_counts(self):
        frame = fixture()
        frame['approval_channel'] = 'Channel, "quoted"'
        _, groups, _ = analysis.summarize(frame)
        flows = analysis.make_flows(groups)
        source = analysis.mermaid_source(flows)
        csv_text = source.split('sankey-beta\n', 1)[1]
        rows = list(csv.reader(io.StringIO(csv_text)))
        self.assertTrue(all(len(row) == 3 for row in rows))
        self.assertEqual(sum(int(row[2]) for row in rows), 18)
        self.assertIn('Channel, "quoted"', rows[0][0])
        self.assertTrue(all(line.startswith('"') for line in csv_text.splitlines()))
        self.assertIn('Canceled - missing reason', source)

    def test_sql_date_bounds_and_upload_identity(self):
        sql = analysis.render_sql('2026-08-14', '2026-10-15')
        self.assertEqual(sql.count(">= '2026-08-14'::TIMESTAMP_NTZ"), 3)
        self.assertEqual(sql.count("< '2026-10-15'::TIMESTAMP_NTZ"), 2)
        self.assertIn('p.rx_id = u.rx_id AND p.customer_id = u.customer_id', sql)
        self.assertIn('COUNT(DISTINCT upload_id)', sql)
        self.assertIn('LATERAL FLATTEN', sql)
        self.assertIn("REGEXP_LIKE(TRIM(customer_id), '^[0-9]+$')", sql)
        for excluded in ['HAS_UPLOADED_FILE', 'HAS_ASSOCIATED_RX', 'ASSOCIATED_RESOURCE_TYPE',
                         'IS_DELETED', 'RXP_RX_USAGE_ACTIONS']:
            self.assertNotIn(excluded, sql.upper())
        for start, end in [('bad', '2026-10-15'), ('2026-10-15', '2026-10-15')]:
            with self.assertRaises(ValueError):
                analysis.render_sql(start, end)

    def test_sql_only_has_no_side_effects(self):
        with patch.object(analysis.subprocess, 'run') as run, patch.object(Path, 'mkdir') as mkdir:
            result = CliRunner().invoke(analysis.main, ['--print-sql'])
        self.assertEqual(result.exit_code, 0, result.output)
        run.assert_not_called()
        mkdir.assert_not_called()

    def test_cached_outputs_and_fingerprint_rejection(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            data = root / 'data' / analysis.NAME / '2026-08-14_2026-10-15'
            data.mkdir(parents=True)
            fixture().to_parquet(data / 'source.parquet', index=False)
            metadata = dict(sql=analysis.render_sql('2026-08-14', '2026-10-15'),
                start_date='2026-08-14', end_date_exclusive='2026-10-15',
                extracted_at_utc='test', parquet_sha256=analysis.digest(data / 'source.parquet'))
            manifest = data / 'source.json'
            manifest.write_text(json.dumps(metadata))
            with patch.object(analysis, 'ROOT', root), patch.object(analysis.subprocess, 'run', side_effect=fake_render) as run:
                result = CliRunner().invoke(analysis.main, LEGACY_ARGS + ['--cached'])
                self.assertEqual(result.exit_code, 0, result.output)
                self.assertEqual(run.call_count, 4)  # SVG and browser PNG for both diagrams; no query.
                self.assertTrue(any(str(analysis.RENDERER) in call.args[0] for call in run.call_args_list))
                self.assertTrue((root / 'outputs/tables/2026-08-14_2026-10-14' /
                                 'cmpu-prescription-first-order-status_distribution.md').is_file())
                focused = root / 'outputs/diagrams' / analysis.NAME / '2026-08-14_2026-10-15/sankey-customer-upload.mmd'
                focused_csv = focused.read_text().split('sankey-beta\n', 1)[1]
                rows = list(csv.reader(io.StringIO(focused_csv)))
                self.assertEqual(sum(int(row[2]) for row in rows), 8)  # Four CUSTOMER_UPLOAD Rx, two stages.
                self.assertNotIn('[Unknown approval channel]', focused_csv)
                self.assertIn('Channel: CUSTOMER_UPLOAD (4; 100.00%)', focused_csv)
                self.assertIn('First order: Customer Initiated Cancellation (1; 25.00%)', focused_csv)
                main_source = focused.with_name('sankey.mmd').read_text()
                self.assertIn('title: "CMPU vet-diet prescriptions | All approval channels | 2026-08-14 through 2026-10-14 | Denominator: 9"', main_source)
                self.assertIn('title: "CMPU vet-diet prescriptions | CUSTOMER_UPLOAD only | 2026-08-14 through 2026-10-14 | Denominator: 4"', focused.read_text())
                visible_svg = ET.fromstring(focused.with_suffix('.svg').read_text())
                heading = visible_svg.findall('{http://www.w3.org/2000/svg}text')
                self.assertIn('CUSTOMER_UPLOAD only', ' '.join(heading[0].itertext()))
                self.assertIn('Denominator: 4', ' '.join(heading[1].itertext()))
                self.assertGreater(float(visible_svg.attrib['height']), 1000)
                self.assertEqual(heading[0].attrib['font-size'], '33.6')
                self.assertEqual(heading[1].attrib['font-size'], '21.6')
                node_labels = visible_svg.find('.//{http://www.w3.org/2000/svg}g[@class="node-labels"]')
                self.assertEqual(node_labels.attrib['font-size'], '30')
                self.assertEqual(node_labels.attrib['font-weight'], 'bold')
                self.assertIn('Channel: CUSTOMER_UPLOAD (4; 44.44%)', main_source)
                self.assertIn('First order: Customer Initiated Cancellation (1; 11.11%)', main_source)
                summary = root / 'outputs/tables/2026-08-14_2026-10-14/cmpu-prescription-first-order-status_customer-upload-summary.md'
                self.assertIn('**4 prescriptions**', summary.read_text())
                for key in ['sql', 'start_date', 'end_date_exclusive', 'upload_start_date', 'parquet_sha256']:
                    manifest.write_text(json.dumps({**metadata, key: 'stale'}))
                    run.reset_mock()
                    result = CliRunner().invoke(analysis.main, LEGACY_ARGS + ['--cached'])
                    self.assertNotEqual(result.exit_code, 0)
                    run.assert_not_called()

    def test_empty_cohort_clears_stale_diagram(self):
        frame, groups, audit = analysis.summarize(fixture().iloc[:0])
        self.assertEqual(audit['cohort_prescriptions'], 0)
        self.assertTrue(analysis.make_flows(groups).empty)
        with TemporaryDirectory() as directory, patch.object(analysis.subprocess, 'run') as run:
            root = Path(directory)
            metadata = dict(start_date='2026-08-14', end_date_exclusive='2026-10-15', extracted_at_utc='test')
            data = root / 'data' / analysis.NAME / '2026-08-14_2026-10-15'
            data.mkdir(parents=True)
            diagram = root / 'diagram'
            diagram.mkdir()
            (diagram / 'sankey.png').write_text('stale')
            (diagram / 'sankey.mmd').write_text('stale')
            with patch.object(analysis, 'ROOT', root):
                analysis.write_outputs(frame, metadata, diagram, root / 'tables')
            run.assert_not_called()
            self.assertFalse((diagram / 'sankey.png').exists())
            self.assertIn('no Sankey', (root / 'tables/summary.md').read_text())

    def test_fresh_runner_uppercase_columns_and_metadata(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)

            def run(command, **kwargs):
                if str(analysis.RUNNER) in command:
                    frame = fixture().assign(extracted_at_session_time='snapshot', extraction_warehouse='warehouse')
                    frame.columns = frame.columns.str.upper()
                    destination = root / command[command.index('--output-parquet') + 1]
                    frame.to_parquet(destination, index=False)
                else:
                    fake_render(command, **kwargs)

            with patch.object(analysis, 'ROOT', root), patch.object(analysis.subprocess, 'run', side_effect=run) as invoked:
                result = CliRunner().invoke(analysis.main, LEGACY_ARGS)
                self.assertEqual(result.exit_code, 0, result.output)
                self.assertEqual(invoked.call_count, 5)
            manifest = root / 'data' / analysis.NAME / '2026-08-14_2026-10-15/source.json'
            metadata = json.loads(manifest.read_text())
            self.assertEqual(metadata['source_extracted_at_session_time'], ['snapshot'])
            self.assertEqual(metadata['warehouse'], ['warehouse'])
            self.assertEqual(metadata['upload_start_date'], '2026-08-14')
            self.assertEqual(metadata['parquet_sha256'], analysis.digest(manifest.with_name('source.parquet')))

    def test_no_customer_upload_channel_clears_only_focused_diagram(self):
        with TemporaryDirectory() as directory, patch.object(analysis.subprocess, 'run', side_effect=fake_render) as run:
            root = Path(directory)
            metadata = dict(start_date='2026-08-14', end_date_exclusive='2026-10-15', extracted_at_utc='test')
            data = root / 'data' / analysis.NAME / '2026-08-14_2026-10-15'
            data.mkdir(parents=True)
            diagram = root / 'diagram'
            diagram.mkdir()
            (diagram / 'sankey-customer-upload.png').write_text('stale')
            (diagram / 'sankey-customer-upload.mmd').write_text('stale')
            with patch.object(analysis, 'ROOT', root):
                analysis.write_outputs(fixture().assign(approval_channel='FAX'), metadata, diagram, root / 'tables')
            self.assertEqual(run.call_count, 2)
            self.assertTrue((diagram / 'sankey.mmd').exists())
            self.assertFalse((diagram / 'sankey-customer-upload.png').exists())
            self.assertFalse((diagram / 'sankey-customer-upload.mmd').exists())

    def test_browser_export_failure_preserves_previous_png(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source, png = root / 'sankey.mmd', root / 'sankey.png'
            png.write_bytes(b'previous PNG')
            _, groups, _ = analysis.summarize(fixture())

            def fail_browser(command, **kwargs):
                if command[0] == 'docker':
                    raise analysis.subprocess.CalledProcessError(1, command)
                fake_render(command, **kwargs)

            with patch.object(analysis, 'ROOT', root), patch.object(analysis.subprocess, 'run', side_effect=fail_browser):
                with self.assertRaises(analysis.subprocess.CalledProcessError):
                    analysis.render_sankey(analysis.make_flows(groups), source, png, 'Fixture title')
            self.assertEqual(png.read_bytes(), b'previous PNG')

    def test_mermaid_source_separate_from_rendered_figures(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'src/diagram.mmd'
            png = root / 'outputs/diagram.png'
            source.parent.mkdir()
            png.parent.mkdir()
            _, groups, _ = analysis.summarize(fixture())
            with patch.object(analysis, 'ROOT', root), patch.object(analysis.subprocess, 'run', side_effect=fake_render):
                analysis.render_sankey(analysis.make_flows(groups), source, png, 'Fixture title')
            self.assertTrue(source.exists())
            self.assertTrue(png.exists())
            self.assertTrue(png.with_suffix('.svg').exists())
            self.assertFalse(source.with_suffix('.svg').exists())

    def test_separate_upload_start_and_cache_scope(self):
        sql = analysis.render_sql('2026-08-15', '2026-10-15', '2026-08-01')
        self.assertIn("rx_creation_datetime >= '2026-08-15'::TIMESTAMP_NTZ", sql)
        self.assertIn("created_ts_utc >= '2026-08-01'::TIMESTAMP_NTZ", sql)
        self.assertEqual(sql.count("< '2026-10-15'::TIMESTAMP_NTZ"), 2)
        self.assertEqual(analysis.period_name('2026-08-15', '2026-10-15', '2026-08-01'),
                         '2026-08-15_2026-10-15_uploads-from-2026-08-01')
        self.assertNotEqual(analysis.period_name('2026-08-15', '2026-10-15', '2026-08-01'),
                            analysis.period_name('2026-08-15', '2026-10-15', '2026-08-15'))
        with self.assertRaises(ValueError):
            analysis.render_sql('2026-08-15', '2026-10-15', '2026-08-16')

    def test_earlier_upload_is_included_and_audited(self):
        frame = fixture()
        frame.loc[1, 'first_upload_at_utc'] = pd.Timestamp('2026-08-02')
        frame.loc[1, 'cohort_window_upload_count'] = 0
        prescriptions, _, audit = analysis.summarize(frame)
        self.assertEqual(prescriptions.loc[1, 'upload_group'], 'Has matching upload')
        self.assertEqual(audit['prescriptions_matched_only_by_earlier_uploads'], 1)
        frame.loc[1, 'cohort_window_upload_count'] = 4
        with self.assertRaises(ValueError):
            analysis.summarize(frame)


if __name__ == '__main__':
    unittest.main()
