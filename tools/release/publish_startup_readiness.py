#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Publish a separate, verified startup-only repair of the 760M Sequoia beta.

Start from the signed-off fresh-files ZIP; keep all compiled native drivers,
firmware, translator, and RADV byte-identical. Only the bounded ioreg startup
reader and its strictly reviewed recovery action are overlaid.
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
from package_manifest import verify,write,inventory,digest
from publish_persistent_windowserver import (
    RELEASE,extract_trusted_zip,verify_original_archive,git,
)

SOURCE_COMMIT='776fd94491946e6a15162b58f4f95adcf8d0add9'
PERSISTENCE_COMMIT='5de9ab4221a5af7af20723b9c2bc1faf5ffa4b64'
OVERLAY={
    'tools/phxctl/hp_bringup.py':'gpu/phxctl/hp_bringup.py',
    'install/recover_hp_boot.py':'recover_hp_boot.py',
}
SUFFIX='-startup-readiness'


def assemble(original,checksums,output):
    verify_original_archive(original,checksums)
    if output.exists():
        raise ValueError('choose a new output directory')
    if original.name!=RELEASE+'-fresh-files.zip':
        raise ValueError('startup hotfix requires the published fresh-files baseline')
    commit=git('rev-parse','HEAD').decode().strip()
    with tempfile.TemporaryDirectory(prefix='nullarc-startup-readiness-') as td:
        package=extract_trusted_zip(original,Path(td))
        baseline=verify(package)
        if (baseline.get('source_commit')!=SOURCE_COMMIT
                or baseline.get('startup_patch_commit')!=PERSISTENCE_COMMIT
                or baseline.get('release_version')!='0.2.0-sequoia-beta'
                or not baseline.get('fresh_installer_patch_commit')):
            raise ValueError('unexpected baseline or compiled GPU provenance')
        original_files=inventory(package)
        changed=set()
        source_archive=package/'sources/startup-readiness-source.tar.gz'
        if source_archive.exists():
            raise ValueError('startup readiness archive already present')
        with tarfile.open(source_archive,'w:gz') as tar:
            for source,target in sorted(OVERLAY.items()):
                payload=git('show',f'{commit}:{source}')
                dest=package/target
                if not dest.is_file():
                    raise ValueError('missing expected startup file '+target)
                dest.write_bytes(payload)
                changed.add(target)
                item=tarfile.TarInfo('nullarc-startup-readiness/'+source)
                item.mode=0o644;item.mtime=0;item.size=len(payload)
                tar.addfile(item,io.BytesIO(payload))
        changed.add('sources/startup-readiness-source.tar.gz')
        new_files=inventory(package)
        for name,sha in original_files.items():
            if name not in changed and new_files.get(name)!=sha:
                raise ValueError('unexpected native or other asset change: '+name)
        if set(new_files)-set(original_files)!={'sources/startup-readiness-source.tar.gz'}:
            raise ValueError('unexpected new file inventory')
        metadata={k:v for k,v in baseline.items()
                  if k not in ('format','files','policy','acceleration_verified')}
        metadata['startup_readiness_patch_commit']=commit
        metadata['startup_readiness_patch_type']='bounded registry wait and reviewed recovery; compiled drivers unchanged'
        write(package,metadata)
        verify(package)
        output.mkdir(parents=True)
        zip_path=output/(RELEASE+SUFFIX+'.zip')
        with zipfile.ZipFile(zip_path,'w',zipfile.ZIP_DEFLATED,compresslevel=6,strict_timestamps=False) as z:
            for node in sorted(package.rglob('*')):
                if node.is_symlink():
                    raise ValueError('symlink inside package')
                if node.is_file():
                    z.write(node,Path(RELEASE)/node.relative_to(package))
        with zipfile.ZipFile(zip_path) as z:
            if z.testzip() is not None:
                raise ValueError('new ZIP failed CRC validation')
        (output/'SHA256SUMS-startup-readiness').write_text(
            f'{digest(zip_path)}  {zip_path.name}\n')
        (output/'RELEASE_NOTES-startup-readiness.md').write_text(
            '# HP 760M automatic-boot ioreg readiness hotfix\n\n'
            f'Source patch: {commit}; compiled GPU binaries: {SOURCE_COMMIT}.\n\n'
            'Fixes an observed startup failure where the firmware entry-point command '
            'succeeded but an early PhxBringup IORegistry read raised Invalid file. '
            'A bounded 90-second retry now waits for a valid HP registry snapshot '
            'before any GPU initialization and records a distinct failure stage.\n\n'
            'The compiled GPU kexts, Metal plugin, translator, RADV and firmware '
            'are byte-for-byte unchanged from the published fresh-files beta. '
            'The previous release ZIPs are preserved.\n\n'
            'For the *exact* previously recorded Invalid file failure, reboot first '
            'to a new idle firmware-framebuffer diagnostic boot, keep pending and '
            'disabled markers intact, and extract this ZIP. From its directory run:\n\n'
            '  sudo python3 -B ./recover_hp_boot.py --package "$PWD" --after-registry-unavailable\n\n'
            'This action verifies the original and patched packages and the protected '
            'failure, checks for a new idle diagnostic boot and no display request, '
            'backs up the service and failure markers, and stages only a next-boot '
            'startup update. It does not initialize the GPU or arm WindowServer. '
            'Reboot with the same OpenCore EFI after successful staging, then inspect '
            '/Users/Shared/nullarc-hp-native-status.json. Do not retry initialization '
            'in the same boot or bypass refused safety checks.\n\n'
            'The timing hypothesis has regression tests, but this hotfix has not '
            'yet been validated on the actual HP. Confirm a successful app-mode '
            'Metal boot before attempting WindowServer persistence.\n'
        )
    return {'zip':zip_path.name,'sha256':digest(zip_path),'source_commit':commit}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--original',type=Path,required=True)
    parser.add_argument('--checksums',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(assemble(args.original,args.checksums,args.output)))


if __name__=='__main__':main()
