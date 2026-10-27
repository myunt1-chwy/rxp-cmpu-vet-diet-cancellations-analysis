"""All-aged order grain, exact timing, actual SQL joins and reproducible modes."""
import json
from unittest.mock import patch

from click.testing import CliRunner
import duckdb
import pandas as pd
import pytest

from src.python import create_aged_order_all_contact_cancellation_distribution as analysis

START, END, ASOF = '2026-08-15', '2026-10-15', '2026-10-27'


def fixtures():
    rows = []
    for rx,order,line,customer in [('r1',100,1,1),('r2',100,1,1),('r3',100,2,1),
                                  ('r4',101,3,1),('r5',102,4,2),('r6',103,5,None)]:
        rows.append(dict(rx_id=rx,rx_customer_id=customer,first_order_id=order,first_orderitem_id=str(line),
            first_order_line_id=line,rx_creation_datetime=START,rx_source_rows=1,order_id=order,order_line_id=line,
            customer_id=customer,customer_variants=1,order_cancel_reason='aged order',reason_variants=1,
            order_cancel_time='2026-09-01',cancel_variants=1,shipment_rows=2))
    a = pd.DataFrame(rows,columns=analysis.ASSOCIATIONS)
    c = pd.DataFrame([dict(order_id=order,leg_id=str(i),session_id='s',session_channel='Voice',
        contact_at_utc=(pd.Timestamp('2026-09-01',tz='UTC')+pd.Timedelta(nanoseconds=ns)).isoformat() if ns is not None else None,
        category_wismo_flag=False,handled_flag=True) for i,(order,ns) in enumerate([
            (100,-analysis.DAY_NS-1),(100,-1),(100,0),(101,analysis.DAY_NS),(101,None)])],columns=analysis.CONTACTS)
    return a,c


def summarize(a,c):
    return analysis.summarize(a,c,START,END,ASOF)


def test_all_orders_without_reorder_and_contact_grain():
    a,c = fixtures(); out=summarize(a,c); row=out['summary'].iloc[0]
    assert (row.aged_orders,row.customers,row.orders_missing_customer)==(4,2,1)
    assert (row.orders_with_contacts,row.orders_without_contacts)==(2,2)
    assert (row.customers_with_contacts,row.customers_without_contacts)==(1,1)
    assert row.contact_legs==5 and row.undated_contact_legs==1
    assert (row.contacts_before_cancellation,row.contacts_at_cancellation,row.contacts_after_cancellation)==(2,1,1)
    assert out['daily-bins'].relative_day.tolist()==[-2,-1,0,1]
    assert out['daily-bins'].contact_legs.tolist()==[1,1,1,1]
    assert out['daily-bins'].share_of_dated_contacts.sum()==1
    assert len(out['associations'])==6
    assert out['contact-details'].loc[lambda d:d.contact_at_utc.isna(),'relative_day'].isna().all()
    # Duplicate source contact legs follow COUNT(*); association duplication does not multiply them.
    assert summarize(a,pd.concat([c,c.iloc[[0]]]))['summary'].contact_legs.iloc[0]==6


@pytest.mark.parametrize('case',['line-key','order-key','customer','cancel','reason','order-conflict','duplicate-rx','unhandled','foreign-contact','rx-date'])
def test_conflicts_rejected(case):
    a,c=fixtures()
    if case=='line-key':a.loc[0,'first_order_line_id']=9
    if case=='order-key':a.loc[0,'first_order_id']=9
    if case=='customer':a.loc[0,'customer_variants']=2
    if case=='cancel':a.loc[0,'cancel_variants']=2
    if case=='reason':a.loc[0,'reason_variants']=2
    if case=='order-conflict':a.loc[2,'order_cancel_time']='2026-09-02'
    if case=='duplicate-rx':a.loc[1,'rx_id']='r1'
    if case=='unhandled':c.loc[0,'handled_flag']=False
    if case=='foreign-contact':c.loc[0,'order_id']=999
    if case=='rx-date':a.loc[0,'rx_creation_datetime']=END
    with pytest.raises(ValueError):summarize(a,c)


def test_missing_associations_cutoff_and_empty_or_undated_contacts():
    a,c=fixtures()
    missing=a.iloc[[0]].copy(); missing['rx_id']='missing'; missing['first_order_id']=None
    missing[analysis.ASSOCIATIONS[7:]]=None
    a=pd.concat([a,missing],ignore_index=True)
    assert summarize(a,c)['audit'].set_index('association_state').loc['Missing order ID','prescriptions']==1
    a.loc[a.order_id.eq(102),'order_cancel_time']=ASOF
    assert summarize(a,c)['summary'].aged_orders.iloc[0]==4
    a.loc[a.order_id.eq(102),'order_cancel_time']='2026-10-27 00:00:00.000000001'
    assert summarize(a,c)['summary'].aged_orders.iloc[0]==3
    c['contact_at_utc']=None
    assert summarize(a,c)['summary'].undated_contact_legs.iloc[0]==5
    assert summarize(a,c)['daily-bins'].contact_legs.sum()==0
    assert summarize(a,c.iloc[:0])['summary'].orders_without_contacts.iloc[0]==3
    assert summarize(a.iloc[:0],c.iloc[:0])['summary'].aged_orders.iloc[0]==0


def test_nanosecond_day_boundaries():
    a,c=fixtures()
    offsets=[-analysis.DAY_NS-1,-analysis.DAY_NS,-1,0,analysis.DAY_NS-1,analysis.DAY_NS]
    c=pd.concat([c.iloc[[0]].assign(contact_at_utc=(pd.Timestamp('2026-09-01',tz='UTC')+
        pd.Timedelta(nanoseconds=n)).isoformat()) for n in offsets],ignore_index=True)
    assert summarize(a,c)['contact-details'].relative_day.tolist()==[-2,-1,-1,0,0,1]


def test_actual_sql_boundaries_shipment_collapse_both_keys_and_contact_filters():
    a,c=fixtures()
    p=a[['rx_id','rx_customer_id','first_order_id','first_orderitem_id','rx_creation_datetime']].rename(columns={'rx_customer_id':'customer_id'})
    p=p.assign(prescription_source='CMPU',is_vet_diet_flag=True,approval_channel='CUSTOMER_UPLOAD')
    extra=p.iloc[[0]].copy().assign(rx_id='outside',rx_creation_datetime=END)
    wrong=p.iloc[[0]].copy().assign(rx_id='wrong',first_orderitem_id='999')
    p=pd.concat([p,extra,wrong],ignore_index=True)
    p['rx_creation_datetime']=pd.to_datetime(p.rx_creation_datetime)
    lines=a[['order_id','order_line_id','customer_id','order_cancel_reason','order_cancel_time']].drop_duplicates()
    lines=pd.concat([lines,lines],ignore_index=True).rename(columns={'order_cancel_time':'order_cancel_dttm'})
    lines['order_cancel_dttm']=pd.to_datetime(lines.order_cancel_dttm)
    c=c.rename(columns={'contact_at_utc':'session_start_dttm'})
    c['session_start_dttm']=pd.to_datetime(c.session_start_dttm,utc=True,format='mixed').dt.tz_localize(None)
    c=pd.concat([c,c.iloc[[0]].assign(handled_flag=False),c.iloc[[0]].assign(order_id=999)],ignore_index=True)
    sql=analysis.render_sql(START,END,ASOF).split('), records AS (')[0]+') SELECT * FROM '
    sql=sql.replace('EDLDB.BT_HCA_HCDM.RXP_PRESCRIPTIONS','p').replace('EDLDB.BT_HCA_HCDM.ORDER_LINE_COST_MEASURES_RXP','l')
    sql=sql.replace('EDLDB.BT_CUSTOMER_CARE.FCT_CONTACTS_BRD','c').replace('TIMESTAMP_NTZ','TIMESTAMP_NS')
    sql=sql.replace('TRY_TO_NUMBER(first_orderitem_id)','TRY_CAST(first_orderitem_id AS BIGINT)')
    with duckdb.connect() as con:
        con.register('p',p);con.register('l',lines);con.register('c',c)
        con.execute('CREATE MACRO IFF(x,y,z) AS IF(x,y,z)')
        con.execute('CREATE MACRO REGEXP_LIKE(x,y) AS REGEXP_FULL_MATCH(x,y)')
        con.execute('CREATE MACRO TO_CHAR(x,f) AS CAST(x AS VARCHAR)')
        associations=con.execute(sql+'associations').df()
        contacts=con.execute(sql+'contacts').df()
    assert 'outside' not in set(associations.rx_id)
    assert associations.loc[associations.rx_id.eq('wrong'),'order_id'].isna().all()
    assert associations.loc[associations.order_id.eq(100),'shipment_rows'].eq(2).all()
    assert len(contacts)==5 and contacts.category_wismo_flag.eq(False).all()
    assert summarize(associations,contacts)['summary'].contact_legs.iloc[0]==5


def raw_source():
    a,c=fixtures()
    return pd.DataFrame([dict(record_type=kind,payload=json.dumps(row),extraction_warehouse='test')
        for kind,frame in [('association',a),('contact',c)]
        for row in json.loads(frame.to_json(orient='records'))])


def test_fresh_cached_exports_fingerprints_and_sql_only(tmp_path):
    runner=CliRunner()
    with patch.object(analysis,'ROOT',tmp_path):
        args=['--start-date',START,'--end-date',END,'--as-of-date',ASOF]
        with patch.object(analysis.subprocess,'run') as execute:
            result=runner.invoke(analysis.main,args+['--print-sql'])
            assert result.exit_code==0,result.output
            assert 'FCT_CONTACTS_BRD' in result.output
            assert not list(tmp_path.iterdir())
            execute.assert_not_called()
        def extract(command,**kwargs):
            raw_source().to_parquet(tmp_path/command[command.index('--output-parquet')+1],index=False)
        with patch.object(analysis.subprocess,'run',side_effect=extract):
            result=runner.invoke(analysis.main,args)
            assert result.exit_code==0,result.output
        with patch.object(analysis.subprocess,'run') as execute:
            result=runner.invoke(analysis.main,args+['--cached'])
            assert result.exit_code==0,result.output
            execute.assert_not_called()
        assert len(list((tmp_path/'outputs/charts').rglob('*.png')))==1
        assert all(p.stat().st_size<=1_000_000 for p in (tmp_path/'outputs').rglob('*.md'))
        manifest=next((tmp_path/'data').rglob('source.json'))
        meta=json.loads(manifest.read_text());meta['sql_sha256']='bad';manifest.write_text(json.dumps(meta))
        result=runner.invoke(analysis.main,args+['--cached'])
        assert result.exit_code!=0 and 'fingerprint' in result.output
        meta['sql_sha256']=__import__('hashlib').sha256(analysis.render_sql(START,END,ASOF).encode()).hexdigest()
        manifest.write_text(json.dumps(meta))
        source=manifest.with_name('source.parquet');source.write_bytes(source.read_bytes()+b'changed')
        assert runner.invoke(analysis.main,args+['--cached']).exit_code!=0
