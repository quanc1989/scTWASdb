# -*- coding: utf-8 -*-
"""Private SSH queue control; run on the web node, never expose as HTTP."""
from __future__ import unicode_literals
import argparse
from contextlib import closing
import io
import json
import os
import sys
import tarfile

from sctwas.tools import spool
from sctwas.tools.result_contract import progress_for, safe_child, task_id


def receive(root, tag, lease):
    archive = safe_child(root, 'incoming/' + task_id(tag) + '.' + task_id(lease) + '.tar.gz')
    destination = safe_child(root, 'result/' + tag)
    spool.mkdir(destination)
    total = 0
    with tarfile.open(archive, 'r:gz') as handle:
        members = handle.getmembers()
        if len(members) > 100:
            raise ValueError('Too many output artifacts')
        seen = set()
        for member in members:
            total += member.size
            if not member.isfile() or member.name in seen or total > 1024 * 1024 * 1024:
                raise ValueError('Invalid output archive')
            seen.add(member.name)
            path = safe_child(destination, member.name)
            if os.path.basename(path) in ('status.json', 'job.json'):
                raise ValueError('State files cannot be supplied as artifacts')
            spool.mkdir(os.path.dirname(path))
            with closing(handle.extractfile(member)) as source, open(path, 'wb') as output:
                os.chmod(path, 0o600)
                while True:
                    chunk = source.read(1024 * 1024)
                    if not chunk:
                        break
                    output.write(chunk)
    os.unlink(archive)


def update_database(job, root):
    # This compatibility counter is secondary to the atomic result manifest.
    # Configuration is read on this host; no DB credentials cross the SSH channel.
    if not os.environ.get('DJANGO_SETTINGS_MODULE'):
        return {'database_updated': False}
    try:
        import django
        django.setup()
        from django.utils import timezone
        from django.db import close_old_connections
        from sctwas.models import Task
        Task.objects.filter(field_id=job['tag']).update(
            progress=progress_for(job['state']), last_edit_timestamp=timezone.now())
        task = Task.objects.get(field_id=job['tag'])
        notification = 'not_requested'
        if task.mail and job['state'] in ('success', 'no_hits'):
            try:
                from sctwas.tools.datautils import QueryGroupDataFromDB, QueryGroupDataFromTrain
                from sctwas.tools.mailutils import sendEmailWithAttachment
                parameters = dict(job['parameters'])
                parameters.pop('random_seed', None)
                cls = QueryGroupDataFromDB if job['kind'] == 'twas' else QueryGroupDataFromTrain
                worker = cls(tag=job['tag'], emailto=task.mail, name_task=task.name, **parameters)
                recorded = spool.read(safe_child(root, 'result/' + job['tag'] + '/status.json'))
                sendEmailWithAttachment(mailto=task.mail, info='Task {0}: {1}.'.format(job['tag'], job['state']),
                                        list_attachment=worker.attachments(recorded))
                notification = 'sent'
            except Exception:
                notification = 'failed'
        close_old_connections()
        return {'database_updated': True, 'notification': notification}
    except Exception as error:
        return {'database_updated': False, 'database_error_type': type(error).__name__}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True)
    args = parser.parse_args()
    message = json.loads(sys.stdin.read(1024 * 1024))
    action = message['action']
    worker = message['worker']
    if not worker or len(worker) > 80:
        raise ValueError('Invalid worker identity')
    if action == 'claim':
        response = {'job': spool.claim(args.root, worker)}
    elif action == 'heartbeat':
        spool.heartbeat(args.root, worker, message.get('tag'), message.get('lease'))
        response = {'ok': True}
    elif action == 'finish':
        # Check the lease before allowing any archive to replace result files.
        spool.heartbeat(args.root, worker, message['tag'], message['lease'])
        if message.get('archive'):
            receive(args.root, message['tag'], message['lease'])
        job = spool.finish(args.root, worker, message['tag'], message['lease'], message['status'])
        response = {'ok': True, 'state': job['state']}
        response.update(update_database(job, args.root))
    else:
        raise ValueError('Unknown queue operation')
    sys.stdout.write(json.dumps(response) + '\n')


if __name__ == '__main__':
    main()
