#!/usr/bin/env python
"""Foreground export worker for a process supervisor."""
from __future__ import print_function

import argparse
import os
import signal
import sys
import threading
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--settings-path', required=True, help='Directory containing the runtime settings package')
    args = parser.parse_args()
    sys.path.insert(0, args.settings_path)
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sctwas.deployment.settings')
    os.umask(0o077)
    import django
    django.setup()
    from django.db import connections
    from sctwas import export_queue as queue, export_store as store

    def terminate(signum, frame):
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, terminate)
    signal.signal(signal.SIGINT, terminate)
    stopped = threading.Event()
    heartbeat_path = os.path.join(store.root_directory(), 'export-worker.json')

    def heartbeat():
        while not stopped.is_set():
            store.write_json(heartbeat_path, dict(updated=time.time(), pid=os.getpid()))
            stopped.wait(10)

    with queue.worker_lock():
        queue.recover()
        # Publish the first heartbeat before serving new work.
        store.write_json(heartbeat_path, dict(updated=time.time(), pid=os.getpid()))
        monitor = threading.Thread(target=heartbeat)
        monitor.daemon = True
        monitor.start()
        last_maintenance = 0
        try:
            while True:
                if time.time() - last_maintenance >= 60:
                    queue.maintenance()
                    last_maintenance = time.time()
                # Reopen source connections after a long idle period or DB restart.
                connections.close_all()
                worked = queue.run_one()
                time.sleep(.25 if worked else 1)
        finally:
            stopped.set()
            monitor.join(2)
            store.write_json(heartbeat_path, dict(updated=0, pid=os.getpid()))
            connections.close_all()


if __name__ == '__main__':
    main()
