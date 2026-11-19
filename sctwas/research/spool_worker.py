#!/usr/bin/env python3
"""One durable scientific executor for a private spool on another owned node.

The web node stores queued jobs before acknowledging submissions. The executor
holds a local lock, claims a remote lease, checks input/output SHA-256 and sends
heartbeats. Expired tasks fail explicitly; they are never silently recomputed.
"""
import argparse
import fcntl
import json
import os
from pathlib import Path
import shlex
import signal
import subprocess
import tarfile
import time

from sctwas.tools.result_contract import assess_training, assess_twas, sha256, task_id


class Worker:
    def __init__(self, args):
        self.args = args
        self.ssh = ['ssh', '-T', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10',
                    '-o', 'ServerAliveInterval=10', '-o', 'ServerAliveCountMax=2', args.host]
        self.scp = ['scp', '-q', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10']
        environment = [
            'env', 'PYTHONPATH=' + args.remote_release + ':' + args.remote_project,
            'DJANGO_SETTINGS_MODULE=' + getattr(args, 'remote_settings', 'sctwas.deployment.settings'),
            'SCTWAS_TASK_ROOT=' + args.remote_root]
        if getattr(args, 'remote_config', None):
            environment.append('SCTWAS_RUNTIME_CONFIG=' + args.remote_config)
        self.remote_command = ' '.join(shlex.quote(x) for x in environment + [
            getattr(args, 'remote_python', 'python3'), '-B',
            '-m', 'sctwas.research.spool_control', '--root', args.remote_root])
        self.root = Path(args.work_root)
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)

    def rpc(self, action, **values):
        message = dict(action=action, worker=self.args.worker, **values)
        completed = subprocess.run(self.ssh + [self.remote_command], input=json.dumps(message),
                                   text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=45)
        if completed.returncode:
            raise RuntimeError('Queue operation failed: ' + action)
        return json.loads(completed.stdout)

    def transfer(self, source, destination):
        subprocess.run(self.scp + [source, destination], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=180)

    @staticmethod
    def stop(process):
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=10)

    def execute(self, job):
        tag, lease = task_id(job['tag']), task_id(job['lease'])
        kind, params = job['kind'], job['parameters']
        suffix = '.txt.gz' if kind == 'twas' else '.tsv'
        if kind not in ('twas', 'grex') or job['input_name'] != tag + suffix:
            raise ValueError('Invalid job input')
        directory = self.root / (tag + '.' + lease)
        directory.mkdir(mode=0o700)
        output = directory / 'result'
        output.mkdir(mode=0o700)
        source = directory / ('input' + suffix)
        result = {'kind': kind, 'state': 'failed', 'reason': 'executor_error', 'artifacts': []}
        process = None
        try:
            self.transfer(self.args.host + ':' + self.args.remote_root + '/upload/' + job['input_name'], str(source))
            if sha256(str(source)) != job['input_sha256']:
                raise ValueError('Input checksum mismatch')
            tools = Path(__file__).resolve().parents[1] / 'tools'
            if kind == 'twas':
                values = [params[key] for key in ('chrom', 'celltype', 'collection', 'thres', 'window', 'weight', 'reference', 'population', 'ztest')]
                command = ['bash', str(tools / 'csTWASweb.sh'), str(source), str(output)] + [str(x) for x in values]
            else:
                values = [params[key] for key in ('chrom', 'reference', 'population', 'train')]
                command = ['bash', str(tools / 'csTWASwebTrain.sh'), str(source), str(output)] + [str(x) for x in values]
            started = last_heartbeat = time.monotonic()
            environment = os.environ.copy()
            if params.get('random_seed') is not None:
                environment['SCTWAS_RANDOM_SEED'] = str(params['random_seed'])
            with (output / 'runner.log').open('wb') as log:
                process = subprocess.Popen(command, cwd=str(tools), stdout=log,
                                           stderr=subprocess.STDOUT, start_new_session=True, env=environment)
                while process.poll() is None:
                    if time.monotonic() - started > self.args.timeout:
                        self.stop(process)
                        raise TimeoutError('Scientific job exceeded its time budget')
                    if time.monotonic() - last_heartbeat > 15:
                        self.rpc('heartbeat', tag=tag, lease=lease)
                        last_heartbeat = time.monotonic()
                    time.sleep(.5)
            if kind == 'twas':
                result = assess_twas(str(output), params['chrom'], params['thres'], process.returncode, method=params['ztest'])
            else:
                result = assess_training(str(output), params['train'], process.returncode)
            markers = (b'lassosum failed', b'SDPR failed',
                       b'Traceback (most recent call last)', b'Caught an exception for num=')
            failures = 0
            for log in [output / 'runner.log'] + list((output / 'logs').glob('*_TWAS_log.txt')):
                with log.open('rb') as handle:
                    failures += sum(any(marker in line for marker in markers) for line in handle)
            if failures and result['state'] in ('success', 'no_hits', 'empty_result'):
                result.update(state='failed' if result['state'] == 'empty_result' else 'partial',
                              reason='upstream_failure_messages', upstream_failure_messages=failures)
        except Exception as error:
            if process:
                self.stop(process)
            result.update(state='failed', reason='executor_' + type(error).__name__)
        finally:
            if process:
                self.stop(process)
        result['parameters'] = params
        result['input_sha256'] = job['input_sha256']
        (directory / 'completion.json').write_text(json.dumps(result, indent=2))
        archive = directory / 'artifacts.tar.gz'
        paths = [output / item['path'] for item in result.get('artifacts', [])]
        paths += [path for path in [output / 'runner.log'] if path.is_file()]
        with tarfile.open(str(archive), 'w:gz') as handle:
            for path in paths:
                handle.add(str(path), arcname=str(path.relative_to(output)), recursive=False)
        # Renew before transfer. A lost lease must not overwrite a newer status.
        self.rpc('heartbeat', tag=tag, lease=lease)
        self.transfer(str(archive), self.args.host + ':' + self.args.remote_root + '/incoming/' + tag + '.' + lease + '.tar.gz')
        response = self.rpc('finish', tag=tag, lease=lease, archive=True, status=result)
        print(json.dumps({'event': 'completed', 'task': tag, 'state': result['state'],
                          'database_updated': response.get('database_updated', False)}), flush=True)
        return result

    def run(self):
        with (self.root / 'worker.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            while True:
                try:
                    response = self.rpc('claim')
                    if response['job']:
                        self.execute(response['job'])
                        if self.args.once:
                            return
                    elif self.args.once:
                        return
                    else:
                        time.sleep(5)
                except Exception as error:
                    print(json.dumps({'event': 'worker_error', 'type': type(error).__name__}), flush=True)
                    if self.args.once:
                        raise
                    time.sleep(10)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['host', 'remote-release', 'remote-project', 'remote-root', 'work-root']:
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--remote-python', default='python3')
    parser.add_argument('--remote-settings', default='sctwas.deployment.settings')
    parser.add_argument('--remote-config', help='Private runtime JSON path on the Web node')
    parser.add_argument('--worker', default='scientific-worker')
    parser.add_argument('--timeout', type=int, default=21600)
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    os.umask(0o077)
    Worker(args).run()


if __name__ == '__main__':
    main()
