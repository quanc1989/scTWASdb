# -*- coding: utf-8 -*-
"""Durable, bounded export jobs. This queue never schedules scientific tasks."""
from __future__ import unicode_literals

import errno
import fcntl
import json
import os
import sqlite3
import time
import uuid
from contextlib import contextmanager

from django.conf import settings
from sctwas import export_store as store

MAX_ATTEMPTS = 3


@contextmanager
def database():
    path = os.path.join(store.root_directory(), 'export-jobs.sqlite')
    try:
        os.close(os.open(path, os.O_RDWR | os.O_CREAT | os.O_EXCL, 0o600))
    except OSError as error:
        if error.errno != errno.EEXIST:
            raise
    db = sqlite3.connect(path, timeout=3)
    db.row_factory = sqlite3.Row
    try:
        db.execute('PRAGMA synchronous=FULL')
        db.execute('''CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY, cache_key TEXT UNIQUE NOT NULL, namespace TEXT NOT NULL,
            params TEXT NOT NULL, state TEXT NOT NULL, artifact TEXT, error TEXT,
            created REAL NOT NULL, updated REAL NOT NULL, attempts INTEGER NOT NULL DEFAULT 0)''')
        db.execute('CREATE INDEX IF NOT EXISTS job_order ON jobs (state, created)')
        with db:
            yield db
    finally:
        db.close()


def worker_ready():
    value = store.read_json(os.path.join(store.root_directory(), 'export-worker.json'))
    return bool(value and 0 <= time.time() - value.get('updated', 0) < 45)


def enqueue(context, kind, params):
    # Validate selection, search and ordering before calling this function.
    selection = context['cache_query']
    existing = store.cached(selection, kind, params)
    if existing:
        return dict(existing, state='ready')
    if not worker_ready():
        raise store.ExportUnavailable('Export preparation is temporarily unavailable. Please retry shortly.')
    namespace, scope, key = store.cache_identity(selection, kind, params)
    canonical = dict(selection, kind=kind)
    canonical.update({'search[value]': scope['search'], 'search[regex]': 'false',
                      'order[0][column]': scope['sort'], 'order[0][dir]': scope['direction']})
    now = time.time()
    with database() as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT * FROM jobs WHERE cache_key=?', (key,)).fetchone()
        row = dict(row) if row else None  # Python 2 sqlite.Row rejects Unicode column keys.
        if row and row['state'] in ('queued', 'running'):
            return public(dict(row))
        if row and row['state'] == 'failed' and now - row['updated'] < 30:
            return public(dict(row))
        active = db.execute("SELECT COUNT(*) FROM jobs WHERE state IN ('queued','running')").fetchone()[0]
        if active >= getattr(settings, 'SCTWAS_EXPORT_QUEUE_LIMIT', 32):
            raise store.ExportBusy('The export queue is full. Please retry shortly.')
        if row:
            db.execute('DELETE FROM jobs WHERE id=?', (row['id'],))
        job = uuid.uuid4().hex
        db.execute('INSERT INTO jobs (id,cache_key,namespace,params,state,created,updated) VALUES (?,?,?,?,?,?,?)',
                   (job, key, namespace, json.dumps(canonical, sort_keys=True), 'queued', now, now))
        return public(dict(db.execute('SELECT * FROM jobs WHERE id=?', (job,)).fetchone()))


def public(row):
    value = dict(job=row['id'], state=row['state'], retry_after=2)
    if row['state'] == 'ready':
        artifact = store.manifest(row['artifact'])
        if artifact:
            value.update(artifact)
        else:
            value.update(state='expired', error='This export has expired. Prepare it again from the results page.')
    elif row['state'] == 'failed':
        value.update(error=row['error'], retry_after=30)
    else:
        value['worker_ready'] = worker_ready()
    return value


def status(job):
    if not store.ARTIFACT.match(job or ''):
        return None
    with database() as db:
        row = db.execute('SELECT * FROM jobs WHERE id=?', (job,)).fetchone()
        return public(dict(row)) if row else None


@contextmanager
def worker_lock():
    handle = os.fdopen(os.open(os.path.join(store.root_directory(), 'export-worker.lock'),
                              os.O_RDWR | os.O_CREAT, 0o600), 'a+')
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    finally:
        handle.close()


def recover():
    """Only the process holding worker_lock may claim/recover/execute jobs."""
    with database() as db:
        db.execute("UPDATE jobs SET state='queued', updated=? WHERE state='running'", (time.time(),))


def run_one():
    from sctwas import association_views as api
    with database() as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute("SELECT * FROM jobs WHERE state='queued' ORDER BY created,id LIMIT 1").fetchone()
        if not row:
            return False
        row = dict(row)
        db.execute("UPDATE jobs SET state='running', attempts=attempts+1, updated=? WHERE id=?", (time.time(), row['id']))
    state, artifact, error = 'failed', None, None
    try:
        current = getattr(settings, 'SCTWAS_DATA_VERSION', getattr(settings, 'SCTWAS_RELEASE', 'development'))
        if current != row['namespace']:
            raise store.ExportUnavailable('The database version changed. Prepare this export again.')
        if row['attempts'] >= MAX_ATTEMPTS or time.time() - row['created'] >= store.RETENTION_SECONDS:
            raise store.ExportUnavailable('This export could not complete after restarts. Prepare it again.')
        params = json.loads(row['params'])
        context = api.selection(params)
        queryset, fields = api.result_query(context, params['kind'])
        queryset, unused = api.filtered_query(queryset, fields, params)
        value = store.prepare(queryset, fields, context['cache_query'], params['kind'], params, api.tsv_rows)
        state, artifact = 'ready', value['artifact']
    except (api.SelectionError, store.ExportUnavailable) as exc:
        error = str(exc)
    except store.ExportBusy:
        state = 'queued'
        # A transient build-slot conflict is not an interrupted build attempt.
        with database() as db:
            db.execute('UPDATE jobs SET attempts=attempts-1 WHERE id=?', (row['id'],))
    except Exception as exc:
        # Do not disclose SQL, private configuration or full paths in public errors.
        error = 'The export could not be prepared. Retry after 30 seconds.'
        import logging
        logging.getLogger(__name__).error('Export preparation failed (%s)', type(exc).__name__)
    with database() as db:
        db.execute('UPDATE jobs SET state=?, artifact=?, error=?, updated=? WHERE id=?',
                   (state, artifact, error, time.time(), row['id']))
    return True


def maintenance():
    root = store.root_directory()
    # Only generated export files with the existing strict names are eligible;
    # uploads, scientific tasks, source data and lock files are never traversed.
    store.cleanup(root)
    with database() as db:
        db.execute("DELETE FROM jobs WHERE state IN ('ready','failed') AND updated<?",
                   (time.time() - store.RETENTION_SECONDS,))
        counts = dict((row[0], row[1]) for row in db.execute('SELECT state,COUNT(*) FROM jobs GROUP BY state'))
    disk = os.statvfs(root)
    value = dict(checked_at=time.time(), jobs=counts, artifact_bytes=store.disk_bytes(root),
                 free_bytes=disk.f_bavail * disk.f_frsize,
                 export_limit_bytes=getattr(settings, 'SCTWAS_EXPORT_DISK_BYTES', 2 * 1024 ** 3))
    value['storage_ok'] = value['artifact_bytes'] < value['export_limit_bytes'] and value['free_bytes'] >= 1024 ** 3
    store.write_json(os.path.join(root, 'export-monitor.json'), value)
    return value
