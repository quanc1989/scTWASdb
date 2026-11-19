# -*- coding: utf-8 -*-
"""Read-only database details: bounded pages and complete, filtered TSV exports.

The legacy tables have no unique row key. Never deduplicate associations or use
the model's declared primary key as a row identifier. Order by all stored fields
so pagination preserves the multiset, including identical duplicate records.
"""
from __future__ import unicode_literals

import csv
import sqlite3
import sys
from collections import defaultdict

from django.db.models import Q
from django.conf import settings
from django.http import JsonResponse
from django.template import loader
from django.views.decorators.http import require_http_methods

from sctwas.models import Celltype, Eqtl, Gene, SNP, Study, Trait, Twas
from sctwas.tools.result_contract import probability, ResultError

TWAS_FIELDS = ('ensemblid', 'celltype', 'n_snps', 'fusion_z', 'fusion_pval',
               'spred_z', 'spred_pval', 'collectionid', 'phecode')
EQTL_FIELDS = ('genename', 'celltype', 'beta', 'se', 'pvalue', 'collectionid', 'rsid')


class SelectionError(ValueError):
    def __init__(self, message, status=400):
        super(SelectionError, self).__init__(message)
        self.status = status


def selection(params):
    key = params.get('key')
    if key not in ('0', '1', '2', '3', '4'):
        raise SelectionError('Choose an association from the Explore or Browse page.')
    try:
        threshold = probability(params.get('thres_twas'))
        eqtl_threshold = probability(params.get('thres'))
    except ResultError:
        raise SelectionError('Enter a valid nominal p threshold greater than zero and no larger than one.')
    trait = list(Trait.objects.filter(phecode=params.get('phecode', '')).values()[:1])
    if not trait:
        raise SelectionError('The requested trait is not present in this database.', 404)
    query = {name: params.get(name, '') for name in
             ('key', 'data', 'gene', 'phecode', 'celltype', 'icd10')}
    query.update(thres=eqtl_threshold, thres_twas=threshold)
    query['celltype'] = query['celltype'] or 'All Celltypes'
    query['icd10'] = query['icd10'] or 'All Traits'
    context = {'cache_query': query, 'data_trait': trait[0]}
    if not (trait[0].get('url') or '').startswith(('https://', 'http://')):
        context['data_trait']['url'] = ''
    if key in ('0', '4'):
        # An Ensembl search must not be replaced by the first displayed symbol.
        genes = Gene.objects.filter(ensemblid=query['data']) if key == '4' else Gene.objects.filter(genename=query['gene'] or query['data'])
        genes = list(genes.order_by('ensemblid').values()[:1])
        if not genes:
            raise SelectionError('The requested gene is not present in this database.', 404)
        context.update(data_gene=genes[0], detail_kind='gene')
    elif key == '2':
        variants = list(SNP.objects.filter(rsid=query['data']).values()[:1])
        if not variants:
            raise SelectionError('The requested variant is not present in this database.', 404)
        context.update(data_snp=variants[0], detail_kind='variant')
    else:
        context['detail_kind'] = 'trait'
    return context


def pair_filter(pairs, gene_field):
    """Grouped OR clauses retain gene/model pairing and use the existing index.

    A separate gene IN (...) AND cell IN (...) would create false matches.
    EXISTS was substantially slower on the production MySQL 5.7 query plan.
    """
    groups = defaultdict(set)
    for gene, cell in pairs:
        groups[gene].add(cell)
    terms = Q()
    for gene in sorted(groups):
        terms |= Q(**{gene_field: gene, 'celltype__in': sorted(groups[gene])})
    return terms if groups else Q(**{gene_field + '__in': []})


def associations(context):
    query = context['cache_query']
    twas = Twas.objects.filter(phecode=query['phecode']).filter(
        Q(fusion_pval__lte=query['thres_twas']) | Q(spred_pval__lte=query['thres_twas']))
    if query['celltype'] != 'All Celltypes':
        cells = list(Celltype.objects.filter(majortype=query['celltype']).values_list('celltypeid', flat=True))
        twas = twas.filter(celltype__in=cells)
    if query['key'] == '3':
        cells = list(Celltype.objects.filter(Q(celltypeid__icontains=query['data']) |
                    Q(subtype__icontains=query['data'])).values_list('celltypeid', flat=True))
        twas = twas.filter(celltype__in=cells)
    if context['detail_kind'] == 'gene':
        twas = twas.filter(ensemblid=context['data_gene']['ensemblid'])
    if context['detail_kind'] == 'variant':
        eqtl = Eqtl.objects.filter(rsid=context['data_snp']['rsid'], pvalue__lte=query['thres'])
        twas = twas.filter(pair_filter(eqtl.values_list('genename', 'celltype').distinct(), 'ensemblid'))
    return twas


def result_query(context, kind):
    twas = associations(context)
    if kind == 'twas':
        return twas, TWAS_FIELDS
    if kind == 'eqtl' and context['detail_kind'] == 'variant':
        pairs = twas.order_by().values_list('ensemblid', 'celltype').distinct()
        query = context['cache_query']
        return Eqtl.objects.filter(rsid=context['data_snp']['rsid'], pvalue__lte=query['thres']).filter(
            pair_filter(pairs, 'genename')), EQTL_FIELDS
    raise SelectionError('Choose TWAS results, or eQTL results for a variant.')


def filtered_query(queryset, fields, params):
    search = params.get('search[value]', '').strip()
    if len(search) > 100:
        raise SelectionError('Use at most 100 characters to filter the table.')
    if params.get('search[regex]', 'false') not in ('false', ''):
        raise SelectionError('Regular-expression filters are not supported.')
    if search:
        queryset = queryset.filter(Q(**{fields[0] + '__icontains': search}) |
                                   Q(celltype__icontains=search) | Q(collectionid__icontains=search))
    try:
        column = int(params.get('order[0][column]', '4'))
    except (ValueError, TypeError):
        raise SelectionError('Choose a valid table sort column.')
    direction = params.get('order[0][dir]', 'asc')
    if not 0 <= column < len(fields) or direction not in ('asc', 'desc'):
        raise SelectionError('Choose a valid table sort column and direction.')
    selected = fields[column]
    order = [('-' if direction == 'desc' else '') + selected]
    order.extend(field for field in fields if field != selected)
    return queryset.order_by(*order), bool(search)


def detail_page(request):
    from sctwas.views import _render_page
    from sctwas.task_views import page_error
    try:
        context = selection(request.GET)
    except SelectionError as error:
        return page_error(request, str(error), status=error.status)
    context['detail_query_string'] = request.GET.urlencode()
    name = {'gene': 'Gene', 'trait': 'Trait', 'variant': 'SNP'}[context['detail_kind']]
    return _render_page(loader.get_template('sctwas/top-nav.' + name + '.html'), context, request)


def table_data(request):
    try:
        # Validate the paging contract before touching a large table.
        try:
            draw = int(request.GET.get('draw', '0'))
            start = int(request.GET.get('start', '0'))
            length = int(request.GET.get('length', '25'))
        except (ValueError, TypeError):
            raise SelectionError('Use integer pagination parameters.')
        if not 0 <= draw <= 2147483647 or not 0 <= start <= 2147483647 or not 1 <= length <= 100:
            raise SelectionError('Request 1 to 100 rows per page, with a nonnegative offset.')
        context = selection(request.GET)
        queryset, fields = result_query(context, request.GET.get('kind', 'twas'))
        filtered, has_search = filtered_query(queryset, fields, request.GET)
        total = queryset.count()
        count = filtered.count() if has_search else total
        response = JsonResponse({'draw': draw, 'recordsTotal': total, 'recordsFiltered': count,
                                 'data': list(filtered.values(*fields)[start:start + length])})
    except SelectionError as error:
        response = JsonResponse({'error': str(error)}, status=error.status)
    response['Cache-Control'] = 'no-store'
    return response


def model_data(request):
    try:
        context = selection(request.GET)
        ids = list(associations(context).order_by().values_list('celltype', flat=True).distinct())
        cells = list(Celltype.objects.filter(celltypeid__in=ids).order_by('celltypeid').values())
        studies = defaultdict(list)
        for study in Study.objects.filter(studyid__in=[row['studyid'] for row in cells]).order_by('studyid', 'title', 'doi').values():
            studies[study['studyid']].append(study)
        for cell in cells:
            sources = studies[cell['studyid']]
            cell.update(sources[0] if sources else {'title': 'Source metadata unavailable', 'doi': '',
                        'journal': 'Not recorded', 'method': '', 'sample': '', 'samplesize': None})
            cell['source_records'] = len(sources)
        return JsonResponse({'data': cells})
    except SelectionError as error:
        return JsonResponse({'error': str(error)}, status=error.status)


class Echo:
    def write(self, value):
        return value


def tsv_rows(queryset, fields, chunk_size=2000):
    from sctwas.export_store import stream_values
    writer = csv.writer(Echo(), delimiter=str('\t'), lineterminator=str('\n'))

    def line(values):
        values = ['' if value is None else format(value, '.17g') if isinstance(value, float) else value for value in values]
        if sys.version_info[0] == 2:
            values = [value.encode('utf-8') if isinstance(value, type('')) else value for value in values]
        return writer.writerow(values)

    yield line(fields)
    for row in stream_values(queryset, fields, chunk_size):
        yield line(row)


def export_value(request):
    from sctwas import export_store
    context = selection(request.GET)
    kind = request.GET.get('kind', 'twas')
    queryset, fields = result_query(context, kind)
    queryset, unused = filtered_query(queryset, fields, request.GET)
    return export_store.prepare(queryset, fields, context['cache_query'], kind, request.GET, tsv_rows)


@require_http_methods(['GET', 'HEAD'])
def table_download(request):
    from sctwas import export_store
    try:
        if getattr(settings, 'SCTWAS_EXPORT_ASYNC', False):
            value = queued_export(request)
            return export_store.serve(request, value) if value['state'] == 'ready' else queue_response(request, value)
        return export_store.serve(request, export_value(request))
    except SelectionError as error:
        return JsonResponse({'error': str(error)}, status=error.status)
    except (export_store.ExportBusy, export_store.ExportUnavailable) as error:
        return export_store.busy_response(error)
    except sqlite3.OperationalError:
        return export_store.busy_response(export_store.ExportBusy('The export queue is temporarily busy. Retry shortly.'))


def queued_export(request):
    from sctwas import export_queue
    context = selection(request.GET)
    kind = request.GET.get('kind', 'twas')
    if kind == 'twas':
        fields, queryset = TWAS_FIELDS, Twas.objects.none()
    elif kind == 'eqtl' and context['detail_kind'] == 'variant':
        fields, queryset = EQTL_FIELDS, Eqtl.objects.none()
    else:
        raise SelectionError('Choose TWAS results, or eQTL results for a variant.')
    # Validate syntax without constructing expensive variant pair queries.
    filtered_query(queryset, fields, request.GET)
    return export_queue.enqueue(context, kind, request.GET)


def queue_response(request, value):
    base = request.path.rsplit('/', 1)[0]
    value = dict(value)
    if value['state'] == 'ready':
        value['download_url'] = base + '/association_file?artifact=' + value['artifact']
    if value.get('job'):
        value['status_url'] = base + '/association_export_status?job=' + value['job']
    status = 200 if value['state'] == 'ready' else 410 if value['state'] == 'expired' else 503 if value['state'] == 'failed' else 202
    response = JsonResponse(value, status=status)
    response['Cache-Control'] = 'no-store'
    if status != 200:
        response['Retry-After'] = str(value.get('retry_after', 2))
    return response


@require_http_methods(['GET'])
def export_status(request):
    from sctwas import export_queue, export_store
    try:
        value = export_queue.status(request.GET.get('job', ''))
    except sqlite3.OperationalError:
        return export_store.busy_response(export_store.ExportBusy('The export queue is temporarily busy. Retry shortly.'))
    if value is None:
        response = JsonResponse({'error': 'This export is unavailable. Prepare it again from the results page.'}, status=404)
        response['Cache-Control'] = 'no-store'
        return response
    return queue_response(request, value)


@require_http_methods(['GET'])
def prepare_export(request):
    from sctwas import export_store
    try:
        if getattr(settings, 'SCTWAS_EXPORT_ASYNC', False):
            return queue_response(request, queued_export(request))
        value = dict(export_value(request))
        value['download_url'] = request.path.rsplit('/', 1)[0] + '/association_file' + '?artifact=' + value['artifact']
        response = JsonResponse(value)
    except SelectionError as error:
        response = JsonResponse({'error': str(error)}, status=error.status)
    except (export_store.ExportBusy, export_store.ExportUnavailable) as error:
        response = export_store.busy_response(error)
    except sqlite3.OperationalError:
        response = export_store.busy_response(export_store.ExportBusy('The export queue is temporarily busy. Retry shortly.'))
    response['Cache-Control'] = 'no-store'
    return response


@require_http_methods(['GET', 'HEAD'])
def export_file(request):
    from sctwas import export_store
    value = export_store.manifest(request.GET.get('artifact', ''))
    if value is None:
        return JsonResponse({'error': 'This export has expired or is unavailable. Prepare it again from the results page.'}, status=404)
    if request.GET.get('metadata') == '1':
        response = JsonResponse(value)
        response['Cache-Control'] = 'no-store'
        return response
    return export_store.serve(request, value)
