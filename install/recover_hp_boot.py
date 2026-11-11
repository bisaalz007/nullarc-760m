#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Backed-up service update for reviewed Metal-publication/display failures.

Default stages only; --resume-metal runs test shaders on existing healthy queues.
Never retries initialization or changes EFI/kexts/NVRAM.
"""
import argparse
import os
from pathlib import Path
import plistlib
import shutil
import sys
import tempfile
import json
import subprocess

sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE));sys.path.insert(0,str(HERE.parent/'tools'))
from package_manifest import verify,inventory
from install_diagnostics import atomic_write

NATIVE=('EFI/OC/Kexts/PhxBringup.kext','Library/Extensions/PhxAccel.kext',
        'PhxGPU/NVMTLDriver.bundle','PhxGPU/nvmtl','gpu/fw',
        'gpu/phxctl/phxctl','gpu/phxctl/mesboot','gpu/phxctl/phxfw',
        'gpu/phxctl/vkprobe-native','gpu/phxctl/render-native','validation')

def validate_failure(evidence,supervisor=None):
    stages=evidence.get('stages',[])
    if not stages:raise ValueError('missing cold-boot stage evidence')
    last=stages[-1]
    if (supervisor and evidence.get('accelerator_claimed') is True and evidence.get('metal_deferred') is True and evidence.get('metal_verified') is False
            and evidence.get('native_compute_verified') is True and evidence.get('native_render_verified') is True
            and last.get('stage')=='accelerator-claim' and last.get('returncode')==0):
        checks=supervisor.get('metal_stages',[])
        if (supervisor.get('native_initialization_verified') is True and supervisor.get('metal_verified') is False
                and len(checks)==1 and checks[0].get('stage')=='metal-hp-device' and checks[0].get('returncode') is None
                and 'timed out' in supervisor.get('error','')):return
    empty=lambda s:s.get('stdout','').strip()=='devices: 0\nno Metal device' and not s.get('stderr','').strip()
    immediate=last.get('returncode') in (1,75) and empty(last)
    attempts=last.get('attempts',[])
    deadline=(last.get('returncode') is None and evidence.get('error')=='HP Metal device publication timed out'
              and bool(attempts) and all(s.get('returncode')==75 and empty(s) for s in attempts))
    if (evidence.get('native_compute_verified') is not True or evidence.get('native_render_verified') is not True
            or evidence.get('metal_verified') is not False or last.get('stage')!='metal-hp-device'
            or not (immediate or deadline)):
        raise ValueError('failure differs from reviewed empty Metal catalogue case; investigate before updating')

def validate_before_gpu(supervisor,folder,boot,accel_uuid):
    if (supervisor.get('boot_session_uuid')!=boot or
        supervisor.get('error')!='framebuffer one-shot was not consumed by the running kext' or
        supervisor.get('automatic_initialization_attempted') is not True or
        supervisor.get('desktop_armed') is not False or
        any(k in supervisor for k in ('last_stage','returncode','native_initialization_verified')) or
        (folder/'execution').exists()):
        raise ValueError('failure is not the reviewed pre-GPU framebuffer miss')
    request=json.loads((folder/'windowserver-next-boot.json').read_text())
    if request.get('format')!=1 or request.get('accelerator_uuid')!=accel_uuid or request.get('armed_from_boot')==boot:
        raise ValueError('protected display request differs')

def validate_display_fallback(supervisor,evidence,folder,boot,accel_uuid):
    """Only the reviewed post-arm GUI failure, after a completed fallback reboot."""
    if (not supervisor.get('boot_session_uuid') or supervisor['boot_session_uuid']==boot or
        supervisor.get('desktop_armed') is not True or
        supervisor.get('firmware_fallback_reboot_requested') is not True or
        supervisor.get('native_initialization_verified') is not True or
        supervisor.get('metal_verified') is not False or
        supervisor.get('error')!='no active console-user GUI session before deadline; native GPU retained, app access restricted'):
        raise ValueError('failure is not the reviewed WindowServer GUI/fallback case')
    stages=evidence.get('stages',[])
    if (not stages or stages[-1].get('stage')!='accelerator-claim' or stages[-1].get('returncode')!=0 or
        not all(evidence.get(k) is True for k in ('executed','native_compute_verified','native_render_verified','accelerator_claimed','metal_deferred')) or
        evidence.get('metal_verified') is not False):
        raise ValueError('previous display boot did not prove healthy native execution')
    request=json.loads((folder/'windowserver-next-boot.json').read_text())
    if (request.get('format')!=1 or request.get('accelerator_uuid')!=accel_uuid or
        not request.get('armed_from_boot') or request.get('armed_from_boot') in (boot,supervisor['boot_session_uuid'])):
        raise ValueError('protected consumed display request differs')

def recover(package,daemon,state,parent,before_gpu=False,after_display_fallback=False):
    if before_gpu and after_display_fallback:raise ValueError('choose one reviewed recovery case')
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
    supervisor=json.loads((latest/'boot-result.json').read_text()) if (latest/'boot-result.json').exists() else None
    if before_gpu or after_display_fallback:
        sys.path.insert(0,str(package/'gpu/phxctl'))
        from hp_bringup import macho_uuid
        boot=subprocess.check_output(['/usr/sbin/sysctl','-n','kern.bootsessionuuid'],text=True).strip()
        accel_uuid=macho_uuid(package/'Library/Extensions/PhxAccel.kext/Contents/MacOS/PhxAccel')
        if before_gpu:validate_before_gpu(supervisor or {},latest,boot,accel_uuid)
        else:
            import hp_windowserver as display
            display.require_library_policy()
            if display.nodes('PhxAMDFB') or display.nodes('NMXAccel'):raise ValueError('fallback recovery requires an idle firmware-framebuffer boot')
            bringup=display.nodes('PhxBringup')
            if len(bringup)!=1 or bringup[0].get('phx-profile')!='hp-760m' or bringup[0].get('phx-stage')!='profile-diagnostic-only':
                raise ValueError('fresh diagnostic-only HP boot required; no queue retry permitted')
            nv=plistlib.loads(subprocess.check_output(['/usr/sbin/nvram','-xp'],timeout=5))
            if 'phxfb-boot' in nv or (state/display.REQUEST).exists():raise ValueError('unexpected display request; review before recovery')
            evidence=json.loads((latest/'execution/result.json').read_text())
            validate_display_fallback(supervisor or {},evidence,latest,boot,accel_uuid)
            if evidence.get('source_package')!=str(old):raise ValueError('boot report belongs to another package')
    else:
        evidence=json.loads((latest/'execution/result.json').read_text())
        validate_failure(evidence,supervisor)
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
    return destination

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--package',type=Path,required=True)
    ap.add_argument('--resume-metal',action='store_true',help='after staging, verify Metal on existing healthy queues without reinitialization')
    ap.add_argument('--after-display-fallback',action='store_true',help='stage only after the reviewed display failure and an idle firmware-fallback reboot');a=ap.parse_args()
    if a.resume_metal and a.after_display_fallback:ap.error('fallback staging and existing-queue verification are different recovery cases')
    if os.geteuid()!=0:ap.error('local administrator authentication required')
    try:
        destination=recover(a.package.resolve(),Path('/Library/LaunchDaemons/local.nullarc.hp-native.plist'),Path('/var/db/nullarc-760m'),Path('/Library/Application Support/NullArc760M'),after_display_fallback=a.after_display_fallback)
        if a.resume_metal:
            subprocess.run([sys.executable,'-B',str(destination/'gpu/phxctl/hp_boot.py'),'--package',str(destination),'--verify-existing'],check=True,timeout=600)
    except (OSError,ValueError,subprocess.SubprocessError) as e:ap.exit(1,str(e)+'\n')
