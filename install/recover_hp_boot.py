#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Backed-up next-boot update for the captured empty Metal catalogue failure.

Never retries initialization, submits GPU commands or changes EFI/kexts/NVRAM.
"""
import argparse
import os
from pathlib import Path
import plistlib
import shutil
import sys
import tempfile
import json

sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE));sys.path.insert(0,str(HERE.parent/'tools'))
from package_manifest import verify,inventory
from install_diagnostics import atomic_write

NATIVE=('EFI/OC/Kexts/PhxBringup.kext','Library/Extensions/PhxAccel.kext',
        'PhxGPU/NVMTLDriver.bundle','PhxGPU/nvmtl','gpu/fw',
        'gpu/phxctl/phxctl','gpu/phxctl/mesboot','gpu/phxctl/phxfw',
        'gpu/phxctl/vkprobe-native','gpu/phxctl/render-native','validation')

def validate_failure(evidence):
    stages=evidence.get('stages',[])
    if not stages:raise ValueError('missing cold-boot stage evidence')
    last=stages[-1]
    empty=lambda s:s.get('stdout','').strip()=='devices: 0\nno Metal device' and not s.get('stderr','').strip()
    immediate=last.get('returncode') in (1,75) and empty(last)
    attempts=last.get('attempts',[])
    deadline=(last.get('returncode') is None and evidence.get('error')=='HP Metal device publication timed out'
              and bool(attempts) and all(s.get('returncode')==75 and empty(s) for s in attempts))
    if (evidence.get('native_compute_verified') is not True or evidence.get('native_render_verified') is not True
            or evidence.get('metal_verified') is not False or last.get('stage')!='metal-hp-device'
            or not (immediate or deadline)):
        raise ValueError('failure differs from reviewed empty Metal catalogue case; investigate before updating')

def recover(package,daemon,state,parent):
    verify(package)
    original=daemon.read_bytes();config=plistlib.loads(original);args=config.get('ProgramArguments',[])
    if config.get('Label')!='local.nullarc.hp-native' or len(args)!=5 or args[:2]!=['/usr/bin/python3','-B'] or args[3]!='--package':
        raise ValueError('unexpected service configuration')
    old=Path(args[4])
    if old.parent!=parent or args[2]!=str(old/'gpu/phxctl/hp_boot.py'):raise ValueError('unexpected installed package path')
    verify(old)
    for name in NATIVE:
        a=old/name;b=package/name
        if a.is_dir():same=inventory(a)==inventory(b)
        else:same=a.read_bytes()==b.read_bytes()
        if not same:raise ValueError('native execution component changed: '+name)
    folders=list(state.glob('boot-*'))
    if not folders:raise ValueError('no protected boot report')
    latest=max(folders,key=lambda p:p.stat().st_mtime)
    evidence=json.loads((latest/'execution/result.json').read_text());validate_failure(evidence)
    if evidence.get('source_package')!=str(old):raise ValueError('boot report belongs to another package')
    for name in ('pending','disabled'):
        if not (state/name).is_file() or (state/name).is_symlink():raise ValueError('expected failed-boot markers missing')
    if parent.is_symlink() or parent.stat().st_uid!=0 or parent.stat().st_mode&0o022:raise ValueError('unsafe service directory')
    backup=Path(tempfile.mkdtemp(prefix='recovery-',dir=state));(backup/'daemon.plist').write_bytes(original)
    destination=Path(tempfile.mkdtemp(prefix='package-update-',dir=parent));destination.rmdir()
    moved=[]
    try:
        shutil.copytree(package,destination);verify(destination)
        for p in [destination]+list(destination.rglob('*')):
            if p.is_symlink():raise ValueError('symlink in new service package')
            os.chown(p,0,0);p.chmod(p.stat().st_mode&0o755)
        config['ProgramArguments']=['/usr/bin/python3','-B',str(destination/'gpu/phxctl/hp_boot.py'),'--package',str(destination)]
        if daemon.read_bytes()!=original:raise ValueError('service changed during staging')
        atomic_write(daemon,plistlib.dumps(config));daemon.chmod(0o644)
        if plistlib.loads(daemon.read_bytes())!=config:raise ValueError('service readback mismatch')
        for name in ('pending','disabled'):
            (state/name).rename(backup/name);moved.append(name)
    except BaseException:
        for name in reversed(moved):(backup/name).rename(state/name)
        # Only restore our own configuration, never an unrelated concurrent edit.
        if plistlib.loads(daemon.read_bytes())==config:atomic_write(daemon,original)
        if destination.exists():shutil.rmtree(destination)
        raise
    print('Next-boot update installed. No GPU initialization or service restart attempted.')
    print('Backup: '+str(backup))
    print('Package: '+str(destination))

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--package',type=Path,required=True);a=ap.parse_args()
    if os.geteuid()!=0:ap.error('local administrator authentication required')
    try:recover(a.package.resolve(),Path('/Library/LaunchDaemons/local.nullarc.hp-native.plist'),Path('/var/db/nullarc-760m'),Path('/Library/Application Support/NullArc760M'))
    except (OSError,ValueError) as e:ap.exit(1,str(e)+'\n')
