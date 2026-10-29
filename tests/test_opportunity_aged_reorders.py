from decimal import Decimal
import pandas as pd
import pytest
from src.python import create_opportunity_aged_reorders as a


def sources():
    common=dict(original_customer_id='7',original_pet_id='8',original_product_part_number='P-01',
        original_reason='aged order',customer_variants=1,pet_variants=1,part_variants=1,cancel_variants=1,reason_variants=1,
        reorder_order_id='10',reorder_line_id='100',reorder_customer_id='7',reorder_pet_id='8',
        reorder_product_part_number='P-01',reorder_placed_utc='2026-06-03',reorder_shipped_utc='2026-06-04',
        reorder_known_net_sales='10.00001',missing_sales_records=0,source_variants=1,
        reorder_order_has_cancellation=0,reorder_order_has_unknown_status=0)
    raw=pd.DataFrame([dict(common,original_order_id='1',original_line_id='11',original_cancel_utc='2026-06-01'),
        dict(common,original_order_id='2',original_line_id='22',original_cancel_utc='2026-06-02')])
    frozen=raw[a.KEYS+['original_customer_id','original_cancel_utc']].rename(columns={
        'original_customer_id':'customer_id','original_cancel_utc':'cancelled_at_utc'})
    frozen['cancelled_at_utc']=pd.to_datetime(frozen.cancelled_at_utc,utc=True)
    return raw,frozen


def test_multi_original_matches_count_reorder_and_sales_once():
    raw,frozen=sources();results,sales=a.analyze(raw,frozen,7,'2026-10-28')
    summary=results['summary'].set_index('measure')['count']
    assert summary['aged_orders']==summary['aged_orders_with_non_cancelled_reorder']==2
    assert summary['matched_non_cancelled_orders']==summary['matched_non_cancelled_lines']==1
    assert summary['customers_with_non_cancelled_reorder']==1
    assert Decimal(sales['matching_line_net_sales'])==Decimal('10.00001')


@pytest.mark.parametrize('field,value',[
    ('reorder_customer_id','9'),('reorder_pet_id','9'),('reorder_product_part_number','P-02'),
    ('reorder_order_id','1'),('reorder_placed_utc','2026-06-01'),('reorder_placed_utc','2026-06-10'),
])
def test_exact_keys_distinct_order_and_window_required(field,value):
    raw,frozen=sources();raw[field]=value
    with pytest.raises(ValueError,match='matching/window'):a.analyze(raw,frozen,7,'2026-10-28')


def test_seven_day_upper_boundary_inclusive():
    raw,frozen=sources();raw=raw.iloc[[0]].copy();frozen=frozen.iloc[[0]]
    raw['reorder_placed_utc']='2026-06-08'
    results,_=a.analyze(raw,frozen,7,'2026-10-28')
    assert len(results['reorders'])==1


@pytest.mark.parametrize('flag',['reorder_order_has_cancellation','reorder_order_has_unknown_status'])
def test_cancelled_or_unknown_order_excluded(flag):
    raw,frozen=sources();raw[flag]=1
    results,sales=a.analyze(raw,frozen,7,'2026-10-28')
    assert len(results['reorders'])==0 and Decimal(sales['matching_line_net_sales'])==0


def test_missing_pet_not_matched_and_missing_sales_incomplete():
    raw,frozen=sources();raw['missing_sales_records']=1
    _,sales=a.analyze(raw,frozen,7,'2026-10-28');assert sales['matching_line_net_sales'] is None
    raw['original_pet_id']=None;raw['reorder_order_id']=None
    results,_=a.analyze(raw,frozen,7,'2026-10-28')
    assert results['summary'].set_index('measure').loc['aged_lines_missing_match_keys','count']==2


def test_source_conflicts_and_frozen_drift_rejected():
    raw,frozen=sources();raw.loc[0,'pet_variants']=2
    with pytest.raises(ValueError,match='conflicting original'):a.analyze(raw,frozen,7,'2026-10-28')
    raw,frozen=sources();frozen.loc[0,'customer_id']='9'
    with pytest.raises(ValueError,match='frozen customer'):a.analyze(raw,frozen,7,'2026-10-28')


def sql_sources():
    rx=pd.DataFrame([dict(rx_id='R1',customer_id=7,is_vet_diet_flag=True,
                         approval_channel='CUSTOMER_UPLOAD',prescription_source='CMPU')])
    common=dict(customer_id=7,pet_id=8,product_part_number='P-01',rx_id='R1',is_vet_diet_flag=True,
                order_line_shipped_dttm=pd.NaT,order_line_net_sales='10.00001')
    original=dict(common,order_id=1,order_line_id=11,shipment_key=None,
                  order_placed_dttm=pd.Timestamp('2026-05-01'),order_cancel_dttm=pd.Timestamp('2026-06-01'),
                  order_order_line_status='X',order_cancel_reason='Aged Order')
    rows=[original]
    for i,days in enumerate([7,14,21,28,35,42,49,56,63],start=1):
        rows.append(dict(common,order_id=10*i,order_line_id=100*i,shipment_key=1000*i,
                         order_placed_dttm=pd.Timestamp('2026-06-01')+pd.Timedelta(days=days),
                         order_cancel_dttm=pd.NaT,order_order_line_status='D',order_cancel_reason=None))
    return rx,pd.DataFrame(rows)


def execute_sql(rx,lines,dates=("2026-06-01","2026-09-01"),all_studies=False,source_days=63):
    import re
    import duckdb
    lines=lines.copy()
    lines['order_line_net_sales']=lines.order_line_net_sales.map(Decimal)
    sql=a.render_sql(dates[0],dates[1],'2026-10-28',source_days,all_studies=all_studies)
    sql=sql.replace('EDLDB.BT_HCA_HCDM.ORDER_LINE_COST_MEASURES_RXP','line_source')
    sql=sql.replace('EDLDB.BT_HCA_HCDM.RXP_PRESCRIPTIONS','rx_source').replace('TIMESTAMP_NTZ','TIMESTAMP_NS')
    sql=re.sub(r'DATEADD\(day,(\d+),([^\)]+)\)',lambda m:"("+m[2]+"+INTERVAL '"+m[1]+" days')",sql)
    with duckdb.connect() as c:
        c.register('rx_source',rx);c.register('line_source',lines)
        c.execute('CREATE MACRO IFF(x,a,b) AS CASE WHEN x THEN a ELSE b END')
        c.execute('CREATE MACRO TO_CHAR(x,f) AS CAST(x AS VARCHAR)')
        return c.execute(sql).df()


def frozen_from_raw(raw):
    f=raw[a.KEYS+['original_customer_id','original_cancel_utc']].drop_duplicates().rename(
        columns={'original_customer_id':'customer_id','original_cancel_utc':'cancelled_at_utc'})
    for col in a.KEYS+['customer_id']:f[col]=f[col].map(a.base.identifier)
    f['cancelled_at_utc']=pd.to_datetime(f.cancelled_at_utc,utc=True)
    return f


def test_date_driven_sql_and_all_window_boundaries_and_split_sales():
    rx,lines=sql_sources()
    # Exact source duplicates collapse; separate shipments with equal sales add.
    lines=pd.concat([lines,lines.iloc[[1]],lines.iloc[[1]].assign(shipment_key=1001)])
    raw=execute_sql(rx,lines);frozen=frozen_from_raw(raw)
    for n,days in enumerate([7,14,21,28,35,42,49,56,63],start=1):
        result,sales=a.analyze(raw,frozen,days,'2026-10-28',source_days=63)
        measures=result['summary'].set_index('measure')['count']
        assert measures['matched_non_cancelled_orders']==n
        assert measures['customers_with_non_cancelled_reorder']==1
        assert Decimal(sales['matching_line_net_sales'])==Decimal('10.00001')*(n+1)
    sql=a.render_sql('2026-06-01','2026-09-01','2026-10-28',63)
    assert 'PARSE_JSON' not in sql and 'keys_json' not in sql
    assert 'product_id' not in sql.lower()


def test_sql_cancellation_dates_and_registry_eligibility():
    rx,lines=sql_sources()
    extra=pd.concat([lines.iloc[[0]].assign(order_id=2,order_line_id=22,order_cancel_dttm=pd.Timestamp('2026-09-01')),
                     lines.iloc[[0]].assign(order_id=3,order_line_id=33,rx_id='OTHER'),
                     lines.iloc[[0]].assign(order_id=4,order_line_id=44,customer_id=9)])
    rx=pd.concat([rx,rx.assign(rx_id='OTHER',approval_channel='VET')])
    raw=execute_sql(rx,pd.concat([lines,extra]))
    assert set(raw.original_order_id)=={1}


def test_sql_excludes_order_when_other_product_line_cancelled():
    rx,lines=sql_sources()
    other=lines.iloc[[1]].assign(order_line_id=999,product_part_number='OTHER',
        order_order_line_status='X',order_cancel_reason='Customer request',order_cancel_dttm=pd.Timestamp('2026-06-10'))
    raw=execute_sql(rx,pd.concat([lines,other]))
    result,_=a.analyze(raw,frozen_from_raw(raw),7,'2026-10-28',source_days=63)
    assert len(result['reorders'])==0


def test_all_windows_fresh_cached_sql_only_and_latex(tmp_path,monkeypatch):
    from click.testing import CliRunner
    raw=execute_sql(*sql_sources())
    real_root=a.ROOT
    # The template is real; all other files are isolated.
    (tmp_path/'src/sql').mkdir(parents=True)
    (tmp_path/'src/sql/opportunity_aged_reorders.sql').write_text((real_root/'src/sql/opportunity_aged_reorders.sql').read_text())
    (tmp_path/'src/latex/appendix').mkdir(parents=True)
    parent=tmp_path/'src/latex/appendix/financial_opportunity.tex';parent.write_text('Financial opportunity\n')
    monkeypatch.setattr(a,'ROOT',tmp_path)
    calls=[]
    def extraction(query,parquet,directory):
        calls.append(query);raw.to_parquet(parquet,index=False);return dict(engine='fixture')
    monkeypatch.setattr(a.base,'extract',extraction)
    args=['--all-windows','--write-latex']
    first=CliRunner().invoke(a.main,args);assert first.exit_code==0,first.output
    cached=CliRunner().invoke(a.main,args+['--cached']);assert cached.exit_code==0,cached.output
    assert len(calls)==1
    assert parent.read_text().count(r'\input{appendix/financial_opportunity_follow_up_same_part_pet}')==1
    assert 'SQL for Table' not in parent.read_text()
    latex=(parent.parent/'financial_opportunity_reorders.tex').read_text()
    assert r'\label{tab:financial-opportunity-reorder-windows}' in latex
    assert 'May 1, 2026 through July 31, 2026' in latex
    assert '56 &' in latex and '63 &' in latex and '70 &' in latex
    summary=pd.read_parquet(next((tmp_path/'data').rglob('summary.parquet')))
    assert summary.followup_days.tolist()==[7,14,21,28,35,42,49,56,63,70]
    assert r'PRODUCT\_PART\_NUMBER' in latex
    printed=CliRunner().invoke(a.main,['--all-windows','--print-sql'])
    assert printed.exit_code==0 and 'PARSE_JSON' not in printed.output
    assert len(calls)==1
    source=next((tmp_path/'data').rglob('source.parquet'));source.write_bytes(b'invalid')
    invalid=CliRunner().invoke(a.main,args+['--cached'])
    assert invalid.exit_code!=0 and 'fingerprint' in invalid.output


def test_verification_preserves_precision_for_large_late_decimal_value():
    raw,frozen=sources()
    large=raw.iloc[[0]].assign(reorder_order_id='20',reorder_line_id='200',reorder_known_net_sales='2944.52000')
    raw=pd.concat([raw.iloc[[0]]]*1000+[raw.iloc[[1]],large],ignore_index=True)
    results,sales=a.analyze(raw,frozen,7,'2026-10-28')
    assert len(results['reorders'])==2
    assert Decimal(sales['matching_line_net_sales'])==Decimal('2954.52001')


def test_may_july_cancellation_cohort_boundaries_and_63_day_limit():
    rx,lines=sql_sources()
    originals=[]
    for i,t in enumerate(pd.to_datetime(['2026-04-30 23:59:59.999999999','2026-05-01',
            '2026-07-31 23:59:59.999999999','2026-08-01'],format='mixed'),start=1):
        originals.append(lines.iloc[[0]].assign(order_id=i,order_line_id=i,
            order_placed_dttm=pd.Timestamp('2026-04-01'),order_cancel_dttm=t))
    raw=execute_sql(rx,pd.concat(originals+[lines.iloc[1:]]),dates=('2026-05-01','2026-08-01'))
    assert set(raw.original_order_id)=={2,3}
    # The standard June-1 fixture has a reorder exactly at day 63; a later
    # nanosecond must not enter the requested maximum window.
    extra=lines.iloc[[-1]].assign(order_id=999,order_line_id=999,
        order_placed_dttm=pd.Timestamp('2026-06-01')+pd.Timedelta(days=63,nanoseconds=1))
    raw=execute_sql(rx,pd.concat([lines,extra]))
    assert 999 not in set(raw.reorder_order_id.dropna())
    result,_=a.analyze(raw,frozen_from_raw(raw),63,'2026-10-28',source_days=63)
    assert len(result['reorders'])==9


def test_56_day_window_excludes_later_orders_from_shared_63_day_source():
    rx,lines=sql_sources()
    extra=lines.iloc[[-1]].assign(order_id=999,order_line_id=999,
        order_placed_dttm=pd.Timestamp('2026-06-01')+pd.Timedelta(days=56,nanoseconds=1))
    raw=execute_sql(rx,pd.concat([lines,extra]))
    result,_=a.analyze(raw,frozen_from_raw(raw),56,'2026-10-28',source_days=63)
    assert len(result['reorders'])==8
    assert '999' not in set(result['reorders'].reorder_order_id)


def broad_sources():
    rx,lines=sql_sources()
    template=lines.iloc[[1]].assign(order_placed_dttm=pd.Timestamp('2026-06-03'))
    rows=[lines]
    def line(order,part,pet=8,vet=True,amount='20.00000',status='D'):
        return template.assign(order_id=order,order_line_id=order*10,shipment_key=order*100,
            product_part_number=part,pet_id=pet,is_vet_diet_flag=vet,order_line_net_sales=amount,order_order_line_status=status)
    rows += [line(201,'Q-02'),line(202,'R-03',vet=False),line(203,'P-01',pet=9),
             line(204,'Q-02',pet=9),line(205,None,pet=None),line(206,'Q-02'),line(207,'Q-02',status=None)]
    # A cancellation elsewhere on the order excludes its otherwise matching line.
    rows += [line(206,'OTHER',vet=False,status='X').assign(order_line_id=2061,order_cancel_reason='Customer request',order_cancel_dttm=pd.Timestamp('2026-06-04'))]
    # An order can contain lines in both exact and different-product studies.
    rows += [line(210,'Q-02'),line(210,'P-01',amount='10.00001').assign(order_line_id=2101,shipment_key=21001)]
    # Preserve the historical exact-match rule while vet-diet studies require TRUE.
    rows += [line(211,'P-01',vet=False),line(212,'Q-02').assign(customer_id=9)]
    # Split shipment and exact duplicate cannot multiply order counts.
    rows += [line(201,'Q-02').assign(shipment_key=20101),line(201,'Q-02')]
    # A second aged association must not multiply reorder sales.
    rows += [lines.iloc[[0]].assign(order_id=2,order_line_id=22,order_cancel_dttm=pd.Timestamp('2026-06-02'))]
    return rx,pd.concat(rows,ignore_index=True)


def test_broad_sql_and_study_specific_matching_and_deduplication():
    raw=execute_sql(*broad_sources(),all_studies=True);frozen=frozen_from_raw(raw)
    results={}
    for study in a.STUDIES:
        results[study],_=a.analyze(raw,frozen,7,'2026-10-28',source_days=63,study=study,broad_source=True)
    exact=results['same-part-pet']['reorders'];different=results['same-pet-different-part']['reorders'];anyvet=results['any-vet-diet']['reorders']
    assert set(different.reorder_order_id)=={'201','210'}
    assert set(exact.reorder_order_id)=={'10','210','211'}
    assert set(anyvet.reorder_order_id)=={'10','201','203','204','205','210'}
    assert not {'202','212'} & set(raw.reorder_order_id.dropna().astype(int).astype(str))
    assert '206' not in set(anyvet.reorder_order_id) and '207' not in set(anyvet.reorder_order_id)
    assert sum(different.reorder_known_net_sales)==Decimal('60.00000')
    assert different.original_customer_id.nunique()==1
    assert set(zip(different.reorder_order_id,different.reorder_line_id))<=set(zip(anyvet.reorder_order_id,anyvet.reorder_line_id))
    for study,result in results.items():
        summary=pd.DataFrame([dict(followup_days=7,customers=1,cohort_customers=1,cohort_percentage=100.0,orders=len(result['reorders']),actual_net_sales=Decimal('1'))])
        latex=a.window_table(summary,a.base.parameters('2026-05-01','2026-08-01'),'2026-10-28',study)
        assert 'studies overlap' in latex
        if study=='same-pet-different-part':assert 'different from the original' in latex
        if study=='any-vet-diet':assert 'any pet and any product part number' in latex


def test_any_vet_diet_does_not_require_original_pet_or_part():
    rx,lines=sql_sources()
    lines.loc[lines.order_id.eq(1),'pet_id']=None
    lines.loc[lines.order_id.eq(1),'product_part_number']=None
    raw=execute_sql(rx,lines,all_studies=True);frozen=frozen_from_raw(raw)
    anyvet,_=a.analyze(raw,frozen,7,'2026-10-28',source_days=63,study='any-vet-diet',broad_source=True)
    different,_=a.analyze(raw,frozen,7,'2026-10-28',source_days=63,study='same-pet-different-part',broad_source=True)
    assert len(anyvet['reorders'])==1 and len(different['reorders'])==0
    assert anyvet['originals'].usable_match_keys.all()
    assert not different['originals'].usable_match_keys.any()


def test_three_studies_one_extract_cached_and_latex(tmp_path,monkeypatch):
    from click.testing import CliRunner
    raw=execute_sql(*broad_sources(),all_studies=True)
    # A zero-return customer with no pet/part must remain in every denominator.
    raw=pd.concat([raw,raw.iloc[[0]].assign(original_order_id=3,original_line_id=33,original_customer_id=8,
        original_pet_id=None,original_product_part_number=None,reorder_order_id=None)],ignore_index=True)
    (tmp_path/'src/sql').mkdir(parents=True)
    (tmp_path/'src/sql/opportunity_aged_reorders.sql').write_text((a.ROOT/'src/sql/opportunity_aged_reorders.sql').read_text())
    (tmp_path/'src/latex/appendix').mkdir(parents=True)
    parent=tmp_path/'src/latex/appendix/financial_opportunity.tex'
    parent.write_text('Financial opportunity\n')
    monkeypatch.setattr(a,'ROOT',tmp_path);calls=[]
    def extraction(query,parquet,directory):
        calls.append(query);raw.to_parquet(parquet,index=False);return dict(engine='fixture')
    monkeypatch.setattr(a.base,'extract',extraction)
    args=['--all-windows','--all-studies','--write-latex']
    fresh=CliRunner().invoke(a.main,args);assert fresh.exit_code==0,fresh.output
    cached=CliRunner().invoke(a.main,args+['--cached']);assert cached.exit_code==0,cached.output
    assert len(calls)==1
    summary=pd.read_parquet(next((tmp_path/'data').rglob('summary.parquet')))
    assert len(summary)==30 and set(summary.study)==set(a.STUDIES)
    assert summary.cohort_customers.eq(2).all()
    assert summary.cohort_percentage.eq(50).all()
    assert summary.customers.eq(1).all()
    assert r'Cohort (\%)' in (parent.parent/'financial_opportunity_reorders.tex').read_text()
    latex=(parent.parent/'financial_opportunity_reorders.tex').read_text()
    assert latex.count(r'\begin{table}')==4
    assert r'\label{tab:financial-opportunity-customer-order-frequency}' in latex
    frequency=pd.read_parquet(next((tmp_path/'data').rglob('same-part-pet-customer-order-frequency.parquet')))
    assert frequency.groupby('followup_days').customers.sum().tolist()==summary.loc[summary.study.eq('same-part-pet'),'customers'].tolist()
    for label in ['tab:financial-opportunity-reorder-windows','tab:financial-opportunity-reorder-same-pet-different-part','tab:financial-opportunity-reorder-any-vet-diet']:
        assert latex.count(r'\label{'+label+'}')==1
    assert 'SQL for Table' not in parent.read_text()
    printed=CliRunner().invoke(a.main,args+['--print-sql'])
    assert printed.exit_code==0 and len(calls)==1 and 'PARSE_JSON' not in printed.output


def test_70_day_boundary_for_all_rxp_studies():
    rx,lines=sql_sources()
    extra=lines.iloc[[1]].assign(order_id=701,order_line_id=7010,shipment_key=70100,
        order_placed_dttm=pd.Timestamp('2026-06-01')+pd.Timedelta(days=70))
    extra=pd.concat([extra,extra.assign(order_id=702,order_line_id=7020,shipment_key=70200,
        order_placed_dttm=pd.Timestamp('2026-06-01')+pd.Timedelta(days=70,nanoseconds=1))])
    extra=pd.concat([extra,extra.iloc[[0]].assign(order_id=703,order_line_id=7030,shipment_key=70300,product_part_number='DIFFERENT')])
    raw=execute_sql(rx,pd.concat([lines,extra]),dates=('2026-05-01','2026-08-01'),all_studies=True,source_days=70)
    for study in a.STUDIES:
        result,_=a.analyze(raw,frozen_from_raw(raw),70,'2026-10-28',source_days=70,study=study,broad_source=True)
        orders=set(result['reorders'].reorder_order_id)
        assert '702' not in orders
        assert ('703' if study=='same-pet-different-part' else '701') in orders
        assert result['originals'].complete_followup.all()


def test_customer_order_frequency_denominator_and_duplicate_associations(tmp_path):
    # Repeat lines/original associations do not add orders; multiple matching
    # part/pet pairs are pooled at the existing study's customer grain.
    lines=pd.DataFrame({'reorder_customer_id':['A','A','A','B','C','C','C'],
                        'reorder_order_id':['1','1','1','2','3','4','5']})
    counts=a.customer_order_frequency(lines,7,3,5)
    later=a.customer_order_frequency(pd.concat([lines,pd.DataFrame({'reorder_customer_id':['A','D'],
        'reorder_order_id':['6','7']})]),14,4,7)
    assert counts.set_index('reorder_customer_id').orders.to_dict()=={'A':1,'B':1,'C':3}
    summary=pd.DataFrame({'followup_days':[7,14],'customers':[3,4]})
    latex=a.frequency_exports(pd.concat([counts,later]),summary,tmp_path,tmp_path,
        {'start_date':'2026-05-01','end_date':'2026-08-01'},'2026-10-28')
    frequency=pd.read_parquet(tmp_path/'same-part-pet-customer-order-frequency.parquet')
    seven=frequency.loc[frequency.followup_days.eq(7)].set_index('orders')
    assert seven.loc[1,'customers']==2 and seven.loc[2,'customers']==0 and seven.loc[3,'customers']==1
    assert seven.loc[1,'percentage']==pytest.approx(50)
    assert frequency.groupby('followup_days').percentage.sum().tolist()==pytest.approx([75,100])
    assert frequency.denominator_customers.eq(4).all()
    assert frequency.denominator_followup_days.eq(14).all()
    assert '50.00' in latex and 'May 1, 2026 through July 31, 2026' in latex
    with pytest.raises(ValueError,match='reconcile'):
        a.customer_order_frequency(lines,7,4,5)
    with pytest.raises(ValueError,match='reconcile'):
        a.customer_order_frequency(lines,7,3,6)


def test_customer_order_frequency_empty_window(tmp_path):
    empty=pd.DataFrame({'reorder_customer_id':pd.Series(dtype='str'),'reorder_order_id':pd.Series(dtype='str')})
    counts=a.customer_order_frequency(empty,7,0,0)
    latex=a.frequency_exports(counts,pd.DataFrame({'followup_days':[7],'customers':[0]}),tmp_path,tmp_path,
        {'start_date':'2026-05-01','end_date':'2026-08-01'},'2026-10-28')
    assert 'N/A' in latex
    frequency=pd.read_parquet(tmp_path/'same-part-pet-customer-order-frequency.parquet')
    assert frequency.percentage.isna().all() and frequency.customers.sum()==0
