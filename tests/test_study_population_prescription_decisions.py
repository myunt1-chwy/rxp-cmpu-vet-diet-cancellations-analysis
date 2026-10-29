import pandas as pd
import pytest

from scripts.summarize_study_population_prescription_decisions import summarize


def fixture():
    return pd.DataFrame([dict(rx_id=f'R{i}',customer_id=7,approval_channel='CUSTOMER_UPLOAD',
        first_order_id=100+i,first_orderitem_id=str(i),first_order_line_id=i,
        rx_creation_datetime='2026-08-15',approved_numerator=approved,
        approved_denominator=True,rx_status=status,rx_lifecycle_state=status,state_change_reason=None,
        rx_first_approved_datetime='2026-08-16' if approved else None,rx_first_denied_datetime=None,
        order_id=100+i,order_line_id=i,shipment_rows=2,prescription_approved=approved,
        approval_flag_variants=1,cancel_reason='aged order',reason_variants=1,cancel_variants=1,
        cancel_time='2026-10-27',line_last_denied_datetime=None)
        for i,(approved,status) in enumerate([(True,'APPROVED'),(False,'SYSTEM_CLOSED'),
            (False,'DENIED'),(None,'VET_REVIEW'),(True,'DENIED')])])


def test_false_or_null_approval_is_unknown_without_explicit_denial():
    f=fixture()
    f.loc[3,'rx_first_denied_datetime']='2026-08-20'  # Historical denial is not current DENIED status.
    details,summary=summarize(f)
    assert details.decision.tolist()==['Approved','Unknown','Rejected','Unknown','Approved']
    assert summary.iloc[0][['approved','unknown','rejected']].tolist()==[2,2,1]
    assert summary[['approved','unknown','rejected']].sum(axis=1).eq(summary.prescriptions).all()


def test_same_populations_and_nanosecond_inclusive_aged_cutoff():
    f=fixture()
    f.loc[0,'approval_channel']='VET'
    f.loc[1,'cancel_time']='2026-10-27 00:00:00.000000001'
    f.loc[2,'cancel_time']='2026-10-26 23:59:59.999999999'
    f.loc[3,'cancel_reason']='Other reason'
    details,summary=summarize(f)
    assert summary.prescriptions.tolist()==[5,4,2]
    assert set(details.loc[details.aged_subset,'rx_id'])=={'R2','R4'}
    assert summary.iloc[2][['approved','unknown','rejected']].tolist()==[1,0,1]


def test_identical_rx_duplicates_collapse_and_conflicts_fail():
    f=fixture()
    duplicated=pd.concat([f,f.iloc[[0]]])
    assert len(summarize(duplicated)[0])==5
    conflict=pd.concat([f,f.iloc[[0]].assign(rx_status='OTHER')])
    with pytest.raises(ValueError,match='conflicting prescription'):
        summarize(conflict)


@pytest.mark.parametrize('column,value,message',[
    ('approval_flag_variants',2,'conflicting shipment'),
    ('cancel_variants',2,'conflicting shipment'),
    ('order_id',999,'both first-order keys'),
    ('order_line_id',999,'both first-order keys'),
    ('rx_creation_datetime','2026-10-15','study window'),
    ('prescription_approved',False,'approval flags disagree')])
def test_inconsistent_source_evidence_rejected(column,value,message):
    f=fixture()
    f.loc[0,column]=value
    with pytest.raises(ValueError,match=message):
        summarize(f)


def test_all_unknown_and_empty_populations_have_explicit_zero_categories():
    f=fixture().iloc[[1]].copy()
    _,summary=summarize(f)
    assert summary.unknown.eq(1).all() and summary.approved.eq(0).all() and summary.rejected.eq(0).all()
    _,empty=summarize(f.iloc[:0])
    assert empty.prescriptions.eq(0).all() and len(empty)==3
