"""Entity existence, uploaded-file flags, timing and exact customer matching."""
import json
from unittest.mock import patch

from click.testing import CliRunner
import pandas as pd
import pytest

from src.python import create_aged_order_reorder_uploads as analysis

ASOF='2026-10-27'


def fixtures():
    requests=pd.DataFrame(dict(rx_id=['A','B','C','D'],customer_id=[7,8,9,10],
        approval_channel=['CUSTOMER_UPLOAD','VERBAL','CUSTOMER_UPLOAD','FAX'],
        channel=['CUSTOMER_UPLOAD','VERBAL','CUSTOMER_UPLOAD','FAX']))
    pairs=pd.DataFrame(dict(reorder_rx_ids=['A','B','C','D'],original_customer_id=[7,8,9,10],
        shipped_by_as_of=[True,False,True,False],order_cancel_time=['2026-10-20']*4,
        prescription_comparison=['Different prescription']*4))
    rows=[]
    for rx,customer,upload,time,flag in [('A',7,'OLD','2020-01-01','true'),
        ('A',7,'ATEND','2026-10-27','true'),('B',8,None,None,None),
        ('C',9,'UNDATED',None,'true'),('D',10,'NOFILE','2026-10-21','false')]:
        rows.append(dict(rx_id=rx,customer_id=customer,rx_customer_id=customer,prescription_rows=1,
            rx_created_at_utc='2026-10-20',upload_id=upload,upload_customer_id=customer if upload else None,
            upload_source_rows=1 if upload else None,uploaded_file_flag=flag,uploaded_at_utc=time,
            invalid_related_upload_rows=0,invalid_related_customer_rows=0,other_customer_uploads=0))
    return pairs,requests,pd.DataFrame(rows)


def test_presence_file_flags_undated_cutoff_and_cancellation_timing():
    rx,details,source,summary,audit=analysis.summarize(*fixtures(),ASOF)
    assert rx.upload_state.tolist()==['Matching upload by as-of','No matching upload','Undated upload only','Matching upload by as-of']
    assert rx.has_recorded_file_upload.tolist()==[True,False,False,False]
    assert details.uploads_after_cancellation.tolist()==[1,0,0,1]
    assert details.uploads_before_or_at_cancellation.tolist()==[1,0,0,0]
    all_rows=summary.loc[summary.population.eq('All different reorder prescriptions') & summary.channel.eq('All channels')]
    assert all_rows['count'].tolist()==[2,1,1,1]
    assert all_rows.denominator.eq(4).all()
    assert source.upload_id.nunique()==4


@pytest.mark.parametrize('column,value',[
    ('rx_customer_id',999),('prescription_rows',2),('upload_customer_id',999),
    ('upload_source_rows',2),('invalid_related_upload_rows',1),('uploaded_at_utc','2026-10-27 00:00:00.000000001')])
def test_invalid_or_late_source_evidence_rejected(column,value):
    p,r,s=fixtures();s.loc[0,column]=value
    with pytest.raises(ValueError):analysis.summarize(p,r,s,ASOF)


def test_key_and_upload_duplicates_rejected_and_unknown_file_flag_retained():
    p,r,s=fixtures()
    with pytest.raises(ValueError,match='duplicate'):analysis.summarize(p,r,pd.concat([s,s.iloc[[0]]]),ASOF)
    with pytest.raises(ValueError,match='keys'):analysis.summarize(p,r,s.loc[s.rx_id.ne('B')],ASOF)
    s.loc[0,'uploaded_file_flag']='unknown'
    *_,audit=analysis.summarize(p,r,s,ASOF)
    assert audit.loc[audit.measure.eq('Matched upload associations with unknown file flag'),'count'].iloc[0]==1


def test_different_prescriptions_only_and_frozen_channel_join():
    p,r,_=fixtures()
    p=pd.concat([p,p.iloc[[0]].assign(prescription_comparison='Same prescription')])
    selected,requests=analysis.requests_for(p,r[['rx_id','approval_channel']])
    assert len(selected)==4 and len(requests)==4
    assert set(requests.channel)=={'CUSTOMER_UPLOAD','VERBAL','FAX'}
    with pytest.raises(ValueError,match='different customers'):
        analysis.requests_for(pd.concat([p,p.iloc[[0]].assign(original_customer_id=999)]),r)


def test_sql_no_lower_upload_bound_and_safe_pairs():
    _,r,_=fixtures();sql=analysis.render_sql(r,ASOF)
    assert "upload_type='DIET_PRESCRIPTION'" in sql
    assert "created_ts_utc <= '2026-10-27'" in sql and 'created_ts_utc IS NULL' in sql
    assert 'created_ts_utc >=' not in sql
    assert 'k.customer_id=e.upload_customer_id' in sql
    assert 'has_uploaded_file::VARCHAR' in sql
    with pytest.raises(ValueError):analysis.render_sql(r.iloc[:0],ASOF)


def execute_sql(requests,uploads):
    import duckdb
    sql=analysis.render_sql(requests,ASOF)
    sql=sql.replace('EDLDB.BT_HCA_HCDM.RXP_PRESCRIPTIONS','prescriptions_source').replace('EDLDB.BT_HCA_HCDM.RXP_UPLOAD_ENTITY','uploads_source')
    sql=sql.replace('TIMESTAMP_NTZ','TIMESTAMP_NS').replace('CURRENT_WAREHOUSE()',"'test'")
    values=json.dumps([[r.rx_id,int(r.customer_id)] for r in requests.itertuples()],separators=(',',':'))
    start=sql.index('    SELECT value[0]::VARCHAR')
    end=sql.index('\n), prescriptions AS')
    sql=sql[:start]+f'''    SELECT json_extract_string(value,'$[0]') AS rx_id,
         CAST(json_extract_string(value,'$[1]') AS DECIMAL(38,0)) AS customer_id
         FROM json_each('{values}')'''+sql[end:]
    sql=sql.replace("LATERAL FLATTEN(INPUT => SPLIT(TRIM(COALESCE(u.rx_ids,''),'{}'),','), OUTER => TRUE) t",
        "LATERAL UNNEST(string_split(TRIM(COALESCE(u.rx_ids,''),'{}'),',')) t(value)")
    registry=requests[['rx_id','customer_id']].assign(rx_creation_datetime=pd.Timestamp('2026-10-20'))
    with duckdb.connect() as con:
        con.register('prescriptions_source',registry);con.register('uploads_source',uploads)
        con.execute('CREATE MACRO REGEXP_LIKE(x,p) AS regexp_full_match(x,p)')
        con.execute('CREATE MACRO TRY_TO_NUMBER(x) AS TRY_CAST(x AS DECIMAL(38,0))')
        con.execute('CREATE MACRO IFF(x,a,b) AS CASE WHEN x THEN a ELSE b END')
        con.execute('CREATE MACRO TO_CHAR(x,f) AS CAST(x AS VARCHAR)')
        return con.execute(sql).df()


def test_sql_expansion_customer_type_time_boundaries_and_early_history():
    p,r,_=fixtures()
    uploads=pd.DataFrame([dict(upload_id=upload,customer_id=customer,rx_id=rx,created_ts_utc=pd.Timestamp(time) if time else pd.NaT,
        has_uploaded_file=flag,upload_type=kind) for upload,customer,rx,time,flag,kind in [
        ('OLD','007','{A,A}','2020-01-01',True,'DIET_PRESCRIPTION'),
        ('END','7','{A}','2026-10-27',True,'DIET_PRESCRIPTION'),
        ('AFTER','7','{A}','2026-10-27 00:00:00.000000001',True,'DIET_PRESCRIPTION'),
        ('WRONG','99','{A}','2026-10-21',True,'DIET_PRESCRIPTION'),
        ('WRONGTYPE','8','{B}','2026-10-21',True,'OTHER'),
        ('UNDATED','9','{C}',None,True,'DIET_PRESCRIPTION'),
        ('NOFILE','10','{D}','2026-10-21',False,'DIET_PRESCRIPTION')]])
    uploads['created_ts_utc']=pd.to_datetime(uploads.created_ts_utc).astype('datetime64[ns]')
    raw=execute_sql(r,uploads)
    rx,_,source,_,_=analysis.summarize(p,r,raw,ASOF)
    assert set(source.upload_id.dropna())=={'OLD','END','UNDATED','NOFILE'}
    assert rx.loc[rx.rx_id.eq('A'),'matching_uploads'].iloc[0]==2
    assert rx.loc[rx.rx_id.eq('A'),'other_customer_uploads'].iloc[0]==1
    assert rx.loc[rx.rx_id.eq('B'),'upload_state'].iloc[0]=='No matching upload'
    duplicate=pd.concat([uploads,uploads.iloc[[0]]])
    with pytest.raises(ValueError,match='duplicate related'):
        analysis.summarize(p,r,execute_sql(r,duplicate),ASOF)


def test_fresh_cached_dependency_dates_and_fingerprint_rejection(tmp_path):
    _,requests,raw=fixtures()
    deps={'baseline':'b','prescriptions':'r','channels':'c'}
    period='2026-08-15_2026-10-15_customer_upload_reorders-7d_as-of-2026-10-27'
    def extract(args,**kwargs):
        raw.assign(extraction_warehouse='test').to_parquet(tmp_path/args[args.index('--output-parquet')+1],index=False)
    with patch.object(analysis,'ROOT',tmp_path),patch.object(analysis.subprocess,'run',side_effect=extract) as run:
        frame,meta,manifest=analysis.load_source(requests,period,deps,ASOF,False)
        assert len(frame)==len(raw)
        run.assert_called_once();run.reset_mock()
        manifest.write_text(json.dumps(meta))
        cached,*_=analysis.load_source(requests,period,deps,ASOF,True)
        assert len(cached)==len(raw);run.assert_not_called()
        for key in ['sql','sql_sha256','dependencies','parquet_sha256']:
            manifest.write_text(json.dumps({**meta,key:'tampered'}))
            with pytest.raises(ValueError,match='fingerprint'):
                analysis.load_source(requests,period,deps,ASOF,True)
        manifest.write_text(json.dumps(meta))
        with pytest.raises(ValueError,match='fingerprint'):
            analysis.load_source(requests,period,deps,'2026-10-26',True)
        manifest.with_suffix('.parquet').write_bytes(b'bad')
        with pytest.raises(ValueError,match='fingerprint'):
            analysis.load_source(requests,period,deps,ASOF,True)
