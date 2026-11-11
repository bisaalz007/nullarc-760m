#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Stage the HP display module, then authorize one display boot after runtime checks.

First invocation replaces only PhxAccel and the immutable next-boot package, with
NVRAM unchanged. After a successful app-mode reboot, the second invocation arms
one framebuffer boot. Identical native binaries allow a startup-only update from
a verified accelerated desktop. Early framebuffer metadata is backed up if needed;
OpenCore configuration and signing policy are preserved. No automatic rearming.
"""
import argparse
import json
import os
from pathlib import Path
import plistlib
import re
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE));sys.path.insert(0,str(HERE.parent/'tools'))
from package_manifest import verify,inventory,digest
from install_diagnostics import atomic_write
from recover_hp_boot import NATIVE

def validate_current_apps(status,boot):
    ready=status.get('native_initialization_verified') is True or status.get('native_readiness_verified') is True
    if not ready or not all(status.get(k) is True for k in ('metal_verified','apps_enabled')):
        raise ValueError('new module must first pass native readiness and Metal app tests')
    if status.get('boot_session_uuid')!=boot:raise ValueError('app validation report is from another boot')

def configured_package(daemon,parent):
    original=daemon.read_bytes();config=plistlib.loads(original);args=config.get('ProgramArguments',[])
    if config.get('Label')!='local.nullarc.hp-native' or len(args)!=5 or args[:2]!=['/usr/bin/python3','-B'] or args[3]!='--package':
        raise ValueError('verified HP app boot service required')
    old=Path(args[4])
    if old.parent!=parent or args[2]!=str(old/'gpu/phxctl/hp_boot.py'):raise ValueError('unexpected installed package path')
    verify(old)
    return original,config,old

def stage_service(package,old,daemon,state,parent,original,config):
    """Update startup scripts only when every native execution input matches."""
    verify(package)
    for name in NATIVE:
        before=old/name;after=package/name
        same=inventory(before)==inventory(after) if before.is_dir() else before.read_bytes()==after.read_bytes()
        if not same:raise ValueError('native component changed; validate it separately: '+name)
    backup=Path(tempfile.mkdtemp(prefix='startup-update-',dir=state))
    (backup/'daemon.plist').write_bytes(original)
    destination=Path(tempfile.mkdtemp(prefix='package-startup-',dir=parent))
    destination.rmdir()
    updated=dict(config)
    updated['ProgramArguments']=['/usr/bin/python3','-B',str(destination/'gpu/phxctl/hp_boot.py'),'--package',str(destination)]
    encoded=plistlib.dumps(updated)
    try:
        shutil.copytree(package,destination);verify(destination)
        for path in [destination]+list(destination.rglob('*')):
            if path.is_symlink():raise ValueError('symlink in immutable package')
            os.chown(path,0,0);path.chmod(path.stat().st_mode&0o755)
        if daemon.read_bytes()!=original:raise ValueError('service changed during staging')
        atomic_write(daemon,encoded);daemon.chmod(0o644)
        if daemon.read_bytes()!=encoded:raise ValueError('service update readback mismatch')
    except BaseException:
        if daemon.read_bytes()==encoded:atomic_write(daemon,original)
        if destination.exists():shutil.rmtree(destination)
        raise
    return backup,destination

def stage_module(package,old,daemon,state,parent,target,source,original,config):
    backup=Path(tempfile.mkdtemp(prefix='display-update-',dir=state));(backup/'daemon.plist').write_bytes(original)
    shutil.copytree(target,backup/'PhxAccel.kext')
    destination=Path(tempfile.mkdtemp(prefix='package-display-',dir=parent));destination.rmdir()
    config=dict(config)
    config['ProgramArguments']=['/usr/bin/python3','-B',str(destination/'gpu/phxctl/hp_boot.py'),'--package',str(destination)]
    changed=False
    try:
        shutil.copytree(package,destination);verify(destination)
        for p in [destination]+list(destination.rglob('*')):
            if p.is_symlink():raise ValueError('symlink in immutable package')
            os.chown(p,0,0);p.chmod(p.stat().st_mode&0o755)
        with tempfile.TemporaryDirectory(prefix='.nullarc-display-',dir=target.parent) as tmp:
            stage=Path(tmp)/'PhxAccel.kext';shutil.copytree(source,stage)
            for p in [stage]+list(stage.rglob('*')):os.chown(p,0,0);p.chmod(p.stat().st_mode&0o755)
            if daemon.read_bytes()!=original or inventory(target)!=inventory(old/'Library/Extensions/PhxAccel.kext'):
                raise ValueError('service/module changed during staging')
            target.rename(Path(tmp)/'previous.kext');changed=True;stage.rename(target)
        atomic_write(daemon,plistlib.dumps(config));daemon.chmod(0o644)
        if inventory(target)!=inventory(source) or plistlib.loads(daemon.read_bytes())!=config:raise ValueError('display staging readback mismatch')
    except BaseException:
        if changed:
            if target.exists():shutil.rmtree(target)
            shutil.copytree(backup/'PhxAccel.kext',target)
        if daemon.read_bytes()==plistlib.dumps(config):atomic_write(daemon,original)
        if destination.exists():shutil.rmtree(destination)
        raise
    return backup,destination

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--package',type=Path,required=True)
    ap.add_argument('--install',action='store_true')
    ap.add_argument('--oc',type=Path,default=Path('/Volumes/EFI/EFI/OC'))
    a=ap.parse_args();package=a.package.resolve()
    document=verify(package)
    if document.get('minimum_macos')!='15.0' or not subprocess.check_output(['/usr/bin/sw_vers','-productVersion'],text=True).startswith('15.'):
        raise ValueError('HP display experiment currently requires the Sequoia build and macOS 15')
    sys.path.insert(0,str(package/'gpu/phxctl'))
    from hp_bringup import macho_uuid
    import hp_windowserver as display
    from hp_boot import verify_existing_native
    parent=Path('/Library/Application Support/NullArc760M');state=Path('/var/db/nullarc-760m')
    daemon=Path('/Library/LaunchDaemons/local.nullarc.hp-native.plist')
    if parent.is_symlink() or parent.stat().st_uid!=0 or parent.stat().st_mode&0o022:raise ValueError('unsafe immutable package directory')
    original,config,old=configured_package(daemon,parent)
    for name in ('pending','disabled',display.REQUEST):
        if (state/name).exists():raise ValueError('review existing boot/failure/request marker before changing display mode: '+name)
    if Path('/Library/LaunchDaemons/local.phxboot.plist').exists():raise ValueError('conflicting reference boot service')
    nv=plistlib.loads(subprocess.check_output(['/usr/sbin/nvram','-xp'],timeout=5))
    if 'phxfb-boot' in nv:raise ValueError('existing framebuffer NVRAM request must be reviewed first')
    active_display=bool(display.nodes('PhxAMDFB'))
    for name in NATIVE:
        if name=='Library/Extensions/PhxAccel.kext':continue
        x=old/name;y=package/name
        same=inventory(x)==inventory(y) if x.is_dir() else x.read_bytes()==y.read_bytes()
        if not same:
            raise ValueError('non-display native component changed; separate validation required: '+name)
    source=package/'Library/Extensions/PhxAccel.kext';target=Path('/Library/Extensions/PhxAccel.kext')
    expected=macho_uuid(source/'Contents/MacOS/PhxAccel')
    loaded=subprocess.check_output(['/usr/bin/kmutil','showloaded','--list-only'],text=True,timeout=15)
    running=any('com.luuumi.PhxAccel (' in line and expected in line.upper() for line in loaded.splitlines())
    if not running and inventory(target)==inventory(source):
        print('New PhxAccel is staged but its UUID is not loaded. Reboot using the same USB, log in, then run this command again. No framebuffer arming performed.')
        return
    verify_existing_native(package if running else old)
    if running:
        display.require_library_policy()
        display.validated_accelerator()
        status=json.loads(Path('/Users/Shared/nullarc-hp-native-status.json').read_text())
        validate_current_apps(status,display.boot_uuid())
        if active_display:
            display.framebuffer()
            if status.get('desktop_armed') is not True or status.get('desktop_present_verified') is not True:
                raise ValueError('active display has no successful current-boot presentation validation')
        if inventory(target)!=inventory(source):raise ValueError('installed module differs from running package')
        update=inventory(old)!=inventory(package)
        if update:
            for name in NATIVE:
                x=old/name;y=package/name
                if (inventory(x)!=inventory(y) if x.is_dir() else x.read_bytes()!=y.read_bytes()):
                    raise ValueError('native execution input changed; separate validation required: '+name)
        from install_early_fb import install as install_early
        install_early(package,a.oc)
        if not a.install:
            print('HP runtime checks passed; startup update '+('needed' if update else 'already installed')+
                  '. Install arms one guarded display boot.')
            return
        if os.geteuid()!=0:raise ValueError('local administrator authentication required')
        if update:
            backup,destination=stage_service(package,old,daemon,state,parent,original,config)
            print('Startup package updated. Backup: '+str(backup))
            print('Package: '+str(destination))
        early=install_early(package,a.oc,apply=True)
        if early.get('backup'):print('EFI metadata backup: '+early['backup'])
        if active_display:
            print('Current copy settings: '+json.dumps(display.configure_copy()))
        request={'format':1,'armed_from_boot':display.boot_uuid(),'accelerator_uuid':expected}
        path=state/display.REQUEST
        with path.open('x') as f:
            os.fchmod(f.fileno(),0o600);json.dump(request,f);f.write('\n');f.flush();os.fsync(f.fileno())
        try:
            subprocess.run(['/usr/sbin/nvram','phxfb-boot=1'],check=True,timeout=5)
            readback=plistlib.loads(subprocess.check_output(['/usr/sbin/nvram','-xp'],timeout=5))
            if readback.get('phxfb-boot') not in (b'1','1'):raise ValueError('NVRAM one-shot readback mismatch')
        except BaseException:
            subprocess.run(['/usr/sbin/nvram','-d','phxfb-boot'],check=True,timeout=5)
            cleared=plistlib.loads(subprocess.check_output(['/usr/sbin/nvram','-xp'],timeout=5))
            if 'phxfb-boot' in cleared:raise ValueError('one-shot removal failed; keep request and review NVRAM before reboot')
            path.unlink(missing_ok=True);raise
        print('One WindowServer boot armed. Reboot with the same USB. It is not automatically rearmed; a failed display boot requests one firmware-fallback reboot.')
        return
    if active_display:raise ValueError('loaded accelerator update requires a firmware-framebuffer boot')
    if inventory(target)!=inventory(old/'Library/Extensions/PhxAccel.kext'):raise ValueError('installed module differs from verified app package')
    subprocess.run(['/usr/bin/codesign','--verify','--strict',str(source)],check=True,timeout=15)
    if not a.install:print('HP display module update checks passed. First install stages app-only reboot; WindowServer remains disabled.');return
    if os.geteuid()!=0:raise ValueError('local administrator authentication required')
    backup,destination=stage_module(package,old,daemon,state,parent,target,source,original,config)
    # Do not unload the live accelerator. Standard approval/reboot requirements
    # are recorded verbatim; never disable security or report a successful load.
    result=subprocess.run(['/usr/bin/kmutil','load','--bundle-path',str(target),'--load-style','start-only'],capture_output=True,text=True,timeout=60)
    (backup/'kmutil.json').write_text(json.dumps({'returncode':result.returncode,'stdout':result.stdout,'stderr':result.stderr},indent=2)+'\n')
    print(result.stdout+result.stderr)
    print('Display module and next-boot app package staged; WindowServer and NVRAM unchanged. Backup: '+str(backup))
    if result.returncode:
        print('kmutil did not load the new UUID; follow its specific approval/reboot message. No successful load is claimed.')
        if not re.search(r'KMErrorDomain\s+Code=(?:27|28)\b',result.stdout+result.stderr):
            raise ValueError('unexpected kmutil failure; staging and backup retained for review. Do not reboot until resolved.')
    print('Reboot with the same USB and log in. Verify app-mode results before running --windowserver again.')

if __name__=='__main__':
    try:main()
    except (OSError,ValueError,subprocess.SubprocessError) as e:raise SystemExit(str(e))
