#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Install source-built HP test components with backup; never load/activate them."""
import argparse
import json
import os
import plistlib
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

def install(package,root=Path('/'),check=True,fresh=False):
    root=Path(root).resolve();package=Path(package).resolve()
    verify(package)
    for src,dst in zip(TARGETS,DESTINATIONS):
        if not (package/src).is_dir():raise ValueError('missing component: '+src)
        target=root/dst
        if target.is_symlink() or any(p.is_symlink() for p in target.parents if p!=root.parent):
            raise ValueError('symlinked installation path: '+str(target))
    if (root/'Library/LaunchDaemons/local.phxboot.plist').exists():
        raise ValueError('existing reference boot daemon requires separate review before component replacement')
    daemon=root/'Library/LaunchDaemons/local.nullarc.hp-native.plist'
    if daemon.is_symlink():raise ValueError('symlinked HP native boot service refused')
    has_daemon=daemon.exists()
    if has_daemon:
        if not fresh:
            raise ValueError('HP native boot service already exists; use --fresh-files only from an idle diagnostic boot to back it up before replacing drivers')
        config=plistlib.loads(daemon.read_bytes())
        args=config.get('ProgramArguments',[])
        if (config.get('Label')!='local.nullarc.hp-native' or len(args)!=5
                or args[:2]!=['/usr/bin/python3','-B'] or args[3]!='--package'
                or Path(args[4]).parent!=Path('/Library/Application Support/NullArc760M')
                or args[2]!=str(Path(args[4])/'gpu/phxctl/hp_boot.py')):
            raise ValueError('unexpected HP native service configuration; do not retire it automatically')
    if check:return {'mode':'fresh-files-check' if fresh else 'component-check',
                     'changes_written':False,'automatic_activation':False,
                     'existing_native_service_will_be_archived':has_daemon}
    backups=root/'Users/Shared/nullarc-component-backups';backups.mkdir(parents=True,exist_ok=True)
    backup=Path(tempfile.mkdtemp(prefix='backup-',dir=backups));entries=[]
    retired=False
    try:
        if has_daemon:
            daemon.rename(backup/'previous-hp-native.plist')
            retired=True
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
        (backup/'receipt.json').write_text(json.dumps({'format':1,'root':str(root),'entries':entries,
            'previous_boot_service':'previous-hp-native.plist' if retired else None},indent=2)+'\n')
    except BaseException:
        for e in reversed(entries):
            target=root/e['destination']
            if e['installed'] and target.exists():shutil.rmtree(target)
            if e['original']:(backup/e['original']).rename(target)
        if retired:(backup/'previous-hp-native.plist').rename(daemon)
        raise
    return {'mode':'fresh-files-installed-no-activation' if fresh else 'components-installed-no-activation',
            'backup':str(backup),'kernel_cache_updated':False,'loaded_kernel_unchanged':True,
            'previous_boot_service_archived':retired,'daemon_installed':False,'WindowServer_armed':False}

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
    daemon=root/'Library/LaunchDaemons/local.nullarc.hp-native.plist'
    old_daemon=receipt.get('previous_boot_service')
    if old_daemon not in (None,'previous-hp-native.plist'):raise ValueError('invalid previous boot service')
    if old_daemon:
        if daemon.exists() or daemon.is_symlink():raise ValueError('a boot service has been installed since this backup; refusing overwrite')
        if not (backup/old_daemon).is_file() or (backup/old_daemon).is_symlink():raise ValueError('previous boot service missing from backup')
    moved=[];daemon_restored=False
    with tempfile.TemporaryDirectory(prefix='restore-',dir=backup) as tmp:
        try:
            for i,e in enumerate(entries):
                target=root/e['destination'];holding=Path(tmp)/str(i)
                target.rename(holding);moved.append((target,holding))
                if e['original']:shutil.copytree(backup/e['original'],target)
            if old_daemon:
                (backup/old_daemon).rename(daemon);daemon_restored=True
        except BaseException:
            if daemon_restored:daemon.rename(backup/old_daemon)
            for target,holding in reversed(moved):
                if target.exists():shutil.rmtree(target)
                holding.rename(target)
            raise
    return {'mode':'components-restored','reboot_performed':False,'previous_boot_service_restored':daemon_restored}

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--package',type=Path,default=Path(__file__).resolve().parent)
    m=ap.add_mutually_exclusive_group();m.add_argument('--check',action='store_true');m.add_argument('--install',action='store_true');m.add_argument('--restore',type=Path)
    ap.add_argument('--fresh-files',action='store_true',help='archive the old HP boot service and stage bundled native components; never activate')
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
            if a.fresh_files:
                # No native engine/WindowServer ownership or live boot supervisor may be active.
                for service in ('NMXAccel','PhxAMDFB'):
                    result=subprocess.check_output(['/usr/sbin/ioreg','-ar','-c',service],timeout=15)
                    if result.strip() and plistlib.loads(result):
                        raise ValueError('fresh file staging requires idle firmware framebuffer; '+service+' is active')
                running=subprocess.run(['/usr/bin/pgrep','-fl','[/]hp_boot.py|[/]hp_bringup.py'],
                    capture_output=True,text=True,timeout=5)
                if running.returncode==0:raise ValueError('HP boot supervisor is still running; do not replace live files')
                if running.returncode not in (0,1):raise ValueError('could not verify idle HP boot supervisor')
                nv=plistlib.loads(subprocess.check_output(['/usr/sbin/nvram','-xp'],timeout=5))
                if 'phxfb-boot' in nv:raise ValueError('a WindowServer boot is armed; cancel/review it before fresh file staging')
                if (Path('/var/db/nullarc-760m')/'windowserver-next-boot.json').exists():
                    raise ValueError('a WindowServer next-boot request exists; review it before fresh file staging')
            if a.install and os.geteuid()!=0:raise ValueError('use sudo to install components')
            result=install(package,check=not a.install,fresh=a.fresh_files)
        print(json.dumps(result,indent=2))
    except (ValueError,OSError,subprocess.CalledProcessError) as e:ap.exit(1,str(e)+'\n')

if __name__=='__main__':main()
