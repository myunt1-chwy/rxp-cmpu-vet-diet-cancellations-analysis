"""Approval-channel denominators, overlapping customers and source integrity."""
import json
from unittest.mock import patch

from click.testing import CliRunner
import pandas as pd
import pytest

from src.python import create_aged_order_reorder_approval_channels as analysis


def fixtures():
    lines=pd.DataFrame(dict(reorder_order_id=[10,11,12,13],reorder_line_id=[1,2,3,4],
        original_customer_id=[1,1,2,3],shipped_by_as_of=[True,False,True,False],rx_id=['A','B','A',None]))
    source=pd.DataFrame(dict(rx_id=['A','B'],matched_rx_id=['A','B'],
        approval_channel=['CUSTOMER_UPLOAD','VERBAL'],prescription_rows=[1,1]))
    return lines,source


def test_prescription_line_customer_denominators_and_multichannel_overlap():
    details,prescriptions,summary,audit=analysis.summarize(*fixtures())
    assert len(details)==4 and len(prescriptions)==2
    all_rows=summary.loc[summary.population.eq('All reorder attempts')]
    rx=all_rows.loc[all_rows.grain.eq('Reorder prescriptions')]
    assert rx.denominator.eq(2).all() and rx['count'].eq(1).all()
    lines=all_rows.loc[all_rows.grain.eq('Reordered lines')]
    assert lines.denominator.eq(4).all()
    assert lines.loc[lines.channel.eq('CUSTOMER_UPLOAD'),'count'].iloc[0]==2
    customers=all_rows.loc[all_rows.grain.eq('Customers with channel')]
    assert customers.denominator.eq(3).all() and customers['count'].sum()==4
    patterns=all_rows.loc[all_rows.grain.eq('Customers by channel combination')]
    assert 'CUSTOMER_UPLOAD + VERBAL' in patterns.channel.tolist()
    assert patterns['count'].sum()==3
    shipped=summary.loc[summary.population.eq('Shipped reorders') & summary.grain.eq('Reorder prescriptions')]
    assert shipped.denominator.iloc[0]==1 and shipped.channel.iloc[0]=='CUSTOMER_UPLOAD'
    assert audit.loc[audit.measure.eq('Customers using multiple channels'),'count'].iloc[0]==1


def test_missing_channel_unmatched_and_missing_rx_are_distinct():
    lines,source=fixtures()
    source.loc[0,'approval_channel']=' '
    source.loc[1,['matched_rx_id','approval_channel','prescription_rows']]=[None,None,0]
    details,_,_,audit=analysis.summarize(lines,source)
    assert set(details.channel)=={'[Missing approval channel]','[Unmatched prescription]','[Missing prescription ID]'}
    assert audit.loc[audit.measure.eq('Prescriptions missing approval channel'),'count'].iloc[0]==1
    assert audit.loc[audit.measure.eq('Unmatched prescriptions'),'count'].iloc[0]==1


@pytest.mark.parametrize('mutation',['duplicate','extra','missing','inconsistent','wrong_id'])
def test_bad_source_records_rejected(mutation):
    lines,source=fixtures()
    if mutation=='duplicate':source=pd.concat([source,source.iloc[[0]]])
    if mutation=='extra':source=pd.concat([source,source.iloc[[0]].assign(rx_id='X')])
    if mutation=='missing':source=source.iloc[:1]
    if mutation=='inconsistent':source.loc[0,'prescription_rows']=0
    if mutation=='wrong_id':source.loc[0,'matched_rx_id']='OTHER'
    with pytest.raises(ValueError):analysis.summarize(lines,source)


def test_repeated_cancellations_usages_and_shared_rx_deduplicate_lines():
    matches=pd.DataFrame(dict(reorder_order_id=[10,10],reorder_line_id=[1,1],original_customer_id=[1,1],shipped_by_as_of=[True,True]))
    source=pd.DataFrame(dict(order_id=[10,10],order_line_id=[1,1],rx_id=['A','A']))
    assert len(analysis.line_prescriptions(matches,source))==1
    assert len(analysis.line_prescriptions(matches,source.rename(columns=str.upper)))==1
    matches.loc[1,'original_customer_id']=999
    with pytest.raises(ValueError,match='conflicting'):analysis.line_prescriptions(matches,source)


def test_sql_ids_deduplicate_and_escape():
    sql=analysis.render_sql(['B','A','A',"O'Hare"])
    assert '["A","B","O\'\'Hare"]' in sql
    assert 'k.rx_id=p.rx_id' in sql
    assert "approval_channel = 'CUSTOMER_UPLOAD'" not in sql
    with pytest.raises(ValueError):analysis.render_sql([])


def test_cli_modes_exports_and_fingerprints(tmp_path):
    lines,source=fixtures()
    matches=lines.assign(original_order_id=99,original_line_id=5,eligibility='Eligible')
    period='2026-08-15_2026-10-15_customer_upload_reorders-7d_as-of-2026-10-27'
    def extract(args,**kwargs):
        source.assign(extraction_warehouse='test').to_parquet(tmp_path/args[args.index('--output-parquet')+1],index=False)
    with patch.object(analysis,'ROOT',tmp_path), \
         patch.object(analysis.reorders,'load_source',return_value=(pd.DataFrame(),{'parquet_sha256':'base'},period)), \
         patch.object(analysis.reorders,'summarize',return_value=(pd.DataFrame(),None,matches,None,None)), \
         patch.object(analysis.prescriptions,'load_source',return_value=(pd.DataFrame(),{'parquet_sha256':'rx'},None)), \
         patch.object(analysis.prescriptions,'summarize'),patch.object(analysis,'line_prescriptions',return_value=lines), \
         patch.object(analysis.subprocess,'run',side_effect=extract) as run:
        result=CliRunner().invoke(analysis.main,['--print-sql'])
        assert result.exit_code==0,result.output
        run.assert_not_called();assert not list(tmp_path.iterdir())
        result=CliRunner().invoke(analysis.main,[])
        assert result.exit_code==0,result.output
        run.assert_called_once();run.reset_mock()
        assert len(list((tmp_path/'outputs/tables/2026-08-15_2026-10-14').glob('*.md')))==4
        result=CliRunner().invoke(analysis.main,['--cached'])
        assert result.exit_code==0,result.output
        run.assert_not_called()
        manifest=next((tmp_path/'data').rglob('source.json'));saved=json.loads(manifest.read_text())
        for key in ['sql','sql_sha256','frozen_prescriptions_sha256','parquet_sha256']:
            manifest.write_text(json.dumps({**saved,key:'bad'}))
            result=CliRunner().invoke(analysis.main,['--cached'])
            assert result.exit_code!=0 and 'fingerprint' in result.output
        manifest.write_text(json.dumps(saved));manifest.with_suffix('.parquet').write_bytes(b'bad')
        result=CliRunner().invoke(analysis.main,['--cached'])
        assert result.exit_code!=0 and 'fingerprint' in result.output
