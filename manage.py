#!/usr/bin/env python3
"""Initialize and serve a local read-only scTWAS example installation."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import secrets
import shutil
import sqlite3
import tempfile


ROOT = Path(__file__).resolve().parent
EXAMPLE_TASK = '00000000000000000000000000000001'


def read_json(path):
    return json.loads(path.read_text())


def insert(connection, table, columns, records):
    fields = ','.join('"' + name + '"' for name in columns)
    placeholders = ','.join('?' for _ in columns)
    connection.executemany('INSERT INTO "' + table + '" (' + fields + ') VALUES (' + placeholders + ')', records)


def initialize(state):
    state.parent.mkdir(parents=True, exist_ok=True)
    if state.exists():
        raise FileExistsError('Choose a new state directory')
    staging = Path(tempfile.mkdtemp(prefix=state.name + '-', dir=state.parent))
    try:
        database = staging / 'catalogue.sqlite3'
        with sqlite3.connect(database) as connection:
            connection.executescript((ROOT/'setup/schema.sqlite.sql').read_text())
            tables = (
                ('models', 'celltype', ['majortype','subtype','condition','celltypeid','collectionid','studyid'],
                 ['majortype','subtype','condition','celltypeID','collectionID','studyID']),
                ('traits', 'trait', ['phecode','description','icd10','n','n_case','n_control','ratio','url'],
                 ['pheCode','description','ICD10','N','N_case','N_control','ratio','url']),
                ('studies', 'study', ['studyid','title','method','sample','journal','year','doi','authors','samplesize','modelsize'],
                 ['studyID','title','method','sample','journal','year','doi','authors','sampleSize','modelSize']),
                ('genes', 'gene', ['CHROM','GeneStart','GeneEnd','TargetID','GeneName'],
                 ['chrom','geneStart','geneEnd','ensemblID','geneName']),
                ('associations', 'twas', ['ensemblid','phecode','n_snps','fusion_z','fusion_pval','spred_z','spred_pval','celltype','collectionid'],
                 ['ensemblID','pheCode','n_snps','FUSION_Z','FUSION_PVAL','SPred_Z','SPred_PVAL','celltype','collectionID']),
            )
            for filename, table, keys, columns in tables:
                rows = read_json(ROOT/'examples/catalogue'/(filename + '.json'))
                insert(connection, table, columns, [[row[key] for key in keys] for row in rows])
            now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat(sep=' ')
            insert(connection,'task',['_id','progress','name','mail','create_timestamp','last_edit_timestamp'],
                   [[EXAMPLE_TASK,100,'Saved chromosome 22 example','',now,now]])
        destination = staging/'tasks/result'/EXAMPLE_TASK
        destination.mkdir(parents=True)
        status = read_json(ROOT/'examples/ukb4118/saved-parameters.json')
        from sctwas.tools.result_contract import CONTRACT_VERSION
        # The demo reconstructs a read-only status wrapper around the saved output.
        status.update(contract_version=CONTRACT_VERSION, returncode=0)
        output = destination/status['artifacts'][0]['path']
        output.parent.mkdir(parents=True)
        shutil.copyfile(ROOT/'examples/ukb4118/scTWASdb_Table_S2_source.tsv',output)
        (destination/'status.json').write_text(json.dumps(status,indent=2)+'\n')
        config = {
            'SECRET_KEY':secrets.token_urlsafe(48),
            'DATABASE':{'ENGINE':'django.db.backends.sqlite3','NAME':str(state/'catalogue.sqlite3')},
            'ALLOWED_HOSTS':['localhost','127.0.0.1'],'HTTPS':False,'READ_ONLY_DEMO':True,
            'STATIC_ROOT':str(state/'static'),'STATIC_URL':'/static/',
            'SCTWAS_RELEASE':'source-20261121.1','SCTWAS_DATA_VERSION':'example-catalogue',
            'SCTWAS_TASK_ROOT':str(state/'tasks'),'SCTWAS_EXPORT_ROOT':str(state/'exports'),
            'SCTWAS_QUERY_CACHE_ROOT':str(state/'query-cache'),
            'MAIL':{'BACKEND':'django.core.mail.backends.locmem.EmailBackend'},
        }
        (staging/'config.json').write_text(json.dumps(config,indent=2)+'\n')
        (staging/'config.json').chmod(0o600)
        (staging/'catalogue.sqlite3').chmod(0o600)
        staging.rename(state)
    except BaseException:
        shutil.rmtree(staging,ignore_errors=True)
        raise
    print('Initialized a read-only catalogue and saved-result example.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('init', 'check', 'run'))
    parser.add_argument('--state', type=Path, default=Path('runtime'))
    parser.add_argument('--port', type=int, default=8000)
    args = parser.parse_args()
    state = args.state.expanduser().resolve()
    if state == ROOT:
        parser.error('State must have its own directory')
    os.umask(0o077)
    if args.operation == 'init':
        initialize(state)
        return
    os.environ['SCTWAS_RUNTIME_CONFIG'] = str(state/'config.json')
    os.environ['DJANGO_SETTINGS_MODULE'] = 'sctwas.deployment.settings'
    import django
    django.setup()
    from django.core.management import call_command
    if args.operation == 'check':
        call_command('check')
        return
    from django.contrib.staticfiles.handlers import StaticFilesHandler
    from django.core.wsgi import get_wsgi_application
    from socketserver import ThreadingMixIn
    from wsgiref.simple_server import WSGIServer, make_server

    class Server(ThreadingMixIn, WSGIServer):
        daemon_threads = True

    print('Serving the read-only example at http://127.0.0.1:' + str(args.port), flush=True)
    with make_server('127.0.0.1', args.port, StaticFilesHandler(get_wsgi_application()), server_class=Server) as server:
        server.serve_forever()


if __name__ == '__main__':
    main()
