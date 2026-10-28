"""Unique-customer subgroup distribution and verified frozen-input dependencies."""
import json
from unittest.mock import patch

from click.testing import CliRunner
import pandas as pd
import pytest

from src.python import create_aged_customer_21d_reorder_clinic_history as analysis
from tests.test_aged_order_reorder_daily_customers import fixtures as reorder_fixtures

START,END,ASOF='2026-08-15','2026-10-15','2026-10-27'


def fixtures():
    matches,population=reorder_fixtures()
    matches['followup_days']=21;population['followup_days']=21
    matches['reorder_customer_id']=matches.original_customer_id
    matches['original_product_id']=matches.original_customer_id*10
    matches['reorder_product_id']=matches.original_product_id
    matches['original_pet_id']=matches.original_customer_id*20
    matches['reorder_pet_id']=matches.original_pet_id
    groups=analysis.clinics.GROUPS+[analysis.clinics.GROUPS[2]]
    history=pd.DataFrame(dict(customer_id=range(1,6),group=groups))
    history['assessable']=history.group.ne('Unknown')
    history['has_prior_same_clinic']=history.group.eq(analysis.clinics.GROUPS[0])
    return population,matches,history


def test_unique_customer_counts_unchanged_classifications_and_unknown_denominator():
    p,m,h=fixtures();out=analysis.summarize(p,m,h)
    assert out['summary'].customers.tolist()==[1,1,1,1]
    assert out['summary'].percent_of_21d_reordered_customers.eq(25).all()
    assert out['summary'].percent_of_assessable_reordered_customers.iloc[:3].sum()==pytest.approx(100)
    assert pd.isna(out['summary'].percent_of_assessable_reordered_customers.iloc[3])
    assert out['summary'].all_aged_customers.tolist()==[1,1,2,1]
    assert len(out['customers'])==4 and out['customers'].customer_id.is_unique
    assert out['customers'].set_index('customer_id').loc[1,'original_order_id']==101
    assert out['audit'].set_index('measure').loc['Eligible complete-21-day customers','customers']==5
    assert set(out['customers'].customer_id)=={1,2,3,4}


@pytest.mark.parametrize('case',['customer','product','pet','missing-history','duplicate-history','wrong-source-group','outside-window'])
def test_invalid_keys_history_grain_and_timing_rejected(case):
    p,m,h=fixtures()
    if case=='customer':m.loc[0,'reorder_customer_id']=999
    if case=='product':m.loc[0,'reorder_product_id']=999
    if case=='pet':m.loc[0,'reorder_pet_id']=None
    if case=='missing-history':h=h.loc[h.customer_id.ne(1)]
    if case=='duplicate-history':h=pd.concat([h,h.iloc[[0]]])
    if case=='wrong-source-group':h.loc[0,'group']='unexpected'
    if case=='outside-window':m.loc[0,'reorder_placed_at_utc']=m.loc[0,'order_cancel_time']+pd.Timedelta(days=21,nanoseconds=1)
    with pytest.raises(ValueError):analysis.summarize(p,m,h)


def test_exact_21_day_boundary_other_horizons_and_empty():
    p,m,h=fixtures()
    m.loc[m.original_customer_id.eq(2),'reorder_placed_at_utc']=m.loc[m.original_customer_id.eq(2),'order_cancel_time']+pd.Timedelta(days=21)
    other=m.iloc[[0]].assign(followup_days=7,reorder_pet_id=999)
    out=analysis.summarize(p,pd.concat([m,other]),h)
    assert out['customers'].set_index('customer_id').loc[2,'day']==21
    assert analysis.summarize(p.iloc[:0],m.iloc[:0],h)['summary'].customers.eq(0).all()


def frozen_inputs(root):
    p,m,h=fixtures()
    wp=root/'data'/analysis.windows.NAME/f'{START}_{END}_customer_upload_same-pet_reorders-7d-14d-21d_as-of-{ASOF}'
    cp=root/'data'/analysis.clinics.NAME/f'{START}_{END}_as-of-{ASOF}_order-line-clinic'
    for folder in [wp,cp]:folder.mkdir(parents=True)
    sql=analysis.windows.render_sql(START,END,ASOF,True,True)
    csql=analysis.clinics.render_sql(START,END,ASOF)
    for folder in [wp,cp]:pd.DataFrame({'source':[1]}).to_parquet(folder/'source.parquet',index=False)
    options=dict(start_date=START,end_date_exclusive=END,as_of_date=ASOF)
    wm=dict(options,sql=sql,sql_sha256=analysis.hashlib.sha256(sql.encode()).hexdigest(),
        parquet_sha256=analysis.digest(wp/'source.parquet'),followup_days=[7,14,21],match_pet=True,include_21_days=True)
    cm=dict(options,sql_sha256=analysis.hashlib.sha256(csql.encode()).hexdigest(),
        parquet_sha256=analysis.digest(cp/'source.parquet'),clinic_source=analysis.clinics.CLINIC_SOURCE)
    p.to_parquet(wp/'customers.parquet',index=False);m.to_parquet(wp/'reorder-matches.parquet',index=False);h.to_parquet(cp/'customers.parquet',index=False)
    (wp/'source.json').write_text(json.dumps(wm));(cp/'source.json').write_text(json.dumps(cm))
    (wp/'exports.json').write_text(json.dumps(dict(source_sha256=wm['parquet_sha256'],files={n:analysis.digest(wp/n) for n in ['customers.parquet','reorder-matches.parquet']})))
    (cp/'manifest.json').write_text(json.dumps(dict(source=cm,files={str((cp/'customers.parquet').relative_to(root)):analysis.digest(cp/'customers.parquet')})))
    return wp,cp


def test_actual_input_loading_cli_exports_cached_and_sql_only(tmp_path):
    runner=CliRunner()
    with patch.object(analysis,'ROOT',tmp_path):
        result=runner.invoke(analysis.main,['--print-sql'])
        assert result.exit_code==0,result.output
        assert 'l.clinic_id' in result.output and not list(tmp_path.iterdir())
        frozen_inputs(tmp_path)
        result=runner.invoke(analysis.main,[])
        assert result.exit_code==0,result.output
        assert runner.invoke(analysis.main,['--cached']).exit_code==0
        manifests=list((tmp_path/'data'/analysis.NAME).rglob('manifest.json'))
        assert len(manifests)==1
        meta=json.loads(manifests[0].read_text());assert meta['followup_days']==21
        assert all(analysis.digest(tmp_path/p)==sha for p,sha in meta['files'].items())
        assert all(p.stat().st_size<=1_000_000 for p in (tmp_path/'outputs').rglob('*.md'))


@pytest.mark.parametrize('case',['sql','source','export','wrong-clinic-source'])
def test_input_fingerprint_rejection(tmp_path,case):
    with patch.object(analysis,'ROOT',tmp_path):
        wp,cp=frozen_inputs(tmp_path)
        if case=='sql':
            path=wp/'source.json';meta=json.loads(path.read_text());meta['sql']='changed';path.write_text(json.dumps(meta))
        if case=='source':
            path=wp/'source.parquet';path.write_bytes(path.read_bytes()+b'changed')
        if case=='export':
            path=cp/'customers.parquet';path.write_bytes(path.read_bytes()+b'changed')
        if case=='wrong-clinic-source':
            path=cp/'source.json';meta=json.loads(path.read_text());meta['clinic_source']='VET_ID';path.write_text(json.dumps(meta))
        with pytest.raises(ValueError,match='fingerprint'):analysis.load_inputs(START,END,ASOF)
