import json
import re

from click.testing import CliRunner
import duckdb
import pandas as pd
import pytest

from src.python import create_opportunity_aged_customer_contacts as a
from test_opportunity_aged_reorders import sql_sources

CANCEL=pd.Timestamp('2026-06-12 12:00:00',tz='UTC')


def source():
    def row(order,owner,offset,leg,direction='inbound',handled=True,caller='owner'):
        return dict(order_id=order,customer_id=owner,cancelled_at_utc=CANCEL,registry_variants=1,
            qualifying_lines=1,customer_variants=1,cancellation_variants=1,
            contact_order_id=order,contact_customer_id=owner if caller=='owner' else caller,
            leg_id=leg,session_id='S'+leg,session_channel='Email',session_ingress_point='Other',
            session_initial_direction=direction,handled_flag=handled,
            contact_at_utc=None if offset is None else CANCEL+offset)
    f=pd.DataFrame([
        row(1,7,pd.Timedelta(days=-13),'new-lower'),row(1,7,pd.Timedelta(days=-12),'new-next'),
        row(1,7,pd.Timedelta(days=3),'new-day3'),row(1,7,pd.Timedelta(days=4,nanoseconds=-1),'new-upper'),
        row(1,7,pd.Timedelta(days=-11),'a'),row(1,7,pd.Timedelta(days=-10),'b'),
        row(1,7,pd.Timedelta(nanoseconds=-1),'c'),row(1,7,pd.Timedelta(0),'d'),
        row(1,7,pd.Timedelta(days=1),'e'),row(1,7,pd.Timedelta(days=3,nanoseconds=-1),'f'),
        row(2,7,pd.Timedelta(0),'g',handled=False),row(3,8,pd.Timedelta(0),'h',handled=False),
        row(3,8,pd.Timedelta(days=1),'i',handled=None),
        row(1,7,pd.Timedelta(days=-3),'j',direction='outbound'),
        row(1,7,pd.Timedelta(days=-4),'k',direction=None),
        row(1,7,pd.Timedelta(days=-5),'l',caller=99),
        row(1,7,pd.Timedelta(days=-6),'m',caller=None),
        row(3,8,None,'n'),
    ])
    placeholder=f.iloc[[0]].assign(order_id=4,customer_id=9,contact_order_id=None,contact_customer_id=None,
        leg_id=None,session_id=None,session_initial_direction=None,contact_at_utc=None,handled_flag=None)
    return pd.concat([f,f.iloc[[0]],placeholder],ignore_index=True)


def test_all_seventeen_days_distinct_customers_orders_boundaries_and_unknowns():
    frames,audit,_=a.analyze(source(),'2026-05-01','2026-08-01')
    t=frames['daily_summary'].set_index('relative_day')
    assert t.index.tolist()==list(range(-13,4))
    assert tuple(t.loc[0])==(2,3)  # two customers, three orders
    assert tuple(t.loc[1])==(2,2)
    for day in [-13,-12,-11,-10,-1,2,3]:assert tuple(t.loc[day])==(1,1)
    for day in [-9,-8,-7,-6,-5,-4,-3,-2]:assert tuple(t.loc[day])==(0,0)
    frequency=frames['contact_day_frequency'].set_index('days_contacted').distinct_customers
    assert frequency.index.tolist()==list(range(18))
    assert frequency.loc[0]==1 and frequency.loc[2]==1 and frequency.loc[9]==1
    assert frequency.sum()==3 and frequency.loc[1:].sum()==2
    assert frames['customer_contact_days'].set_index('customer_id').loc['7','days_contacted']==9
    assert audit['distinct_customers_contacting']==2
    assert t.distinct_customers.sum()>audit['distinct_customers_contacting']
    assert audit['aged_customers']==3 and audit['aged_orders']==4
    assert audit['identical_contact_duplicates_collapsed']==1
    assert audit['missing_contact_time_rows']==1
    assert audit['missing_contact_customer_rows']==1 and audit['mismatched_contact_customer_rows']==1
    handled,_,_=a.analyze(source(),'2026-05-01','2026-08-01',handled_only=True)
    assert handled['contact_day_frequency'].set_index('days_contacted').loc[0,'distinct_customers']==2
    h=handled['daily_summary'].set_index('relative_day');assert tuple(h.loc[0])==(1,1) and tuple(h.loc[1])==(1,1)


def test_conflicting_leg_or_order_rejected_and_leg_ids_can_repeat_across_sessions():
    f=source();copy=f.iloc[[0]].assign(contact_at_utc=CANCEL+pd.Timedelta(days=-9))
    with pytest.raises(ValueError,match='conflicting contact'):a.analyze(pd.concat([f,copy]),'2026-05-01','2026-08-01')
    copy=copy.assign(session_id='OTHER-SESSION')
    frames,_,_=a.analyze(pd.concat([f,copy]),'2026-05-01','2026-08-01')
    assert frames['daily_summary'].set_index('relative_day').loc[-9,'distinct_aged_orders']==1
    f.loc[1,'customer_id']=10
    with pytest.raises(ValueError,match='conflicting aged'):a.analyze(f,'2026-05-01','2026-08-01')


def test_empty_source_and_no_contacts_still_seventeen_zero_rows():
    for raw in [source().iloc[:0],source().loc[source().contact_order_id.isna()]]:
        frames,_,_=a.analyze(raw,'2026-05-01','2026-08-01')
        assert len(frames['daily_summary'])==17
        assert frames['daily_summary'][['distinct_customers','distinct_aged_orders']].sum().sum()==0
        assert frames['contact_day_frequency'].distinct_customers.sum()==raw.customer_id.nunique()
        assert frames['contact_day_frequency'].iloc[1:].distinct_customers.sum()==0


def test_source_sql_exact_lower_upper_time_boundaries_and_direct_order_link():
    rx,lines=sql_sources();lines=lines.iloc[[0]].assign(order_cancel_dttm=CANCEL.tz_localize(None))
    f=source();f=f.loc[f.contact_order_id.notna()].copy()
    extra=f.iloc[[0]].assign(contact_at_utc=CANCEL+pd.Timedelta(days=-13,nanoseconds=-1),leg_id='OUT-LOWER',session_id='OUT-LOWER')
    upper=f.iloc[[0]].assign(contact_at_utc=CANCEL+pd.Timedelta(days=4),leg_id='OUT-UPPER',session_id='OUT-UPPER')
    f=pd.concat([f,extra,upper]);f['contact_at_utc']=pd.to_datetime(f.contact_at_utc,utc=True).dt.tz_localize(None)
    contacts=f[['contact_order_id','contact_customer_id','leg_id','session_id','session_channel','session_ingress_point','session_initial_direction','handled_flag','contact_at_utc']].rename(
        columns={'contact_order_id':'order_id','contact_customer_id':'customer_id','contact_at_utc':'session_start_dttm'})
    sql=a.render_sql('2026-05-01','2026-08-01').replace('EDLDB.BT_HCA_HCDM.ORDER_LINE_COST_MEASURES_RXP','line_source').replace(
        'EDLDB.BT_HCA_HCDM.RXP_PRESCRIPTIONS','rx_source').replace('EDLDB.BT_CUSTOMER_CARE.FCT_CONTACTS_BRD','contacts_source').replace('TIMESTAMP_NTZ','TIMESTAMP_NS')
    sql=re.sub(r'DATEADD\(day,(-?\d+),([^\)]+)\)',lambda m:'('+m[2]+"+INTERVAL '"+m[1]+" days')",sql)
    with duckdb.connect() as c:
        for name,frame in [('line_source',lines),('rx_source',rx),('contacts_source',contacts)]:c.register(name,frame)
        c.execute('CREATE MACRO IFF(x,a,b) AS CASE WHEN x THEN a ELSE b END')
        c.execute('CREATE MACRO TO_CHAR(x,f) AS CAST(x AS VARCHAR)')
        raw=c.execute(sql).df()
    assert not raw.leg_id.isin(['OUT-LOWER','OUT-UPPER']).any()
    frames,_,_=a.analyze(raw,'2026-05-01','2026-08-01')
    table=frames['daily_summary'].set_index('relative_day')
    assert tuple(table.loc[-13])==(1,1) and tuple(table.loc[3])==(1,1)
    assert frames['aged_orders'].order_id.tolist()==['1']


def test_fresh_cached_handled_only_sql_mode_and_source_hash(tmp_path,monkeypatch):
    (tmp_path/'src/sql').mkdir(parents=True);name='opportunity_aged_customer_contacts.sql'
    (tmp_path/'src/sql'/name).write_text((a.ROOT/'src/sql'/name).read_text())
    (tmp_path/'src/latex').mkdir()
    main=tmp_path/'src/latex/main.tex'
    main.write_text('\\input{appendix/financial_opportunity}\n\\input{appendix/study_population_analysis}\n')
    monkeypatch.setattr(a,'ROOT',tmp_path);calls=[]
    def extract(query,parquet,directory):
        calls.append(query);source().to_parquet(parquet,index=False);return dict(engine='fixture')
    monkeypatch.setattr(a.base,'extract',extract);runner=CliRunner()
    printed=runner.invoke(a.main,['--print-sql']);assert printed.exit_code==0 and not calls
    assert 'GENERATOR(ROWCOUNT=>17)' in printed.output and 'ROW_NUMBER()' in printed.output
    for args in [['--write-latex'],['--cached','--write-latex'],['--cached','--handled-only']]:
        result=runner.invoke(a.main,args);assert result.exit_code==0,result.output
    assert len(calls)==1
    latex=(tmp_path/'src/latex/appendix/contact_analysis.tex').read_text()
    assert r'\label{tab:aged-customer-contact-day-frequency}' in latex
    assert 'Number of days contacted & Number of customers' in latex
    assert '9 & 1' in latex
    assert r'\caption{' in latex and r'\label{tab:aged-customer-contacts-by-cancellation-day}' in latex
    assert 'May 1, 2026 through July 31, 2026' in latex and '2026-10-28 00:00 UTC' in latex
    assert '-13 & 1 & 1' in latex and '3 & 1 & 1' in latex
    assert 'A total of 2 distinct customers contacted across this window.' in latex
    include=r'\input{appendix/contact_analysis}'
    assert main.read_text().count(include)==1
    assert main.read_text().index('financial_opportunity')<main.read_text().index('contact_analysis')<main.read_text().index('study_population_analysis')
    root=next((tmp_path/'data/opportunity/aged-customer-contacts').glob('*'))
    for mode in ['all-inbound','handled-inbound']:
        t=pd.read_parquet(root/mode/'daily-summary.parquet');assert len(t)==17
        assert len(t.columns)==3
        meta=json.loads((root/mode/'analysis.json').read_text());assert meta['audit']['aged_orders']==4
    report=next((tmp_path/'outputs').rglob('aged-customer-contacts-by-cancellation-day.md')).read_text()
    assert 'unhandled' in report and 'zero' in report and '24-hour' in report
    (root/'source.parquet').write_bytes(b'broken')
    result=runner.invoke(a.main,['--cached']);assert result.exit_code!=0 and 'fingerprint differs' in result.output
