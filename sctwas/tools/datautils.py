# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import logging
import os
import subprocess
import threading

from django.conf import settings
from django.db import close_old_connections
from django.utils import timezone

from sctwas.models import Task
from sctwas.tools.task_storage import task_root, result_directory
from sctwas.tools.mailutils import sendEmailWithAttachment
from sctwas.tools.result_contract import (
    assess_training, assess_twas, atomic_status, progress_for, task_id,
    TWAS_COLUMNS, inspect_twas, safe_child,
)

logger = logging.getLogger(__name__)


class _ResultWorker(threading.Thread):
    """Shared task contract with private-spool and legacy-thread executors."""

    def _initialize(self, tag, emailto, name_task, suffix):
        threading.Thread.__init__(self)
        self.tag = task_id(tag)
        self.taskname = name_task or self.tag
        self.emailto = emailto or ''
        root = task_root()
        self.input = safe_child(root, 'upload/' + tag + suffix)
        self.output = result_directory(tag)

    def run(self):
        close_old_connections()
        result = {'kind': self.kind, 'state': 'failed', 'reason': 'worker_exception', 'artifacts': []}
        try:
            atomic_status(self.output, {'kind': self.kind, 'state': 'running', 'parameters': self.parameters()})
            cwd = os.path.dirname(os.path.abspath(__file__))
            with open(os.path.join(self.output, 'runner.log'), 'ab') as log:
                process = subprocess.Popen(self.command(), cwd=cwd, stdout=log, stderr=subprocess.STDOUT)
                returncode = process.wait()
            result = self.assess(returncode)
            # Both upstream programs can catch per-gene exceptions and still exit zero.
            if result['state'] in ('success', 'no_hits', 'empty_result'):
                paths = [os.path.join(self.output, 'runner.log')]
                if self.kind == 'twas':
                    paths.append(safe_child(self.output, 'logs/' + self.chrom.upper() + '_sumstat_TWAS_log.txt'))
                failures = 0
                for path in paths:
                    if not os.path.isfile(path):
                        continue
                    with open(path, 'rb') as log:
                        failures += sum(any(mark in line for mark in
                                            (b'lassosum failed', b'SDPR failed', b'Traceback (most recent call last)',
                                             b'Caught an exception for num=')) for line in log)
                if failures:
                    result.update(state='failed' if result['state'] == 'empty_result' else 'partial', reason='upstream_failure_messages',
                                  upstream_failure_messages=failures)
        except Exception:
            logger.exception('scTWAS worker failed')
        finally:
            try:
                result['parameters'] = self.parameters()
                atomic_status(self.output, result)
                Task.objects.filter(field_id=self.tag).update(
                    last_edit_timestamp=timezone.now(), progress=progress_for(result['state']))
            finally:
                close_old_connections()
        # Notification failure cannot change scientific completion status.
        if self.emailto and result['state'] in ('success', 'no_hits'):
            try:
                sendEmailWithAttachment(mailto=self.emailto,
                                        info='Task {0}: {1}.'.format(self.tag, result['state']),
                                        list_attachment=self.attachments(result))
            except Exception:
                logger.exception('scTWAS completion notification failed')

    def start_recorded(self):
        """Record launch failures as terminal failures before returning to the caller."""
        try:
            atomic_status(self.output, {'kind': self.kind, 'state': 'queued', 'parameters': self.parameters()})
            if getattr(settings, 'SCTWAS_EXECUTOR', 'thread') == 'spool':
                from sctwas.tools.spool import enqueue
                enqueue(task_root(), self.tag, self.kind, self.parameters(), self.input)
            else:
                self.start()
        except Exception:
            Task.objects.filter(field_id=self.tag).update(last_edit_timestamp=timezone.now(), progress=-1)
            try:
                atomic_status(self.output, {'kind': self.kind, 'state': 'failed', 'reason': 'launch_failed',
                                           'parameters': self.parameters(), 'artifacts': []})
            except Exception:
                logger.exception('scTWAS launch status could not be written')
            logger.exception('scTWAS thread could not be started')
            return False
        return True

    def attachments(self, result):
        return [safe_child(self.output, item['path']) for item in result['artifacts']]


class QueryGroupDataFromDB(_ResultWorker):
    kind = 'twas'

    def __init__(self, tag, emailto, name_task, chrom, celltype, collection, thres,
                 window, weight, reference, population, ztest):
        self._initialize(tag, emailto, name_task, '.txt.gz')
        self.chrom, self.celltype, self.collection = chrom, celltype, collection
        self.thres, self.window, self.weight = thres, window, weight
        self.reference, self.population, self.ztest = reference, population, ztest

    def parameters(self):
        return {key: getattr(self, key) for key in
                ('chrom', 'celltype', 'collection', 'thres', 'window', 'weight', 'reference', 'population', 'ztest')}

    def command(self):
        return ['bash', 'csTWASweb.sh', self.input, self.output, self.chrom, self.celltype,
                self.collection, str(self.thres), str(self.window), str(self.weight),
                self.reference, self.population, self.ztest]

    def assess(self, returncode):
        return assess_twas(self.output, self.chrom, self.thres, returncode, method=self.ztest)

    def attachments(self, result):
        path = safe_child(self.output, result['artifacts'][0]['path'])
        rows = inspect_twas(path, self.thres, single_method=self.ztest, expected_chrom=self.chrom)['data']
        selected = os.path.join(self.output, 'selected.tsv')
        with open(selected, 'wb') as handle:
            for row in [dict(zip(TWAS_COLUMNS, TWAS_COLUMNS))] + rows:
                handle.write(('\t'.join(row[key] for key in TWAS_COLUMNS) + '\n').encode('utf-8'))
        return [selected]


class QueryGroupDataFromTrain(_ResultWorker):
    kind = 'grex'

    def __init__(self, tag, emailto, name_task, chrom, reference, population, train):
        self._initialize(tag, emailto, name_task, '.tsv')
        self.chrom, self.reference, self.population, self.train = chrom, reference, population, train

    def parameters(self):
        values = {key: getattr(self, key) for key in ('chrom', 'reference', 'population', 'train')}
        values['random_seed'] = os.environ.get('SCTWAS_RANDOM_SEED')
        return values

    def command(self):
        return ['bash', 'csTWASwebTrain.sh', self.input, self.output, self.chrom,
                self.reference, self.population, self.train]

    def assess(self, returncode):
        return assess_training(self.output, self.train, returncode)
