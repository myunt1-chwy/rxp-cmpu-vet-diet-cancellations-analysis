from decimal import Decimal
import importlib.util
from pathlib import Path
import pandas as pd
import pytest

spec = importlib.util.spec_from_file_location('comparison', Path(__file__).parents[1]/'scripts/summarize_prescription_cohort_order_comparison.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def sample():
    frozen = pd.DataFrame([
        dict(order_id='1', order_line_id='10', customer_id='7', reason='aged order', report_reason='aged order', first_order_line=1, aged_by_prior_cutoff=1),
        dict(order_id='2', order_line_id='20', customer_id='7', reason='aged order', report_reason='[Aged order outside cutoff]', first_order_line=0, aged_by_prior_cutoff=0),
    ])
    raw = pd.DataFrame([
        dict(order_id='1', order_line_id='10', customer_id='7', shipment_key='100', order_cancel_reason='AGED ORDER', order_placed_utc='2026-10-01', order_cancel_utc='2026-10-27', order_line_net_sales='10.12345'),
        dict(order_id='1', order_line_id='10', customer_id='7', shipment_key='101', order_cancel_reason='AGED ORDER', order_placed_utc='2026-10-01', order_cancel_utc='2026-10-27', order_line_net_sales='10.12345'),
        dict(order_id='2', order_line_id='20', customer_id='7', shipment_key=None, order_cancel_reason='aged order', order_placed_utc='2026-10-01', order_cancel_utc='2026-10-27 00:00:00.000000001', order_line_net_sales='-1.00000'),
    ])
    return frozen, raw


def test_split_shipments_exact_duplicates_and_cutoff():
    f,r=sample()
    r=pd.concat([r,r.iloc[[0]]],ignore_index=True)
    ships,lines,s=m.summarize(f,r)
    assert len(ships)==3 and len(lines)==2
    t=s.iloc[-1]
    assert (t.first_orders,t.first_lines,t.all_orders,t.all_lines)==(1,1,2,2)
    assert t.first_net_sales==Decimal('20.24690')
    assert t.all_net_sales==Decimal('19.24690')
    assert m.verify(f,r,s)['verified_cells']==6
    assert r'\label{tab:first-all-order-cancellations}' in m.latex_table(s)


@pytest.mark.parametrize('column,value,match',[
    ('order_line_net_sales','99.00000','conflicting sales'),
    ('customer_id','8','conflicting financial'),
    ('order_cancel_reason','Other','conflicting financial'),
])
def test_conflicting_shipment_source(column,value,match):
    f,r=sample()
    duplicate=r.iloc[[0]].copy();duplicate[column]=value
    with pytest.raises(ValueError,match=match):m.summarize(f,pd.concat([r,duplicate]))


def test_missing_sales_stays_incomplete_and_zero_retained():
    f,r=sample();r.loc[0,'order_line_net_sales']=None;r.loc[2,'order_line_net_sales']='0'
    _,lines,s=m.summarize(f,r)
    assert lines.iloc[0].missing_sales_records==1
    assert s.iloc[-1].all_net_sales is None
    assert s.iloc[-1].all_known_net_sales==Decimal('10.12345')
    m.verify(f,r,s)


@pytest.mark.parametrize('change,match', [('key','keys differ'),('customer','identity/reason'),('reason','identity/reason'),('cutoff','membership differs')])
def test_frozen_membership_drift_rejected(change,match):
    f,r=sample()
    if change=='key':r.loc[2,'order_line_id']='21'
    if change=='customer':r.loc[:1,'customer_id']='8'
    if change=='reason':r.loc[:1,'order_cancel_reason']='other'
    if change=='cutoff':r.loc[2,'order_cancel_utc']='2026-10-27'
    with pytest.raises(ValueError,match=match):m.summarize(f,r)


def test_same_order_multiple_lines_counts_once_and_verifier_catches_error():
    f,r=sample();f.loc[1,'order_id']='1';r.loc[2,'order_id']='1'
    _,_,s=m.summarize(f,r)
    assert s.iloc[-1].all_orders==1 and s.iloc[-1].all_lines==2
    m.verify(f,r,s)
    s.loc[s.row_type.eq('total'),'all_net_sales']=Decimal('19.24691')
    with pytest.raises(ValueError,match='independent'):m.verify(f,r,s)
