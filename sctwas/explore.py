# -*- coding: utf-8 -*-
"""Batched, read-only Explore summaries. Counts share one association scope."""
from __future__ import unicode_literals

import hashlib
import json
import time
from collections import defaultdict

from django.conf import settings
from django.core.cache import caches
from django.db import OperationalError
from django.db.models import Count, Min, Max, Q
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from sctwas.association_views import pair_filter, SelectionError
from sctwas.models import Celltype, Eqtl, Gene, Trait, Twas
from sctwas.tools.result_contract import probability, ResultError

BATCH_SIZE = 12
CACHE_SECONDS = 3600


def parameters(params):
    query = {key: params.get(key, '') for key in ('key', 'data', 'celltype', 'icd10')}
    query['data'] = (query['data'] or '').strip()
    query['celltype'] = query['celltype'] or 'All Celltypes'
    query['icd10'] = query['icd10'] or 'All Traits'
    if query['key'] not in ('0', '1', '2', '3', '4') or not 0 < len(query['data']) <= 200:
        raise SelectionError('A valid query type and search value are required.')
    try:
        query['thres_twas'] = probability(params.get('thres_twas'))
        query['thres'] = probability(params.get('thres'))
    except ResultError as error:
        raise SelectionError(str(error))
    return query


def candidates(query):
    if query['key'] == '3':
        cells = Celltype.objects.filter(Q(celltypeid__icontains=query['data']) | Q(subtype__icontains=query['data']))
        if query['celltype'] != 'All Celltypes':
            cells = cells.filter(majortype=query['celltype'])
        if not cells.exists():
            return []
    traits = Trait.objects.all()
    if query['key'] == '1':
        # Preserve the established description-first, category-fallback contract.
        described = traits.filter(description__icontains=query['data'])
        traits = described if described.exists() else traits.filter(icd10__icontains=query['data'])
    if query['icd10'] != 'All Traits':
        traits = traits.filter(icd10=query['icd10'])
    return list(traits.order_by('phecode').values())


def selected_cells(query):
    cells = Celltype.objects.all()
    if query['celltype'] != 'All Celltypes':
        cells = cells.filter(majortype=query['celltype'])
    if query['key'] == '3':
        cells = cells.filter(Q(celltypeid__icontains=query['data']) | Q(subtype__icontains=query['data']))
    return {row['celltypeid']: row for row in cells.order_by('celltypeid').values()}


def summarize(query, traits):
    if not traits:
        return []
    cells = selected_cells(query)
    if not cells:
        return []
    twas = Twas.objects.filter(
        phecode__in=[row['phecode'] for row in traits], celltype__in=sorted(cells)).filter(
        Q(fusion_pval__lte=query['thres_twas']) | Q(spred_pval__lte=query['thres_twas']))
    if query['key'] == '0':
        gene = list(Gene.objects.filter(genename=query['data']).order_by('ensemblid').values_list('ensemblid', flat=True)[:1])
        twas = twas.filter(ensemblid__in=gene)
    elif query['key'] == '4':
        twas = twas.filter(ensemblid=query['data'])
    elif query['key'] == '2':
        pairs = Eqtl.objects.filter(rsid=query['data'], pvalue__lte=query['thres'],
                                    celltype__in=sorted(cells)).order_by().values_list('genename', 'celltype').distinct()
        twas = twas.filter(pair_filter(pairs, 'ensemblid'))
    # No joins against non-unique metadata keys. Major type restricts BOTH genes
    # and models before aggregation. Distinct genes mean Ensembl identifiers.
    totals = list(twas.order_by().values('phecode').annotate(
        n_genes=Count('ensemblid', distinct=True), first_gene=Min('ensemblid'), last_gene=Max('ensemblid')))
    if not totals:
        return []
    matched = defaultdict(set)
    for trait, cell in twas.order_by().values_list('phecode', 'celltype').distinct():
        matched[trait].add(cell)
    return render_counts(traits, cells, totals, matched)


def render_counts(traits, cells, totals, matched):
    gene_ids = set(value for row in totals for value in (row['first_gene'], row['last_gene']))
    symbols = {}
    for gene, symbol in Gene.objects.filter(ensemblid__in=gene_ids).order_by('ensemblid', 'genename').values_list('ensemblid', 'genename'):
        symbols.setdefault(gene, symbol or gene)
    lookup = {row['phecode']: row for row in traits}
    result = []
    for count in totals:
        trait = dict(lookup[count['phecode']])
        metadata = [cells[cell] for cell in sorted(matched[count['phecode']])]
        trait.update(n_celltypes=len(metadata), n_genes=count['n_genes'])
        for field, name in [('majortype', 'majortypes'), ('subtype', 'subtypes'),
                            ('studyid', 'studies'), ('condition', 'conditions')]:
            trait['n_' + name] = len(set(row[field] for row in metadata))
        trait['target_celltype'] = sorted(set(row['subtype'] for row in metadata))[:2]
        trait['target_condition'] = sorted(set(row['condition'] for row in metadata))[:2]
        ids = sorted(set([count['first_gene'], count['last_gene']]))
        trait['target_genes'] = [symbols.get(gene, gene) for gene in ids]
        result.append(trait)
    return sorted(result, key=lambda row: row['phecode'])


def indexed_result(query, traits):
    from sctwas.explore_index import indexed_counts
    if not getattr(settings, 'SCTWAS_EXPLORE_INDEX', '') or query['key'] not in ('1', '3'):
        return None
    cells = selected_cells(query)
    counts = indexed_counts(query, [row['phecode'] for row in traits], cells)
    if counts is None:
        return None
    genes, matched = counts
    totals = [dict(phecode=trait, n_genes=len(ids), first_gene=min(ids), last_gene=max(ids))
              for trait, ids in genes.items()]
    return render_counts(traits, cells, totals, matched)


def all_results(query):
    traits = candidates(query)
    indexed = indexed_result(query, traits)
    if indexed is not None:
        return indexed
    if query['key'] in ('0', '2', '4'):
        return summarize(query, traits)
    result = []
    for start in range(0, len(traits), BATCH_SIZE):
        result.extend(summarize(query, traits[start:start + BATCH_SIZE]))
    return result


def batch_result(query, start=0):
    cache = caches['sctwas_queries']
    release = getattr(settings, 'SCTWAS_DATA_VERSION', getattr(settings, 'SCTWAS_RELEASE', 'development'))
    key = 'explore-v2-' + hashlib.sha256(json.dumps([release, query], sort_keys=True).encode('utf-8')).hexdigest()
    # Do not serve cached indexed results after a source update. Indexed reads
    # are already small and avoid the cross-batch database cache entirely.
    if start == 0 and getattr(settings, 'SCTWAS_EXPLORE_INDEX', '') and query['key'] in ('1', '3'):
        traits = candidates(query)
        indexed = indexed_result(query, traits)
        if indexed is not None:
            return dict(data=indexed, checked=len(traits), candidates=len(traits),
                        complete=True, next_start=len(traits), cache_age_seconds=0)
    complete = cache.get(key)
    if complete is not None and start == 0:
        response = dict(complete)
        response['cache_age_seconds'] = max(0, int(time.time() - response.pop('created')))
        return response
    traits = candidates(query)
    size = (len(traits) or 1) if query['key'] in ('0', '2', '4') else BATCH_SIZE
    if start < 0 or start > len(traits) or start % size:
        raise SelectionError('Use the next batch offset returned by the search.')
    prefix = key + '-' + hashlib.sha256(json.dumps([row['phecode'] for row in traits]).encode('utf-8')).hexdigest()
    batch_key = prefix + '-' + str(start)
    part = cache.get(batch_key)
    if part is None:
        part = {'data': summarize(query, traits[start:start + size]), 'created': time.time()}
        cache.set(batch_key, part, CACHE_SECONDS)
    checked = min(start + size, len(traits))
    response = dict(data=part['data'], checked=checked, candidates=len(traits),
                    complete=checked == len(traits), next_start=checked,
                    cache_age_seconds=max(0, int(time.time() - part['created'])))
    if response['complete']:
        keys = [prefix + '-' + str(i) for i in range(0, len(traits) or 1, size)]
        parts = cache.get_many(keys)
        if len(parts) == len(keys):
            created = min(parts[name]['created'] for name in keys)
            full = dict(response, data=[row for name in keys for row in parts[name]['data']], created=created)
            cache.set(key, full, max(1, int(CACHE_SECONDS - (time.time() - created))))
    return response


@require_GET
def search_data(request):
    try:
        try:
            start = int(request.GET.get('start', '0'))
        except (TypeError, ValueError):
            raise SelectionError('Use a valid batch offset.')
        response = JsonResponse(batch_result(parameters(request.GET), start))
    except SelectionError as error:
        response = JsonResponse({'error': str(error)}, status=error.status)
    except OperationalError:
        response = JsonResponse({'error': 'This search batch could not be completed. Retry, or narrow the trait category and cell type.'}, status=503)
    response['Cache-Control'] = 'no-store'
    return response
