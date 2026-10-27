"""Separate complete-follow-up populations and cumulative 7/14-day matching."""
import json
import re
from unittest.mock import patch

from click.testing import CliRunner
import duckdb
import pandas as pd
import pytest

from src.python import create_aged_order_reorder_windows as analysis
from tests.test_aged_order_same_product_reorders import sql_sources

DATES=('2026-08-15','2026-10-15','2026-10-27')
DAY_NS=86_400_000_000_000


def execute_sql(p,l,c,require_same_pet=False,include_21_days=False):
    sql=analysis.render_sql(*DATES,require_same_pet=require_same_pet,include_21_days=include_21_days)
    for table,name in [('RXP_PRESCRIPTIONS','p_source'),('ORDER_LINE_COST_MEASURES_RXP','l_source')]:
        sql=sql.replace('EDLDB.BT_HCA_HCDM.'+table,name)
    sql=sql.replace('EDLDB.PDM.PRODUCT','c_source').replace('TIMESTAMP_NTZ','TIMESTAMP_NS').replace('CURRENT_WAREHOUSE()',"'test'")
    sql=re.sub(r'DATEADD\(day,\s*(21|14|7|h\.followup_days),\s*a\.order_cancel_time\)',
        lambda m:f'make_timestamp_ns(epoch_ns(a.order_cancel_time) + CAST({m[1]} AS BIGINT) * {DAY_NS})',sql)
    with duckdb.connect() as con:
        con.register('p_source',p);con.register('l_source',l);con.register('c_source',c)
        con.execute('CREATE MACRO TRY_TO_NUMBER(x) AS TRY_CAST(x AS DECIMAL(38,0))')
        con.execute('CREATE MACRO REGEXP_LIKE(x,p) AS regexp_full_match(x,p)')
        con.execute('CREATE MACRO IFF(x,a,b) AS CASE WHEN x THEN a ELSE b END')
        con.execute('CREATE MACRO TO_CHAR(x,f) AS CAST(x AS VARCHAR)')
        return con.execute(sql).df()


def test_cumulative_windows_exact_product_keys_deduplication_and_boundaries():
    p,l,c=sql_sources()
    created=l.loc[l.order_id.eq(100),'order_cancel_dttm'].dropna().iloc[0]
    template=l.loc[l.order_id.eq(303)].iloc[[0]]
    l=pd.concat([l,template.assign(order_id=400,order_placed_dttm=created+pd.Timedelta(days=14),order_placed_dttm_est=None),
        template.assign(order_id=401,order_placed_dttm=created+pd.Timedelta(days=14,nanoseconds=1),order_placed_dttm_est=None)],ignore_index=True)
    result=analysis.summarize(execute_sql(p,l,c),*DATES)
    matches=result['reorder-matches']
    assert set(matches.loc[matches.followup_days.eq(7),'reorder_order_id'])=={300,303}
    assert set(matches.loc[matches.followup_days.eq(14),'reorder_order_id'])=={300,303,304,400}
    assert result['summary'].eligible_customers.tolist()==[1,1]
    assert result['summary'].reordered_customers.tolist()==[1,1]
    original=result['cancellation-details']
    assert original.original_shipment_rows.eq(2).all() and len(original)==2
    assert len(result['associations'])==8  # Four source prescriptions per horizon; no shipment multiplication.


def maturity_sources():
    p,l,c=sql_sources()
    p=p.iloc[:0].copy();template=l.iloc[[0]].copy()
    lines=[];prescriptions=[]
    cut=pd.Timestamp('2026-10-27')
    for i,cancel in enumerate([cut-pd.Timedelta(days=7),cut-pd.Timedelta(days=7)+pd.Timedelta(nanoseconds=1),
                               cut-pd.Timedelta(days=14),cut-pd.Timedelta(days=14)+pd.Timedelta(nanoseconds=1)]):
        prescriptions.append(dict(rx_id=f'RX{i}',customer_id=17+i,product_id=200,
            rx_creation_datetime=pd.Timestamp('2026-08-15'),approval_channel='CUSTOMER_UPLOAD',
            prescription_source='CMPU',is_vet_diet_flag=True,first_order_id=1000+i,first_orderitem_id=str(i)))
        original=template.assign(order_id=1000+i,order_line_id=i,customer_id=17+i,
            order_cancel_dttm=cancel,order_placed_dttm=cancel-pd.Timedelta(days=11),
            order_placed_dttm_est=cancel-pd.Timedelta(days=11,hours=4))
        reordered=original.assign(order_id=2000+i,order_line_id=10+i,order_cancel_dttm=pd.NaT,
            order_cancel_reason=None,order_order_line_status='P',order_placed_dttm=cancel+pd.Timedelta(days=7),
            order_placed_dttm_est=cancel+pd.Timedelta(days=7)-pd.Timedelta(hours=4))
        lines.extend([original,reordered])
    return pd.DataFrame(prescriptions),pd.concat(lines,ignore_index=True),c


def test_separate_maturity_cutoffs_exact_and_one_nanosecond_later():
    outputs=analysis.summarize(execute_sql(*maturity_sources()),*DATES)
    original=outputs['cancellation-details'].set_index(['followup_days','original_order_id'])
    assert original.loc[(7,1000),'eligibility']=='Eligible'
    assert original.loc[(7,1001),'eligibility']=='Incomplete seven-day follow-up'
    assert original.loc[(14,1002),'eligibility']=='Eligible'
    assert original.loc[(14,1003),'eligibility']=='Incomplete fourteen-day follow-up'
    assert outputs['summary'].eligible_customers.tolist()==[3,1]
    assert outputs['summary'].reordered_customers.tolist()==[3,1]
    assert set(outputs['reorder-matches'].followup_days)=={7,14}
    assert outputs['reorder-matches'].eligibility.eq('Eligible').all()


def test_customer_with_recent_and_old_cancellation_cannot_use_recent_match_for_14_days():
    p,l,c=maturity_sources()
    # Same customer and product, old cancellation has no reorder in its 14-day window;
    # recent cancellation has a qualifying 7-day reorder.
    p=p.iloc[[0,2]].copy();p['customer_id']=17
    l=l.loc[l.order_id.isin([1000,2000,1002])].copy();l['customer_id']=17
    l.loc[l.order_id.eq(1002),'order_cancel_dttm']=pd.Timestamp('2026-09-01')
    outputs=analysis.summarize(execute_sql(p,l,c),*DATES)
    assert outputs['summary'].eligible_customers.tolist()==[1,1]
    assert outputs['summary'].reordered_customers.tolist()==[1,0]


def test_missing_keys_and_empty_population_retain_audits_and_zero_denominators():
    raw=execute_sql(*sql_sources())
    outputs=analysis.summarize(raw.loc[raw.rx_id.isin(['BADKEY','WRONGORDER'])],*DATES)
    assert len(outputs['associations'])==4
    assert outputs['summary'].eligible_customers.eq(0).all()
    assert outputs['summary'].reorder_percent.isna().all()
    empty=analysis.summarize(raw.iloc[:0],*DATES)
    assert empty['summary'].eligible_customers.eq(0).all() and len(empty['summary'])==2


@pytest.mark.parametrize('field,value',[('followup_days',30),('followup_complete',False),('window_end_utc','2026-10-27')])
def test_invalid_sql_horizon_or_maturity_evidence_rejected(field,value):
    raw=execute_sql(*sql_sources());raw.loc[raw.rx_id.eq('RX') & raw.followup_days.eq(7),field]=value
    with pytest.raises(ValueError):analysis.summarize(raw,*DATES)


def test_missing_horizon_rejected():
    raw=execute_sql(*sql_sources())
    with pytest.raises(ValueError,match='missing follow-up'):
        analysis.summarize(raw.loc[raw.followup_days.eq(7)],*DATES)


def test_existing_seven_day_cache_and_results_unchanged():
    from tests.test_aged_order_same_product_reorders import source
    default=analysis.prior.summarize(source(),*DATES)
    explicit=analysis.prior.summarize(source(),*DATES,followup_days=7)
    for old,new in zip(default,explicit):pd.testing.assert_frame_equal(old,new)
    assert 'shipped_within_seven_days' in default[2]
    with pytest.raises(ValueError):analysis.prior.summarize(source(),*DATES,followup_days=30)


def test_fresh_cached_sql_only_dated_outputs_and_fingerprint_rejection(tmp_path):
    raw=execute_sql(*sql_sources())
    def extract(args,**kwargs):raw.to_parquet(tmp_path/args[args.index('--output-parquet')+1],index=False)
    with patch.object(analysis,'ROOT',tmp_path),patch.object(analysis.subprocess,'run',side_effect=extract) as run:
        result=CliRunner().invoke(analysis.main,['--print-sql'])
        assert result.exit_code==0,result.output
        assert not list(tmp_path.iterdir());run.assert_not_called()
        result=CliRunner().invoke(analysis.main,[])
        assert result.exit_code==0,result.output
        run.assert_called_once();run.reset_mock()
        tables=list((tmp_path/'outputs/tables/2026-08-15_2026-10-14').glob('*.md'))
        assert len(tables)==6 and all('reorders-7d-14d_as-of-2026-10-27' in p.name for p in tables)
        summary=next(p for p in tables if p.name.endswith('_summary.md')).read_text()
        assert 'latest_eligible_cancellation_utc' in summary and '2026-10-13' in summary and '2026-10-20' in summary
        result=CliRunner().invoke(analysis.main,['--cached'])
        assert result.exit_code==0,result.output
        run.assert_not_called()
        manifest=next((tmp_path/'data').rglob('source.json'));saved=json.loads(manifest.read_text())
        for field in ['sql','sql_sha256','parquet_sha256','start_date','end_date_exclusive','as_of_date','followup_days']:
            manifest.write_text(json.dumps({**saved,field:'bad'}))
            result=CliRunner().invoke(analysis.main,['--cached'])
            assert result.exit_code!=0 and 'fingerprint' in result.output
        manifest.write_text(json.dumps(saved));manifest.with_suffix('.parquet').write_bytes(b'bad')
        result=CliRunner().invoke(analysis.main,['--cached'])
        assert result.exit_code!=0 and 'fingerprint' in result.output


def pet_sources():
    p,l,c=sql_sources()
    return p,l.assign(pet_id=50),c


def test_same_pet_sql_excludes_other_and_unknown_pets_and_audits_candidates():
    p,l,c=pet_sources()
    l.loc[l.order_id.eq(303),'pet_id']=51
    l.loc[l.order_id.eq(304),'pet_id']=None
    raw=execute_sql(p,l,c,require_same_pet=True)
    outputs=analysis.summarize(raw,*DATES,require_same_pet=True)
    matches=outputs['reorder-matches']
    assert set(matches.reorder_order_id)=={300}
    assert matches.original_pet_id.eq(matches.reorder_pet_id).all()
    assert outputs['summary'].eligible_customers.tolist()==[1,1]
    assert outputs['audit'].loc[outputs['audit'].measure.eq('All-horizon candidate_missing_pet_lines'),'count'].eq(1).all()
    # Both customers/products agree for excluded rows; PET_ID is what changes qualification.
    loose=analysis.summarize(execute_sql(p,l,c),*DATES)
    assert set(loose['reorder-matches'].reorder_order_id)=={300,303,304}


@pytest.mark.parametrize('missing',[True,False])
def test_missing_or_ambiguous_original_pet_does_not_enter_denominator(missing):
    p,l,c=pet_sources()
    if missing:l.loc[(l.order_id.eq(100)&l.order_line_id.eq(1)),'pet_id']=None
    else:l=pd.concat([l,l.loc[l.order_id.eq(100)&l.order_line_id.eq(1)].iloc[[0]].assign(pet_id=51)])
    outputs=analysis.summarize(execute_sql(p,l,c,require_same_pet=True),*DATES,require_same_pet=True)
    assert outputs['summary'].eligible_customers.eq(0).all()
    assert outputs['reorder-matches'].empty
    label='Missing pet ID' if missing else 'Ambiguous pet ID'
    assert outputs['cancellation-details'].eligibility.eq(label).all()


def test_ambiguous_reorder_pet_and_tampered_pet_match_rejected():
    p,l,c=pet_sources()
    l=pd.concat([l,l.loc[l.order_id.eq(300)].iloc[[0]].assign(pet_id=51)])
    raw=execute_sql(p,l,c,require_same_pet=True)
    outputs=analysis.summarize(raw,*DATES,require_same_pet=True)
    assert 300 not in outputs['reorder-matches'].reorder_order_id.tolist()
    assert outputs['audit'].loc[outputs['audit'].measure.eq('All-horizon candidate_ambiguous_pet_lines'),'count'].eq(1).all()
    raw=execute_sql(*pet_sources(),require_same_pet=True)
    raw.loc[raw.reorder_order_id.eq(300),'reorder_pet_id']=999
    with pytest.raises(ValueError,match='pet identity'):
        analysis.summarize(raw,*DATES,require_same_pet=True)


def test_same_pet_cli_cache_and_filenames_separate_from_existing_variant(tmp_path):
    raw=execute_sql(*pet_sources(),require_same_pet=True)
    def extract(args,**kwargs):raw.to_parquet(tmp_path/args[args.index('--output-parquet')+1],index=False)
    with patch.object(analysis,'ROOT',tmp_path),patch.object(analysis.subprocess,'run',side_effect=extract) as run:
        result=CliRunner().invoke(analysis.main,['--same-pet','--print-sql'])
        assert result.exit_code==0 and 'a.original_pet_id=r.reorder_pet_id' in result.output
        run.assert_not_called()
        result=CliRunner().invoke(analysis.main,['--same-pet'])
        assert result.exit_code==0,result.output
        manifest=next((tmp_path/'data').rglob('source.json'))
        assert 'same-pet' in str(manifest)
        assert json.loads(manifest.read_text())['match_pet'] is True
        tables=list((tmp_path/'outputs/tables/2026-08-15_2026-10-14').glob('*.md'))
        assert len(tables)==6 and all('same-pet' in p.name for p in tables)
        run.reset_mock()
        result=CliRunner().invoke(analysis.main,['--same-pet','--cached'])
        assert result.exit_code==0,result.output
        run.assert_not_called()


def test_twenty_one_day_cumulative_window_exact_and_one_nanosecond_later():
    p,l,c=pet_sources()
    cancel=l.loc[l.order_id.eq(100),'order_cancel_dttm'].dropna().iloc[0]
    template=l.loc[l.order_id.eq(303)].iloc[[0]]
    l=pd.concat([l,template.assign(order_id=400,order_placed_dttm=cancel+pd.Timedelta(days=14),order_placed_dttm_est=None),
        template.assign(order_id=401,order_placed_dttm=cancel+pd.Timedelta(days=14,nanoseconds=1),order_placed_dttm_est=None),
        template.assign(order_id=500,order_placed_dttm=cancel+pd.Timedelta(days=21),order_placed_dttm_est=None),
        template.assign(order_id=501,order_placed_dttm=cancel+pd.Timedelta(days=21,nanoseconds=1),order_placed_dttm_est=None)])
    outputs=analysis.summarize(execute_sql(p,l,c,True,True),*DATES,True,True)
    matches=outputs['reorder-matches']
    assert set(matches.loc[matches.followup_days.eq(7),'reorder_order_id'])=={300,303}
    assert set(matches.loc[matches.followup_days.eq(14),'reorder_order_id'])=={300,303,304,400}
    assert set(matches.loc[matches.followup_days.eq(21),'reorder_order_id'])=={300,303,304,400,401,500}
    assert outputs['summary'].followup_days.tolist()==[7,14,21]


def test_twenty_one_day_maturity_cutoff_and_customer_deduplication():
    p,l,c=pet_sources()
    p=p.iloc[[0,1]].copy()
    p['rx_id']=['BOUNDARY','AFTER'];p['first_order_id']=[1000,1001];p['first_orderitem_id']=['0','1'];p['customer_id']=[17,18]
    template=l.iloc[[0]];lines=[]
    for i,cancel in enumerate([pd.Timestamp('2026-10-06'),pd.Timestamp('2026-10-06 00:00:00.000000001')]):
        original=template.assign(order_id=1000+i,order_line_id=i,customer_id=17+i,order_cancel_dttm=cancel,
            order_placed_dttm=cancel-pd.Timedelta(days=11),order_placed_dttm_est=cancel-pd.Timedelta(days=11,hours=4))
        reordered=original.assign(order_id=2000+i,order_line_id=i+10,order_cancel_reason=None,order_cancel_dttm=pd.NaT,
            order_order_line_status='P',order_placed_dttm=cancel+pd.Timedelta(days=21),
            order_placed_dttm_est=cancel+pd.Timedelta(days=21)-pd.Timedelta(hours=4))
        lines.extend([original,reordered])
    outputs=analysis.summarize(execute_sql(p,pd.concat(lines),c,True,True),*DATES,True,True)
    assert outputs['summary'].eligible_customers.tolist()==[2,2,1]
    assert outputs['summary'].reordered_customers.tolist()==[0,0,1]
    lines21=outputs['cancellation-details'].loc[outputs['cancellation-details'].followup_days.eq(21)].set_index('original_order_id')
    assert lines21.loc[1000,'eligibility']=='Eligible'
    assert lines21.loc[1001,'eligibility']=='Incomplete twenty-one-day follow-up'


def test_twenty_one_day_mode_cache_and_output_identity(tmp_path):
    raw=execute_sql(*pet_sources(),True,True)
    def extract(args,**kwargs):raw.to_parquet(tmp_path/args[args.index('--output-parquet')+1],index=False)
    with patch.object(analysis,'ROOT',tmp_path),patch.object(analysis.subprocess,'run',side_effect=extract) as run:
        result=CliRunner().invoke(analysis.main,['--same-pet','--include-21-days'])
        assert result.exit_code==0,result.output
        manifest=next((tmp_path/'data').rglob('source.json'));metadata=json.loads(manifest.read_text())
        assert '7d-14d-21d' in str(manifest)
        assert metadata['followup_days']==[7,14,21] and metadata['include_21_days'] is True
        run.reset_mock()
        result=CliRunner().invoke(analysis.main,['--same-pet','--include-21-days','--cached'])
        assert result.exit_code==0,result.output
        run.assert_not_called()
    with pytest.raises(ValueError,match='requires same-pet'):analysis.render_sql(*DATES,include_21_days=True)
