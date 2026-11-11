#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Add a separate fresh-file installer ZIP to the existing Sequoia beta release.

The original compiled binaries are unmodified: only the installer, instructions,
source patch archive, and package manifest are changed.
"""
import argparse
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import zipfile

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
from package_manifest import verify, write, inventory, digest
from publish_persistent_windowserver import (
    RELEASE, extract_trusted_zip, verify_original_archive, git,
)

EXPECTED_SOURCE_COMMIT='776fd94491946e6a15162b58f4f95adcf8d0add9'
EXPECTED_STARTUP_PATCH='5de9ab4221a5af7af20723b9c2bc1faf5ffa4b64'
OVERLAY={
    'install/install.sh':'install.sh',
    'install/install_components.py':'install_components.py',
    'docs/INSTALL.md':'docs/INSTALL.md',
}


def assemble(original,checksums,output):
    verify_original_archive(original,checksums)
    if output.exists():
        raise ValueError('choose a new output directory')
    commit=git('rev-parse','HEAD').decode().strip()
    with tempfile.TemporaryDirectory(prefix='nullarc-fresh-assets-') as td:
        package=extract_trusted_zip(original,Path(td))
        before=verify(package)
        if (before.get('source_commit')!=EXPECTED_SOURCE_COMMIT or
                before.get('startup_patch_commit')!=EXPECTED_STARTUP_PATCH or
                before.get('release_version')!='0.2.0-sequoia-beta'):
            raise ValueError('unexpected base release/compiled binary provenance')
        old=inventory(package)
        modified=set()
        source_dir=package/'sources'
        if not source_dir.is_dir():raise ValueError('missing sources directory')
        patch_archive=source_dir/'fresh-files-source.tar.gz'
        with tarfile.open(patch_archive,'w:gz') as tar:
            for source,target in OVERLAY.items():
                payload=git('show',f'{commit}:{source}')
                dst=package/target
                if not dst.is_file():raise ValueError('missing packaged installer file '+target)
                dst.write_bytes(payload)
                modified.add(target)
                entry=tarfile.TarInfo('nullarc-fresh-files/'+source)
                entry.size=len(payload);entry.mode=0o644;entry.mtime=0
                tar.addfile(entry,io.BytesIO(payload))
        modified.add('sources/fresh-files-source.tar.gz')
        guide=(package/'docs/INSTALL.md').read_text().replace(
            '](INSTALL_REFERENCE.md)','](docs/INSTALL_REFERENCE.md)')
        (package/'INSTALL.md').write_text(guide)
        modified.add('INSTALL.md')
        updated=inventory(package)
        for name,sha in old.items():
            if name not in modified and updated.get(name)!=sha:
                raise ValueError('unexpected change to original compiled asset: '+name)
        metadata={k:v for k,v in before.items()
                  if k not in ('files','format','policy','acceleration_verified')}
        metadata['fresh_installer_patch_commit']=commit
        metadata['fresh_installer_patch_type']='installer and docs only; native binaries unchanged'
        write(package,metadata)
        verify(package)
        output.mkdir(parents=True)
        bundle=output/(RELEASE+'-fresh-files.zip')
        with zipfile.ZipFile(bundle,'w',zipfile.ZIP_DEFLATED,compresslevel=6,strict_timestamps=False) as z:
            for p in sorted(package.rglob('*')):
                if p.is_symlink():raise ValueError('release symlink refused: '+str(p))
                if p.is_file():z.write(p,Path(RELEASE)/p.relative_to(package))
        with zipfile.ZipFile(bundle) as z:
            if z.testzip() is not None:raise ValueError('failed ZIP CRC verification')
        (output/'SHA256SUMS-fresh-files').write_text(f'{digest(bundle)}  {bundle.name}\n')
        (output/'RELEASE_NOTES-fresh-files.md').write_text(
            '# Fresh-file staging for NullArc 0.2.0 Sequoia beta\n\n'
            f'Installer change: {commit}. Original compiled GPU binaries: {EXPECTED_SOURCE_COMMIT}.\n\n'
            'Download the fresh-files ZIP and verify SHA256SUMS-fresh-files. Its '
            'native drivers, kexts, translator, RADV and firmware are exactly the '
            'same compiled files as the original beta; the earlier persistent '
            'WindowServer scripts are retained.\n\n'
            'The new sudo ./install.sh --fresh-files command creates a backup '
            'and stages a fresh copy of the native files on an idle HP diagnostic '
            'boot. A recognized old HP startup service is archived, not replaced '
            'with an automatically active new service. --check previews the '
            'operation. Neither mode removes failure markers or activates '
            'WindowServer. See INSTALL.md for required following stages and '
            'rollback.\n\n'
            '**Fresh-file staging is unverified on the actual HP.** This is not '
            'a one-step fresh accelerated desktop installer. A release binary '
            'may differ from a previously modified locally installed driver.\n')
    return {'zip':bundle.name,'sha256':digest(bundle),'commit':commit}


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--original',type=Path,required=True)
    ap.add_argument('--checksums',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    a=ap.parse_args()
    print(json.dumps(assemble(a.original,a.checksums,a.output)))


if __name__=='__main__':main()
