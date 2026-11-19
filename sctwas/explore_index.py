# -*- coding: utf-8 -*-
"""Optional immutable projection of legacy nominal hits, never a scientific release.

Only broad Explore summaries use this accelerator. Detail/download rows still
come from the source database. Missing, stale or damaged files fail back to SQL.
"""
from __future__ import unicode_literals
import hashlib
import json
import os
import sqlite3
from collections import defaultdict

from django.conf import settings
from django.db import connections

_verified = {}


def source_signature():
    from sctwas.models import Twas
    source = connections[Twas.objects.db]
    if source.vendor != 'mysql':
        return None
    with source.cursor() as cursor:
        cursor.execute('SHOW TABLE STATUS LIKE %s', ['twas'])
        row = dict(zip([c[0] for c in cursor.description], cursor.fetchone()))
    # For this legacy MyISAM table, Update_time detects ordinary data writes.
    # It is a freshness guard, not a cryptographic database snapshot.
    if row['Engine'] != 'MyISAM' or row['Update_time'] is None:
        return None
    return {k: str(row[k]) for k in ('Engine', 'Rows', 'Data_length', 'Index_length', 'Update_time')}


def digest_file(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def indexed_counts(query, traits, cells):
    """Return (gene sets, model sets), or None to request live SQL fallback."""
    path = getattr(settings, 'SCTWAS_EXPLORE_INDEX', '')
    expected = getattr(settings, 'SCTWAS_EXPLORE_INDEX_SHA256', '')
    if not path or len(expected) != 64 or query['key'] not in ('1', '3'):
        return None
    db = None
    try:
        stat = os.stat(path)
        identity = (path, stat.st_ino, stat.st_size, stat.st_mtime, expected)
        if identity not in _verified:
            if digest_file(path) != expected:
                return None
            _verified.clear()
            _verified[identity] = True
        db = sqlite3.connect(path, timeout=2)
        db.execute('PRAGMA query_only=ON')
        meta = json.loads(db.execute("SELECT value FROM metadata WHERE key='manifest'").fetchone()[0])
        if (meta['schema_version'] != 1 or
                meta['data_version'] != getattr(settings, 'SCTWAS_DATA_VERSION', '') or
                query['thres_twas'] > meta['max_p'] or
                meta['source_signature'] != source_signature()):
            return None
        allowed_traits, allowed_cells = set(traits), set(cells)
        genes, matched = defaultdict(set), defaultdict(set)
        # Small strict-threshold projection; no 999-parameter limit and no
        # buffer of all rows. Exact filters remain in Python sets.
        sql, args = 'SELECT trait,gene,model FROM hits WHERE min_p<=?', [query['thres_twas']]
        if not allowed_traits or not allowed_cells:
            return genes, matched
        if len(allowed_cells) <= 900:
            ordered = sorted(allowed_cells)
            sql += ' AND model IN (' + ','.join(['?'] * len(ordered)) + ')'
            args.extend(ordered)
        for trait, gene, cell in db.execute(sql, args):
            if trait in allowed_traits and cell in allowed_cells:
                genes[trait].add(gene)
                matched[trait].add(cell)
        return genes, matched
    except (IOError, OSError, ValueError, KeyError, TypeError, sqlite3.Error):
        return None
    finally:
        if db is not None:
            db.close()
