"""Prescription identity, incomplete evidence, repeated cancellations and frozen keys."""
import json
from unittest.mock import patch

from click.testing import CliRunner
import pandas as pd
import pytest

from src.python import create_aged_order_reorder_prescriptions as analysis


def fixtures():
    matches=pd.DataFrame([dict(original_order_id=100+i,original_line_id=i,
        reorder_order_id=200+i,reorder_line_id=i,original_customer_id=i if i<2 else 0,
        shipped_by_as_of=i!=1) for i in range(4)])
    associations=matches[['original_order_id','original_line_id']].assign(rx_id=['RX0','RX1','RX2','RX3'])
    rows=[]
    for i in range(4):
        rows.append(dict(order_id=100+i,order_line_id=i,rx_id=f'RX{i}',rx_usage_id=f'U{i}',shipment_rows=2))
        rows.append(dict(order_id=200+i,order_line_id=i,rx_id=f'RX{i}' if i==0 else 'NEW' if i==1 else None if i==2 else 'RX3',
            rx_usage_id=f'NEWUSAGE{i}',shipment_rows=1))
    rows.append(dict(order_id=203,order_line_id=3,rx_id='ALSO',rx_usage_id='EXTRA',shipment_rows=1))
    return matches,associations,pd.DataFrame(rows)


def test_same_different_unknown_multiple_and_usage_identity():
    details,customers,summary,audit=analysis.summarize(*fixtures())
    assert details.prescription_comparison.tolist()==['Same prescription','Different prescription','Unknown','Multiple prescriptions']
    assert details.original_rx_usage_ids.iloc[0]!=details.reorder_rx_usage_ids.iloc[0]
    assert details.has_shared_rx_id.tolist()==[True,False,False,True]
    assert details.original_rx_matches_cohort.all()
    assert len(customers)==2
    assert customers.loc[customers.original_customer_id.eq(0),'has_unresolved'].iloc[0]
    for _,group in summary.groupby(['population','grain']):assert group['count'].sum()==group.denominator.iloc[0]
    shipped=summary.loc[summary.population.eq('Shipped reorders') & summary.grain.eq('Cancellation/reorder line pairs')]
    assert shipped.denominator.eq(3).all() and not shipped.category.eq('Different prescription').any()


def test_partial_missing_ids_are_unknown_and_absent_line_audited():
    m,a,s=fixtures()
    s=pd.concat([s,s.iloc[[1]].assign(rx_id=None,rx_usage_id=None)],ignore_index=True)
    s.loc[s.order_id.eq(201),['rx_id','rx_usage_id','shipment_rows']]=[None,None,0]
    details,*_=analysis.summarize(m,a,s)
    assert details.prescription_comparison.iloc[0]=='Unknown'
    assert details.reorder_line_missing.iloc[1]


def test_repeated_cancellation_and_customer_patterns_do_not_double_count():
    m,a,s=fixtures()
    # Same reorder line linked to a second cancellation with a different original RX_ID.
    row=m.iloc[[0]].assign(original_order_id=999,original_line_id=9)
    m=pd.concat([m,row],ignore_index=True)
    a=pd.concat([a,pd.DataFrame([dict(original_order_id=999,original_line_id=9,rx_id='DIFFERENT')])])
    s=pd.concat([s,pd.DataFrame([dict(order_id=999,order_line_id=9,rx_id='DIFFERENT',rx_usage_id='DIFFERENTUSE',shipment_rows=1)])])
    details,customers,summary,audit=analysis.summarize(m,a,s)
    assert len(details)==5 and len(customers)==2
    c=customers.loc[customers.original_customer_id.eq(0)].iloc[0]
    assert c.has_same_prescription and c.has_different_prescription
    line_summary=summary.loc[summary.population.eq('All reorder attempts') & summary.grain.eq('Distinct reordered lines')]
    assert line_summary.denominator.eq(4).all()
    assert line_summary.category.str.contains('Different prescription \\+ Same prescription').any()


@pytest.mark.parametrize('mutation',['missing','extra','duplicate','negative','evidence_without_line'])
def test_invalid_extraction_rejected(mutation):
    m,a,s=fixtures()
    if mutation=='missing':s=s.iloc[1:]
    if mutation=='extra':s=pd.concat([s,s.iloc[[0]].assign(order_id=999)])
    if mutation=='duplicate':s=pd.concat([s,s.iloc[[0]]])
    if mutation=='negative':s.loc[0,'shipment_rows']=-1
    if mutation=='evidence_without_line':s.loc[0,'shipment_rows']=0
    with pytest.raises(ValueError):analysis.summarize(m,a,s)


def test_requested_keys_and_readonly_sql():
    m,_,_=fixtures()
    keys=analysis.requested_keys(pd.concat([m,m]))
    assert len(keys)==8
    sql=analysis.render_sql(keys)
    assert 'k.order_id = l.order_id AND k.order_line_id = l.order_line_id' in sql
    assert 'RX_ID' in sql.upper() and 'RX_USAGE_ID' in sql.upper()
    assert 'MIN(' not in sql.upper()
    with pytest.raises(ValueError,match='no reorder'):analysis.render_sql(keys.iloc[:0])
    with pytest.raises(ValueError,match='invalid'):analysis.requested_keys(m.assign(original_order_id=None))


def test_fresh_cached_frozen_fingerprints_and_cli_outputs(tmp_path):
    m,a,s=fixtures()
    m['eligibility']='Eligible'
    baseline=pd.DataFrame()
    meta=dict(parquet_sha256='baseline')
    period='2026-08-15_2026-10-15_customer_upload_reorders-7d_as-of-2026-10-27'
    def extract(args,**kwargs):
        s.assign(extraction_warehouse='test').to_parquet(tmp_path/args[args.index('--output-parquet')+1],index=False)
    with patch.object(analysis,'ROOT',tmp_path),patch.object(analysis.reorders,'load_source',return_value=(baseline,meta,period)), \
         patch.object(analysis.reorders,'summarize',return_value=(a,None,m,None,None)), \
         patch.object(analysis.subprocess,'run',side_effect=extract) as run:
        result=CliRunner().invoke(analysis.main,['--print-sql'])
        assert result.exit_code==0,result.output
        assert not list(tmp_path.iterdir());run.assert_not_called()
        result=CliRunner().invoke(analysis.main,[])
        assert result.exit_code==0,result.output
        run.assert_called_once();run.reset_mock()
        assert len(list((tmp_path/'outputs/tables/2026-08-15_2026-10-14').glob('*.md')))==4
        result=CliRunner().invoke(analysis.main,['--cached'])
        assert result.exit_code==0,result.output
        run.assert_not_called()
        manifest=next((tmp_path/'data').rglob('source.json'));saved=json.loads(manifest.read_text())
        for col in ['sql','sql_sha256','baseline_sha256','parquet_sha256']:
            manifest.write_text(json.dumps({**saved,col:'tampered'}))
            result=CliRunner().invoke(analysis.main,['--cached'])
            assert result.exit_code!=0 and 'fingerprint' in result.output
        manifest.write_text(json.dumps(saved))
        manifest.with_suffix('.parquet').write_bytes(b'bad')
        result=CliRunner().invoke(analysis.main,['--cached'])
        assert result.exit_code!=0 and 'fingerprint' in result.output
