"""Keep financial follow-up tables grouped by study, with frequency last."""
from src.python.markdown_tables import write_text

STUDIES=['same-part-pet','same-pet-different-part','any-vet-diet']
WHOLE_FILES={study:'financial_opportunity_follow_up_'+study.replace('-','_') for study in STUDIES}
UPLOAD_FILES={study:'financial_opportunity_new_upload_follow_up_'+study.replace('-','_') for study in STUDIES}
VET_FILES={study:'financial_opportunity_new_vet_diet_follow_up_'+study.replace('-','_') for study in STUDIES}
FREQUENCY='financial_opportunity_customer_order_frequency'
CHEWY='financial_opportunity_chewy_follow_up'
UPLOAD_CHEWY='financial_opportunity_new_upload_chewy_follow_up'
VET_CHEWY='financial_opportunity_new_vet_diet_chewy_follow_up'
LEGACY_VET='financial_opportunity_new_vet_diet_follow_up'
LEGACY_WHOLE='financial_opportunity_reorders'
LEGACY_UPLOAD='financial_opportunity_new_upload_follow_up'
KNOWN_FILES=list(WHOLE_FILES.values())+list(UPLOAD_FILES.values())+list(VET_FILES.values())+[VET_CHEWY,LEGACY_VET,FREQUENCY,CHEWY,UPLOAD_CHEWY,LEGACY_WHOLE,LEGACY_UPLOAD]


def follow_up_inputs(appendix):
    """Use per-study fragments; allow older aggregate-only outputs as fallback."""
    names=[]
    whole_fragments=any((appendix/(name+'.tex')).exists() for name in WHOLE_FILES.values())
    upload_fragments=any((appendix/(name+'.tex')).exists() for name in UPLOAD_FILES.values())
    vet_fragments=any((appendix/(name+'.tex')).exists() for name in VET_FILES.values())
    for index,study in enumerate(STUDIES):
        for available,fragments,legacy in [(WHOLE_FILES,whole_fragments,LEGACY_WHOLE),(UPLOAD_FILES,upload_fragments,LEGACY_UPLOAD),(VET_FILES,vet_fragments,LEGACY_VET)]:
            name=available[study] if fragments else (legacy if index==0 else None)
            if name and (appendix/(name+'.tex')).exists():names.append(name)
    for name in [CHEWY,UPLOAD_CHEWY,VET_CHEWY,FREQUENCY]:
        if (appendix/(name+'.tex')).exists():names.append(name)
    return '\n'.join('\\input{appendix/'+name+'}' for name in names)


def update_follow_up_inputs(parent):
    if not parent.exists():return
    text=parent.read_text()
    for name in KNOWN_FILES:text=text.replace('\\input{appendix/'+name+'}','')
    block=follow_up_inputs(parent.parent)
    text=text.rstrip()+'\n\n'+block+'\n'
    write_text(parent,text)
