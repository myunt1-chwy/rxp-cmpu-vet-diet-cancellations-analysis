"""Shared classification and unique-customer distributions for validated prior shipments."""
import pandas as pd

FLAGS = ['prior_inclusive_pharmacy','prior_vet_diet','prior_cmpu_vet_diet']


def summarize_history(customers, evidence):
    """Evidence has validated customer IDs and an eligibility classification from its caller."""
    h=evidence.copy()
    customers=customers.copy()
    merch=h.merch_class2.astype('string').str.strip().str.casefold()
    vet=h.is_vet_diet_flag.eq(True)
    h['category']='Other/unclassified'
    for label in ['Pharmacy','Compound','Over the Counter']:
        h.loc[merch.eq(label.casefold()).fillna(False),'category']=label
    h.loc[vet,'category']='Vet diet'
    eligible=h.eligibility.eq('Eligible')
    h[FLAGS[0]]=eligible & h.category.ne('Other/unclassified')
    h[FLAGS[1]]=eligible & vet
    h[FLAGS[2]]=eligible & vet & h.prescription_source.astype('string').str.strip().str.upper().eq('CMPU').fillna(False)
    flags=h.groupby('customer_id')[FLAGS].any()
    customers=customers.merge(flags,on='customer_id',how='left',validate='one_to_one')
    for col in FLAGS: customers[col]=customers[col].eq(True)
    if (customers[FLAGS[2]] & ~customers[FLAGS[1]]).any() or (customers[FLAGS[1]] & ~customers[FLAGS[0]]).any():
        raise ValueError('historical customer flags are not nested')
    customers['history_group']='No qualifying inclusive-pharmacy history'
    customers.loc[customers[FLAGS[0]],'history_group']='Inclusive pharmacy without vet diet'
    customers.loc[customers[FLAGS[1]],'history_group']='Vet diet without CMPU vet diet'
    customers.loc[customers[FLAGS[2]],'history_group']='CMPU vet diet'
    denominator=len(customers)
    summary=pd.DataFrame([dict(measure=label,customers=count,percent_of_customers=100*count/denominator if denominator else None)
        for label,count in [('Customers',denominator),
            ('Prior inclusive pharmacy shipment',int(customers[FLAGS[0]].sum())),
            ('Prior vet-diet shipment',int(customers[FLAGS[1]].sum())),
            ('Prior CMPU vet-diet shipment',int(customers[FLAGS[2]].sum()))]])
    exclusive=customers.groupby('history_group').size().reindex([
        'No qualifying inclusive-pharmacy history','Inclusive pharmacy without vet diet',
        'Vet diet without CMPU vet diet','CMPU vet diet'],fill_value=0).rename('customers').reset_index()
    exclusive['percent_of_customers']=100*exclusive.customers/denominator if denominator else None
    categories=[]
    for label in ['Pharmacy','Compound','Over the Counter','Vet diet','Other/unclassified']:
        sub=h.loc[eligible & h.category.eq(label)]
        categories.append(dict(category=label,customers=sub.customer_id.nunique(),orders=sub.order_id.nunique(),
            order_lines=len(sub[['order_id','order_line_id']].drop_duplicates()),prescriptions=sub.rx_id.nunique()))
    if exclusive.customers.sum()!=denominator or customers.customer_id.duplicated().any():
        raise ValueError('customer groups do not reconcile')
    return {'customers':customers,'shipment-evidence':h,'summary':summary,
            'exclusive-groups':exclusive,'categories':pd.DataFrame(categories)}
