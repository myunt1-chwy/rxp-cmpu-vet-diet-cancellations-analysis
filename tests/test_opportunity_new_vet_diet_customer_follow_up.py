import json
import re

from click.testing import CliRunner
import duckdb
import pandas as pd

from src.python import create_opportunity_new_upload_customer_follow_up as a
from test_opportunity_new_upload_customer_follow_up import cohort_fixture
from test_opportunity_new_upload_follow_up_studies import broad_raw,chewy_raw
from test_opportunity_aged_first_vet_diet_customers import history

KIND='first-vet-diet'


def test_first_vet_diet_anchor_excludes_prior_other_channel_vet_orders():
    headers,lines=history(vet=True)
    from test_opportunity_aged_reorders import sql_sources
    rx,_=sql_sources()
    def run():
        sql=a.render_sql('2026-05-01','2026-08-01','2026-10-28',all_studies=True,cohort_kind=KIND)
        sql=sql.replace('EDLDB.BT_HCA_HCDM.ORDER_LINE_COST_MEASURES_RXP','line_source').replace(
            'EDLDB.BT_HCA_HCDM.RXP_PRESCRIPTIONS','rx_source').replace('EDLDB.ECOM.ORDERS','headers').replace('TIMESTAMP_NTZ','TIMESTAMP_NS')
        sql=re.sub(r'DATEADD\(day,(\d+),([^\)]+)\)',lambda m:'('+m[2]+"+INTERVAL '"+m[1]+" days')",sql)
        f=lines.copy();f.order_line_net_sales=f.order_line_net_sales.map(a.base.money)
        with duckdb.connect() as c:
            for name,frame in [('line_source',f),('rx_source',rx),('headers',headers)]:c.register(name,frame)
            c.execute('CREATE MACRO IFF(x,a,b) AS CASE WHEN x THEN a ELSE b END')
            c.execute('CREATE MACRO TO_CHAR(x,f) AS CAST(x AS VARCHAR)')
            return c.execute(sql).df()
    # An older vet-diet order without a matching CUSTOMER_UPLOAD prescription
    # still prevents the aged order from being first in the category.
    assert run().empty
    lines.loc[lines.order_id.eq(99),'is_vet_diet_flag']=False
    raw=run();assert set(raw.original_order_id)=={1}


def test_first_vet_diet_cohort_fingerprints_modes_and_report_triplets(tmp_path,monkeypatch):
    (tmp_path/'src/sql').mkdir(parents=True)
    for name in ['opportunity_new_vet_diet_customer_follow_up.sql','opportunity_new_vet_diet_customer_chewy_follow_up.sql']:
        (tmp_path/'src/sql'/name).write_text((a.ROOT/'src/sql'/name).read_text())
    cohort_fixture(tmp_path,scope='vet-diet')
    appendix=tmp_path/'src/latex/appendix';appendix.mkdir(parents=True)
    r=a.report_tables
    for name in list(r.WHOLE_FILES.values())+list(r.UPLOAD_FILES.values())+[r.CHEWY,r.UPLOAD_CHEWY,r.FREQUENCY]:
        (appendix/(name+'.tex')).write_text('Existing table\n')
    parent=appendix/'financial_opportunity.tex';parent.write_text('Financial opportunity\n')
    rxp=broad_raw();ecom=chewy_raw(cohort_kind=KIND)
    monkeypatch.setattr(a,'ROOT',tmp_path);calls=[]
    def extract(query,parquet,directory):
        calls.append(query);(ecom if 'EDLDB.ECOM.ORDER_LINE' in query.read_text() else rxp).to_parquet(parquet,index=False)
        return dict(engine='fixture')
    monkeypatch.setattr(a.base,'extract',extract);runner=CliRunner()
    for mode in [['--all-studies'],['--study','any-chewy']]:
        args=['--cohort',KIND,'--write-latex']+mode
        for cache in [[],['--cached']]:
            result=runner.invoke(a.main,args+cache);assert result.exit_code==0,result.output
        printed=runner.invoke(a.main,args+['--print-sql']);assert printed.exit_code==0
    assert len(calls)==2
    manifests=list((tmp_path/'data/opportunity').glob('new-vet-diet-customer-follow-up*/*/analysis.json'))
    assert len(manifests)==2
    for path in manifests:
        meta=json.loads(path.read_text());assert meta['identity']['cohort_kind']==KIND
        summary=pd.read_parquet(path.parent/'summary.parquet')
        assert summary.cohort_customers.eq(1).all()
    body=parent.read_text();order=[]
    for study in r.STUDIES:order.extend([r.WHOLE_FILES[study],r.UPLOAD_FILES[study],r.VET_FILES[study]])
    order.extend([r.CHEWY,r.UPLOAD_CHEWY,r.VET_CHEWY,r.FREQUENCY])
    positions=[body.index('\\input{appendix/'+name+'}') for name in order]
    assert positions==sorted(positions) and positions[-1] and 'SQL for Table' not in body
    latex=(appendix/'financial_opportunity_new_vet_diet_follow_up_same_part_pet.tex').read_text()
    assert r'\label{tab:financial-opportunity-new-vet-diet-follow-up}' in latex
    assert 'whose first observed vet-diet order was an aged order' in latex
    assert 'across all historical approval channels' in latex
    assert 'fixed denominator of 1 customers' in latex
    eco=(appendix/'financial_opportunity_new_vet_diet_chewy_follow_up.tex').read_text()
    assert 'tab:financial-opportunity-new-vet-diet-all-chewy' in eco
    assert r'\texttt{NET\_SALES}' in eco
