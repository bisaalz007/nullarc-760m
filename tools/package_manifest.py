#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Hash and validate the exact files in a development package."""
import argparse
import hashlib
import json
from pathlib import Path

NAME = 'package-manifest.json'


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def inventory(root):
    files = {}
    for path in sorted(root.rglob('*')):
        if path.is_symlink():
            raise ValueError(f'symlinks are not permitted: {path}')
        if path.is_file() and path != root / NAME:
            files[path.relative_to(root).as_posix()] = digest(path)
    return files


def write(root, metadata):
    policy='hp-experimental-bootstrap' if metadata.get('experimental_hp_bootstrap') is True else 'hp-diagnostic-only'
    document = dict(metadata, format=1, policy=policy, acceleration_verified=False,
                    files=inventory(root))
    (root / NAME).write_text(json.dumps(document, indent=2, sort_keys=True) + '\n')


def verify(root):
    document = json.loads((root / NAME).read_text())
    if document.get('format') != 1 or document.get('policy') not in ('hp-diagnostic-only','hp-experimental-bootstrap') or document.get('acceleration_verified') is not False:
        raise ValueError('unsupported package policy or acceleration claim')
    if document.get('policy')=='hp-experimental-bootstrap' and document.get('bootstrap_requires_local_admin') is not True:
        raise ValueError('experimental bootstrap requires explicit local administrator policy')
    files = document.get('files')
    if not isinstance(files, dict) or not files or inventory(root) != files:
        raise ValueError('package file inventory or hashes differ')
    return document


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('package', type=Path)
    a = ap.parse_args()
    try:
        d = verify(a.package.resolve())
        print(f'verified {len(d["files"])} files; {d["policy"]}, acceleration unverified')
    except (ValueError, OSError) as e:
        ap.exit(1, f'{e}\n')
