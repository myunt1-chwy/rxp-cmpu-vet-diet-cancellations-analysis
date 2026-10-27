"""Seven-day recovery definitions, deduplication and rate denominators."""
from unittest.mock import patch
import json

from click.testing import CliRunner
import pandas as pd
import pytest

from src.python import create_aged_order_same_product_reorders as analysis

DATES=('2026-08-15','2026-10-15','2026-10-27')
CANCEL=pd.Timestamp('2026-09-01 12:00:00.123456789',tz='UTC')


def source():
    records=[]
    for i in range(6):
        row=dict(rx_id=f'RX{i}',rx_source_rows=1,rx_creation_datetime='2026-08-15',
            approval_channel='CUSTOMER_UPLOAD',customer_id=7+i,product_id=200+i,
            first_order_id=100+i,first_orderitem_id=str(i),first_order_line_id=i,
            original_order_id=100+i,original_line_id=i,original_customer_id=7+i,original_product_id=200+i,
            original_product_variants=1,original_customer_variants=1,original_shipment_rows=2,original_line_status='X',original_status_variants=1,
            order_cancel_reason=' Aged Order ',original_reason_variants=1,order_cancel_time=CANCEL,
            original_cancel_variants=1)
        row.update(dict.fromkeys(analysis.REORDER_COLUMNS))
        if i in [0,1,5]:
            placed=CANCEL+pd.Timedelta(days=1 if i!=1 else 7)
            shipped=placed+pd.Timedelta(days=1 if i!=1 else 3)
            row.update(reorder_order_id=300+i,reorder_line_id=i,reorder_customer_id=7+i,
                reorder_product_id=200+i,reorder_product_variants=1,reorder_customer_variants=1,reorder_shipment_rows=2,
                reorder_line_status='D',reorder_status_variants=1,reorder_placed_at_utc=placed,
                reorder_placed_at_eastern=placed.tz_convert('America/New_York').tz_localize(None),
                reorder_placement_variants=1,reorder_shipped_at_utc=shipped,
                reorder_shipped_at_eastern=shipped.tz_convert('America/New_York').tz_localize(None))
        if i==3:row['order_cancel_time']=pd.Timestamp('2026-10-25',tz='UTC')
        if i==4:row['order_cancel_reason']='Customer Request'
        if i==5:
            row['reorder_shipped_at_utc']=None;row['reorder_shipped_at_eastern']=None
            row['reorder_line_status']='X'
        records.append(row)
    return pd.DataFrame(records)


def test_counts_exact_boundary_maturity_and_shipment_evidence():
    a,original,matches,summary,audit=analysis.summarize(source(),*DATES)
    assert len(a)==len(original)==6 and len(matches)==3
    assert original.eligibility.tolist()==['Eligible']*3+['Incomplete seven-day follow-up','Not an Aged Order cancellation','Eligible']
    assert matches.elapsed_days.tolist()==[1,7,1]
    assert matches.shipped_by_as_of.tolist()==[True,True,False]
    assert matches.shipped_within_seven_days.tolist()==[True,False,False]
    assert summary.denominator.eq(4).all()
    assert summary['count'].tolist()==[3,2]*4
    assert summary.percent.tolist()==[75,50]*4


def test_multiple_prescriptions_cancellations_and_reorder_lines_do_not_multiply_customers():
    frame=source().iloc[[0]]
    same=frame.assign(rx_id='OTHER')
    another=frame.assign(rx_id='SECOND',first_order_id=999,original_order_id=999,
        order_cancel_time=CANCEL-pd.Timedelta(hours=1))
    second_attempt=frame.assign(reorder_order_id=400,reorder_line_id=10)
    raw=pd.concat([frame,same,another,second_attempt],ignore_index=True)
    a,o,m,s,audit=analysis.summarize(raw,*DATES)
    assert len(a)==3 and len(o)==2 and len(m)==3
    assert o.reorder_line_attempts.tolist()==[2,1]
    assert s.loc[s.grain.eq('Customers'),'denominator'].eq(1).all()
    assert s.loc[s.grain.eq('Customer/product pairs'),'count'].eq(1).all()
    assert audit.loc[audit.measure.eq('Distinct reorder lines'),'count'].iloc[0]==2


@pytest.mark.parametrize('offset',[0,7*86400*1_000_000_000+1,-1])
def test_nonpositive_and_beyond_seven_day_reorders_rejected(offset):
    f=source().iloc[[0]].copy()
    f['reorder_placed_at_utc']=CANCEL+pd.Timedelta(nanoseconds=offset)
    f['reorder_placed_at_eastern']=None
    with pytest.raises(ValueError,match='seven-day'):
        analysis.summarize(f,*DATES)


@pytest.mark.parametrize('column,value',[
    ('reorder_customer_id',999),('reorder_product_id',999),('reorder_order_id',100),
    ('original_product_id',999),('original_customer_id',999),('first_order_line_id',999),
    ('original_status_variants',2),('original_product_variants',2),('original_cancel_variants',2),
    ('reorder_status_variants',2),('reorder_placement_variants',2),('rx_source_rows',2),
    ('reorder_placed_at_eastern','2026-09-10'),('rx_creation_datetime','2026-10-15')])
def test_conflicting_or_invalid_source_evidence_rejected(column,value):
    f=source().iloc[[0]].copy()
    f[column]=value
    with pytest.raises(ValueError):analysis.summarize(f,*DATES)


def test_missing_keys_cancellation_and_unmatched_associations():
    f=source().iloc[[2]].copy()
    variants=[]
    for i,(col,value) in enumerate([('original_customer_id',None),('original_product_id',None),('order_cancel_time',None)]):
        variants.append(f.assign(rx_id=f'NEW{i}',original_order_id=500+i,first_order_id=500+i,**{col:value}))
    absent=f.assign(rx_id='UNMATCHED',first_order_id=999)
    absent[analysis.ORIGINAL_COLUMNS]=None
    missing=absent.assign(rx_id='MISSING',first_order_id=None)
    a,o,m,s,audit=analysis.summarize(pd.concat([*variants,absent,missing],ignore_index=True),*DATES)
    assert len(a)==5 and len(o)==3 and m.empty
    assert set(o.eligibility)=={'Missing customer ID','Missing product mapping','Missing cancellation time'}
    assert set(a.association_state)==set(o.eligibility)|{'Missing order ID','Unmatched line'}
    assert s.denominator.eq(0).all() and s.percent.isna().all()


def test_exact_maturity_boundary_and_asof_shipment_cutoff():
    f=source().iloc[[0]].copy()
    cancel=pd.Timestamp('2026-10-20',tz='UTC')
    f['order_cancel_time']=cancel
    f['reorder_placed_at_utc']=cancel+pd.Timedelta(days=1)
    f['reorder_placed_at_eastern']=None
    f['reorder_shipped_at_utc']=pd.Timestamp('2026-10-27 00:00:00.000000001',tz='UTC')
    f['reorder_shipped_at_eastern']=None
    _,o,m,s,_=analysis.summarize(f,*DATES)
    assert o.eligibility.iloc[0]=='Eligible' and not m.shipped_by_as_of.iloc[0]
    assert s['count'].tolist()==[1,0]*4


def test_empty_population():
    a,o,m,s,audit=analysis.summarize(source().iloc[:0],*DATES)
    assert len(a)==len(o)==len(m)==0 and s.denominator.eq(0).all()


def test_dated_exports_and_fingerprints(tmp_path):
    metadata=dict(start_date=DATES[0],end_date_exclusive=DATES[1],as_of_date=DATES[2],
        approval_channel='CUSTOMER_UPLOAD',parquet_sha256='fingerprint',extracted_at_utc='now')
    period='_'.join(DATES[:2])+'_customer_upload_reorders-7d_as-of-'+DATES[2]
    with patch.object(analysis,'ROOT',tmp_path):
        summary,audit,tables=analysis.write_outputs(source(),metadata,period)
        assert tables.name=='2026-08-15_2026-10-14'
        assert len(list(tables.glob('*.md')))==5
        assert all('reorders-7d_as-of-2026-10-27' in p.name for p in tables.glob('*.md'))
        manifest=next((tmp_path/'data').rglob('exports.json'))
        info=json.loads(manifest.read_text())
        for name,sha in info['files'].items():assert analysis.digest(manifest.parent/name)==sha


def sql_sources():
    prescriptions=pd.DataFrame([dict(rx_id=rx,customer_id=7,product_id=200,
        rx_creation_datetime=pd.Timestamp(created),approval_channel=channel,
        prescription_source='CMPU',is_vet_diet_flag=True,first_order_id=order,first_orderitem_id=line)
        for rx,order,line,created,channel in [
            ('RX',100,'001','2026-08-15','CUSTOMER_UPLOAD'),
            ('REPEAT',100,'001','2026-10-14 23:59:59.999999999','CUSTOMER_UPLOAD'),
            ('BADKEY',100,'bad','2026-08-15','CUSTOMER_UPLOAD'),
            ('WRONGORDER',999,'001','2026-08-15','CUSTOMER_UPLOAD'),
            ('OTHERCHANNEL',100,'001','2026-08-15','VERBAL'),
            ('BEFORE',100,'001','2026-08-14 23:59:59.999999999','CUSTOMER_UPLOAD'),
            ('END',100,'001','2026-10-15','CUSTOMER_UPLOAD')]])
    cancel=CANCEL.tz_localize(None)
    def line(order,item,placed,product='SKU1',customer=7,cancellation=None,status='D',shipped=None):
        return dict(order_id=order,order_line_id=item,customer_id=customer,product_part_number=product,
            order_order_line_status=status,order_cancel_reason='Aged Order' if cancellation is not None else None,
            order_cancel_dttm=cancellation,order_placed_dttm=placed,
            order_placed_dttm_est=placed-pd.Timedelta(hours=4),
            order_line_shipped_dttm=shipped,order_line_shipped_dttm_est=shipped-pd.Timedelta(hours=4) if shipped is not None else None)
    originals=line(100,1,cancel-pd.Timedelta(days=11),cancellation=cancel,status='X')
    reordered=line(300,3,cancel+pd.Timedelta(days=1),shipped=cancel+pd.Timedelta(days=2))
    lines=pd.DataFrame([originals,originals,reordered,reordered,
        line(301,3,cancel+pd.Timedelta(days=1),customer=8),
        line(302,3,cancel+pd.Timedelta(days=1),product='SKU2'),
        line(100,4,cancel+pd.Timedelta(days=1)),
        line(303,3,cancel+pd.Timedelta(hours=168)),
        line(304,3,cancel+pd.Timedelta(hours=168,nanoseconds=1)),
        line(305,3,cancel),line(306,3,cancel-pd.Timedelta(nanoseconds=1))])
    for c in ['order_cancel_dttm','order_placed_dttm','order_placed_dttm_est',
              'order_line_shipped_dttm','order_line_shipped_dttm_est']:
        lines[c]=pd.to_datetime(lines[c]).astype('datetime64[ns]')
    catalog=pd.DataFrame([dict(part_number=part,product_id=product,snapshot_date=pd.Timestamp(snapshot),
        last_updated_dttm=pd.Timestamp(snapshot)) for part,product,snapshot in [
            ('SKU1',999,'2026-01-01'),('SKU1',200,'2026-10-27'),('SKU1',200,'2026-10-27'),('SKU2',201,'2026-10-27')]])
    return prescriptions,lines,catalog


def execute_sql(prescriptions,lines,catalog,channel='CUSTOMER_UPLOAD'):
    import duckdb
    sql=analysis.render_sql(*DATES,channel)
    for name,replacement in [('RXP_PRESCRIPTIONS','prescriptions_source'),('ORDER_LINE_COST_MEASURES_RXP','lines_source')]:
        sql=sql.replace('EDLDB.BT_HCA_HCDM.'+name,replacement)
    sql=sql.replace('EDLDB.PDM.PRODUCT','catalog_source').replace('TIMESTAMP_NTZ','TIMESTAMP_NS')
    sql=sql.replace('CURRENT_WAREHOUSE()',"'test'")
    sql=sql.replace('DATEADD(hour, 168, a.order_cancel_time)','make_timestamp_ns(epoch_ns(a.order_cancel_time) + 604800000000000)')
    sql=sql.replace('DATEADD(hour,168,a.order_cancel_time)','make_timestamp_ns(epoch_ns(a.order_cancel_time) + 604800000000000)')
    with duckdb.connect() as con:
        for name,frame in [('prescriptions_source',prescriptions),('lines_source',lines),('catalog_source',catalog)]:con.register(name,frame)
        con.execute('CREATE MACRO TRY_TO_NUMBER(x) AS TRY_CAST(x AS DECIMAL(38,0))')
        con.execute('CREATE MACRO REGEXP_LIKE(x,p) AS regexp_full_match(x,p)')
        con.execute('CREATE MACRO IFF(x,a,b) AS CASE WHEN x THEN a ELSE b END')
        con.execute('CREATE MACRO TO_CHAR(x,f) AS CAST(x AS VARCHAR)')
        return con.execute(sql).df()


def test_sql_keys_shipment_dedup_product_mapping_channel_and_time_boundaries():
    raw=execute_sql(*sql_sources())
    a,o,m,s,audit=analysis.summarize(raw,*DATES)
    assert set(a.rx_id)=={'RX','REPEAT','BADKEY','WRONGORDER'}
    assert len(o)==1 and o.original_shipment_rows.iloc[0]==2
    assert set(m.reorder_order_id)=={300,303}
    assert m.loc[m.reorder_order_id.eq(300),'reorder_shipment_rows'].iloc[0]==2
    assert m.elapsed_days.max()==7
    assert s.denominator.eq(1).all() and s['count'].eq(1).all()
    raw_all=execute_sql(*sql_sources(),channel='ALL')
    a_all,*_=analysis.summarize(raw_all,*DATES,channel='ALL')
    assert set(a_all.rx_id)==set(a.rx_id)|{'OTHERCHANNEL'}


def test_sql_conflicting_latest_product_mapping_rejected():
    p,l,c=sql_sources()
    c=pd.concat([c,c.iloc[[1]].assign(product_id=777)],ignore_index=True)
    with pytest.raises(ValueError,match='product mappings'):
        analysis.summarize(execute_sql(p,l,c),*DATES)


def test_cli_fresh_cached_sql_only_and_fingerprint_rejection(tmp_path):
    def extract(args,**kwargs):
        source().assign(extracted_at_session_time='now',extraction_warehouse='test').to_parquet(
            tmp_path/args[args.index('--output-parquet')+1],index=False)
    with patch.object(analysis,'ROOT',tmp_path),patch.object(analysis.subprocess,'run',side_effect=extract) as run:
        result=CliRunner().invoke(analysis.main,['--as-of-date',DATES[2],'--print-sql'])
        assert result.exit_code==0,result.output
        run.assert_not_called();assert not list(tmp_path.iterdir())
        result=CliRunner().invoke(analysis.main,['--as-of-date',DATES[2]])
        assert result.exit_code==0,result.output
        run.assert_called_once();run.reset_mock()
        result=CliRunner().invoke(analysis.main,['--as-of-date',DATES[2],'--cached'])
        assert result.exit_code==0,result.output
        run.assert_not_called()
        manifest=next((tmp_path/'data').rglob('source.json'));original=json.loads(manifest.read_text())
        for key in ['sql','sql_sha256','parquet_sha256','start_date','end_date_exclusive','as_of_date','approval_channel']:
            manifest.write_text(json.dumps({**original,key:'tampered'}))
            result=CliRunner().invoke(analysis.main,['--as-of-date',DATES[2],'--cached'])
            assert result.exit_code!=0 and 'fingerprint' in result.output
        manifest.write_text(json.dumps(original))
        manifest.with_suffix('.parquet').write_bytes(b'tampered')
        result=CliRunner().invoke(analysis.main,['--as-of-date',DATES[2],'--cached'])
        assert result.exit_code!=0 and 'fingerprint' in result.output


@pytest.mark.parametrize('options',[('2026-10-15','2026-10-15',DATES[2]),
                                   (DATES[0],DATES[1],'2026-10-01')])
def test_invalid_date_options(options):
    with pytest.raises(ValueError):analysis.render_sql(*options)


def test_nonaged_prescription_product_disagreement_is_audited():
    f=source()
    f.loc[4,'product_id']=999
    *_,audit=analysis.summarize(f,*DATES)
    assert audit.loc[audit.measure.str.contains('disagreements outside aged'),'count'].iloc[0]==1


def test_incomplete_cancellation_reorder_does_not_raise_mature_customer_rate():
    mature=source().iloc[[2]].copy()
    immature=source().iloc[[0]].copy()
    immature['rx_id']='IMMATURE'
    immature['first_order_id']=999;immature['original_order_id']=999
    immature['customer_id']=mature.customer_id.iloc[0]
    immature['original_customer_id']=mature.original_customer_id.iloc[0]
    immature['reorder_customer_id']=mature.original_customer_id.iloc[0]
    immature['product_id']=mature.product_id.iloc[0]
    immature['original_product_id']=mature.original_product_id.iloc[0]
    immature['reorder_product_id']=mature.original_product_id.iloc[0]
    immature['order_cancel_time']=pd.Timestamp('2026-10-25',tz='UTC')
    immature['reorder_placed_at_utc']=pd.Timestamp('2026-10-26',tz='UTC')
    immature['reorder_placed_at_eastern']=None
    immature['reorder_shipped_at_utc']=None;immature['reorder_shipped_at_eastern']=None
    _,_,matches,summary,_=analysis.summarize(pd.concat([mature,immature],ignore_index=True),*DATES)
    assert len(matches)==1 and summary.denominator.eq(1).all() and summary['count'].eq(0).all()
