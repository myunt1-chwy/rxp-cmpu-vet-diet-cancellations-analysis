"""Exercise the SQL rules with real joins, then check the independent Python audit."""
import json
from unittest.mock import patch

from click.testing import CliRunner
import duckdb
import pandas as pd
import pytest

from src.python import create_cmpu_first_order_line_event_times as analysis

DATES = ('2026-08-15', '2026-10-15', '2026-08-01')
BASE = pd.Timestamp('2026-08-15 12:00:00.123456789')


def sources():
    prescriptions = pd.DataFrame([dict(rx_id=f'RX{i}', customer_id=7, rx_creation_datetime=pd.Timestamp('2026-08-15'),
        prescription_source='CMPU', is_vet_diet_flag=True, approval_channel='CUSTOMER_UPLOAD',
        first_order_id=100, first_orderitem_id=str(i)) for i in range(12)])
    # Actual before/after cancel; cancel only; upload only; neither; estimate before/after cancel;
    # actual tie; estimate tie; missing creation with cancellation; negative and fractional interval.
    triples = [(10, 20, 30), (10, 5, 30), (None, 20, None), (10, None, 30),
               (None, None, None), (None, 20, 10), (None, 5, 10),
               (10, 10, 30), (None, 9.6, 10), (None, 20, 10),
               (None, None, -1), (None, None, 0)]
    lines, uploads = [], []
    for i, (upload, cancel, approval) in enumerate(triples):
        lines.append(dict(order_id=100, order_line_id=i, order_order_line_status=['D','X','P',None][i % 4],
            is_deleted=[True,False,None][i % 3], is_refill=[None,True,False][i % 3],
            order_line_created_dttm=BASE if i != 9 else pd.NaT,
            order_line_created_dttm_est=BASE - pd.Timedelta(hours=4) if i != 9 else pd.NaT,
            order_cancel_dttm=BASE + pd.Timedelta(hours=cancel) if cancel is not None else pd.NaT,
            min_approved_denied_datetime=BASE + pd.Timedelta(hours=approval) if approval is not None else pd.NaT))
        if upload is not None:
            uploads.append(dict(upload_id=f'U{i}', customer_id='007', rx_id=f'{{RX{i},RX{i}}}',
                                upload_type='DIET_PRESCRIPTION', created_ts_utc=BASE + pd.Timedelta(hours=upload)))
    # Fractional nanosecond estimate must round 0.96 * 13 = 12.48 to 12 ns.
    lines[11]['min_approved_denied_datetime'] = BASE + pd.Timedelta(nanoseconds=13)
    return prescriptions, pd.DataFrame(lines), pd.DataFrame(uploads)


def execute(prescriptions, lines, uploads):
    sql = analysis.render_sql(*DATES)
    for name, replacement in [('RXP_PRESCRIPTIONS','p_source'), ('ORDER_LINE_COST_MEASURES_RXP','l_source'),
                              ('RXP_UPLOAD_ENTITY','u_source')]:
        sql = sql.replace('EDLDB.BT_HCA_HCDM.' + name, replacement)
    sql = sql.replace('TIMESTAMP_NTZ', 'TIMESTAMP_NS').replace('NUMBER(38,0)', 'DECIMAL(38,0)')
    sql = sql.replace('CURRENT_WAREHOUSE()', "'test'")
    sql = sql.replace("LATERAL FLATTEN(INPUT => SPLIT(TRIM(COALESCE(u.rx_ids, ''), '{}'), ','), OUTER => TRUE) t",
        "LATERAL UNNEST(string_split(TRIM(COALESCE(u.rx_ids, ''), '{}'), ',')) t(value)")
    sql = sql.replace('t.value::VARCHAR', 't.value')
    sql = sql.replace('DATEADD(nanosecond,\n                   ROUND(DATEDIFF(nanosecond, l.line_created_utc,\n                                  l.min_approved_denied_datetime) * 0.96, 0)::DECIMAL(38,0),\n                   l.line_created_utc)',
        'make_timestamp_ns(epoch_ns(l.line_created_utc) + CAST(ROUND((epoch_ns(l.min_approved_denied_datetime) - epoch_ns(l.line_created_utc)) * 0.96, 0) AS BIGINT))')
    sql = sql.replace('DATEDIFF(nanosecond, e.line_created_utc, e.event_time)',
                      '(epoch_ns(e.event_time) - epoch_ns(e.line_created_utc))')
    with duckdb.connect() as con:
        for name, data in [('p_source', prescriptions), ('l_source', lines), ('u_source', uploads)]:
            con.register(name, data)
        con.execute('CREATE MACRO TRY_TO_NUMBER(x) AS TRY_CAST(x AS DECIMAL(38,0))')
        con.execute('CREATE MACRO REGEXP_LIKE(x, p) AS regexp_full_match(x, p)')
        con.execute('CREATE MACRO IFF(x, a, b) AS CASE WHEN x THEN a ELSE b END')
        con.execute('CREATE MACRO TO_CHAR(x, f) AS CAST(x AS VARCHAR)')
        return con.execute(sql).df()


def test_event_rules_all_statuses_flags_and_nanosecond_estimate():
    frame = execute(*sources())
    associations, lines, audit = analysis.validate(frame, *DATES)
    lines = lines.sort_values('order_line_id').reset_index(drop=True)
    assert len(associations) == len(lines) == 12
    assert lines.event_time_source.tolist() == ['actual_upload', 'order_cancellation', 'order_cancellation',
        'actual_upload', 'missing', 'estimated_upload', 'order_cancellation', 'tie', 'tie',
        'order_cancellation', 'estimated_upload', 'estimated_upload']
    assert lines.candidate_upload_source.iloc[7:9].tolist() == ['actual_upload', 'estimated_upload']
    assert lines.elapsed_hours.iloc[0:4].tolist() == [10, 5, 20, 10]
    assert pd.isna(lines.elapsed_hours.iloc[4]) and pd.isna(lines.elapsed_hours.iloc[9])
    assert lines.elapsed_hours.iloc[10] == -.96
    assert lines.estimated_upload_time.iloc[11].value - BASE.value == 12
    assert lines.estimated_upload_time.iloc[0] == pd.Timestamp(BASE + pd.Timedelta(hours=28.8), tz='UTC')
    assert set(lines.line_status.dropna()) == {'D','X','P'}
    assert lines.line_status.isna().sum() == 3
    assert lines.is_deleted.isna().sum() == lines.is_refill.isna().sum() == 4
    assert audit.loc[audit.grain.eq('event_time_source'), 'count'].sum() == len(lines)


def test_shipment_collapse_both_keys_associations_and_earliest_upload():
    p, l, u = sources()
    p = pd.concat([p, p.iloc[[0]].assign(rx_id='EXTRA'),
        p.iloc[[0]].assign(rx_id='MISSORDER', first_order_id=None),
        p.iloc[[0]].assign(rx_id='MISSLINE', first_orderitem_id=''),
        p.iloc[[0]].assign(rx_id='BADLINE', first_orderitem_id='1.1'),
        p.iloc[[0]].assign(rx_id='UNMATCHED', first_order_id=999)])
    l = pd.concat([l, l.iloc[[0]].assign(min_approved_denied_datetime=pd.NaT),
        l.iloc[[0]].assign(min_approved_denied_datetime=BASE + pd.Timedelta(hours=20)),
        l.iloc[[0]].assign(order_id=101, min_approved_denied_datetime=BASE),
        l.iloc[[0]].assign(order_line_id=99, min_approved_denied_datetime=BASE)])
    u = pd.concat([u, u.iloc[[0]].assign(upload_id='EARLY', rx_id='{EXTRA}', created_ts_utc=BASE),
                  u.iloc[[0]].assign(upload_id='WRONGCUSTOMER', customer_id='8', created_ts_utc=BASE - pd.Timedelta(days=1))])
    a, lines, audit = analysis.validate(execute(p,l,u), *DATES)
    assert len(a) == 17 and len(lines) == 12
    assert set(a.association_state) == set(analysis.STATES)
    row = lines.loc[lines.order_line_id.eq(0)].iloc[0]
    assert row.shipment_rows == 3 and row.prescription_associations == 2
    assert row.actual_upload_time == pd.Timestamp(BASE, tz='UTC')
    assert row.min_approved_denied_datetime == pd.Timestamp(BASE + pd.Timedelta(hours=20), tz='UTC')


@pytest.mark.parametrize('column,value', [('order_order_line_status','Z'), ('is_deleted',False),
    ('is_refill',True), ('order_line_created_dttm',BASE + pd.Timedelta(seconds=1)),
    ('order_cancel_dttm',BASE)])
def test_conflicting_shipment_fields_rejected(column,value):
    p,l,u = sources()
    l = pd.concat([l, l.iloc[[0]].assign(**{column:value})])
    with pytest.raises(ValueError, match='conflicting'):
        analysis.validate(execute(p,l,u), *DATES)


def test_date_boundaries_and_upload_bounds():
    p,l,u = sources()
    p = pd.concat([p, p.iloc[[0]].assign(rx_id='BEFORE',rx_creation_datetime=pd.Timestamp('2026-08-14 23:59:59.999999999')),
        p.iloc[[0]].assign(rx_id='END',rx_creation_datetime=pd.Timestamp('2026-10-15')),
        p.iloc[[0]].assign(rx_id='LAST',rx_creation_datetime=pd.Timestamp('2026-10-14 23:59:59.999999999'))])
    for timestamp, expected in [('2026-07-31 23:59:59.999999999',False),('2026-08-01',True),
                                ('2026-10-25 23:59:59.999999999',True),('2026-10-26',False)]:
        upload = u.iloc[[0]].assign(created_ts_utc=pd.Timestamp(timestamp))
        frame = execute(p,l,upload)
        a,lines,_ = analysis.validate(frame,*DATES)
        assert set(a.rx_id) == set(sources()[0].rx_id) | {'LAST'}
        assert bool(lines.actual_upload_time.notna().any()) == expected


@pytest.mark.parametrize('column,value', [('event_time','2026-08-17'),('estimated_upload_time','2026-08-17'),
    ('candidate_upload_source','estimated_upload'),('event_time_source','missing'),('elapsed_hours',11),
    ('negative_duration',True),('rx_source_rows',2),('invalid_upload_source_rows',1),
    ('first_order_line_id',99),('line_created_eastern','2026-08-15 12:00')])
def test_independent_audit_rejects_bad_extract(column,value):
    f=execute(*sources())
    f.loc[f.rx_id.eq('RX0'),column]=value
    with pytest.raises(ValueError):
        analysis.validate(f,*DATES)


def test_estimate_rounding_negative_and_missing():
    created = pd.Timestamp(BASE,tz='UTC')
    for delta, expected in [(13,12),(-13,-12),(14,13),(-14,-13),(0,0),(1,1)]:
        assert analysis.expected_estimate(created, created + pd.Timedelta(nanoseconds=delta)).value - created.value == expected
    assert pd.isna(analysis.expected_estimate(pd.NaT,created))
    assert pd.isna(analysis.expected_estimate(created,pd.NaT))


def test_fresh_cached_print_sql_fingerprints_and_flat_outputs(tmp_path):
    frame=execute(*sources())
    def extract(args, **kwargs):
        path = tmp_path / args[args.index('--output-parquet')+1]
        frame.to_parquet(path,index=False)
    with patch.object(analysis,'ROOT',tmp_path), patch.object(analysis.subprocess,'run',side_effect=extract) as run:
        result=CliRunner().invoke(analysis.main,['--print-sql'])
        assert result.exit_code==0, result.output
        assert not list(tmp_path.iterdir())
        run.assert_not_called()
        result=CliRunner().invoke(analysis.main,[])
        assert result.exit_code==0, result.output
        assert run.call_count==1
        run.reset_mock()
        result=CliRunner().invoke(analysis.main,['--cached'])
        assert result.exit_code==0,result.output
        run.assert_not_called()
        tables=list((tmp_path/'outputs/tables/2026-08-15_2026-10-14').glob('*.md'))
        assert len(tables)==3
        assert all('uploads-2026-08-01_2026-10-26' in p.name for p in tables)
        line_table=next(p for p in tables if p.name.endswith('_lines.md')).read_text()
        assert '-0.96' in line_table and 'NaT' in line_table and 'No survival outcomes' in line_table
        manifest=next((tmp_path/'data').rglob('source.json'))
        original=json.loads(manifest.read_text())
        for field in ['sql','sql_sha256','parquet_sha256','start_date','upload_start_date','upload_end_date_exclusive']:
            manifest.write_text(json.dumps({**original,field:'bad'}))
            result=CliRunner().invoke(analysis.main,['--cached'])
            assert result.exit_code!=0 and 'fingerprint' in result.output
        manifest.write_text(json.dumps(original))
        next((tmp_path/'data').rglob('source.parquet')).write_bytes(b'tampered')
        result=CliRunner().invoke(analysis.main,['--cached'])
        assert result.exit_code!=0 and 'fingerprint' in result.output


def test_empty_and_invalid_options():
    f=execute(*sources()).iloc[:0]
    a,l,audit=analysis.validate(f,*DATES)
    assert len(a)==len(l)==0
    for options in [('2026-10-15','2026-10-15','2026-08-01'),('2026-08-15','2026-10-15','2026-08-16')]:
        with pytest.raises(ValueError):
            analysis.render_sql(*options)


def test_null_cancellation_shipment_and_multiple_uploads():
    p,l,u=sources()
    l=pd.concat([l,l.iloc[[0]].assign(order_cancel_dttm=pd.NaT)])
    u=pd.concat([u,u.iloc[[0]].assign(upload_id='LATER',created_ts_utc=BASE + pd.Timedelta(hours=11))])
    a,lines,_=analysis.validate(execute(p,l,u),*DATES)
    row=lines.loc[lines.order_line_id.eq(0)].iloc[0]
    assert row.shipment_rows==2 and row.cancellation_variants==1
    assert row.actual_upload_time==pd.Timestamp(BASE + pd.Timedelta(hours=10),tz='UTC')
    assert a.loc[a.rx_id.eq('RX0'),'upload_count'].iloc[0]==2


def test_repeated_association_conflict_and_missing_flags_rejected():
    f=execute(*sources())
    other=f.loc[f.rx_id.eq('RX0')].assign(rx_id='OTHER',shipment_rows=99)
    with pytest.raises(ValueError,match='inconsistent repeated'):
        analysis.validate(pd.concat([f,other]),*DATES)
    f.loc[f.rx_id.eq('RX0'),'negative_duration']=pd.NA
    with pytest.raises(ValueError,match='negative_duration'):
        analysis.validate(f,*DATES)
