"""Build deterministic bundles from the repository's existing vendored assets.

Run: python -m sctwas.research.build_assets [--check]
No network, package upgrades, minifier, or scientific result transformations.
"""
from __future__ import print_function
import hashlib
import json
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static', 'sctwas'))
PLUGIN = 'AdminLTE-3.2.0/plugins/'
BUNDLES = {
    'base.css': ['AdminLTE-3.2.0/dist/css/adminlte.min.css'],
    'theme.css': ['css/science.css'],
    'tables.css': [PLUGIN + path for path in ['datatables-bs4/css/dataTables.bootstrap4.min.css',
        'datatables-responsive/css/responsive.bootstrap4.min.css', 'datatables-buttons/css/buttons.bootstrap4.min.css']],
    'base.js': [PLUGIN + path for path in ['jquery/jquery.min.js', 'bootstrap/js/bootstrap.bundle.min.js']] + ['js/ui.js'],
    'tables.js': [PLUGIN + path for path in ['datatables/jquery.dataTables.min.js', 'datatables-bs4/js/dataTables.bootstrap4.min.js',
        'datatables-responsive/js/dataTables.responsive.min.js', 'datatables-responsive/js/responsive.bootstrap4.min.js']],
    'exports.js': [PLUGIN + path for path in ['datatables-buttons/js/dataTables.buttons.min.js',
        'datatables-buttons/js/buttons.bootstrap4.min.js', 'datatables-buttons/js/buttons.html5.min.js']],
}


def build(check=False):
    target = os.path.join(ROOT, 'bundles')
    if not os.path.isdir(target):
        os.makedirs(target)
    manifest = {}
    for name, sources in sorted(BUNDLES.items()):
        parts, checksums = [], {}
        for source in sources:
            with open(os.path.join(ROOT, source), 'rb') as handle:
                content = handle.read()
            checksums[source] = hashlib.sha256(content).hexdigest()
            if source == 'AdminLTE-3.2.0/dist/css/adminlte.min.css':
                # This vendored build puts the complete Bootstrap 4.6.1 CSS
                # before AdminLTE's first animation. Keep all Bootstrap states,
                # breakpoints and print rules, not a DOM-derived selector purge.
                marker = b'@-webkit-keyframes flipInX'
                assert content.count(marker) == 1 and b'Bootstrap v4.6.1' in content
                content = content.split(marker)[0]
                assert content.rstrip().endswith(b'}}') and b'.table .thead-dark th' in content

            # A source-map path in a concatenated file no longer has its original base.
            content = re.sub(br'//# sourceMappingURL=[^\r\n]*', b'', content)
            if name.endswith('.css'):
                urls = re.findall(br'url\((.*?)\)', content)
                assert all(value.strip(b'\"\' ').startswith(b'data:') for value in urls), source
            parts.append(b'/* Source: ' + source.encode('ascii') + b' */\n' + content)
        content = (b'\n;\n' if name.endswith('.js') else b'\n').join(parts) + b'\n'
        path = os.path.join(target, name)
        if check:
            with open(path, 'rb') as handle:
                assert handle.read() == content, 'Rebuild stale bundle: ' + name
        else:
            with open(path, 'wb') as handle:
                handle.write(content)
        manifest[name] = dict(bytes=len(content), sha256=hashlib.sha256(content).hexdigest(), sources=checksums)
    encoded = (json.dumps(manifest, sort_keys=True, indent=2) + '\n').encode('ascii')
    path = os.path.join(target, 'manifest.json')
    if check:
        with open(path, 'rb') as handle:
            assert handle.read() == encoded, 'Rebuild stale bundle manifest'
    else:
        with open(path, 'wb') as handle:
            handle.write(encoded)
    print(json.dumps({name: value['bytes'] for name, value in manifest.items()}, sort_keys=True))


if __name__ == '__main__':
    build('--check' in sys.argv)
