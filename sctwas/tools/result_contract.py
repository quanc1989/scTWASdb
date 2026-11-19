# -*- coding: utf-8 -*-
"""Small Python 2/3 compatible contracts shared by workers, views and audits."""
from __future__ import unicode_literals

import gzip
import codecs
import hashlib
import io
import json
import math
import os
import re
import tempfile
from datetime import datetime

CONTRACT_VERSION = 1
DEFAULT_P_THRESHOLD = 1e-5
TWAS_COLUMNS = ('CHROM', 'GeneStart', 'GeneEnd', 'TargetID', 'GeneName',
                'n_snps', 'Method', 'Zscore', 'PVALUE')
DUAL_COLUMNS = ('TargetID', 'n_snps', 'FUSION_Z', 'FUSION_PVAL', 'SPred_Z', 'SPred_PVAL')
TRAINING_OUTPUTS = {'PT': ('P0.001', 'P0.05'), 'lassosum': ('lassosum',),
                    'PRScs': ('PRScs',), 'SDPR': ('SDPR',)}


class ResultError(ValueError):
    pass


def finite_number(value):
    number = float(value)
    if math.isnan(number) or math.isinf(number):
        raise ResultError('nonfinite_number')
    return number


def probability(value, default=DEFAULT_P_THRESHOLD, allow_zero=False):
    """Parse the literal numeric value; never reinterpret legacy '10e-5' as '1e-5'."""
    try:
        number = finite_number(default if value is None else value)
    except (ValueError, TypeError, OverflowError):
        raise ResultError('Threshold must be a finite number greater than 0 and at most 1.')
    if not ((0 <= number <= 1) if allow_zero else (0 < number <= 1)):
        raise ResultError('Threshold must be greater than 0 and at most 1.')
    return number


def chromosome(value):
    if not value or not re.match(r'^chr(?:[1-9]|1[0-9]|2[0-2])$', value):
        raise ResultError('Chromosome must be chr1 through chr22.')
    return value


def task_id(value):
    if not value or not re.match(r'^[0-9a-f]{32}$', value):
        raise ResultError('Invalid task ID.')
    return value


def safe_child(root, relative):
    if not relative or os.path.isabs(relative) or '\x00' in relative:
        raise ResultError('Invalid artifact path.')
    base = os.path.realpath(root)
    path = os.path.realpath(os.path.join(base, relative))
    if not path.startswith(base + os.sep):
        raise ResultError('Artifact path is outside the result directory.')
    return path


def open_table(path):
    if path.endswith('.gz'):
        # Python 2 GzipFile lacks the io.RawIOBase methods used by TextIOWrapper.
        return codecs.getreader('utf-8')(gzip.open(path, 'rb'))
    return io.open(path, 'r', encoding='utf-8')


def table_rows(path, required):
    """Strict TSV schema; yield row errors explicitly rather than silently dropping them."""
    with open_table(path) as handle:
        header = handle.readline().strip().split('\t')
        if len(header) != len(set(header)) or not set(required).issubset(header):
            raise ResultError('invalid_header')
        for lineno, line in enumerate(handle, 2):
            if not line.strip():
                continue
            values = line.rstrip('\r\n').split('\t')
            if len(values) != len(header):
                yield lineno, None
            else:
                yield lineno, dict(zip(header, values))


def sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def inspect_twas(path, threshold=None, include_rows=True, single_method='single', expected_chrom=None):
    threshold = probability(threshold, 1.0)
    with open_table(path) as handle:
        header = handle.readline().strip().split('\t')
    common = TWAS_COLUMNS[:6]
    if {'Zscore', 'PVALUE'}.issubset(header):
        if single_method == 'both':
            raise ResultError('expected_dual_method_statistics')
        methods = [(single_method, 'Zscore', 'PVALUE')]
    elif set(DUAL_COLUMNS).issubset(header):
        if single_method in ('FUSION', 'SPrediXcan'):
            raise ResultError('expected_single_method_statistics')
        methods = [('FUSION', 'FUSION_Z', 'FUSION_PVAL'), ('SPrediXcan', 'SPred_Z', 'SPred_PVAL')]
    else:
        raise ResultError('invalid_statistics_header')
    result = {'rows': 0, 'valid_rows': 0, 'invalid_rows': 0, 'selected_rows': 0,
              'zero_p_rows': 0, 'data': []}
    genes = set()
    for _, row in table_rows(path, common):
        result['rows'] += 1
        try:
            if row is None or not row['TargetID'] or row['TargetID'] in genes:
                raise ResultError('invalid_or_duplicate_row')
            if int(row['n_snps']) <= 0 or int(row['GeneStart']) < 0 or int(row['GeneEnd']) < int(row['GeneStart']):
                raise ResultError('invalid_coordinates_or_n_snps')
            if expected_chrom and row['CHROM'].lower().replace('chr', '') != chromosome(expected_chrom)[3:]:
                raise ResultError('chromosome_mismatch')
            genes.add(row['TargetID'])
        except (ValueError, TypeError, KeyError, OverflowError):
            result['invalid_rows'] += 1
            continue
        for method, z_key, p_key in methods:
            try:
                p = finite_number(row[p_key])
                finite_number(row[z_key])
                if not 0 <= p <= 1:
                    raise ResultError('invalid_statistic')
            except (ValueError, TypeError, KeyError, OverflowError):
                result['invalid_rows'] += 1
                continue
            result['valid_rows'] += 1
            result['zero_p_rows'] += int(p == 0)
            if p <= threshold:
                result['selected_rows'] += 1
                if include_rows:
                    normalized = {key: row[key] for key in common}
                    normalized.update(Method=method, Zscore=row[z_key], PVALUE=row[p_key])
                    result['data'].append(normalized)
    return result


def dual_statistics(row):
    """Keep each method's validity independently and preserve binary64 precision."""
    if row is None or not row.get('TargetID'):
        raise ResultError('invalid_row')
    try:
        n_snps = int(row['n_snps'])
        if n_snps <= 0:
            raise ValueError()
    except (KeyError, ValueError, TypeError):
        raise ResultError('invalid_n_snps')
    values = {'TargetID': row['TargetID'], 'n_snps': n_snps}
    for method in ('FUSION', 'SPred'):
        try:
            z = finite_number(row[method + '_Z'])
            p = finite_number(row[method + '_PVAL'])
            if not 0 <= p <= 1:
                raise ValueError()
        except (KeyError, ValueError, TypeError, OverflowError):
            z, p = None, None
        values[method + '_Z'] = z
        values[method + '_PVAL'] = p
    return values


def inspect_weights(path):
    valid = invalid = 0
    for _, row in table_rows(path, ('CHROM', 'POS', 'TargetID', 'ES')):
        try:
            if row is None or not row['TargetID'] or int(row['POS']) <= 0:
                raise ValueError()
            if not (row.get('A1') and row.get('A2') or row.get('REF') and row.get('ALT')):
                raise ValueError()
            finite_number(row['ES'])
            valid += 1
        except (ValueError, TypeError, KeyError, OverflowError):
            invalid += 1
    return {'rows': valid + invalid, 'valid_rows': valid, 'invalid_rows': invalid}


def atomic_status(directory, value):
    if not os.path.isdir(directory):
        os.makedirs(directory, 0o700)
    value = dict(value, contract_version=CONTRACT_VERSION,
                 updated_at_utc=datetime.utcnow().isoformat() + 'Z')
    fd, temporary = tempfile.mkstemp(prefix='.status-', dir=directory)
    try:
        with os.fdopen(fd, 'w') as handle:
            json.dump(value, handle, ensure_ascii=True, allow_nan=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.rename(temporary, os.path.join(directory, 'status.json'))
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return value


def load_status(directory):
    path = os.path.join(directory, 'status.json')
    if not os.path.isfile(path):
        return None
    with io.open(path, encoding='utf-8') as handle:
        data = json.load(handle)
    if not isinstance(data, dict) or data.get('contract_version') != CONTRACT_VERSION:
        raise ResultError('unsupported_status_version')
    if data.get('state') not in ('queued', 'running', 'success', 'no_hits', 'failed', 'partial', 'empty_result'):
        raise ResultError('invalid_status_state')
    if not isinstance(data.get('parameters', {}), dict) or not isinstance(data.get('artifacts', []), list):
        raise ResultError('invalid_status_metadata')
    for artifact in data.get('artifacts', []):
        if not isinstance(artifact, dict) or not artifact.get('path') or not artifact.get('sha256'):
            raise ResultError('invalid_artifact_metadata')
    return data


def assess_twas(directory, chrom, threshold, returncode, method="single"):
    relative = 'TWAS_{0}/{0}_sumstat_TWAS_assoc.txt'.format(chromosome(chrom).upper())
    path = safe_child(directory, relative)
    result = {'kind': 'twas', 'returncode': returncode, 'threshold': probability(threshold),
              'state': 'failed', 'reason': 'process_failed', 'artifacts': []}
    if returncode != 0:
        return result
    try:
        summary = inspect_twas(path, threshold, include_rows=False, single_method=method, expected_chrom=chrom)
        summary.pop('data')
        result.update(summary)
        result['artifacts'] = [{'path': relative, 'sha256': sha256(path), 'bytes': os.path.getsize(path)}]
        if summary['invalid_rows']:
            result.update(state='partial', reason='invalid_result_rows')
        elif not summary['valid_rows']:
            # A header alone does not prove that any gene was actually tested.
            result.update(state='empty_result', reason='no_valid_tests')
        else:
            result.update(state='success' if summary['selected_rows'] else 'no_hits', reason=None)
    except (OSError, IOError, ValueError, UnicodeError):
        result['reason'] = 'missing_or_invalid_result'
    return result


def assess_training(directory, model, returncode):
    result = {'kind': 'grex', 'model': model, 'returncode': returncode,
              'state': 'failed', 'reason': 'process_failed', 'artifacts': []}
    if returncode != 0:
        return result
    if model not in TRAINING_OUTPUTS:
        result['reason'] = 'unsupported_training_model'
        return result
    try:
        for stem in TRAINING_OUTPUTS[model]:
            names = [stem + '.txt']
            if model == 'PT':
                names.append(stem + '.tigar.txt.gz')
            for name in names:
                path = safe_child(directory, name)
                summary = inspect_weights(path)
                result['artifacts'].append(dict(summary, path=name, sha256=sha256(path)))
        invalid = sum(a['invalid_rows'] for a in result['artifacts'])
        empty = any(a['valid_rows'] == 0 for a in result['artifacts'])
        if invalid:
            result.update(state='partial', reason='invalid_weight_rows')
        elif empty:
            result.update(state='empty_result', reason='no_valid_weights')
        else:
            result.update(state='success', reason=None)
    except (OSError, IOError, ValueError, UnicodeError):
        result.update(state='partial' if result['artifacts'] else 'failed', reason='missing_or_invalid_weights')
    return result


def progress_for(state):
    return 100 if state in ('success', 'no_hits') else (0 if state in ('queued', 'running') else -1)
