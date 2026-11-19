# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from django.template import loader, Context
from django.shortcuts import render
from django.http import JsonResponse, HttpResponseNotFound, HttpResponse, FileResponse
from django.views.decorators.csrf import csrf_protect
from django.conf import settings
from django.core import serializers
from django.core.serializers.json import DjangoJSONEncoder
from django.core.files.storage import FileSystemStorage
from django.utils import timezone
from django.forms.models import model_to_dict
from django.db.models import Max, Count, Q

import os
import uuid
import requests
import json
import logging
import hashlib

from sctwas.task_views import detail_twas, page_error
from sctwas.provenance import SOURCE_PRESENTATIONS
from sctwas.tools.result_contract import probability, chromosome, ResultError, safe_child, TRAINING_OUTPUTS
try:
    from urllib.parse import quote as urlquote, urlencode
except ImportError:  # Python 2 compatibility until the production cutover.
    from django.utils.http import urlquote, urlencode

from sctwas.models import Task, Trait, SNP, Gene, Celltype, Twas, Eqtl, Study
from sctwas.tools.datautils import QueryGroupDataFromDB, QueryGroupDataFromTrain
from sctwas.tools.mailutils import sendEmail, sendEmailWithHtml
from sctwas.tools.task_storage import upload_root, task_root

from sctwas.dao.TraitDao import getTraitsByGeneName, getTraitsByEnsembleID, getTraitsByDescription, getTraitsBySNP, \
    getTraitsByCelltype

CONST_SELECT_GENE = "0"
CONST_SELECT_TRAIT = "1"
CONST_SELECT_SNP = "2"
CONST_SELECT_CELLTYPE = "3"
CONST_SELECT_ENSEMBLEID = "4"
CONST_SELECT_SCTWAS = "5"
CONST_SELECT_GREX = "6"

# Create your views here.

logger = logging.getLogger(__name__)


def _submission_error(upload):
    if upload.size <= 0 or upload.size > getattr(settings, 'SCTWAS_MAX_UPLOAD_BYTES', 100 * 1024 * 1024):
        return JsonResponse({'result': 'error', 'error': 'Choose a non-empty file no larger than 100 MiB.'}, status=413)
    if getattr(settings, 'SCTWAS_EXECUTOR', 'thread') == 'spool':
        from sctwas.tools.spool import available
        if not available(task_root()):
            return JsonResponse({'result': 'error', 'error': 'The compute worker is temporarily unavailable. Please retry shortly.'}, status=503)
    return None


def health(request):
    from django.db import connections
    from sctwas.tools.spool import available
    try:
        with connections[Task.objects.db].cursor() as cursor:
            cursor.execute('SELECT 1')
            database_ready = cursor.fetchone()[0] == 1
    except Exception:
        database_ready = False
    compute_ready = available(task_root()) if getattr(settings, 'SCTWAS_EXECUTOR', 'thread') == 'spool' else True
    response = JsonResponse({'release': getattr(settings, 'SCTWAS_RELEASE', 'development'),
                             'database_ready': database_ready, 'compute_ready': compute_ready},
                            status=200 if database_ready and compute_ready else 503)
    response['Cache-Control'] = 'no-store'
    return response


def _render_page(template, context, request, template_only=None):
    context['legacy_duplicate_advisory'] = getattr(settings, 'SCTWAS_DATA_VERSION', 'legacy-db-20260917') == 'legacy-db-20260917'
    trait = context.get('data_trait')
    context['trait_duplicate_advisory'] = context['legacy_duplicate_advisory'] and isinstance(trait, dict) and trait.get('phecode') == '296.22'
    titles = {'top-nav.html': 'Overview', 'top-nav.Browse.html': 'Data catalogue',
              'twas.html': 'TWAS analysis', 'grex.html': 'Expression-weight construction',
              'top-nav.Gene.html': 'Gene associations', 'top-nav.Trait.html': 'Trait associations',
              'top-nav.SNP.html': 'Variant associations'}
    template_name = template.origin.template_name.rsplit('/', 1)[-1]
    if context.get('detail_kind') or template_name == 'top-nav.Browse.html':
        context['study_presentations'] = SOURCE_PRESENTATIONS
    context['light_assets'] = template_name in ('top-nav.html', 'twas.html', 'grex.html', 'documentation.html', 'downloads.html', 'provenance.html')
    context['select_assets'] = template_name in ('top-nav.query.html', 'twas.html', 'grex.html')
    context['table_export_assets'] = template_name in ('top-nav.Browse.html', 'top-nav.Gene.html', 'top-nav.Trait.html', 'top-nav.SNP.html')
    context['document_export_assets'] = False
    context['chart_assets'] = False
    if not context.get('page_title'):
        context['page_title'] = titles.get(template.origin.template_name.rsplit('/', 1)[-1], 'Research resource') + ' · scTWASdb'
    # Serialize data once; never convert Python repr to JSON in the browser.
    context['page_payload'] = json.dumps(context, cls=DjangoJSONEncoder, ensure_ascii=True)
    if template_only:
        context.update(template_only)
    context['preview_mode'] = getattr(settings, 'SCTWAS_UI_PREVIEW', False)
    return HttpResponse(template.render(context, request))


def example_download(request):
    examples = {'twas': 'UKB.411.8.chr22.two-genes.txt.gz',
                'grex': 'D11_Stegle_2021_FPP.iPSCs.chr22.one-gene.tsv'}
    name = examples.get(request.GET.get('kind'))
    if not name:
        return JsonResponse({'error': 'Choose the twas or grex example.'}, status=400)
    path = os.path.join(os.path.dirname(__file__), 'static', 'sctwas', 'examples', name)
    response = FileResponse(open(path, 'rb'), content_type='application/gzip' if name.endswith('.gz') else 'text/tab-separated-values')
    # A gzip file is an archive, not HTTP content encoding. Browsers must save its bytes intact.
    response['Content-Disposition'] = 'attachment; filename="{0}"'.format(name)
    return response


def catalog_download(request):
    kind = request.GET.get('kind')
    catalogs = {'models': (Celltype, 'celltypeid'), 'traits': (Trait, 'phecode'),
                'studies': (Study, 'studyid')}
    if kind not in catalogs:
        return JsonResponse({'error': 'Choose models, traits or studies.'}, status=400)
    model, key = catalogs[kind]
    rows = list(model.objects.order_by(key).values())
    response = JsonResponse({'kind': kind, 'scope': 'database registry metadata; not validated result coverage',
                             'generated_at': timezone.now().isoformat(),
                             'preview': getattr(settings, 'SCTWAS_UI_PREVIEW', False),
                             'count': len(rows), 'records': rows})
    response['Content-Disposition'] = 'attachment; filename="sctwas-{0}-registry.json"'.format(kind)
    return response


def documentation(request):
    return _render_page(loader.get_template('sctwas/documentation.html'),
                        {'page_title': 'Documentation · scTWASdb'}, request)


def downloads(request):
    return _render_page(loader.get_template('sctwas/downloads.html'),
                        {'page_title': 'Downloads · scTWASdb'}, request)


def index(request):
    """

    :param request:
    :return:
    """
    template = loader.get_template('sctwas/top-nav.html')
    context = {
        'registry': {'models': Celltype.objects.count(), 'traits': Trait.objects.count(), 'studies': Study.objects.count()},
    }
    return _render_page(template, context, request)


def query(request):
    """

    :param request:
    :return:
    """
    template = loader.get_template('sctwas/top-nav.query.html')
    context = {
        'page_title': 'Explore associations · scTWASdb',
        'query_catalog': json.dumps({
            'celltypes': list(Celltype.objects.order_by('majortype').values_list('majortype', flat=True).distinct()),
            'categories': list(Trait.objects.order_by('icd10').values_list('icd10', flat=True).distinct()),
            'study_presentations': SOURCE_PRESENTATIONS,
        }, ensure_ascii=True),
    }
    return _render_page(template, context, request)


def detail(request):
    if request.GET.get('key') == CONST_SELECT_SCTWAS:
        return detail_twas(request)
    from sctwas.association_views import detail_page
    return detail_page(request)


def browse(request):
    """

    :param request:
    :return:
    """

    data_study = Study.objects.all()
    list_data_study = list(data_study.values())

    data_trait = Trait.objects.all()
    list_data_trait = list(data_trait.values())

    data_celltype = Celltype.objects.all()
    list_data_celltype = list(data_celltype.values())

    for obj_celltype in list_data_celltype:
        obj_celltype['evidence_id'] = 'SCM-' + hashlib.sha256((obj_celltype['collectionid']+'\t'+obj_celltype['celltypeid']).encode('utf8')).hexdigest()[:16]
        obj_study = data_study.filter(studyid=obj_celltype["studyid"])
        obj_celltype.update(next(iter(obj_study.values()), {'title': 'Source metadata unavailable', 'doi': '', 'journal': 'Not recorded', 'method': '', 'sample': '', 'samplesize': None, 'modelsize': None}))

    template = loader.get_template('sctwas/top-nav.Browse.html')
    context = {
        "data_trait": list_data_trait,
        "data_study": list_data_study,
        "data_celltype": list_data_celltype,
    }

    # The raw page shows one page of records while the full catalogue enhances.
    # These HTML-only values are kept out of the table data and export fields.
    def publication(record):
        doi = record.get('doi') or ''
        return doi if doi.startswith(('https://', 'http://')) else ''

    fallback_models = [dict(row, publication_url=publication(row)) for row in list_data_celltype[:10]]
    fallback_traits = []
    for row in list_data_trait[:10]:
        association = urlencode(dict(key='1', phecode=row['phecode'], data=row['description'],
                                     celltype='All Celltypes', icd10='All Traits', thres='1e-5', thres_twas='1e-5'))
        count = row['n']
        fallback_traits.append(dict(row, association_url='detail?' + association,
                                    display_n=format(int(count), ',') if count and count.isdecimal() else count))
    fallback_studies = [dict(row, publication_url=publication(row), display_assay=SOURCE_PRESENTATIONS.get(
        row['studyid'], {}).get('assay', row['method'])) for row in list_data_study[:10]]
    return _render_page(template, context, request, dict(fallback_models=fallback_models,
                        fallback_traits=fallback_traits, fallback_studies=fallback_studies))


def twas(request):
    """

    :param request:
    :return:
    """

    data_celltype = Celltype.objects.all()
    list_data_celltype = list(data_celltype.values())

    template = loader.get_template('sctwas/twas.html')
    context = {
        'data_celltype': list_data_celltype,
    }
    return _render_page(template, context, request)


def grex(request):
    """

    :param request:
    :return:
    """

    data_celltype = Celltype.objects.all()
    list_data_celltype = list(data_celltype.values())

    template = loader.get_template('sctwas/grex.html')
    context = {
        'data_celltype': list_data_celltype,
    }
    return _render_page(template, context, request)


def test(request):
    """

    :param request:
    :return:
    """
    template = loader.get_template('sctwas/top-nav.html')
    context = {
        'registry': {'models': Celltype.objects.count(), 'traits': Trait.objects.count(), 'studies': Study.objects.count()},
    }
    return _render_page(template, context, request)


@csrf_protect
def celltypes(request):
    """

    :param request:
    :return:
    """

    phecode = request.POST.get('phecode')
    genename = request.POST.get('gene')
    ensemblid = request.POST.get('ensemblid')

    try:
        twasThres = probability(request.POST.get('thres_twas'))
    except ResultError as error:
        return JsonResponse({'error': str(error)}, status=400)

    data_twas = Twas.objects.filter(ensemblid=ensemblid, phecode=phecode).filter(
        Q(fusion_pval__lte=twasThres) | Q(spred_pval__lte=twasThres)).order_by("spred_pval")
    list_data_twas = list(data_twas.values())

    return JsonResponse({"data": list_data_twas,
                         "code": 200})


@csrf_protect
def getTraitData(request):
    """

    :param request:
    :return:
    """

    celltypeID = request.POST.get('celltype')
    icd10ID = request.POST.get('icd10')
    searchKey = request.POST.get('key')
    eQTLthres = request.POST.get('thres')
    queryData = request.POST.get('data')
    twasThres = request.POST.get('thres_twas')

    try:
        twasThres = probability(twasThres)
        eQTLthres = probability(eQTLthres)
    except ResultError as error:
        return JsonResponse({'error': str(error)}, status=400)
    if searchKey not in ('0', '1', '2', '3', '4') or not queryData or len(queryData) > 200:
        return JsonResponse({'error': 'A valid query type and search value are required.'}, status=400)

    logger.info('trait query from celltype: %s; ICD10: %s; Data: %s; Key: %s' %
                (celltypeID, icd10ID, searchKey, queryData))

    print('celltype: %s; ICD10: %s; Data: %s; Key: "%s"; eQTLthre: %s; twasThres: %s' % (
        celltypeID, icd10ID, queryData, searchKey, eQTLthres, twasThres))

    if searchKey == CONST_SELECT_GENE:

        print('celltype: %s; ICD10: %s; Data: %s; Key: "GeneName"' % (celltypeID, icd10ID, queryData))
        objects_traits = getTraitsByGeneName(celltypeID, icd10ID, twasThres, queryData)

    elif searchKey == CONST_SELECT_ENSEMBLEID:
        print('celltype: %s; ICD10: %s; Data: %s; Key: "EnsembleID"' % (celltypeID, icd10ID, queryData))
        objects_traits = getTraitsByEnsembleID(celltypeID, icd10ID, twasThres, queryData)

    elif searchKey == CONST_SELECT_TRAIT:
        print('celltype: %s; ICD10: %s; Data: %s; Key: "Trait"' % (celltypeID, icd10ID, queryData))
        objects_traits = getTraitsByDescription(celltypeID, icd10ID, twasThres, queryData)

    elif searchKey == CONST_SELECT_SNP:
        print('celltype: %s; ICD10: %s; Data: %s; Key: "SNP"; eqtlThres: %s' % (
            celltypeID, icd10ID, queryData, eQTLthres))
        objects_traits = getTraitsBySNP(celltypeID, icd10ID, eQTLthres, twasThres, queryData)

    elif searchKey == CONST_SELECT_CELLTYPE:
        print('celltype: %s; ICD10: %s; Data: %s; Key: "Celltype"' % (celltypeID, icd10ID, queryData))
        # objects_traits = list(Trait.objects.all().values())
        objects_traits = getTraitsByCelltype(celltypeID, icd10ID, twasThres, queryData)
    else:
        print('celltype: %s; ICD10: %s; Data: %s; Key: "Nothing Matched"' % (celltypeID, icd10ID, queryData))
        objects_traits = list(Trait.objects.all().values())

    return JsonResponse({"data": json.dumps(objects_traits),
                         "code": 200})


@csrf_protect
def upload_twas(request):
    """
    start a mission
    :param request:
    :return:
    """
    str_content = None

    if request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest':

        if request.method == 'POST' and request.FILES.getlist('file'):

            myfile = request.FILES['file']
            error = _submission_error(myfile)
            if error is not None:
                return error
            fs = FileSystemStorage(location=upload_root(), file_permissions_mode=0o600, directory_permissions_mode=0o700)

            emailto = request.POST.get('email')
            name_task = request.POST.get('jobid')
            task_chrom = request.POST.get('chrom')
            task_celltype = request.POST.get('celltype')
            task_thres = request.POST.get('thres')
            task_collection = request.POST.get('majortype')
            task_eqtl_window = request.POST.get('window')
            task_eqtl_weight = request.POST.get('weight')
            task_reference = request.POST.get('reference')
            task_population = request.POST.get('population')
            task_ztest = request.POST.get('ztest')

            try:
                chromosome(task_chrom)
                task_thres = format(probability(task_thres), '.17g')
                task_eqtl_weight = format(probability(task_eqtl_weight, allow_zero=True), '.17g')
                if not task_eqtl_window or not task_eqtl_window.isdigit() or not 1 <= int(task_eqtl_window) <= 10000000:
                    raise ResultError('Invalid cis window.')
                if task_reference != 'hg38' or task_population not in ('EUR', 'EAS') or task_ztest not in ('FUSION', 'SPrediXcan', 'both'):
                    raise ResultError('Unsupported reference, population or test statistic.')
                if not Celltype.objects.filter(celltypeid=task_celltype, collectionid=task_collection).exists():
                    raise ResultError('Unknown model and collection.')
            except ResultError as error:
                return JsonResponse({'result': 'error', 'error': str(error)}, status=400)

            tag_download = uuid.uuid4().hex

            time_start = str(timezone.now().strftime('%Y-%m-%d %H:%M:%S'))
            info = ('<p> You create a new Task for scTWAS' + '</p>\n')
            info += ('\n<p>Task ID:&nbsp;&nbsp;&nbsp;' + str(name_task if name_task else tag_download) + '</p>\n')
            info += ('\n<p>Start Time:&nbsp;&nbsp;&nbsp;' + time_start + '</p>\n')
            info += ('\n<p>Trained eQTL weights:&nbsp;&nbsp;&nbsp;' + task_celltype + '</p>\n')
            info += ('\n<p>Window size (bp) to include SNPs:&nbsp;&nbsp;&nbsp;' + task_eqtl_window + '</p>\n')
            info += ('\n<p>eQTL Weight threshold:&nbsp;&nbsp;&nbsp;' + task_eqtl_weight + '</p>\n')
            info += ('\n<p>Human reference:&nbsp;&nbsp;&nbsp;' + task_reference + '</p>\n')
            info += ('\n<p>Human Population for LD reference:&nbsp;&nbsp;&nbsp;' + task_population + '</p>\n')
            info += ('\n<p>Burden Z test statistic:&nbsp;&nbsp;&nbsp;' + task_ztest + '</p>\n')
            info += ('\n<p>scTWAS Pvalue thresholds:&nbsp;&nbsp;&nbsp;' + task_thres + '</p>\n')
            info += (
                        '\n<p>Result Page:&nbsp;&nbsp;&nbsp;<a href="' + "https://sctwas.omic.tech/detail?celltype=" + task_celltype +
                        "&key=" + CONST_SELECT_SCTWAS + "&thres=" + task_eqtl_weight + "&thres_twas=" + task_thres +
                        "&data=" + tag_download + "&chrom=" + task_chrom + "&reference=" + task_reference +
                        "&population=" + task_population +
                        "&window=" + task_eqtl_window + "&ztest=" + task_ztest + '">Go to the result page</a></p>\n')

            filename = fs.save(tag_download + '.txt.gz', myfile)

            # with open(settings.STATIC_ROOT + '/sctwas/source/upload/' + filename, 'r') as file:
            #    str_content = file.read().strip()


            Task(field_id=tag_download,
                 progress=0,
                 mail=emailto,
                 name=name_task,
                 create_timestamp=timezone.now(),
                 last_edit_timestamp=timezone.now()).save()

            # qld = QueryGroupData(array_snplist=array_snplist,
            #                      array_genelist=array_genelist,
            #                      tissue=tissue,
            #                      tag=tag_download,
            #                      emailto=emailto)
            qld = QueryGroupDataFromDB(tag=tag_download,
                                       emailto=emailto,
                                       name_task=name_task,
                                       chrom=task_chrom,
                                       celltype=task_celltype,
                                       collection=task_collection,
                                       thres=task_thres,
                                       window=task_eqtl_window,
                                       weight=task_eqtl_weight,
                                       reference=task_reference,
                                       population=task_population,
                                       ztest=task_ztest)
            if not qld.start_recorded():
                return JsonResponse({'result': 'error', 'tag': tag_download, 'error': 'Task could not be started.'}, status=503)
            if emailto:
                try:
                    sendEmailWithHtml(mailto=emailto, info=info)
                except Exception:
                    logger.exception('scTWAS submission notification failed')

            return JsonResponse({'result': 'ok', 'tag': tag_download})
        else:
            return JsonResponse({'result': 'error'})
    else:
        return JsonResponse({'result': 'error'})


@csrf_protect
def upload_grex(request):
    """
    start a mission
    :param request:
    :return:
    """
    str_content = None

    if request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest':

        if request.method == 'POST' and request.FILES.getlist('file'):

            myfile = request.FILES['file']
            error = _submission_error(myfile)
            if error is not None:
                return error
            fs = FileSystemStorage(location=upload_root(), file_permissions_mode=0o600, directory_permissions_mode=0o700)

            emailto = request.POST.get('email')
            name_task = request.POST.get('jobid')
            task_chrom = request.POST.get('chrom')
            task_reference = request.POST.get('reference')
            task_population = request.POST.get('population')
            task_train = request.POST.get('train')
            try:
                chromosome(task_chrom)
                if task_reference != 'hg38' or task_population != 'EUR' or task_train not in TRAINING_OUTPUTS:
                    raise ResultError('Unsupported training reference, population or method.')
            except ResultError as error:
                return JsonResponse({'result': 'error', 'error': str(error)}, status=400)
            tag_download = uuid.uuid4().hex

            time_start = str(timezone.now().strftime('%Y-%m-%d %H:%M:%S'))
            info = ('You create a new Task for training GReX imputation models' + '\n')
            info += ('\nTask ID:  ' + str(name_task if name_task else tag_download) + '\n')
            info += ('\nStart Time:   ' + time_start + '\n')
            info += ('\nHuman reference:   ' + task_reference + '\n')
            info += ('\nHuman Population for LD reference:   ' + task_population + '\n')
            info += ('\nTraining method :   ' + task_train + '\n')

            filename = fs.save(tag_download + '.tsv', myfile)


            Task(field_id=tag_download,
                 progress=0,
                 mail=emailto,
                 name=name_task,
                 create_timestamp=timezone.now(),
                 last_edit_timestamp=timezone.now()).save()

            qld = QueryGroupDataFromTrain(tag=tag_download,
                                          emailto=emailto,
                                          name_task=name_task,
                                          chrom=task_chrom,
                                          reference=task_reference,
                                          population=task_population,
                                          train=task_train)
            if not qld.start_recorded():
                return JsonResponse({'result': 'error', 'tag': tag_download, 'error': 'Task could not be started.'}, status=503)
            if emailto:
                try:
                    sendEmail(mailto=emailto, info=info)
                except Exception:
                    logger.exception('scTWAS submission notification failed')

            return JsonResponse({'result': 'ok', 'tag': tag_download})
        else:
            return JsonResponse({'result': 'error'})
    else:
        return JsonResponse({'result': 'error'})


@csrf_protect
def download(request):
    """
    download the results
    :param request:
    :return:
    """
    try:
        path = safe_child(os.path.join(settings.STATIC_ROOT, 'sctwas', 'source'), request.GET.get('url'))
    except ResultError:
        return JsonResponse({'error': 'Invalid download path.'}, status=400)
    if not os.path.isfile(path):
        return HttpResponseNotFound('The requested file is not available.')
    response = FileResponse(open(path, 'rb'), content_type='application/octet-stream')
    response['Content-Disposition'] = "attachment; filename*=UTF-8''" + urlquote(os.path.basename(path))
    return response
