# -*- coding: utf-8 -*-
"""Immutable TSV artifacts, shared across web processes; no scientific task jobs."""
from __future__ import unicode_literals

import errno
import fcntl
import hashlib
import json
import os
import re
import time
import uuid
from contextlib import contextmanager

from django.conf import settings
from django.db import connections
from django.core.exceptions import EmptyResultSet
from django.http import HttpResponse, JsonResponse, StreamingHttpResponse

CACHE_SECONDS = 3600
RETENTION_SECONDS = 86400
ARTIFACT = re.compile(r'^[a-f0-9]{32}$')
OWNED_FILE = re.compile(r'^(?:[a-f0-9]{32}\.(?:tsv|json|part)|key-[a-f0-9]{64}\.json)$')


class ExportBusy(Exception):
    pass


class ExportUnavailable(Exception):
    pass


def stream_values(queryset, fields, chunk_size=2000):
    """One SELECT, bounded driver buffering, and a dedicated MySQL connection.

    Django 1.11's default MySQL cursor buffers the entire result. An SSCursor
    must not share its connection with metadata queries while rows are pending.
    """
    source = connections[queryset.db]
    try:
        sql, args = queryset.values_list(*fields).query.get_compiler(queryset.db).as_sql()
    except EmptyResultSet:
        return
    raw = None
    if source.vendor == 'mysql':
        from MySQLdb.cursors import SSCursor
        raw = source.Database.connect(**source.get_connection_params())
        raw.autocommit(True)
        cursor = raw.cursor(SSCursor)
    else:
        cursor = source.cursor()
    try:
        cursor.execute(sql, args)
        while True:
            rows = cursor.fetchmany(chunk_size)
            if not rows:
                break
            for row in rows:
                yield row
    finally:
        try:
            cursor.close()
        finally:
            if raw is not None:
                raw.close()


def root_directory():
    root = settings.SCTWAS_EXPORT_ROOT
    if not os.path.isdir(root):
        try:
            os.makedirs(root, 0o700)
        except OSError as error:
            if error.errno != errno.EEXIST:
                raise
    return root


def read_json(path):
    try:
        with open(path, 'r') as handle:
            return json.load(handle)
    except (IOError, ValueError):
        return None


def write_json(path, value):
    temporary = path + '.next-' + uuid.uuid4().hex
    try:
        with os.fdopen(os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as handle:
            json.dump(value, handle, sort_keys=True)
            handle.flush()
            os.fsync(handle.fileno())
        os.rename(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@contextmanager
def build_slot(root):
    # Fixed lock files do not accumulate per-query lock inodes. At most two
    # artifact builders read the database at once across all uWSGI processes.
    chosen = None
    for slot in range(2):
        handle = os.fdopen(os.open(os.path.join(root, 'build-%d.lock' % slot), os.O_RDWR | os.O_CREAT, 0o600), 'a+')
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            chosen = handle
            break
        except IOError as error:
            handle.close()
            if error.errno not in (errno.EACCES, errno.EAGAIN):
                raise
    if chosen is None:
        raise ExportBusy('Other exports are being prepared. Retry shortly.')
    try:
        yield
    finally:
        fcntl.flock(chosen.fileno(), fcntl.LOCK_UN)
        chosen.close()


def cleanup(root):
    cutoff = time.time() - RETENTION_SECONDS
    for name in os.listdir(root):
        path = os.path.join(root, name)
        if OWNED_FILE.match(name):
            try:
                if os.path.getmtime(path) < cutoff:
                    os.unlink(path)
            except OSError as error:
                if error.errno != errno.ENOENT:
                    raise


def disk_bytes(root):
    size = 0
    for name in os.listdir(root):
        if re.match(r'^[a-f0-9]{32}\.(tsv|part)$', name):
            try:
                size += os.path.getsize(os.path.join(root, name))
            except OSError as error:
                if error.errno != errno.ENOENT:
                    raise
    return size


def check_storage(root, limit):
    disk = os.statvfs(root)
    if disk_bytes(root) >= limit or disk.f_bavail * disk.f_frsize < 1024 ** 3:
        raise ExportUnavailable('Export storage is temporarily full. Please retry later.')


def manifest(artifact):
    if not ARTIFACT.match(artifact or ''):
        return None
    root = root_directory()
    value = read_json(os.path.join(root, artifact + '.json'))
    if not value or value.get('artifact') != artifact or value.get('expires_at', 0) <= time.time():
        return None
    path = os.path.join(root, artifact + '.tsv')
    if not os.path.isfile(path) or os.path.getsize(path) != value.get('bytes'):
        return None
    return value


def cache_identity(selection, kind, params):
    namespace = getattr(settings, 'SCTWAS_DATA_VERSION', getattr(settings, 'SCTWAS_RELEASE', 'development'))
    scope = dict(selection=selection, kind=kind, search=params.get('search[value]', '').strip(),
                 sort=params.get('order[0][column]', '4'), direction=params.get('order[0][dir]', 'asc'))
    key = hashlib.sha256(json.dumps([namespace, scope], sort_keys=True).encode('utf-8')).hexdigest()
    return namespace, scope, key


def cached(selection, kind, params):
    key = cache_identity(selection, kind, params)[2]
    pointer = read_json(os.path.join(root_directory(), 'key-' + key + '.json'))
    existing = manifest(pointer.get('artifact', '')) if pointer else None
    return existing if existing and time.time() - existing['created_at'] < CACHE_SECONDS else None


def prepare(queryset, fields, selection, kind, params, rows):
    root = root_directory()
    namespace, scope, key = cache_identity(selection, kind, params)
    key_path = os.path.join(root, 'key-' + key + '.json')

    value = cached(selection, kind, params)
    if value:
        return value
    # Hash-striped locks bound lock-file count and stop duplicate concurrent builds.
    lock = os.fdopen(os.open(os.path.join(root, 'query-' + key[:2] + '.lock'), os.O_RDWR | os.O_CREAT, 0o600), 'a+')
    try:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except IOError as error:
            if error.errno in (errno.EACCES, errno.EAGAIN):
                raise ExportBusy('This export is being prepared. Retry shortly.')
            raise
        value = cached(selection, kind, params)
        if value:
            return value
        with build_slot(root):
            cleanup(root)
            limit = getattr(settings, 'SCTWAS_EXPORT_DISK_BYTES', 2 * 1024 ** 3)
            check_storage(root, limit)
            artifact = uuid.uuid4().hex
            partial = os.path.join(root, artifact + '.part')
            final = os.path.join(root, artifact + '.tsv')
            digest, count, size = hashlib.sha256(), -1, 0
            try:
                with os.fdopen(os.open(partial, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as handle:
                    for line in rows(queryset, fields):
                        content = line.encode('utf-8') if not isinstance(line, bytes) else line
                        handle.write(content)
                        digest.update(content)
                        size += len(content)
                        count += 1
                        if count % 2000 == 0:
                            handle.flush()
                            check_storage(root, limit)
                    handle.flush()
                    check_storage(root, limit)
                    os.fsync(handle.fileno())
                created = time.time()
                value = dict(artifact=artifact, kind=kind, rows=count, bytes=size, sha256=digest.hexdigest(),
                             created_at=created, expires_at=created + RETENTION_SECONDS,
                             cache_namespace=namespace, scope=scope)
                os.rename(partial, final)
                write_json(os.path.join(root, artifact + '.json'), value)
                write_json(key_path, {'artifact': artifact})
                return value
            except Exception:
                for path in (partial, final, os.path.join(root, artifact + '.json')):
                    if os.path.exists(path):
                        os.unlink(path)
                raise
    finally:
        lock.close()


def file_chunks(path, start, length):
    with open(path, 'rb') as handle:
        handle.seek(start)
        while length:
            block = handle.read(min(65536, length))
            if not block:
                break
            length -= len(block)
            yield block


def serve(request, value):
    etag = '"' + value['sha256'] + '"'
    size, start, end, status = value['bytes'], 0, value['bytes'] - 1, 200
    requested = request.META.get('HTTP_RANGE', '')
    if request.META.get('HTTP_IF_RANGE', etag) != etag:
        requested = ''
    if not requested and request.META.get('HTTP_IF_NONE_MATCH') == etag:
        response = HttpResponse(status=304)
    else:
        if requested:
            matched = re.match(r'^bytes=(\d*)-(\d*)$', requested)
            if matched and any(matched.groups()):
                left, right = matched.groups()
                if left:
                    start, end = int(left), min(int(right), size - 1) if right else size - 1
                else:
                    start, end = max(0, size - int(right)), size - 1
            else:
                start = size
            if start > end or start >= size:
                response = HttpResponse(status=416)
                response['Content-Range'] = 'bytes */%d' % size
                return response
            status = 206
        response = HttpResponse(status=status) if request.method == 'HEAD' else StreamingHttpResponse(
            file_chunks(os.path.join(root_directory(), value['artifact'] + '.tsv'), start, end - start + 1), status=status)
        response['Content-Length'] = str(end - start + 1)
        if status == 206:
            response['Content-Range'] = 'bytes %d-%d/%d' % (start, end, size)
    response['Content-Type'] = 'text/tab-separated-values; charset=utf-8'
    response['Content-Disposition'] = 'attachment; filename="sctwas-' + value['kind'] + '-filtered.tsv"'
    response['Accept-Ranges'] = 'bytes'
    response['ETag'] = etag
    response['Cache-Control'] = 'private, max-age=0, must-revalidate'
    response['X-scTWAS-Export-Scope'] = 'all-filtered-records'
    response['X-scTWAS-Export-Rows'] = str(value['rows'])
    return response


def busy_response(error):
    response = JsonResponse({'error': str(error), 'retry_after': 3}, status=503)
    response['Retry-After'] = '3'
    response['Cache-Control'] = 'no-store'
    return response
