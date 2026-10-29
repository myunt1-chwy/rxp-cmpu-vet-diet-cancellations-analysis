import json

from click.testing import CliRunner
import pandas as pd
import pytest

from src.python import create_opportunity_contact_frequency_reorders as a
from test_opportunity_aged_customer_contacts import source as contact_source, CANCEL
from test_opportunity_aged_reorders import sources


def fixtures():
    contact=contact_source()
    # Customer 7 contacts on one relative day despite multiple legs and orders.
    contact.loc[contact.customer_id.eq(7) & contact.contact_at_utc.notna(),'contact_at_utc']=CANCEL
    raw,_=sources()
    raw['original_cancel_utc']=CANCEL
    raw['reorder_placed_utc']=CANCEL+pd.Timedelta(days=14)
    raw['reorder_shipped_utc']=CANCEL+pd.Timedelta(days=15)
    extra=raw.iloc[[0]].assign(original_order_id='3',original_line_id='33',original_customer_id='8',
        reorder_order_id='30',reorder_line_id='300',reorder_customer_id='8',reorder_order_has_cancellation=1)
    none=raw.iloc[[0]].assign(original_order_id='4',original_line_id='44',original_customer_id='9',reorder_order_id=None)
    combined=pd.concat([raw,extra,none],ignore_index=True)
    combined.reorder_placed_utc=combined.reorder_placed_utc.astype('datetime64[ns, UTC]')
    return contact,combined


def test_segment_denominators_returners_dedup_and_inclusive_fourteen_days():
    c,r=fixtures();frames,audit,_=a.analyze(c,r,'2026-05-01','2026-08-01','2026-10-28',14)
    s=frames['summary'].set_index('days_contacted')
    assert tuple(s.loc[1])==(1,1,100.0)
    assert tuple(s.loc[2])==(1,0,0.0)
    assert frames['customer_results'].set_index('customer_id').loc['7','reorder_orders']==1
    assert audit['contact_audit']['aged_customers']==3
    assert len(frames['reorder_associations'])==2  # one reorder, two original orders
    r.loc[r.original_customer_id.eq('8'),'reorder_order_has_cancellation']=0
    frames,_,_=a.analyze(c,r,'2026-05-01','2026-08-01','2026-10-28',14)
    assert frames['summary'].reordered_customers.tolist()==[1,1]


@pytest.mark.parametrize('flag',['reorder_order_has_cancellation','reorder_order_has_unknown_status'])
def test_cancelled_or_unknown_status_does_not_remove_segment_denominator(flag):
    c,r=fixtures();r.loc[r.original_customer_id.eq('7'),flag]=1
    frames,_,_=a.analyze(c,r,'2026-05-01','2026-08-01','2026-10-28',14)
    assert frames['summary'].segment_customers.tolist()==[1,1]
    assert frames['summary'].reordered_customers.tolist()==[0,0]


def test_missing_matching_keys_handled_mode_and_empty_segment():
    c,r=fixtures();r.loc[r.original_customer_id.eq('8'),'original_pet_id']=None
    r.loc[r.original_customer_id.eq('8'),'reorder_order_id']=None
    frames,_,_=a.analyze(c,r,'2026-05-01','2026-08-01','2026-10-28',14,handled_only=True)
    s=frames['summary'].set_index('days_contacted')
    assert s.loc[1,'segment_customers']==1 and s.loc[1,'reordered_customers']==1
    assert s.loc[2,'segment_customers']==0 and pd.isna(s.loc[2,'reordered_percentage'])
    frames,_,_=a.analyze(c,r,'2026-05-01','2026-08-01','2026-10-28',14)
    assert frames['summary'].set_index('days_contacted').loc[2,'segment_customers']==1


def test_cohort_mismatch_and_out_of_window_reorder_fail():
    c,r=fixtures()
    with pytest.raises(AssertionError,match='cohorts'):
        a.analyze(c,r.loc[r.original_order_id.ne('4')],'2026-05-01','2026-08-01','2026-10-28',14)
    for offset in [pd.Timedelta(0),pd.Timedelta(days=14,nanoseconds=1)]:
        changed=r.copy();changed.loc[changed.original_customer_id.eq('7'),'reorder_placed_utc']=CANCEL+offset
        with pytest.raises(ValueError,match='matching/window'):
            a.analyze(c,changed,'2026-05-01','2026-08-01','2026-10-28',14)


def test_fresh_cached_handled_sql_only_and_cache_hashes(tmp_path,monkeypatch):
    monkeypatch.setattr(a,'ROOT',tmp_path);calls=[]
    c,r=fixtures()
    def extract(query,parquet,directory):
        calls.append(query)
        (c if query.parent.name=='contacts' else r).to_parquet(parquet,index=False)
        return dict(engine='fixture')
    monkeypatch.setattr(a.base,'extract',extract);runner=CliRunner()
    printed=runner.invoke(a.main,['--print-sql']);assert printed.exit_code==0,printed.output
    assert 'DATEADD(day,-13' in printed.output and 'DATEADD(day,4' in printed.output
    assert 'DATEADD(day,14' in printed.output and 'product_part_number' in printed.output
    assert not list(tmp_path.iterdir())
    for args in [['--write-latex'],['--cached','--write-latex'],['--cached','--handled-only']]:
        result=runner.invoke(a.main,args);assert result.exit_code==0,str(result.exception)+result.output
    assert len(calls)==2
    child=tmp_path/'src/latex/appendix/contact_frequency_reorders.tex'
    text=child.read_text()
    assert r'\subsubsection{Reorders by contact-day frequency}' in text
    assert r'\label{tab:contact-frequency-same-pet-part-reorders}' in text
    assert r'\ref{tab:aged-customer-contact-day-frequency}' in text
    assert 'within 14 days' in text and 'May 1, 2026 through July 31, 2026' in text
    assert r'1 & 1 & 1 & 100.00\%' in text
    parent=child.with_name('contact_analysis.tex');include=r'\input{appendix/contact_frequency_reorders}'
    assert parent.read_text().count(include)==1
    child.with_name('contact_window_reorders.tex').write_text('Timing comparison table\n')
    with monkeypatch.context() as scoped:
        scoped.setattr(a.contacts,'ROOT',tmp_path)
        a.contacts.publish_latex('Updated contact tables\n')
    assert parent.read_text().count(include)==1 and 'Updated contact tables' in parent.read_text()
    assert parent.read_text().count(r'\input{appendix/contact_window_reorders}')==1

    directory=next((tmp_path/'data/opportunity/contact-frequency-reorders').iterdir())
    meta=json.loads((directory/'source.json').read_text());assert meta['identity']['followup_days']==14
    assert meta['identity']['contact_days']==[-13,3]
    s=pd.read_parquet(directory/'all-inbound/summary.parquet');assert s.reordered_customers.tolist()==[1,0]
    assert list((tmp_path/'outputs/tables/opportunity').rglob('contact-frequency-14d-same-pet-part-reorders.md'))
    result=runner.invoke(a.main,['--as-of-date','2026-08-02']);assert result.exit_code!=0
    meta['identity']['contact_days']=[-11,2];(directory/'source.json').write_text(json.dumps(meta))
    result=runner.invoke(a.main,['--cached']);assert result.exit_code!=0 and 'fingerprint differs' in result.output
    meta['identity']['contact_days']=[-13,3];(directory/'source.json').write_text(json.dumps(meta))
    (directory/'reorders.parquet').write_bytes(b'broken')
    result=runner.invoke(a.main,['--cached']);assert result.exit_code!=0 and 'fingerprint differs' in result.output
