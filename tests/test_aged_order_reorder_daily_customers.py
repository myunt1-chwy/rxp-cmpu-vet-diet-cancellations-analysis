"""One customer per bin, exact day boundaries and population reconciliation."""
import json
from unittest.mock import patch

import pandas as pd
import pytest

from src.python import create_aged_order_reorder_daily_customers as analysis


def fixtures():
    created=pd.Timestamp('2026-09-01',tz='UTC')
    rows=[]
    for i,(customer,delay,origin) in enumerate([(1,4*analysis.DAY_NS,created),(1,analysis.DAY_NS,created+pd.Timedelta(days=10)),
            (2,14*analysis.DAY_NS,created),(3,analysis.DAY_NS+1,created),(4,1,created)]):
        rows.append(dict(original_customer_id=customer,original_order_id=100+i,original_line_id=i,
            reorder_order_id=200+i,reorder_line_id=i,followup_days=14,eligibility='Eligible',
            order_cancel_time=origin,reorder_placed_at_utc=origin+pd.Timedelta(nanoseconds=delay)))
    matches=pd.DataFrame(rows)
    customers=pd.DataFrame(dict(original_customer_id=[1,2,3,4,5],followup_days=14,has_reordered=[True,True,True,True,False]))
    return matches,customers


def test_minimum_delay_customer_once_exact_boundaries_and_zero_days():
    selected,bins,eligible=analysis.daily_counts(*fixtures())
    assert eligible==5 and len(selected)==bins.customers.sum()==4
    assert selected.day.tolist()==[1,14,2,1]
    assert bins.day.tolist()==list(range(1,15))
    assert bins.loc[bins.day.eq(1),'customers'].iloc[0]==2
    assert bins.loc[bins.day.eq(2),'customers'].iloc[0]==1
    assert bins.loc[bins.day.eq(14),'customers'].iloc[0]==1
    assert bins.percent_of_reordered_customers.sum()==100


def test_ties_choose_earlier_reorder_timestamp_and_other_horizon_excluded():
    matches,customers=fixtures()
    tie=matches.iloc[[1]].assign(reorder_order_id=999,order_cancel_time=pd.Timestamp('2026-09-02',tz='UTC'),
        reorder_placed_at_utc=pd.Timestamp('2026-09-03',tz='UTC'))
    other=matches.iloc[[0]].assign(followup_days=7,original_customer_id=999)
    selected,_,_=analysis.daily_counts(pd.concat([matches,tie,other]),customers)
    assert selected.loc[selected.original_customer_id.eq(1),'reorder_order_id'].iloc[0]==999
    assert selected.original_customer_id.nunique()==4


@pytest.mark.parametrize('delay',[0,-1,14*analysis.DAY_NS+1])
def test_invalid_reorder_timing_rejected(delay):
    m,c=fixtures();m.loc[0,'reorder_placed_at_utc']=m.loc[0,'order_cancel_time']+pd.Timedelta(nanoseconds=delay)
    with pytest.raises(ValueError,match='outside'):analysis.daily_counts(m,c)


def test_customer_population_mismatch_rejected_and_empty_handled():
    m,c=fixtures()
    with pytest.raises(ValueError,match='customer IDs'):analysis.daily_counts(m.iloc[1:],c.loc[c.original_customer_id.ne(4)])
    selected,bins,n=analysis.daily_counts(m.iloc[:0],c.iloc[:0])
    assert selected.empty and bins.customers.eq(0).all() and n==0


def test_exports_and_no_population_chart_cleanup(tmp_path):
    m,c=fixtures()
    metadata=dict(start_date='2026-08-15',end_date_exclusive='2026-10-15',as_of_date='2026-10-27',
        parquet_sha256='frozen-source',extracted_at_utc='now')
    period='2026-08-15_2026-10-15_customer_upload_reorders-7d-14d_as-of-2026-10-27'
    def render(bins,eligible,reordered,path,metadata,followup_days=14):path.write_bytes(b'png')
    with patch.object(analysis,'ROOT',tmp_path),patch.object(analysis,'figure',side_effect=render) as figure:
        bins,path=analysis.write_outputs({'reorder-matches':m,'customers':c},metadata,period)
        assert path.is_file() and path.parent.name=='2026-08-15_2026-10-14'
        assert len(list((tmp_path/'outputs/tables/2026-08-15_2026-10-14').glob('*.md')))==2
        assert 'shortest observed' in path.with_suffix('.md').read_text()
        manifest=json.loads(next((tmp_path/'data').rglob('manifest.json')).read_text())
        assert manifest['reordered_customers']==4 and manifest['eligible_customers']==5
        assert manifest['chart_sha256']==analysis.digest(path)
        figure.assert_called_once()
        analysis.write_outputs({'reorder-matches':m.iloc[:0],'customers':c.iloc[:0]},metadata,period)
        assert not path.exists()


def test_twenty_one_day_bins_and_last_boundary():
    m,c=fixtures();m['followup_days']=21;c['followup_days']=21
    m.loc[m.original_customer_id.eq(2),'reorder_placed_at_utc']=m.loc[m.original_customer_id.eq(2),'order_cancel_time']+pd.Timedelta(days=21)
    selected,bins,eligible=analysis.daily_counts(m,c,followup_days=21)
    assert len(bins)==21 and bins.day.tolist()==list(range(1,22))
    assert bins.customers.sum()==4 and eligible==5
    assert bins.loc[bins.day.eq(21),'customers'].iloc[0]==1
    m.loc[m.original_customer_id.eq(2),'reorder_placed_at_utc']+=pd.Timedelta(nanoseconds=1)
    with pytest.raises(ValueError,match='outside'):analysis.daily_counts(m,c,followup_days=21)
