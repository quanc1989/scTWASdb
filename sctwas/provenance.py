"""Read-only, versioned scientific metadata, separate from legacy associations."""
import hashlib
import json
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlencode

from django.http import HttpResponse
from django.template import loader

CATALOG=Path(__file__).parent/'data'/'provenance-20260919.json'
STATES={'22_archives':'22 autosomes',
        'partial_chromosomes':'Partial chromosome coverage',
        'identifier_review':'Different archive identifier',
        'incompatible_header':'A1/A2 allele columns',
        'unavailable':'Archive unavailable'}

SOURCE_PRESENTATIONS = {
    'Bonder_2021': {
        'assay': 'Bulk RNA-seq',
        'context': 'Cultured induced pluripotent stem cells.',
        'cohort': '948 donors overall. The cis-eQTL analysis used 936 samples from 682 donors.',
    },
    'Cuomo_2020': {
        'assay': 'scRNA-seq',
        'context': 'iPSC differentiation into mesendoderm and definitive endoderm.',
        'cohort': 'iPSC lines from 125 donors.',
    },
    'Neavin_2021': {
        'assay': 'scRNA-seq',
        'context': 'Cultured dermal fibroblasts and reprogrammed iPSCs.',
        'cohort': '79 fibroblast donors, with iPSC lines from 31 of those donors.',
    },
    'Natri_2023': {
        'assay': 'scRNA-seq',
        'context': 'The models cite the 2023 source record.',
        'cohort': 'Related 2024 cohort · 114 individuals, including 66 with pulmonary fibrosis and 48 unaffected individuals.',
        'catalogue_sample_label': '2023 source record sample size',
    },
}


@lru_cache(maxsize=1)
def catalog():
    raw=CATALOG.read_bytes();value=json.loads(raw)
    if value['schema_version']!=1:raise ValueError('Unsupported provenance catalog')
    return raw,value,hashlib.sha256(raw).hexdigest()


def download(request):
    raw,value,digest=catalog()
    response=HttpResponse(raw,content_type='application/json; charset=utf-8')
    response['Content-Disposition']='attachment; filename="sctwas-'+value['catalog_version']+'.json"'
    response['ETag']='"'+digest+'"'
    response['X-Content-SHA256']=digest
    response['Cache-Control']='public, max-age=3600'
    return response


def page(request):
    from sctwas.views import _render_page
    _,value,digest=catalog()
    model_id=request.GET.get('model','')
    context={'page_title':'Reference models · scTWASdb','catalog_version':value['catalog_version'],
             'association_version':value['association_data_version'],
             'summary':value['summary'],'catalog_sha256':digest}
    if model_id:
        model=next((x for x in value['models'] if x['id']==model_id),None)
        if model is None:
            from sctwas.task_views import page_error
            return page_error(request,'The reference model identifier was not found.',status=404)
        study_id=model['study_id']
        source=value['studies'][study_id]
        publication=source['review'] or {}
        context.update(model=model,source_records=source['registry_records'],
                       source_presentation=SOURCE_PRESENTATIONS.get(study_id, {}),
                       source_reference=publication.get('reference'),
                       source_accessions=publication.get('accessions',[]),
                       page_title=model['registered_model']+' · scTWASdb',
                       weight_label=STATES[model['weight_audit']['state']])
    else:
        q=request.GET.get('q','').strip()[:200]
        study=request.GET.get('study','')
        assay=request.GET.get('assay','')
        status=request.GET.get('status','')
        try:page_number=max(1,int(request.GET.get('page','1')))
        except ValueError:page_number=1
        models=value['models']
        if q:
            needle=q.casefold()
            models=[x for x in models if needle in ' '.join(str(x[k]) for k in ('id','registered_model','major_type','subtype','condition','study_id','context')).casefold()]
        if study:models=[x for x in models if x['study_id']==study]
        if assay:models=[x for x in models if x['assay']==assay]
        if status:models=[x for x in models if x['weight_audit']['state']==status]
        pages=max(1,(len(models)+19)//20);page_number=min(page_number,pages)
        selection=[]
        for model in models[(page_number-1)*20:page_number*20]:
            # Copy only the display row; never mutate the cached catalog.
            row=dict(model);row['weight_label']=STATES[row['weight_audit']['state']];selection.append(row)
        def link(number):
            return 'provenance?'+urlencode({'q':q,'study':study,'assay':assay,'status':status,'page':number})
        context.update(models=selection,matched=len(models),query=q,selected_study=study,selected_assay=assay,
            selected_status=status,studies=sorted(value['studies']),assays=sorted(value['summary']['assay_models']),
            states=sorted(STATES.items()),page_number=page_number,page_count=pages,
            previous_url=link(page_number-1) if page_number>1 else '',next_url=link(page_number+1) if page_number<pages else '')
    return _render_page(loader.get_template('sctwas/provenance.html'),context,request)
