# -*- coding: utf-8 -*-
"""Private task storage, with read-only lookup of historical static results."""
from __future__ import unicode_literals
import os

from django.conf import settings
from sctwas.tools.result_contract import safe_child, task_id


def legacy_root():
    return os.path.join(settings.STATIC_ROOT, 'sctwas', 'source')


def task_root():
    return os.path.abspath(getattr(settings, 'SCTWAS_TASK_ROOT', None) or legacy_root())


def upload_root():
    return safe_child(task_root(), 'upload')


def result_directory(tag, existing=False):
    tag = task_id(tag)
    current = safe_child(task_root(), 'result/' + tag)
    if existing and not os.path.isdir(current):
        historical = safe_child(legacy_root(), 'result/' + tag)
        if os.path.isdir(historical):
            return historical
    return current
