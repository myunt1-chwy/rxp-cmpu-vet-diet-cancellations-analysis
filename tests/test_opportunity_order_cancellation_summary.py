from decimal import Decimal
import json
from unittest.mock import patch

from click.testing import CliRunner
import duckdb
import pandas as pd
import pyarrow.parquet as pq
import pytest

from src.python import create_opportunity_order_cancellation_summary as a

DATES = ('2026-06-01', '2026-09-01')


def sources():
    prescriptions = pd.DataFrame([dict(rx_id='R1', customer_id=7, is_vet_diet_flag=True,
        approval_channel='CUSTOMER_UPLOAD', prescription_source='CMPU',
        rx_creation_datetime=pd.Timestamp('2020-01-01'), first_order_id=999, first_orderitem_id='999')])
    lines = pd.DataFrame([dict(order_id=1, order_line_id=11, shipment_key=101, customer_id=7,
        rx_id='R1', order_placed_dttm=pd.Timestamp('2026-06-01'), is_vet_diet_flag=True,
        approval_channel='CUSTOMER_UPLOAD', order_order_line_status='X', order_cancel_reason='Aged Order',
        order_line_net_sales='10.10000', site_key=13500002, order_line_site_key=13500002,
        legal_company_description='Retail', order_line_transaction_type='Retail')])
    return prescriptions, lines


def execute(prescriptions, lines, date_basis="placed", dates=DATES):
    sql = a.render_sql(*dates, date_basis=date_basis).replace('EDLDB.BT_HCA_HCDM.ORDER_LINE_COST_MEASURES_RXP', 'line_source')
    sql = sql.replace('EDLDB.BT_HCA_HCDM.RXP_PRESCRIPTIONS', 'rx_source')
    sql = sql.replace('TIMESTAMP_NTZ', 'TIMESTAMP_NS').replace('CURRENT_WAREHOUSE()', "'test'")
    with duckdb.connect() as connection:
        connection.register('rx_source', prescriptions)
        connection.register('line_source', lines)
        connection.execute('CREATE MACRO IFF(x,a,b) AS CASE WHEN x THEN a ELSE b END')
        connection.execute('CREATE MACRO TO_CHAR(x,f) AS CAST(x AS VARCHAR)')
        return connection.execute(sql).df()


def calculate(p=None, l=None):
    defaults = sources()
    return a.summarize(execute(p if p is not None else defaults[0], l if l is not None else defaults[1]), *DATES)


def total(result):
    return result['summary'].loc[result['summary'].row_type.eq('total')].iloc[0]


def test_real_sql_order_window_all_orders_no_prescription_creation_restriction():
    p, l = sources()
    l = pd.concat([l.assign(order_id=i+1, order_line_id=i+11, shipment_key=i+101, order_placed_dttm=t)
        for i, t in enumerate(pd.to_datetime(['2026-05-31 23:59:59.999999999', '2026-06-01',
            '2026-08-31 23:59:59.999999999', '2026-09-01'], format='mixed'))])
    result = calculate(p, l)
    assert set(result['order_lines'].order_id) == {'2', '3'}
    assert total(result).orders == total(result).line_items == 2
    assert total(result).actual_net_sales == Decimal('20.20000')
    assert not result['order_lines'].order_id.eq('999').any()


def test_split_shipments_equal_and_unequal_amounts_and_duplicate_associations():
    p, l = sources()
    p = pd.concat([p, p])  # Identical registry duplicates cannot multiply sales.
    l = pd.concat([l, l, l.assign(shipment_key=102),
                   l.assign(shipment_key=103, order_line_net_sales='20.20000')])
    result = calculate(p, l)
    assert total(result).orders == total(result).line_items == 1
    assert len(result['shipments']) == 3 and len(result['associations']) == 4
    assert total(result).actual_net_sales == Decimal('40.40000')
    assert result['audit'].set_index('measure').loc['repeated_financial_keys_collapsed', 'count'] == 1


def test_qualifying_lines_only_mixed_products_channels_sources_and_customer_mismatches():
    p, l = sources()
    rx = pd.concat([p, p.assign(rx_id='VET', approval_channel='VET'),
        p.assign(rx_id='OTHER', prescription_source='OTHER'), p.assign(rx_id='DRUG', is_vet_diet_flag=False),
        p.assign(rx_id='WRONG', customer_id=8)])
    lines = pd.concat([l.assign(order_line_id=11+i, shipment_key=101+i, rx_id=rxid)
                      for i, rxid in enumerate(['R1','VET','OTHER','DRUG','WRONG','MISSING'])])
    # A non-vet-diet item in the same order must not contribute revenue.
    lines = pd.concat([lines, l.assign(order_line_id=99, shipment_key=199, is_vet_diet_flag=False,
                                     order_line_net_sales='9999.00000')])
    result = calculate(rx, lines)
    assert total(result).actual_net_sales == Decimal('10.10000')
    assert total(result).line_items == 1 and total(result).orders == 1
    assert result['audit'].set_index('measure').loc['excluded_physical_lines','count'] == 5


def test_any_qualifying_rx_association_selects_physical_line_once():
    p, l = sources()
    p = pd.concat([p, p.assign(rx_id='OTHER', approval_channel='VET')])
    l = pd.concat([l, l.assign(rx_id='OTHER')])
    result = calculate(p, l)
    assert len(result['associations']) == 2 and len(result['shipments']) == 1
    assert total(result).actual_net_sales == Decimal('10.10000')


def test_missing_shipment_key_and_negative_zero_decimal_precision():
    p, l = sources()
    l = pd.concat([l.assign(order_line_id=11+i, shipment_key=None, order_line_net_sales=v)
        for i,v in enumerate(['0.10001', '0.20002', '-0.05001', '0.00000'])])
    result = calculate(p, l)
    assert total(result).actual_net_sales == Decimal('0.25002')
    assert total(result).line_items == 4
    assert len(result['shipments']) == 4
    assert result['audit'].set_index('measure').loc['negative_sales_records','count'] == 1


def test_missing_sales_marks_partial_group_and_grand_total_incomplete():
    p, l = sources()
    l = pd.concat([l, l.assign(shipment_key=102, order_line_net_sales=None)])
    result = calculate(p, l)
    assert total(result).actual_net_sales is None
    assert total(result).known_net_sales == Decimal('10.10000')
    assert total(result).missing_revenue_lines == total(result).missing_revenue_records == 1
    assert not total(result).revenue_complete
    assert 'Incomplete' in a.display_summary(result['summary']).iloc[-1,-1]


def test_reasons_blank_casefold_and_overlapping_order_totals():
    p, l = sources()
    l = pd.concat([l, l.assign(order_line_id=12, shipment_key=102, order_cancel_reason=' aged order '),
        l.assign(order_line_id=13, shipment_key=103, order_cancel_reason=None),
        l.assign(order_line_id=14, shipment_key=104, order_cancel_reason='  ')])
    result = calculate(p, l)
    groups = result['summary'].loc[result['summary'].row_type.eq('reason')]
    assert set(groups.cancellation_reason) == {'Aged order', a.MISSING_REASON}
    assert groups.orders.sum() == 2 and total(result).orders == 1
    assert total(result).line_items == 4 and total(result).actual_net_sales == Decimal('40.40000')
    assert result['audit'].set_index('measure').loc['orders_in_multiple_reason_groups','count'] == 1


@pytest.mark.parametrize('column,value,message', [
    ('order_line_net_sales','20.10000','conflicting sales'),
    ('order_line_net_sales',None,'conflicting sales'),
    ('order_cancel_reason','OTHER','cancellation reason'),
    ('order_placed_dttm',pd.Timestamp('2026-05-31'),'placement'),
    ('customer_id',8,'customer'),
])
def test_conflicting_same_source_key_or_physical_line_rejected(column,value,message):
    p, l = sources()
    l = pd.concat([l, l.assign(**{column:value})])
    with pytest.raises(ValueError, match=message):
        calculate(p, l)


def test_conflicting_registry_eligibility_rejected():
    p, l = sources()
    p = pd.concat([p, p.assign(approval_channel='VET')])
    with pytest.raises(ValueError, match='registry eligibility'):
        calculate(p, l)


def test_empty_cohort_and_invalid_parameters():
    p, l = sources()
    result = calculate(p.assign(prescription_source='OTHER'), l)
    assert total(result).orders == total(result).line_items == 0
    assert total(result).actual_net_sales == Decimal('0.00000')
    assert len(result['summary']) == 1
    assert len(calculate(p, l.iloc[:0])['shipments']) == 0
    with pytest.raises(ValueError, match='exclusive end'):
        a.render_sql('2026-09-01', '2026-06-01')
    for value in ['NaN','infinity','0.000001',0.1]:
        with pytest.raises(ValueError):
            a.money(value)


def test_exports_decimal_schema_bounded_markdown_and_stable_overwrite(tmp_path):
    result = calculate()
    meta = dict(parameters=a.parameters(*DATES), extracted_at_utc='fixture', parquet_sha256='fixture')
    path = a.write_outputs(result, meta, tmp_path, tmp_path/'tables')
    assert path.name == 'order-cancellation-summary.md'
    assert '10.10' in path.read_text()
    before = sorted(p.name for p in (tmp_path/'tables').iterdir())
    a.write_outputs(result, meta, tmp_path, tmp_path/'tables')
    assert sorted(p.name for p in (tmp_path/'tables').iterdir()) == before
    schema = pq.read_schema(tmp_path/'summary.parquet')
    assert str(schema.field('actual_net_sales').type) == 'decimal128(38, 5)'
    assert pd.read_parquet(tmp_path/'summary.parquet').actual_net_sales.iloc[-1] == Decimal('10.10000')
    assert all(p.stat().st_size <= 1_000_000 for p in (tmp_path/'tables').glob('*.md'))
    empty = calculate(p=sources()[0].assign(prescription_source='OTHER'))
    a.write_outputs(empty, meta, tmp_path, tmp_path/'tables')
    assert str(pq.read_schema(tmp_path/'order-lines.parquet').field('actual_net_sales').type) == 'decimal128(38, 5)'


def test_fresh_cached_sql_only_and_fingerprint_rejection(tmp_path, monkeypatch):
    raw = execute(*sources())
    monkeypatch.setattr(a, 'ROOT', tmp_path)
    def extraction(sql_path, parquet, directory):
        raw.to_parquet(parquet, index=False)
        return dict(engine='fixture')
    with patch.object(a, 'extract', side_effect=extraction) as fetch:
        first = CliRunner().invoke(a.main, [])
        assert first.exit_code == 0, first.output
        cached = CliRunner().invoke(a.main, ['--cached'])
        assert cached.exit_code == 0, cached.output
        assert fetch.call_count == 1
    directory = tmp_path/'data/opportunity/order-cancellation-summary/2026-05-01_2026-08-01'
    source = directory/'source.parquet'
    raw.assign(order_line_net_sales='99.00000').to_parquet(source,index=False)
    invalid = CliRunner().invoke(a.main, ['--cached'])
    assert invalid.exit_code != 0 and 'fingerprint' in invalid.output
    with patch.object(a, 'load_source', side_effect=AssertionError('SQL-only performed I/O')):
        sql = CliRunner().invoke(a.main, ['--print-sql','--cached'])
    assert sql.exit_code == 0 and '2026-05-01' in sql.output and '2026-08-01' in sql.output
    code = '\n'.join(line for line in sql.output.splitlines() if not line.lstrip().startswith('--'))
    assert 'first_order_id' not in code.lower()


def test_stale_sql_or_definition_manifest_rejected(tmp_path, monkeypatch):
    raw = execute(*sources())
    monkeypatch.setattr(a, 'ROOT', tmp_path)
    with patch.object(a, 'extract', side_effect=lambda query,parquet,directory:
                      (raw.to_parquet(parquet,index=False) or dict(engine='fixture'))):
        assert CliRunner().invoke(a.main,[]).exit_code == 0
    manifest = next((tmp_path/'data').rglob('source.json'))
    metadata = json.loads(manifest.read_text())
    metadata['identity']['version'] = 999
    manifest.write_text(json.dumps(metadata))
    assert CliRunner().invoke(a.main,['--cached']).exit_code != 0


def test_independent_raw_source_revenue_check_detects_a_five_decimal_error():
    raw = execute(*sources())
    summary = a.summarize(raw, *DATES)['summary']
    a.independent_verify(raw, summary, *DATES)
    summary.loc[summary.row_type.eq('total'), 'actual_net_sales'] += Decimal('0.00001')
    with pytest.raises(ValueError, match='independent raw-source'):
        a.independent_verify(raw, summary, *DATES)


def test_financial_appendix_dates_filters_source_and_safe_row_labels():
    text=a.financial_opportunity_latex(calculate()['summary'],a.parameters(*DATES))
    assert 'June 1, 2026 through August 31, 2026' in text
    assert '2026-06-01, 2026-09-01' in text
    assert r'APPROVAL\_CHANNEL = CUSTOMER\_UPLOAD' in text
    assert r'PRESCRIPTION\_SOURCE = CMPU' in text
    assert r'ORDER\_LINE\_NET\_SALES' in text and 'LOCAL' not in text
    assert r'\label{tab:financial-opportunity-cancellations}' in text
    assert r'\ref{tab:financial-opportunity-cancellations}' in text
    assert r'\ref{tab:study-population-counts}' in text
    assert 'tab:first-all-order-cancellations' not in text
    assert 'vet-diet' in text and '10.10' in text
    assert 'incomplete' in text and 'subsequent orders' in text


def event_calculate(lines, prescriptions=None):
    raw=execute(sources()[0] if prescriptions is None else prescriptions,lines,'shipped-or-cancelled')
    results=a.summarize(raw,*DATES,date_basis='shipped-or-cancelled')
    a.independent_verify(raw,results['summary'],*DATES,date_basis='shipped-or-cancelled')
    return raw,results


def event_sources():
    return sources()[1].assign(order_placed_dttm=pd.Timestamp('2026-01-01'),
        order_line_shipped_dttm=pd.NaT,order_cancel_dttm=pd.NaT)


@pytest.mark.parametrize('field',['order_line_shipped_dttm','order_cancel_dttm'])
def test_event_window_boundaries_independent_of_order_placement(field):
    base=event_sources()
    dates=pd.to_datetime(['2026-05-31 23:59:59.999999999','2026-06-01',
        '2026-08-31 23:59:59.999999999','2026-09-01'],format='mixed')
    lines=pd.concat([base.assign(order_id=i+1,order_line_id=i+1,shipment_key=i+1,**{field:t})
                     for i,t in enumerate(dates)])
    raw,result=event_calculate(lines)
    assert set(result['order_lines'].order_id)=={'2','3'}
    assert total(result).actual_net_sales==Decimal('20.20000')
    assert len(raw)==2


def test_event_split_shipments_both_dates_no_double_count_and_complete_associations():
    base=event_sources()
    lines=pd.concat([
        base.assign(shipment_key=1,order_line_shipped_dttm=pd.Timestamp('2026-05-31'),order_line_net_sales='100'),
        base.assign(shipment_key=2,order_line_shipped_dttm=pd.Timestamp('2026-06-01'),order_line_net_sales='20.00001'),
        base.assign(shipment_key=3,order_line_shipped_dttm=pd.Timestamp('2026-09-01'),order_line_net_sales='200'),
        base.assign(shipment_key=4,order_line_shipped_dttm=pd.Timestamp('2026-07-01'),
                    order_cancel_dttm=pd.Timestamp('2026-08-01'),order_line_net_sales='-1'),
    ])
    lines=pd.concat([lines,lines.iloc[[1]]])
    raw,result=event_calculate(lines)
    assert len(raw)==5 and len(result['associations'])==5
    assert len(result['shipments'])==2
    assert total(result).orders==total(result).line_items==1
    assert total(result).actual_net_sales==Decimal('19.00001')
    audit=result['audit'].set_index('measure')['count']
    assert audit['out_of_window_association_rows']==2
    assert audit['repeated_financial_keys_collapsed']==1
    assert audit['shipment_records_in_window']==2
    assert audit['cancellation_records_in_window']==1
    assert audit['records_meeting_both_events']==1
    result['summary'].loc[result['summary'].row_type.eq('total'),'actual_net_sales']=Decimal('19.00002')
    with pytest.raises(ValueError,match='independent raw-source'):
        a.independent_verify(raw,result['summary'],*DATES,date_basis='shipped-or-cancelled')


def test_event_null_dates_no_fallback_to_placement_and_missing_sales():
    base=event_sources().assign(order_placed_dttm=pd.Timestamp('2026-07-01'))
    _,empty=event_calculate(base)
    assert total(empty).orders==0
    line=base.assign(order_cancel_dttm=pd.Timestamp('2026-07-01'),shipment_key=None,order_line_net_sales=None)
    _,missing=event_calculate(line)
    assert total(missing).orders==1 and total(missing).actual_net_sales is None


def test_event_timestamp_conflict_rejected():
    base=event_sources().assign(order_line_shipped_dttm=pd.Timestamp('2026-07-01'))
    raw=execute(sources()[0],pd.concat([base,base.assign(order_line_shipped_dttm=pd.Timestamp('2026-09-01'))]),'shipped-or-cancelled')
    with pytest.raises(ValueError,match='conflicting event timestamps'):
        a.summarize(raw,*DATES,date_basis='shipped-or-cancelled')


def test_event_latex_defines_window_and_financial_record_scope():
    _,result=event_calculate(event_sources().assign(order_cancel_dttm=pd.Timestamp('2026-07-01')))
    text=a.financial_opportunity_latex(result['summary'],a.parameters(*DATES,date_basis='shipped-or-cancelled'))
    assert 'orders shipped or cancelled' in text
    assert 'Split-shipment sales outside the window are excluded' in text
    assert 'no order-placement or prescription-creation restriction' in text
    assert 'no prescription-creation, order-status or cancellation-date cutoff' not in text


def test_event_fresh_cached_sql_only_and_separate_cache(tmp_path,monkeypatch):
    raw=execute(sources()[0],event_sources().assign(order_cancel_dttm=pd.Timestamp('2026-07-01')),'shipped-or-cancelled')
    monkeypatch.setattr(a,'ROOT',tmp_path)
    def extraction(query,parquet,directory):
        raw.to_parquet(parquet,index=False)
        return dict(engine='fixture')
    args=['--date-basis','shipped-or-cancelled','--write-latex']
    with patch.object(a,'extract',side_effect=extraction) as fetch:
        first=CliRunner().invoke(a.main,args)
        assert first.exit_code==0,first.output
        cached=CliRunner().invoke(a.main,args+['--cached'])
        assert cached.exit_code==0,cached.output
        assert fetch.call_count==1
    assert (tmp_path/'data/opportunity/order-cancellation-summary/2026-05-01_2026-08-01/shipped-or-cancelled/source.json').exists()
    assert not (tmp_path/'data/opportunity/order-cancellation-summary/2026-05-01_2026-08-01/source.json').exists()
    assert 'orders shipped or cancelled' in (tmp_path/'src/latex/appendix/financial_opportunity.tex').read_text()
    with patch.object(a,'load_source',side_effect=AssertionError('SQL-only accessed cache')):
        printed=CliRunner().invoke(a.main,args+['--print-sql'])
    assert printed.exit_code==0 and 'order_line_shipped_dttm' in printed.output
    assert 'order_placed_dttm >=' not in printed.output


@pytest.mark.parametrize('basis',['placed','shipped-or-cancelled'])
def test_standalone_report_sql_reproduces_summary(basis):
    prescriptions,lines=sources()
    if basis=='shipped-or-cancelled':
        lines=event_sources().assign(order_cancel_dttm=pd.Timestamp('2026-07-01'))
    raw=execute(prescriptions,lines,basis)
    results=a.summarize(raw,*DATES,date_basis=basis)
    verification=a.independent_verify(raw,results['summary'],*DATES,date_basis=basis)
    sql=a.financial_opportunity_report_sql(a.render_sql(*DATES,date_basis=basis),verification)
    assert '?' not in sql and 'TIMESTAMP_NS' not in sql
    adapted=sql.replace('EDLDB.BT_HCA_HCDM.ORDER_LINE_COST_MEASURES_RXP','line_source')
    adapted=adapted.replace('EDLDB.BT_HCA_HCDM.RXP_PRESCRIPTIONS','rx_source')
    adapted=adapted.replace('TIMESTAMP_NTZ','TIMESTAMP_NS').replace('CURRENT_WAREHOUSE()',"'test'")
    adapted=adapted.replace('COUNT(DISTINCT order_id,order_line_id)','COUNT(DISTINCT(order_id,order_line_id))')
    with duckdb.connect() as connection:
        connection.register('rx_source',prescriptions)
        connection.register('line_source',lines)
        connection.execute('CREATE MACRO IFF(x,a,b) AS CASE WHEN x THEN a ELSE b END')
        connection.execute('CREATE MACRO TO_CHAR(x,f) AS CAST(x AS VARCHAR)')
        rows=connection.execute(adapted).fetchall()
    expected={(r.row_type,r.cancellation_reason.casefold()):(r.customers,r.orders,r.line_items,r.actual_net_sales)
              for r in results['summary'].itertuples()}
    assert {(kind,reason.casefold()):(customers,orders,n,sales) for kind,reason,customers,orders,n,sales in rows}==expected
    text=a.financial_opportunity_latex(results['summary'],a.parameters(*DATES,date_basis=basis))
    assert r'\label{tab:financial-opportunity-cancellations}' in text
    assert 'lstlisting' not in text and 'SQL for Table' not in text
    assert sql.rstrip() not in text


def test_distinct_customers_across_orders_lines_shipments_and_reason_groups():
    p,l=sources()
    p=pd.concat([p,p.assign(rx_id='R2',customer_id=8)])
    lines=pd.concat([l,l.assign(shipment_key=102),
        l.assign(order_id=2,order_line_id=22,shipment_key=202,order_cancel_reason='Customer request'),
        l.assign(order_id=3,order_line_id=33,shipment_key=303,rx_id='R2',customer_id=8)])
    raw=execute(p,lines);results=a.summarize(raw,*DATES)
    groups=results['summary'].set_index('cancellation_reason')
    assert groups.loc['Aged order','customers']==2
    assert groups.loc['Customer request','customers']==1
    assert groups.loc['TOTAL','customers']==2
    assert groups.loc['TOTAL','orders']==3
    a.independent_verify(raw,results['summary'],*DATES)
    results['summary'].loc[results['summary'].row_type.eq('total'),'customers']=3
    with pytest.raises(ValueError,match='independent raw-source'):
        a.independent_verify(raw,results['summary'],*DATES)


@pytest.mark.parametrize('field',['order_line_shipped_dttm','order_cancel_dttm'])
def test_may_july_event_window_boundaries(field):
    dates=('2026-05-01','2026-08-01')
    p,_=sources();base=event_sources()
    stamps=pd.to_datetime(['2026-04-30 23:59:59.999999999','2026-05-01',
        '2026-07-31 23:59:59.999999999','2026-08-01'],format='mixed')
    lines=pd.concat([base.assign(order_id=i+1,order_line_id=i+1,shipment_key=i+1,**{field:t})
                     for i,t in enumerate(stamps)])
    raw=execute(p,lines,'shipped-or-cancelled',dates)
    results=a.summarize(raw,*dates,date_basis='shipped-or-cancelled')
    a.independent_verify(raw,results['summary'],*dates,date_basis='shipped-or-cancelled')
    assert set(results['order_lines'].order_id)=={'2','3'}
    text=a.financial_opportunity_latex(results['summary'],a.parameters(*dates,date_basis='shipped-or-cancelled'))
    assert 'May 1, 2026 through July 31, 2026' in text


def test_baseline_preserves_new_customer_followup_without_sql(tmp_path,monkeypatch):
    appendix=tmp_path/'src/latex/appendix';appendix.mkdir(parents=True)
    (appendix/'financial_opportunity_new_upload_follow_up.tex').write_text('Follow-up table\n')
    monkeypatch.setattr(a,'ROOT',tmp_path)
    prescriptions,lines=sources()
    results=a.summarize(execute(prescriptions,lines),*DATES)
    text=a.financial_opportunity_latex(results['summary'],a.parameters(*DATES))
    include=r'\input{appendix/financial_opportunity_new_upload_follow_up}'
    assert text.count(include)==1 and text.rstrip().endswith(include)
    assert 'SQL for Table' not in text and 'lstlisting' not in text
