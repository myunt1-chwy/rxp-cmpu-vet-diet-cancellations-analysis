"""Customer selection, current RX/channel evidence and branching flow conservation."""
import json
from unittest.mock import patch

from click.testing import CliRunner
import pandas as pd
import pytest

from src.python import create_aged_order_reorder_prescription_sankeys as analysis
from tests.test_aged_order_reorder_prescriptions import fixtures as rx_fixtures
from tests.test_aged_order_reorder_daily_customers import fixtures as daily_fixtures


def fixtures():
    matches, associations, source = rx_fixtures()
    matches['original_customer_id'] = range(4)
    selected = pd.concat([matches.assign(followup_days=d) for d in analysis.HORIZONS], ignore_index=True)
    source['matched_rx_id'] = source.rx_id
    source['prescription_rows'] = source.rx_id.notna().astype(int)
    source['approval_channel'] = source.rx_id.map(lambda x: 'CUSTOMER_EMAIL' if pd.notna(x) else None)
    return selected, associations, source


def test_identity_channels_and_terminal_conservation():
    selected, associations, source = fixtures()
    details, audit = analysis.summarize(selected, associations, source)
    assert len(details) == 12 and len(audit)
    for days in analysis.HORIZONS:
        identity, channels, flows = analysis.distributions(details, days)
        assert set(identity.category) == {'Same prescription', 'Different prescription', 'Unknown', 'Multiple prescriptions'}
        assert identity.customers.sum() == 4
        assert channels.customers.sum() == 1
        assert channels.approval_channel.tolist() == ['CUSTOMER_EMAIL']
        assert channels.percent_of_different_prescription_customers.tolist() == [100.]
        assert flows.loc[flows.transition.eq(1), 'prescriptions'].sum() == 4
        assert flows.loc[flows.transition.eq(2), 'prescriptions'].sum() == 1
        assert set(flows.loc[flows.transition.eq(2), 'source']) == {'Different prescription'}
    assert details.loc[details.prescription_comparison.ne('Different prescription'), 'reorder_approval_channel'].isna().all()


@pytest.mark.parametrize('case', ['missing-channel', 'unmatched', 'partial'])
def test_missing_evidence_preserved(case):
    selected, associations, source = fixtures()
    if case == 'missing-channel': source.loc[source.rx_id.eq('NEW'), 'approval_channel'] = None
    if case == 'unmatched':
        source.loc[source.rx_id.eq('NEW'), ['matched_rx_id', 'approval_channel', 'prescription_rows']] = [None, None, 0]
    if case == 'partial':
        source = pd.concat([source, source.loc[source.order_id.eq(200)].assign(rx_id=None, rx_usage_id=None,
            matched_rx_id=None, approval_channel=None, prescription_rows=0)])
    details, _ = analysis.summarize(selected, associations, source)
    first = details.loc[details.followup_days.eq(7)]
    if case == 'partial': assert first.prescription_comparison.eq('Unknown').sum() == 2
    else:
        label = '[Missing approval channel]' if case == 'missing-channel' else '[Unmatched prescription]'
        assert first.loc[first.prescription_comparison.eq('Different prescription'), 'reorder_approval_channel'].tolist() == [label]


@pytest.mark.parametrize('case', ['registry-duplicate', 'registry-conflict', 'missing-key', 'extra-key', 'duplicate-evidence', 'shipment-negative', 'duplicate-customer'])
def test_conflicting_sources_rejected(case):
    selected, associations, source = fixtures()
    if case == 'registry-duplicate': source.loc[source.rx_id.eq('NEW'), 'prescription_rows'] = 2
    if case == 'registry-conflict': source = pd.concat([source, source.iloc[[0]].assign(approval_channel='FAX')])
    if case == 'missing-key': source = source.loc[source.order_id.ne(200)]
    if case == 'extra-key': source = pd.concat([source, source.iloc[[0]].assign(order_id=999)])
    if case == 'duplicate-evidence': source = pd.concat([source, source.iloc[[0]]])
    if case == 'shipment-negative': source.loc[0, 'shipment_rows'] = -1
    if case == 'duplicate-customer': selected = pd.concat([selected, selected.iloc[[0]]])
    with pytest.raises(ValueError): analysis.summarize(selected, associations, source)


def test_shortest_delay_and_existing_ties_across_all_horizons():
    matches, customers = daily_fixtures()
    # Fit all matches inside seven days; the later cancellation still gives the shortest delay.
    matches.loc[matches.original_customer_id.eq(2), 'reorder_placed_at_utc'] = matches.loc[matches.original_customer_id.eq(2), 'order_cancel_time'] + pd.Timedelta(days=7)
    outputs = {'reorder-matches': pd.concat([matches.assign(followup_days=d) for d in analysis.HORIZONS]),
               'customers': pd.concat([customers.assign(followup_days=d) for d in analysis.HORIZONS])}
    selected = analysis.select_customers(outputs)
    assert len(selected) == 12
    assert selected.loc[selected.original_customer_id.eq(1), 'reorder_order_id'].eq(201).all()
    assert not selected.duplicated(['followup_days', 'original_customer_id']).any()


def test_empty_and_no_different_prescriptions():
    selected, associations, source = fixtures()
    details, _ = analysis.summarize(selected.iloc[:0], associations, source.iloc[:0])
    for days in analysis.HORIZONS:
        identity, channels, flows = analysis.distributions(details, days)
        assert identity.empty and channels.empty and flows.empty
    details = pd.DataFrame(dict(followup_days=[7], prescription_comparison=['Same prescription'], reorder_approval_channel=[None]))
    _, channels, flows = analysis.distributions(details, 7)
    assert channels.empty and flows.transition.tolist() == [1]


def test_fresh_cached_sql_only_fingerprint_and_exports(tmp_path):
    selected, associations, source = fixtures()
    period = '2026-08-15_2026-10-15_customer_upload_same-pet_reorders-7d-14d-21d_as-of-2026-10-27'
    population = selected[['followup_days', 'original_customer_id']].assign(has_reordered=True)
    outputs = dict(associations=associations, customers=population)
    metadata = dict(parquet_sha256='baseline')
    def extract(args, **kwargs):
        source.assign(extraction_warehouse='test').to_parquet(tmp_path / args[args.index('--output-parquet') + 1], index=False)
    def render(flows, source_path, png, title):
        source_path.write_text('sankey-beta')
        png.write_bytes(b'png')
        png.with_suffix('.svg').write_text('<svg/>')
        return str(png)
    with patch.object(analysis, 'ROOT', tmp_path), \
         patch.object(analysis.windows, 'load_source', return_value=(pd.DataFrame(), metadata, period)), \
         patch.object(analysis.windows, 'summarize', return_value=outputs), \
         patch.object(analysis, 'select_customers', return_value=selected), \
         patch.object(analysis.subprocess, 'run', side_effect=extract) as run, \
         patch.object(analysis, 'render_sankey', side_effect=render):
        runner = CliRunner()
        result = runner.invoke(analysis.main, ['--print-sql'])
        assert result.exit_code == 0, result.output
        run.assert_not_called()
        assert not list(tmp_path.iterdir())
        assert 'k.order_id=l.order_id AND k.order_line_id=l.order_line_id' in result.output
        assert 'line_evidence' in result.output and 'APPROVAL_CHANNEL' in result.output.upper()
        result = runner.invoke(analysis.main, [])
        assert result.exit_code == 0, result.output
        run.assert_called_once()
        run.reset_mock()
        result = runner.invoke(analysis.main, ['--cached'])
        assert result.exit_code == 0, result.output
        run.assert_not_called()
        assert len(list((tmp_path / 'outputs/diagrams/2026-08-15_2026-10-14').glob('*.png'))) == 3
        assert len(list((tmp_path / 'outputs/tables/2026-08-15_2026-10-14').glob('*.md'))) == 11
        manifest = next((tmp_path / 'data').rglob('source.json'))
        saved = json.loads(manifest.read_text())
        for field in ['sql_sha256', 'baseline_sha256', 'parquet_sha256', 'customer_selection', 'followup_days']:
            manifest.write_text(json.dumps({**saved, field: 'tampered'}))
            result = runner.invoke(analysis.main, ['--cached'])
            assert result.exit_code != 0 and 'fingerprint differs' in result.output
        manifest.write_text(json.dumps(saved))
        exports = json.loads(next((tmp_path / 'data').rglob('exports.json')).read_text())
        for path, fingerprint in exports['files'].items(): assert analysis.digest(tmp_path / path) == fingerprint


def test_optional_padding_keeps_last_channel_label_inside_canvas():
    import xml.etree.ElementTree as ET
    from src.python.create_cmpu_prescription_first_order_status import add_title
    svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 2400 1000"/>'
    normal = ET.fromstring(add_title(svg, 'Fixture'))
    padded = ET.fromstring(add_title(svg, 'Fixture', bottom_padding=24))
    assert float(padded.attrib['height']) == float(normal.attrib['height']) + 24
    assert float(padded.attrib['viewBox'].split()[-1]) == float(padded.attrib['height'])


def evidence_fixture():
    from tests.test_aged_order_reorder_upload_approval_evidence import fixtures as evidence_source
    from src.python import create_aged_order_reorder_upload_approval_evidence as evidence_analysis
    pairs, requests, lines, raw = evidence_source()
    evidence = evidence_analysis.summarize(pairs, requests, lines, raw, '2026-10-27')['selected-customers']
    details = evidence.copy()
    details['original_order_id'] = 1000 + details.original_customer_id
    details['original_line_id'] = 2000 + details.original_customer_id
    evidence['original_order_id'] = details.original_order_id
    evidence['original_line_id'] = details.original_line_id
    same = details.loc[details.rx_id.eq('A')].assign(original_customer_id=99,
        original_order_id=1999, original_line_id=2999, reorder_order_id=9999, reorder_line_id=9999,
        prescription_comparison='Same prescription', reorder_rx_ids='SAME', reorder_approval_channel=None)
    details = pd.concat([details, same], ignore_index=True)
    return details, evidence


def test_four_stage_channel_specific_evidence_conserves_customers():
    details, evidence = evidence_fixture()
    for days in analysis.HORIZONS:
        _, _, original = analysis.distributions(details, days)
        _, _, extended = analysis.distributions(details, days, evidence)
        pd.testing.assert_frame_equal(original, extended.loc[extended.transition.le(2)].reset_index(drop=True))
        final = extended.loc[extended.transition.eq(3)]
        assert final.prescriptions.sum() == 4
        assert final.target.str.startswith('Evidence: ').all()
        assert set(final.target) == {'Evidence: CUSTOMER_UPLOAD / Both upload and decision time',
            'Evidence: CUSTOMER_UPLOAD / Neither', 'Evidence: VERBAL / Decision time only', 'Evidence: FAX / Upload only'}
        assert final.prescriptions.eq(1).all()
        assert final.percent_of_reordered_customers.eq(20).all()
        assert 'Same prescription' not in set(final.source)
        incoming = extended.groupby('target').prescriptions.sum()
        outgoing = extended.groupby('source').prescriptions.sum()
        for node in set(incoming.index) & set(outgoing.index): assert incoming[node] == outgoing[node]
        assert len(extended.attrs['columns']) == 4


@pytest.mark.parametrize('case', ['missing', 'extra', 'duplicate', 'wrong-line', 'wrong-channel', 'missing-flag'])
def test_final_partition_requires_exact_selected_customer_evidence(case):
    details, evidence = evidence_fixture()
    if case == 'missing': evidence = evidence.iloc[1:]
    if case == 'extra': evidence = pd.concat([evidence, evidence.iloc[[0]].assign(original_customer_id=999)])
    if case == 'duplicate': evidence = pd.concat([evidence, evidence.iloc[[0]]])
    if case == 'wrong-line': evidence.loc[0, 'reorder_line_id'] = 999
    if case == 'wrong-channel': evidence.loc[0, 'reorder_approval_channel'] = 'FAX'
    if case == 'missing-flag':
        evidence['has_decision_timestamp'] = evidence.has_decision_timestamp.astype('boolean')
        evidence.loc[0, 'has_decision_timestamp'] = pd.NA
    with pytest.raises(ValueError): analysis.distributions(details, 7, evidence)


def test_extended_outputs_are_separate_and_record_evidence_fingerprint(tmp_path):
    details, evidence = evidence_fixture()
    period = '2026-08-15_2026-10-15_customer_upload_same-pet_reorders-7d-14d-21d_as-of-2026-10-27'
    outputs = dict(customers=details[['followup_days', 'original_customer_id']].assign(has_reordered=True))
    metadata = dict(start_date='2026-08-15', end_date_exclusive='2026-10-15', as_of_date='2026-10-27',
        baseline_sha256='baseline', parquet_sha256='prescriptions', extracted_at_utc='rx-time')
    evidence_meta = dict(parquet_sha256='evidence', extracted_at_utc='evidence-time')
    def render(flows, source, png, title):
        assert flows.transition.max() == (3 if 'with-upload-decision' in png.name else 2)
        source.write_text('sankey-beta')
        png.write_bytes(b'png')
        png.with_suffix('.svg').write_text('<svg/>')
        return str(png)
    with patch.object(analysis, 'ROOT', tmp_path), patch.object(analysis, 'render_sankey', side_effect=render):
        analysis.write_outputs(details, pd.DataFrame(), outputs, metadata, period)
        old_manifest = tmp_path / 'data' / analysis.NAME / period / 'exports.json'
        prior_bytes = old_manifest.read_bytes()
        tables, diagrams = analysis.write_outputs(details, pd.DataFrame(), outputs, metadata, period, evidence, evidence_meta)
        assert old_manifest.read_bytes() == prior_bytes
        assert len(list(diagrams.glob('*with-upload-decision-evidence*.png'))) == 3
        assert len(list(tables.glob('*with-upload-decision-evidence*.md'))) == 15
        manifest = json.loads((tmp_path / 'data' / analysis.NAME / (period + '_with-upload-decision-evidence') / 'exports.json').read_text())
        assert manifest['evidence_source_sha256'] == 'evidence'
        for path, fingerprint in manifest['files'].items(): assert analysis.digest(tmp_path / path) == fingerprint
        note = next(diagrams.glob('*with-upload-decision-evidence*.md')).read_text()
        assert 'including minima after the cutoff' in note
        assert 'by RX_ID/customer' in note


def test_evidence_mode_cli_reads_frozen_caches_and_validates_dependencies():
    details, evidence = evidence_fixture()
    meta = dict(baseline_sha256='baseline', parquet_sha256='rx', as_of_date='2026-10-27')
    from src.python import create_aged_order_reorder_upload_approval_evidence as evidence_analysis
    with patch.object(evidence_analysis, 'load_source', return_value=(pd.DataFrame(), {'parquet_sha256': 'ev'}, None)) as load, \
         patch.object(evidence_analysis, 'summarize', return_value={'selected-customers': evidence}):
        returned, metadata = analysis.load_evidence(details, meta, 'period')
        pd.testing.assert_frame_equal(returned, evidence)
        assert metadata['parquet_sha256'] == 'ev'
        args = load.call_args.args
        assert args[2:] == ('period', dict(baseline='baseline', prescription_channels='rx', customer_selection=analysis.SELECTION), '2026-10-27', True)
    with patch.object(analysis.windows, 'load_source', return_value=(pd.DataFrame(), {'parquet_sha256': 'baseline'}, 'period')), \
         patch.object(analysis.windows, 'summarize', return_value={'associations': pd.DataFrame()}), \
         patch.object(analysis, 'select_customers', return_value=pd.DataFrame()), \
         patch.object(analysis, 'load_source', return_value=(pd.DataFrame(), {'parquet_sha256': 'rx'}, None)) as load, \
         patch.object(analysis, 'summarize', return_value=(details, pd.DataFrame())), \
         patch.object(analysis, 'load_evidence', side_effect=ValueError('cached evidence fingerprint differs')):
        result = CliRunner().invoke(analysis.main, ['--with-evidence'])
        assert result.exit_code != 0 and 'cached evidence fingerprint differs' in result.output
        assert load.call_args.args[-1] is True


def wismo_fixture():
    details, evidence = evidence_fixture()
    details['order_cancel_time'] = pd.to_datetime(details.order_cancel_time, utc=True)
    details['reorder_placed_at_utc'] = details.order_cancel_time + pd.Timedelta(days=1)
    return details, evidence


def test_wismo_stage_includes_same_prescription_customers_and_conserves_all_paths():
    details, evidence = wismo_fixture()
    wismo = details.copy()
    wismo['wismo_contact_count'] = wismo.original_customer_id.map(lambda c: 4 if c==7 else 3 if c==99 else 0)
    wismo['has_wismo_contact'] = wismo.wismo_contact_count.gt(0)
    for days in analysis.HORIZONS:
        _, _, prior = analysis.distributions(details, days, evidence)
        _, _, extended = analysis.distributions(details, days, evidence, wismo)
        pd.testing.assert_frame_equal(prior, extended.loc[extended.transition.le(3)].reset_index(drop=True))
        final = extended.loc[extended.transition.eq(4)]
        assert final.prescriptions.sum()==5  # customers, not the 7 matching contact legs
        totals=final.groupby('target').prescriptions.sum().to_dict()
        assert totals=={'WISMO: Handled contact before reorder':2,'WISMO: No dated matching contact':3}
        assert final.loc[final.source.eq('Same prescription'),'target'].tolist()==['WISMO: Handled contact before reorder']
        incoming=extended.groupby('target').prescriptions.sum()
        outgoing=extended.groupby('source').prescriptions.sum()
        for node in set(incoming.index)&set(outgoing.index):assert incoming[node]==outgoing[node]
        assert len(extended.attrs['columns'])==5


@pytest.mark.parametrize('case',['missing','duplicate','wrong-cancel','wrong-reorder','wrong-original-order','flag-count'])
def test_wismo_stage_rejects_mismatched_selected_intervals(case):
    details,evidence=wismo_fixture();wismo=details.copy()
    wismo['wismo_contact_count']=0;wismo['has_wismo_contact']=False
    if case=='missing':wismo=wismo.iloc[1:]
    if case=='duplicate':wismo=pd.concat([wismo,wismo.iloc[[0]]])
    if case=='wrong-cancel':wismo.loc[0,'order_cancel_time']=pd.Timestamp('2026-01-01',tz='UTC')
    if case=='wrong-reorder':wismo.loc[0,'reorder_order_id']=99999
    if case=='wrong-original-order':wismo.loc[0,'original_order_id']=99999
    if case=='flag-count':wismo.loc[0,'has_wismo_contact']=True
    with pytest.raises(ValueError):analysis.distributions(details,7,evidence,wismo)


def test_wismo_render_mode_requires_explicit_timezone_before_accessing_data():
    with patch.object(analysis.windows,'load_source') as source:
        result=CliRunner().invoke(analysis.main,['--with-wismo'])
        assert result.exit_code!=0 and 'explicit --contact-timezone' in result.output
        source.assert_not_called()


def test_wismo_variant_exports_all_customers_and_source_fingerprints(tmp_path):
    details,evidence=wismo_fixture();wismo=details.copy()
    wismo['wismo_contact_count']=0;wismo['has_wismo_contact']=False
    outputs={'customers':details[['followup_days','original_customer_id']].assign(has_reordered=True)}
    metadata=dict(start_date='2026-08-15',end_date_exclusive='2026-10-15',as_of_date='2026-10-27',
        baseline_sha256='baseline',parquet_sha256='rx',extracted_at_utc='rx-time')
    evmeta=dict(parquet_sha256='ev',extracted_at_utc='ev-time')
    wmmeta=dict(parquet_sha256='wm',extracted_at_utc='wm-time',contact_timezone='UTC')
    period='2026-08-15_2026-10-15_customer_upload_same-pet_reorders-7d-14d-21d_as-of-2026-10-27'
    def render(flows,source,png,title):
        assert flows.transition.max()==4 and len(flows.attrs['columns'])==5
        assert 'WISMO' in title
        source.write_text('sankey-beta');png.write_bytes(b'png');png.with_suffix('.svg').write_text('<svg/>')
        return str(png)
    with patch.object(analysis,'ROOT',tmp_path),patch.object(analysis,'render_sankey',side_effect=render):
        tables,diagrams=analysis.write_outputs(details,pd.DataFrame(),outputs,metadata,period,evidence,evmeta,wismo,wmmeta)
        assert len(list(tables.glob('*with-wismo-UTC*.md')))==19
        assert len(list(diagrams.glob('*with-wismo-UTC*.png')))==3
        manifest=next((tmp_path/'data').rglob('exports.json'))
        exported=json.loads(manifest.read_text())
        assert exported['wismo_source_sha256']=='wm' and exported['evidence_source_sha256']=='ev'
        assert exported['contact_timezone']=='UTC'
        for file,sha in exported['files'].items():assert analysis.digest(tmp_path/file)==sha


def test_all_handled_contact_stage_uses_neutral_labels_and_separate_exports(tmp_path):
    details,evidence=wismo_fixture();contacts=details.copy()
    contacts['wismo_contact_count']=1;contacts['has_wismo_contact']=True
    _,_,flows=analysis.distributions(details,7,evidence,contacts,True)
    assert set(flows.loc[flows.transition.eq(1),'target'])=={'Contact: Handled contact before reorder'}
    assert flows.loc[flows.transition.eq(1),'prescriptions'].sum()==5
    assert flows.attrs['columns'][1]==('Contact: ','Contacts after cancel / before reorder')
    metadata=dict(start_date='2026-08-15',end_date_exclusive='2026-10-15',as_of_date='2026-10-27',
        baseline_sha256='baseline',parquet_sha256='rx',extracted_at_utc='rx-time')
    evmeta=dict(parquet_sha256='ev',extracted_at_utc='ev-time')
    cm=dict(parquet_sha256='contact',extracted_at_utc='contact-time',contact_timezone='UTC',contact_scope='all-handled')
    period='2026-08-15_2026-10-15_customer_upload_same-pet_reorders-7d-14d-21d_as-of-2026-10-27'
    outputs={'customers':details[['followup_days','original_customer_id']].assign(has_reordered=True)}
    def render(flows,source,png,title):
        assert 'WISMO' not in title and 'contacts' in title
        source.write_text('sankey-beta');png.write_bytes(b'png');png.with_suffix('.svg').write_text('<svg/>')
        return str(png)
    with patch.object(analysis,'ROOT',tmp_path),patch.object(analysis,'render_sankey',side_effect=render):
        tables,diagrams=analysis.write_outputs(details,pd.DataFrame(),outputs,metadata,period,evidence,evmeta,contacts,cm)
        assert len(list(diagrams.glob('*with-all-handled-contacts-UTC*.png')))==3
        assert len(list(tables.glob('*with-all-handled-contacts-UTC*.md')))==19
        note=next(diagrams.glob('*.md')).read_text()
        assert 'CATEGORY_WISMO_FLAG=TRUE' not in note
        assert 'without any CATEGORY_WISMO_FLAG filter' in note
        manifest=json.loads(next((tmp_path/'data').rglob('exports.json')).read_text())
        assert manifest['contact_scope']=='all-handled'
        exported=pd.read_parquet(next((tmp_path/'data').rglob('customers-with-contacts.parquet')))
        assert 'has_handled_contact' in exported and 'has_wismo_contact' not in exported


def test_all_history_contact_nodes_do_not_claim_pre_reorder_timing():
    details,evidence=wismo_fixture();contacts=details.copy()
    contacts['wismo_contact_count']=1;contacts['has_wismo_contact']=True
    _,_,flows=analysis.distributions(details,7,evidence,contacts,all_order_history=True)
    assert set(flows.loc[flows.transition.eq(1),'target'])=={'Contact: Handled contact on aged order'}
    assert flows.attrs['columns'][1]==('Contact: ','Contacts on aged order / all history')
    contacts['wismo_contact_count']=0;contacts['has_wismo_contact']=False
    _,_,flows=analysis.distributions(details,7,evidence,contacts,all_order_history=True)
    assert set(flows.loc[flows.transition.eq(1),'target'])=={'Contact: No handled contact on aged order'}


def test_contact_presence_immediately_after_root_splits_prescription_identity():
    details,evidence=wismo_fixture();contacts=details.copy()
    contacts['has_wismo_contact']=contacts.original_customer_id.isin([7,99])
    contacts['wismo_contact_count']=contacts.has_wismo_contact.astype(int)*3
    for days in analysis.HORIZONS:
        _,_,before=analysis.distributions(details,days,evidence)
        _,_,after=analysis.distributions(details,days,evidence,contacts,all_order_history=True)
        root=after.loc[after.transition.eq(1)].set_index('target').prescriptions.to_dict()
        assert root=={'Contact: Handled contact on aged order':2,'Contact: No handled contact on aged order':3}
        second=after.loc[after.transition.eq(2)]
        assert second.set_index(['source','target']).prescriptions.to_dict()=={
            ('Contact: Handled contact on aged order','Different prescription'):1,
            ('Contact: Handled contact on aged order','Same prescription'):1,
            ('Contact: No handled contact on aged order','Different prescription'):3}
        assert second.groupby('target').prescriptions.sum().to_dict()==before.loc[before.transition.eq(1)].set_index('target').prescriptions.to_dict()
        for old,new in [(2,3),(3,4)]:
            a=before.loc[before.transition.eq(old),['source','target','prescriptions']].reset_index(drop=True)
            b=after.loc[after.transition.eq(new),['source','target','prescriptions']].reset_index(drop=True)
            pd.testing.assert_frame_equal(a,b)
        incoming=after.groupby('target').prescriptions.sum();outgoing=after.groupby('source').prescriptions.sum()
        for node in set(incoming.index)&set(outgoing.index):assert incoming[node]==outgoing[node]
        assert [x[1] for x in after.attrs['columns']]==['Reordered customers','Contacts on aged order / all history',
            'Prescription identity','Approval channel','Entity upload / decision time']
