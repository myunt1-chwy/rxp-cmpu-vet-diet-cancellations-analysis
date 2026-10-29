from decimal import Decimal
from pathlib import Path
import re
import pandas as pd
import pytest
from click.testing import CliRunner
import duckdb
from src.python import create_opportunity_aged_reorders as a
from test_opportunity_aged_reorders import sql_sources, frozen_from_raw


def ecom_source():
    common=dict(customer_id=7,order_status='D',order_order_line_status='D',order_cancel_reason=None,
                order_cancel_dttm=pd.NaT,order_line_shipped_dttm=pd.Timestamp('2026-06-04'),
                order_line_currency='USD')
    rows=[]
    for order,placed,amount in [(100,'2026-06-01','999.0000'),(101,'2026-06-02','100.1234'),
            (102,'2026-06-08','-5.2500'),(103,'2026-06-08 00:00:00.000000001','20.0000'),
            (104,'2026-08-03','30.0000'),(105,'2026-08-03 00:00:00.000000001','50.0000'),
            (106,'2026-06-02','60.0000'),(107,'2026-06-02','70.0000'),
            (108,'2026-06-02','80.0000'),(109,'2026-06-02','90.0000'),(111,'2026-06-02','10.0000')]:
        rows.append(dict(common,order_id=order,order_line_id=order*10,
                         order_placed_dttm=pd.Timestamp(placed),net_sales=Decimal(amount)))
    f=pd.DataFrame(rows)
    f.loc[f.order_id.eq(106),'order_status']='X'
    f.loc[f.order_id.eq(107),'order_cancel_reason']='Customer request'
    f.loc[f.order_id.eq(108),'order_order_line_status']=None
    f.loc[f.order_id.eq(109),'customer_id']=8
    # Identical source rows collapse, while a second physical line contributes.
    f=pd.concat([f,f.loc[f.order_id.eq(101)],
        f.loc[f.order_id.eq(101)].assign(order_line_id=1011,net_sales=Decimal('0.0000')),
        f.loc[f.order_id.eq(111)].assign(order_line_id=1111,order_order_line_status='X',order_cancel_reason='Customer request')],ignore_index=True)
    return f


def execute_ecom(ecom,rx=None,lines=None,source_days=63):
    default_rx,default_lines=sql_sources()
    rx=default_rx if rx is None else rx
    lines=default_lines if lines is None else lines
    sql=a.render_sql('2026-05-01','2026-08-01','2026-10-28',source_days,all_chewy=True)
    sql=sql.replace('EDLDB.BT_HCA_HCDM.ORDER_LINE_COST_MEASURES_RXP','rx_lines')
    sql=sql.replace('EDLDB.BT_HCA_HCDM.RXP_PRESCRIPTIONS','rx_source').replace('EDLDB.ECOM.ORDER_LINE','ecom_lines')
    sql=sql.replace('TIMESTAMP_NTZ','TIMESTAMP_NS').replace('NUMBER(', 'DECIMAL(')
    sql=re.sub(r'DATEADD\(day,(\d+),([^\)]+)\)',lambda m:'('+m[2]+"+INTERVAL '"+m[1]+" days')",sql)
    with duckdb.connect() as c:
        c.register('rx_source',rx);c.register('rx_lines',lines);c.register('ecom_lines',ecom)
        c.execute('CREATE MACRO IFF(x,a,b) AS CASE WHEN x THEN a ELSE b END')
        c.execute('CREATE MACRO TO_CHAR(x,f) AS CAST(x AS VARCHAR)')
        return c.execute(sql).df()


def test_all_chewy_line_grain_boundaries_customer_and_order_exclusions():
    raw=execute_ecom(ecom_source());frozen=frozen_from_raw(raw)
    seven,sales=a.analyze(raw,frozen,7,'2026-10-28',source_days=63,study='any-chewy',broad_source=True)
    assert set(seven['reorders'].reorder_order_id)=={'101','102'}
    assert len(seven['reorders'])==3  # two lines on 101, one on 102
    assert Decimal(sales['matching_line_net_sales'])==Decimal('94.87340')
    sixty_three,sales=a.analyze(raw,frozen,63,'2026-10-28',source_days=63,study='any-chewy',broad_source=True)
    assert set(sixty_three['reorders'].reorder_order_id)=={'101','102','103','104'}
    assert Decimal(sales['matching_line_net_sales'])==Decimal('144.87340')
    assert '109' not in set(raw.reorder_order_id.dropna().astype(int).astype(str))
    # ECOM has no prescription, product-part-number or pet filters on later orders.
    sql=a.render_sql('2026-05-01','2026-08-01','2026-10-28',63,all_chewy=True)
    later=sql.split('), candidate_keys AS (')[1]
    assert 'l.is_vet_diet_flag' not in later and 'l.rx_id' not in later and 'l.product_part_number' not in later
    assert 'l.net_sales' in later and 'PARSE_JSON' not in sql


def test_all_chewy_multiple_originals_and_missing_original_pet_part():
    rx,lines=sql_sources()
    lines=pd.concat([lines,lines.iloc[[0]].assign(order_id=2,order_line_id=22)],ignore_index=True)
    lines.loc[lines.order_id.isin([1,2]),'pet_id']=None
    lines.loc[lines.order_id.isin([1,2]),'product_part_number']=None
    raw=execute_ecom(ecom_source(),rx,lines)
    result,sales=a.analyze(raw,frozen_from_raw(raw),7,'2026-10-28',source_days=63,study='any-chewy',broad_source=True)
    assert len(result['originals'])==2 and result['originals'].usable_match_keys.all()
    assert len(result['reorders'])==3
    assert Decimal(sales['matching_line_net_sales'])==Decimal('94.87340')


def test_all_chewy_conflicting_source_amounts_rejected():
    f=ecom_source()
    f=pd.concat([f,f.loc[f.order_id.eq(101)].iloc[[0]].assign(net_sales=Decimal('999.0000'))])
    raw=execute_ecom(f)
    with pytest.raises(ValueError,match='conflicting reorder'):
        a.analyze(raw,frozen_from_raw(raw),63,'2026-10-28',source_days=63,study='any-chewy',broad_source=True)


def test_all_chewy_missing_sales_incomplete():
    f=ecom_source();f.loc[f.order_id.eq(101),'net_sales']=None
    raw=execute_ecom(f)
    _,sales=a.analyze(raw,frozen_from_raw(raw),7,'2026-10-28',source_days=63,study='any-chewy',broad_source=True)
    assert sales['matching_line_net_sales'] is None
    assert Decimal(sales['known_matching_line_net_sales'])==Decimal('-5.25000')


def test_ecom_fresh_cached_latex_and_preserved_include_order(tmp_path,monkeypatch):
    raw=execute_ecom(ecom_source())
    raw=pd.concat([raw,raw.iloc[[0]].assign(original_order_id=2,original_line_id=22,original_customer_id=8,
        original_pet_id=None,original_product_part_number=None,reorder_order_id=None)],ignore_index=True)
    (tmp_path/'src/sql').mkdir(parents=True)
    (tmp_path/'src/sql/opportunity_chewy_follow_up.sql').write_text((a.ROOT/'src/sql/opportunity_chewy_follow_up.sql').read_text())
    appendix=tmp_path/'src/latex/appendix';appendix.mkdir(parents=True)
    (appendix/'financial_opportunity_reorders.tex').write_text('Existing three studies\n')
    (appendix/'financial_opportunity_new_upload_follow_up.tex').write_text('New customer follow-up\n')
    parent=appendix/'financial_opportunity.tex'
    parent.write_text('Financial opportunity\n')
    monkeypatch.setattr(a,'ROOT',tmp_path);calls=[]
    def extraction(query,parquet,directory):
        calls.append(query);raw.to_parquet(parquet,index=False);return dict(engine='fixture')
    monkeypatch.setattr(a.base,'extract',extraction)
    args=['--all-chewy','--all-windows','--write-latex']
    result=CliRunner().invoke(a.main,args);assert result.exit_code==0,result.output
    result=CliRunner().invoke(a.main,args+['--cached']);assert result.exit_code==0,result.output
    assert len(calls)==1
    text=parent.read_text()
    assert text.index('appendix/financial_opportunity_reorders')<text.index('appendix/financial_opportunity_new_upload_follow_up')<text.index('appendix/financial_opportunity_chewy_follow_up') and 'SQL for Table' not in text
    assert text.count(r'\input{appendix/financial_opportunity_new_upload_follow_up}')==1
    assert text.index('appendix/financial_opportunity_new_upload_follow_up')<text.index('appendix/financial_opportunity_chewy_follow_up') and 'SQL for Table' not in text
    latex=(appendix/'financial_opportunity_chewy_follow_up.tex').read_text()
    assert r'\label{tab:financial-opportunity-reorder-all-chewy}' in latex
    assert r'\texttt{NET\_SALES}' in latex and r'\texttt{EDLDB.ECOM.ORDER\_LINE}' in latex
    assert 'once per physical order line' in latex and 'shipment/line contribution' not in latex
    assert 'May 1, 2026 through July 31, 2026' in latex
    assert '70 &' in latex
    summary=pd.read_parquet(next((tmp_path/'data').rglob('summary.parquet')))
    assert summary.cohort_customers.eq(2).all() and summary.cohort_percentage.eq(50).all()
    assert r'Cohort (\%)' in latex
    printed=CliRunner().invoke(a.main,args+['--print-sql'])
    assert printed.exit_code==0 and 'EDLDB.ECOM.ORDER_LINE' in printed.output and len(calls)==1
    source=next((tmp_path/'data').rglob('source.parquet'));source.write_bytes(b'invalid')
    bad=CliRunner().invoke(a.main,args+['--cached'])
    assert bad.exit_code!=0 and 'fingerprint' in bad.output


def test_all_chewy_70_day_boundary():
    f=ecom_source()
    extra=f.iloc[[0]].assign(order_id=701,order_line_id=7010,
        order_placed_dttm=pd.Timestamp('2026-06-01')+pd.Timedelta(days=70),net_sales=Decimal('12.3456'))
    extra=pd.concat([extra,extra.assign(order_id=702,order_line_id=7020,
        order_placed_dttm=pd.Timestamp('2026-06-01')+pd.Timedelta(days=70,nanoseconds=1))])
    raw=execute_ecom(pd.concat([f,extra]),source_days=70)
    result,_=a.analyze(raw,frozen_from_raw(raw),70,'2026-10-28',source_days=70,study='any-chewy',broad_source=True)
    assert '701' in set(result['reorders'].reorder_order_id)
    assert '702' not in set(result['reorders'].reorder_order_id)
    assert result['originals'].complete_followup.all()
