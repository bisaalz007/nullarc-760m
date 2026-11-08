#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Install source-built HP test components with backup; never load/activate them."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from package_manifest import verify,inventory

TARGETS=('Library/Extensions/PhxAccel.kext','PhxGPU/NVMTLDriver.bundle','PhxGPU/nvmtl','gpu')
DESTINATIONS=('Library/Extensions/PhxAccel.kext','Library/GPUBundles/NVMTLDriver.bundle',
              'Library/GPUBundles/nvmtl','Users/Shared/gpu')

def install(package,root=Path('/'),check=True):
    root=Path(root).resolve();package=Path(package).resolve()
    verify(package)
    for src,dst in zip(TARGETS,DESTINATIONS):
        if not (package/src).is_dir():raise ValueError('missing component: '+src)
        target=root/dst
        if target.is_symlink() or any(p.is_symlink() for p in target.parents if p!=root.parent):
            raise ValueError('symlinked installation path: '+str(target))
    if (root/'Library/LaunchDaemons/local.phxboot.plist').exists():
        raise ValueError('existing boot daemon requires separate review before component replacement')
    if check:return {'mode':'component-check','changes_written':False,'automatic_activation':False}
    backups=root/'Users/Shared/nullarc-component-backups';backups.mkdir(parents=True,exist_ok=True)
    backup=Path(tempfile.mkdtemp(prefix='backup-',dir=backups));entries=[]
    try:
        for i,(src,dst) in enumerate(zip(TARGETS,DESTINATIONS)):
            staged=backup/('new-'+str(i));shutil.copytree(package/src,staged)
            if src=='gpu':(staged/'phxboot-off').touch()
            target=root/dst;target.parent.mkdir(parents=True,exist_ok=True)
            old=backup/('original-'+str(i));had=target.exists()
            original_files=inventory(target) if had else {}
            if had:target.rename(old)
            entry={'destination':dst,'original':old.name if had else None,'original_files':original_files,'installed':False}
            entries.append(entry)
            staged.rename(target);entry['installed']=True
            entry['files']=inventory(target)
        (backup/'receipt.json').write_text(json.dumps({'format':1,'root':str(root),'entries':entries},indent=2)+'\n')
    except BaseException:
        for e in reversed(entries):
            target=root/e['destination']
            if e['installed'] and target.exists():shutil.rmtree(target)
            if e['original']:(backup/e['original']).rename(target)
        raise
    return {'mode':'components-installed-no-activation','backup':str(backup),'kernel_cache_updated':False,
            'loaded_kernel_unchanged':True,'daemon_installed':False,'WindowServer_armed':False}

def restore(backup,root=Path('/')):
    root=Path(root).resolve();backup=Path(backup).resolve()
    receipt=json.loads((backup/'receipt.json').read_text())
    if receipt.get('format')!=1 or receipt.get('root')!=str(root):raise ValueError('backup belongs to another root')
    entries=receipt['entries']
    if [e['destination'] for e in entries]!=list(DESTINATIONS):raise ValueError('unexpected restore destinations')
    for i,e in enumerate(entries):
        if e['original'] not in (None,'original-'+str(i)):raise ValueError('invalid backup path')
        if inventory(root/e['destination'])!=e['files']:raise ValueError('installed components changed; refusing overwrite')
        if e['original'] and inventory(backup/e['original'])!=e['original_files']:raise ValueError('original backup changed')
    moved=[]
    with tempfile.TemporaryDirectory(prefix='restore-',dir=backup) as tmp:
        try:
            for i,e in enumerate(entries):
                target=root/e['destination'];holding=Path(tmp)/str(i)
                target.rename(holding);moved.append((target,holding))
                if e['original']:shutil.copytree(backup/e['original'],target)
        except BaseException:
            for target,holding in reversed(moved):
                if target.exists():shutil.rmtree(target)
                holding.rename(target)
            raise
    return {'mode':'components-restored','reboot_performed':False}

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--package',type=Path,default=Path(__file__).resolve().parent)
    m=ap.add_mutually_exclusive_group();m.add_argument('--check',action='store_true');m.add_argument('--install',action='store_true');m.add_argument('--restore',type=Path)
    a=ap.parse_args()
    try:
        if a.restore:
            if os.geteuid()!=0:raise ValueError('use sudo to restore components')
            result=restore(a.restore.resolve())
        else:
            package=a.package.resolve();document=verify(package)
            os_version=subprocess.check_output(['sw_vers','-productVersion'],text=True).strip()
            if document.get('minimum_macos')!='15.0' or not os_version.startswith('15.'):
                raise ValueError('this component test requires the Sequoia package on macOS 15')
            policy=subprocess.check_output([sys.executable,'-B',str(package/'collect_macos_evidence.py'),'--target-policy'],text=True).strip()
            if policy!='hp-diagnostic-only':raise ValueError('this component test is restricted to the exact HP profile')
            registry=subprocess.check_output(['ioreg','-rc','PhxBringup','-l'],text=True)
            if '"phx-stage" = "profile-diagnostic-only"' not in registry:raise ValueError('loaded diagnostic PhxBringup required')
            if a.install and os.geteuid()!=0:raise ValueError('use sudo to install components')
            result=install(package,check=not a.install)
        print(json.dumps(result,indent=2))
    except (ValueError,OSError,subprocess.CalledProcessError) as e:ap.exit(1,str(e)+'\n')

if __name__=='__main__':main()
