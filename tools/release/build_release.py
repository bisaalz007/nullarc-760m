#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Assemble a release from the verified source-built stack; never read installed drivers/EFI."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
from package_manifest import verify, write, digest

def git(*args,cwd=ROOT):
    return subprocess.check_output(['git','-C',str(cwd),*args])

def zip_tree(source,path,prefix):
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED,compresslevel=6,strict_timestamps=False) as z:
        for p in sorted(source.rglob('*')):
            if p.is_symlink(): raise ValueError('release symlinks are unsupported')
            if p.is_file(): z.write(p,Path(prefix)/p.relative_to(source))
    with zipfile.ZipFile(path) as z:
        if z.testzip() is not None: raise ValueError('ZIP CRC verification failed')

def assemble(a):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,79}',a.version) or '..' in a.version:
        raise ValueError('invalid release version')
    stack=verify(a.stack)
    fixtures=None
    if stack.get('experimental_hp_bootstrap') is True:
        fixture_root=ROOT/'build/metal-stack-test'
        fixtures=json.loads((fixture_root/'fixture-receipt.json').read_text())
        if fixtures.get('independent_spirv_validation') is not True or fixtures.get('gpu_commands_submitted')!=0:
            raise ValueError('missing offline fixture validation')
        for name,sha in fixtures['inputs'].items():
            if digest(a.stack/name)!=sha:raise ValueError('shader fixture runtime inputs differ; rerun test_metal_stack')
        for name,sha in fixtures['shaders'].items():
            if digest(fixture_root/name)!=sha:raise ValueError('shader fixture differs')
    commit=git('rev-parse','HEAD').decode().strip()
    if git('status','--porcelain'): raise ValueError('commit source changes before assembling a release')
    if stack.get('source_commit')!=commit: raise ValueError('stack source commit differs from checkout')
    if git('rev-parse','HEAD',cwd=a.mesa).decode().strip()!=stack['mesa_commit'] or git('status','--porcelain',cwd=a.mesa):
        raise ValueError('Mesa source differs from the built stack receipt')
    required=('install.sh','uninstall.sh','INSTALL.md','install_diagnostics.py','collect_macos_evidence.py',
              'LICENSES/LICENSE.amdgpu.txt','sources/nvmtl-translator-source.tar.gz')
    for name in required:
        if not (a.stack/name).is_file(): raise ValueError(f'incomplete installer stack: {name}')
    expected=json.loads((ROOT/'hardware/dumps/hp_envy_760m/linux-2026-11-08.json').read_text())['decompressed_firmware_files']
    for item in expected:
        f=a.firmware/item['name']
        if not f.is_file() or digest(f)!=item['sha256']: raise ValueError(f'firmware differs from measured set: {f.name}')
    # Validate the whole set with the actual compiled parser before copying any output.
    subprocess.run([str(a.stack/'gpu/phxctl/phxfw'),'--phoenix-plan',str(a.firmware)],check=True,capture_output=True)
    dest=a.output.resolve()
    if dest.exists(): raise ValueError('output exists; choose a new directory')
    dest.parent.mkdir(parents=True,exist_ok=True)
    name='nullarc-760m-'+a.version
    with tempfile.TemporaryDirectory(prefix='.nullarc-release-',dir=dest.parent) as tmp:
        tmp=Path(tmp);p=tmp/name;shutil.copytree(a.stack,p)
        fw=p/'gpu/fw';fw.mkdir()
        if fixtures:
            validation=p/'validation';validation.mkdir()
            for source,target in [('store.spv','store.spv'),('triangle_vertex.spv','vertex.spv'),('solid_fragment.spv','fragment.spv')]:
                shutil.copy2(ROOT/'build/metal-stack-test'/source,validation/target)
            shutil.copy2(ROOT/'build/metal-stack-test/fixture-receipt.json',validation/'fixture-receipt.json')
        for item in expected:shutil.copy2(a.firmware/item['name'],fw/item['name'])
        (fw/'manifest.json').write_text(json.dumps({'source':'HP Linux Mint linux-firmware 20240318.git3b128b60-0ubuntu2.22',
            'files':expected,'runtime_compatibility_verified':False},indent=2)+'\n')
        (p/'sources/nullarc-source.tar.gz').write_bytes(git('archive','--format=tar.gz','--prefix=nullarc-760m-source/',commit))
        (p/'sources/mesa-darwin-phoenix.patch').write_bytes(git('diff','f5cb8ee032adabef599ae892ec4e42d796b84da9','HEAD',cwd=a.mesa))
        (p/'README.txt').write_text(f'NullArc Radeon 760M {a.version} development prerelease\n'
            f'Source commit: {commit}\nRead INSTALL.md before running install.sh.\n'
            'HP build 39 passed native and public Metal compute/render; WindowServer unverified.\n'
            'Default diagnostic boot; explicit bootstrap or opt-in app-only boot service.\n'
            'Includes AMD firmware under LICENSES/LICENSE.amdgpu.txt; no automatic activation.\n')
        metadata={k:v for k,v in stack.items() if k not in ('files','format','policy','acceleration_verified')}
        metadata.update(release_version=a.version,firmware_included=True,
                        firmware_loading_enabled_on_hp=stack.get('experimental_hp_bootstrap') is True,release_kind='development-prerelease')
        write(p,metadata);verify(p)
        bundle=tmp/(name+'.zip');zip_tree(p,bundle,name)
        kext=tmp/('PhxBringup.kext-'+a.version+'.zip')
        zip_tree(p/'EFI/OC/Kexts/PhxBringup.kext',kext,'PhxBringup.kext')
        source=tmp/'nvmtl-translator-source.tar.gz';shutil.copy2(p/'sources/nvmtl-translator-source.tar.gz',source)
        assets=[bundle,kext,source]
        (tmp/'SHA256SUMS').write_text(''.join(f'{digest(f)}  {f.name}\n' for f in assets))
        (tmp/'RELEASE_NOTES.md').write_text(f'''## Radeon 760M development prerelease

Built from [`{commit[:12]}`](https://github.com/yt42c2mvn2-cmd/nullarc-760m/commit/{commit})
on the development branch. Download **{bundle.name}** for compiled binaries;
GitHub's automatic source archives follow the existing `alpha` tag and are not
the binary installer. Matching driver source is inside the binary ZIP under
`sources/nullarc-source.tar.gz`; translator source is also attached separately.

The ZIP includes the source-built kexts, Metal plugin, translator, patched RADV,
seven command-line tools, AMD firmware, installer/uninstaller, checksums and licenses.
Use `INSTALL.md` from the extracted ZIP. Noncommercial terms apply to components
derived from NullMoth; see the included license notices.

**HP Radeon 760M macOS acceleration is not functional or runtime-verified.**
`sudo ./install.sh --windowserver` is included but refuses the diagnostic HP path.
For HP diagnostics use:

```sh
./install.sh --diagnostics --oc /Volumes/EFI/EFI/OC --check
sudo ./install.sh --diagnostics --oc /Volumes/EFI/EFI/OC
```

Supply your actual EFI/OC path. This mode preserves boot/security settings and
does not install an accelerator or enable WindowServer. HP Sequoia build-37
firmware/scanout captures and CPU translation/compiler tests passed. This packaged
build-38 kext and its PSP changes have not been runtime-tested; no macOS GPU
execution or accelerated display is verified. Linux shader readback success is
separate from macOS bring-up. No Apple software or personal EFI is distributed.
''')
        # Publish the directory atomically after payload/ZIP verification.
        stage=tmp/'ready';stage.mkdir()
        for f in assets+[tmp/'SHA256SUMS',tmp/'RELEASE_NOTES.md']:f.rename(stage/f.name)
        stage.rename(dest)
    print(json.dumps({'output':str(dest),'source_commit':commit,'zip':bundle.name,'hp_policy':'diagnostic-only'}))

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--version',required=True);ap.add_argument('--stack',type=Path,required=True)
    ap.add_argument('--firmware',type=Path,required=True);ap.add_argument('--mesa',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
    a.stack=a.stack.resolve();a.firmware=a.firmware.resolve();a.mesa=a.mesa.resolve()
    try:assemble(a)
    except (ValueError,OSError,subprocess.CalledProcessError) as e:ap.exit(1,f'release: {e}\n')

if __name__=='__main__':main()
