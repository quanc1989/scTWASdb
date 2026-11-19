# -*- coding: utf-8 -*-
"""Single-executor disk queue. SSH transports jobs; no public queue endpoint."""
from __future__ import unicode_literals
import contextlib
import fcntl
import io
import json
import os
import time
import uuid

from sctwas.tools.result_contract import atomic_status, safe_child, sha256, task_id

LEASE_SECONDS = 600
TERMINAL = ('success', 'no_hits', 'failed', 'partial', 'empty_result')


def mkdir(path):
    try:
        os.makedirs(path, 0o700)
    except OSError:
        if not os.path.isdir(path):
            raise


def read(path):
    try:
        with io.open(path, encoding='utf-8') as handle:
            return json.load(handle)
    except (IOError, ValueError):
        return None


def write(path, value):
    mkdir(os.path.dirname(path))
    temporary = path + '.' + uuid.uuid4().hex + '.tmp'
    with open(temporary, 'wb') as handle:
        os.chmod(temporary, 0o600)
        handle.write(json.dumps(value, ensure_ascii=True).encode('utf-8'))
        handle.flush()
        os.fsync(handle.fileno())
    os.rename(temporary, path)
    directory_fd = os.open(os.path.dirname(path), os.O_RDONLY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


@contextlib.contextmanager
def locked(root):
    mkdir(root)
    with open(os.path.join(root, 'queue.lock'), 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def available(root):
    health = read(os.path.join(root, 'worker.json')) or {}
    return 0 <= time.time() - health.get('seen_at', 0) < 300


def enqueue(root, tag, kind, parameters, input_path):
    task_id(tag)
    if kind not in ('twas', 'grex'):
        raise ValueError('Unsupported task kind')
    with locked(root):
        if not available(root):
            raise ValueError('Compute worker unavailable')
        path = safe_child(root, 'jobs/' + tag + '.json')
        if os.path.exists(path):
            raise ValueError('Task already queued')
        write(path, {'version': 1, 'tag': tag, 'kind': kind, 'parameters': parameters,
                     'input_name': os.path.basename(input_path), 'input_sha256': sha256(input_path),
                     'state': 'queued', 'queued_at': time.time()})


def heartbeat(root, worker, tag=None, lease=None):
    with locked(root):
        now = time.time()
        write(os.path.join(root, 'worker.json'), {'worker': worker, 'seen_at': now})
        if tag:
            path = safe_child(root, 'jobs/' + task_id(tag) + '.json')
            job = read(path)
            if not job or job.get('state') != 'running' or job.get('lease') != lease or job.get('worker') != worker:
                raise ValueError('Task lease is no longer owned')
            job['heartbeat_at'] = now
            write(path, job)


def claim(root, worker):
    with locked(root):
        now = time.time()
        write(os.path.join(root, 'worker.json'), {'worker': worker, 'seen_at': now})
        directory = os.path.join(root, 'jobs')
        mkdir(directory)
        jobs = []
        for name in sorted(os.listdir(directory)):
            if not name.endswith('.json'):
                continue
            job = read(safe_child(directory, name))
            if not job:
                continue
            if job.get('state') == 'running':
                if now - job.get('heartbeat_at', 0) <= LEASE_SECONDS:
                    return None  # One scientific task at a time, across all workers.
                # Do not silently re-run interrupted scientific jobs.
                status = {'kind': job['kind'], 'state': 'failed', 'reason': 'worker_lease_expired',
                          'parameters': job['parameters'], 'artifacts': []}
                atomic_status(safe_child(root, 'result/' + task_id(job['tag'])), status)
                job.update(state='failed', finished_at=now)
                write(safe_child(directory, name), job)
            if job.get('state') == 'queued':
                jobs.append(job)
        if not jobs:
            return None
        job = min(jobs, key=lambda item: item['queued_at'])
        job.update(state='running', worker=worker, lease=uuid.uuid4().hex,
                   heartbeat_at=now, started_at=now)
        write(safe_child(directory, job['tag'] + '.json'), job)
        atomic_status(safe_child(root, 'result/' + job['tag']),
                      {'kind': job['kind'], 'state': 'running', 'parameters': job['parameters']})
        mkdir(safe_child(root, 'incoming'))
        return job


def finish(root, worker, tag, lease, status):
    with locked(root):
        path = safe_child(root, 'jobs/' + task_id(tag) + '.json')
        job = read(path)
        if not job or job.get('state') != 'running' or job.get('worker') != worker or job.get('lease') != lease:
            raise ValueError('Task lease is no longer owned')
        if status.get('kind') != job['kind'] or status.get('state') not in TERMINAL:
            raise ValueError('Invalid result state')
        directory = safe_child(root, 'result/' + tag)
        for item in status.get('artifacts', []):
            if sha256(safe_child(directory, item['path'])) != item['sha256']:
                raise ValueError('Transferred result checksum mismatch')
        if status['state'] in ('success', 'no_hits') and (status.get('returncode') != 0 or not status.get('artifacts')):
            raise ValueError('Successful task requires validated artifacts')
        status['parameters'] = job['parameters']
        status['executor'] = {'worker': worker, 'lease': lease, 'transport': 'ssh_private_spool'}
        atomic_status(directory, status)
        job.update(state=status['state'], finished_at=time.time())
        write(path, job)
        return job
