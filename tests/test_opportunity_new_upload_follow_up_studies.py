from decimal import Decimal
import json
import re

from click.testing import CliRunner
import duckdb
import pandas as pd

from src.python import create_opportunity_new_upload_customer_follow_up as a
from test_opportunity_new_upload_customer_follow_up import cohort_fixture
from test_opportunity_aged_reorders import broad_sources,execute_sql,frozen_from_raw,sql_sources
from test_opportunity_chewy_follow_up import ecom_source


def broad_raw():
    raw=execute_sql(*broad_sources(),all_studies=True)
    return raw.loc[raw.original_order_id.eq(1)].copy()


def test_new_cohort_broad_scopes_matching_and_distinct_counts():
    raw=broad_raw();frozen=frozen_from_raw(raw)
    anchors=pd.DataFrame({'order_id':['1'],'customer_id':['7']})
    expected={'same-part-pet':{'10','210','211'},'same-pet-different-part':{'201','210'},
              'any-vet-diet':{'10','201','203','204','205','210'}}
    for study,orders in expected.items():
        summary,exports=a.analyze_windows(raw,frozen,anchors,'2026-10-28',study=study,broad_source=True)
        assert set(exports['7d-reorders'].reorder_order_id)==orders
        assert summary.cohort_customers.eq(1).all() and summary.return_percentage.eq(100).all()
        if study=='same-pet-different-part':assert summary.iloc[0].actual_net_sales==Decimal('60.00000')
        latex=a.latex_table(summary,'2026-05-01','2026-08-01','2026-10-28',study)
        assert a.STUDY_TABLE_LABELS[study] in latex
        if study=='any-vet-diet':assert 'any pet and product part number' in latex


def chewy_raw(cohort_kind="first-upload"):
    rx,lines=sql_sources();headers=lines[['order_id','customer_id','order_placed_dttm']].drop_duplicates().assign(order_first_order_placed_flag=False)
    ecom=ecom_source()
    extra=ecom.iloc[[0]].assign(order_id=112,order_line_id=1120,order_placed_dttm=pd.Timestamp('2026-08-10'),net_sales=Decimal('12.3456'))
    extra=pd.concat([extra,extra.assign(order_id=113,order_line_id=1130,order_placed_dttm=pd.Timestamp('2026-08-10')+pd.Timedelta(nanoseconds=1))])
    ecom=pd.concat([ecom,extra])
    sql=a.render_sql('2026-05-01','2026-08-01','2026-10-28',all_chewy=True,cohort_kind=cohort_kind).replace('EDLDB.BT_HCA_HCDM.ORDER_LINE_COST_MEASURES_RXP','line_source').replace(
        'EDLDB.BT_HCA_HCDM.RXP_PRESCRIPTIONS','rx_source').replace('EDLDB.ECOM.ORDERS','headers').replace('EDLDB.ECOM.ORDER_LINE','ecom_lines')
    sql=re.sub(r'\bNUMBER\(', 'DECIMAL(', sql.replace('TIMESTAMP_NTZ','TIMESTAMP_NS'))
    sql=re.sub(r'DATEADD\(day,(\d+),([^\)]+)\)',lambda m:'('+m[2]+"+INTERVAL '"+m[1]+" days')",sql)
    with duckdb.connect() as c:
        for name,frame in [('line_source',lines),('rx_source',rx),('headers',headers),('ecom_lines',ecom)]:c.register(name,frame)
        c.execute('CREATE MACRO IFF(x,a,b) AS CASE WHEN x THEN a ELSE b END')
        c.execute('CREATE MACRO TO_CHAR(x,f) AS CAST(x AS VARCHAR)')
        return c.execute(sql).df()


def test_new_cohort_ecom_source_all_categories_line_grain_and_70_day_limit():
    raw=chewy_raw();frozen=frozen_from_raw(raw);anchors=pd.DataFrame({'order_id':['1'],'customer_id':['7']})
    summary,exports=a.analyze_windows(raw,frozen,anchors,'2026-10-28',study='any-chewy',broad_source=True)
    assert set(exports['7d-reorders'].reorder_order_id)=={'101','102'}
    assert summary.iloc[0].actual_net_sales==Decimal('94.87340')
    assert set(exports['70d-reorders'].reorder_order_id)=={'101','102','103','104','105','112'}
    assert summary.iloc[-1].actual_net_sales==Decimal('207.21900')
    latex=a.latex_table(summary,'2026-05-01','2026-08-01','2026-10-28','any-chewy')
    assert r'\texttt{NET\_SALES}' in latex and 'once per physical order line' in latex
    assert 'no later prescription' in latex and 'All-Chewy' in latex


def test_all_scopes_fresh_cached_sql_and_report_inclusions(tmp_path,monkeypatch):
    (tmp_path/'src/sql').mkdir(parents=True)
    for name in ['opportunity_new_upload_customer_follow_up.sql','opportunity_new_upload_customer_chewy_follow_up.sql']:
        (tmp_path/'src/sql'/name).write_text((a.ROOT/'src/sql'/name).read_text())
    cohort_fixture(tmp_path)
    appendix=tmp_path/'src/latex/appendix';appendix.mkdir(parents=True)
    parent=appendix/'financial_opportunity.tex';parent.write_text('Financial opportunity\n')
    rxp=broad_raw();ecom=chewy_raw();monkeypatch.setattr(a,'ROOT',tmp_path);calls=[]
    def extract(query,parquet,directory):
        calls.append(query);(ecom if 'EDLDB.ECOM.ORDER_LINE' in query.read_text() else rxp).to_parquet(parquet,index=False);return dict(engine='fixture')
    monkeypatch.setattr(a.base,'extract',extract);runner=CliRunner()
    for args in [['--all-studies','--write-latex'],['--study','any-chewy','--write-latex']]:
        for cache in [[],['--cached']]:
            result=runner.invoke(a.main,args+cache);assert result.exit_code==0,result.output
        printed=runner.invoke(a.main,args+['--print-sql']);assert printed.exit_code==0,printed.output
    assert len(calls)==2
    body=parent.read_text();rxlabel='appendix/financial_opportunity_new_upload_follow_up_same_part_pet';ecolabel='appendix/financial_opportunity_new_upload_chewy_follow_up'
    assert body.count(r'\input{'+rxlabel+'}')==body.count(r'\input{'+ecolabel+'}')==1
    assert body.index(rxlabel)<body.index(ecolabel) and 'SQL for Table' not in body
    rxlatex=(appendix/'financial_opportunity_new_upload_follow_up.tex').read_text()
    assert rxlatex.count(r'\begin{table}')==3
    for study in a.reorders.STUDIES:assert a.STUDY_TABLE_LABELS[study] in rxlatex
    eco=next((tmp_path/'data/opportunity/new-upload-customer-follow-up-chewy').rglob('analysis.json'))
    assert json.loads(eco.read_text())['source_definition']['grain']=='physical order line'
    rx=next((tmp_path/'data/opportunity/new-upload-customer-follow-up-studies').rglob('summary.parquet'))
    assert len(pd.read_parquet(rx))==30
