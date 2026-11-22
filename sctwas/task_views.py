# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import json
import os

from django.conf import settings
from django.http import HttpResponse, JsonResponse, FileResponse
from django.template import loader
from django.utils.http import urlencode

from sctwas.models import Task, Celltype, Study
from sctwas.provenance import SOURCE_PRESENTATIONS
from sctwas.tools.task_storage import result_directory
from sctwas.tools.result_contract import (
    ResultError, TWAS_COLUMNS, chromosome, inspect_twas, load_status,
    probability, safe_child, sha256, task_id, assess_training,
)

DISPLAY_STATES = {
    'running': ('Analysis in progress', 'Refresh this page to check progress.'),
    'queued': ('Queued', 'The task is awaiting execution.'),
    'success': ('Completed', 'Results are available below.'),
    'no_hits': ('No associations at this threshold', 'No associations meet the selected nominal P threshold.'),
    'failed': ('Analysis failed', 'The task did not produce a complete result.'),
    'partial': ('Analysis incomplete', 'The output contains incomplete or invalid records.'),
    'empty_result': ('No usable results', 'The output contains no usable result records.'),
    'invalid_result': ('Result unavailable', 'An output file failed a format or integrity check.'),
    'legacy_unverified': ('Completion status unavailable', 'The task has no recorded completion status.'),
}

def display_state(state):
    title, description = DISPLAY_STATES.get(state, ('Status unavailable', ''))
    return {'status_title': title, 'status_description': description}


def page_error(request, message, status=400):
    context = {'page_title': 'Result unavailable · scTWASdb', 'status_code': status,
               'message': message, 'light_assets': True, 'preview_mode': getattr(settings, 'SCTWAS_UI_PREVIEW', False)}
    return HttpResponse(loader.get_template('sctwas/error.html').render(context, request), status=status)


def task_result(request):
    tag = task_id(request.GET.get('data') or request.GET.get('task'))
    chrom = chromosome(request.GET.get('chrom'))
    threshold = probability(request.GET.get('thres_twas'))
    tasks = list(Task.objects.filter(field_id=tag).values('progress'))
    if not tasks:
        raise ResultError('Task was not found.')
    directory = result_directory(tag, existing=True)
    state = load_status(directory)
    values = {'tag': tag, 'chrom': chrom, 'threshold': threshold, 'rows': [], 'all_rows': [],
              'valid_rows': 0, 'selected_rows': 0, 'state': 'running', 'parameters': {}}
    if state:
        values['parameters'] = state.get('parameters', {})
        if state.get('kind') != 'twas' or values['parameters'].get('chrom') != chrom:
            raise ResultError('Task parameters do not match this result.')
        values['state'] = state['state']
    else:
        progress = tasks[0]['progress']
        values['state'] = 'legacy_unverified' if progress == 100 else ('failed' if progress < 0 else 'running')
    if values['state'] not in ('success', 'no_hits', 'legacy_unverified'):
        return values
    relative = 'TWAS_{0}/{0}_sumstat_TWAS_assoc.txt'.format(chrom.upper())
    try:
        path = safe_child(directory, relative)
        if state:
            expected = {item['path']: item['sha256'] for item in state.get('artifacts', [])}
            if expected.get(relative) != sha256(path) or state.get('returncode') != 0:
                raise ResultError('unverified_artifact')
        # Parse the verified artifact once. The figure and all-results export
        # retain valid nonhits; the existing table keeps its literal P filter.
        summary = inspect_twas(path, 1.0, single_method=values['parameters'].get('ztest') or request.GET.get('ztest') or 'single', expected_chrom=chrom)
        if summary['invalid_rows']:
            values['state'] = 'partial'
        elif not summary['valid_rows']:
            values['state'] = 'empty_result'
        else:
            selected = [row for row in summary['data'] if float(row['PVALUE']) <= threshold]
            values.update(rows=selected, all_rows=summary['data'], valid_rows=summary['valid_rows'],
                          selected_rows=len(selected))
            if state:
                values['state'] = 'success' if selected else 'no_hits'
    except (OSError, IOError, ValueError, UnicodeError):
        values['state'] = 'invalid_result'
    return values


def detail_twas(request):
    try:
        result = task_result(request)
    except (ResultError, OSError, IOError, ValueError):
        return page_error(request, 'Check the saved task link, chromosome and nominal p threshold. The requested task or its metadata could not be read.')
    model = result['parameters'].get('celltype') or request.GET.get('celltype')
    celltypes = list(Celltype.objects.filter(celltypeid=model).values()) if model else []
    for celltype in celltypes:
        studies = list(Study.objects.filter(studyid=celltype['studyid']).values())
        if studies:
            celltype.update(studies[0])
    for row in result['all_rows']:
        row['celltype'] = model or ''
    cache = {key: request.GET.get(key) or '' for key in
             ('celltype', 'key', 'thres', 'reference', 'population', 'window', 'ztest')}
    cache.update(result['parameters'])
    cache['thres'] = result['parameters'].get('weight', request.GET.get('thres') or '')
    cache.update(jobid=result['tag'], chrom=result['chrom'], thres_twas=result['threshold'],
                 progress=100 if result['state'] in ('success', 'no_hits', 'legacy_unverified') else -1,
                 state=result['state'], info_progression=display_state(result['state'])['status_description'])
    context = {'cache_query': cache, 'data_twas': result['rows'], 'data_celltype': celltypes,
               'valid_rows': result['valid_rows'], 'selected_rows': result['selected_rows'],
               'download_query': urlencode({'data': result['tag'], 'chrom': result['chrom'],
                                           'thres_twas': result['threshold']}),
               'can_download': result['state'] in ('success', 'no_hits', 'legacy_unverified'),
               'task_payload': json.dumps({'cache': cache, 'rows': result['rows'], 'all_rows': result['all_rows'], 'celltypes': celltypes,
                                           'study_presentations': SOURCE_PRESENTATIONS}, ensure_ascii=True)}
    context['preview_mode'] = getattr(settings, 'SCTWAS_UI_PREVIEW', False)
    context.update(display_state(result['state']))
    context['page_title'] = 'TWAS results · scTWASdb'
    return HttpResponse(loader.get_template('sctwas/top-nav.Task.html').render(context, request))


def download_twas(request):
    """Same parser and literal threshold as the task page; the raw file is never rewritten."""
    try:
        result = task_result(request)
    except (ResultError, OSError, IOError, ValueError):
        return JsonResponse({'error': 'Invalid task, chromosome, threshold or result metadata.'}, status=400)
    if result['state'] not in ('success', 'no_hits', 'legacy_unverified'):
        return JsonResponse({'error': 'A validated result is not available.', 'state': result['state']}, status=409)
    response = HttpResponse(content_type='text/tab-separated-values; charset=utf-8')
    scope = request.GET.get('scope', 'selected')
    if scope not in ('all', 'selected'):
        return JsonResponse({'error': 'Choose the selected or all-results export.'}, status=400)
    response['Content-Disposition'] = 'attachment; filename="twas-{0}.tsv"'.format('all-valid' if scope == 'all' else 'selected')
    response['X-scTWAS-Result-Scope'] = scope
    response['X-scTWAS-P-Threshold'] = format(result['threshold'], '.17g')
    response['X-scTWAS-Result-State'] = result['state']
    response.write('\t'.join(TWAS_COLUMNS) + '\n')
    for row in result['all_rows'] if scope == 'all' else result['rows']:
        response.write('\t'.join(row[key] for key in TWAS_COLUMNS) + '\n')
    return response


def training_result(request):
    tag = task_id(request.GET.get('task'))
    tasks = list(Task.objects.filter(field_id=tag).values('progress'))
    if not tasks:
        raise ResultError('Task was not found.')
    directory = result_directory(tag, existing=True)
    recorded = load_status(directory)
    result = {'tag': tag, 'state': 'legacy_unverified', 'parameters': {}, 'artifacts': []}
    if not recorded:
        return result
    if recorded.get('kind') != 'grex':
        raise ResultError('This is not a training task.')
    result.update(state=recorded['state'], parameters=recorded.get('parameters', {}))
    if result['state'] != 'success':
        return result
    current = assess_training(directory, result['parameters'].get('train'), recorded.get('returncode'))
    expected = {a['path']: a['sha256'] for a in recorded['artifacts']}
    observed = {a['path']: a['sha256'] for a in current['artifacts']}
    if current['state'] != 'success' or not expected or observed != expected:
        result['state'] = 'invalid_result'
        return result
    result['artifacts'] = current['artifacts']
    for artifact in result['artifacts']:
        artifact['download_query'] = urlencode({'task': tag, 'file': artifact['path']})
    return result


def detail_training(request):
    try:
        result = training_result(request)
    except (ResultError, OSError, IOError, ValueError):
        return page_error(request, 'Check the saved training task link. The task or its metadata could not be read.')
    result.update(display_state(result['state']))
    if result['state'] == 'legacy_unverified':
        result['status_description'] = 'The task has no recorded completion status. Weight files are unavailable.'
    result['preview_mode'] = getattr(settings, 'SCTWAS_UI_PREVIEW', False)
    result['page_title'] = 'Expression-weight results · scTWASdb'
    result['light_assets'] = True
    return HttpResponse(loader.get_template('sctwas/training-result.html').render(result, request))


def download_training(request):
    try:
        result = training_result(request)
        if result['state'] != 'success':
            return JsonResponse({'error': 'Validated weights are not available.', 'state': result['state']}, status=409)
        name = request.GET.get('file')
        if name not in {a['path'] for a in result['artifacts']}:
            raise ResultError('Unknown training artifact.')
        directory = result_directory(result['tag'], existing=True)
        response = FileResponse(open(safe_child(directory, name), 'rb'),
                                content_type='application/gzip' if name.endswith('.gz') else 'text/tab-separated-values')
        response['Content-Disposition'] = 'attachment; filename="{0}"'.format(name)
        return response
    except (ResultError, OSError, IOError, ValueError):
        return JsonResponse({'error': 'Invalid training task or artifact.'}, status=400)
