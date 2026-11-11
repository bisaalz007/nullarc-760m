#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""One-shot HP firmware-console presentation; no modesetting or hot takeover."""
import json
import os
from pathlib import Path
import plistlib
import struct
import subprocess
import time
from hp_bringup import claimed_hp,macho_uuid
from collect_macos_evidence import walk

REQUEST='windowserver-next-boot.json'
DESKTOP='# NullArc: one-shot HP accelerated compositor; firmware scanout\n-mediaanalysisd\n-photoanalysisd\n-Spotlight\n!WindowServer\n*\n'
class DisplayOwnershipError(ValueError):pass

def require_library_policy():
    """Dependency guard, not proof WindowServer can load our ad-hoc plugin.

    The HP's old 1.3.1 binary declares maxKernel=22; Sequoia is Darwin 24.
    OCLP's 1.4.1 declares maxKernel=24. Lilu can return KERN_SUCCESS without
    starting a plugin on unsupported kernels, so showloaded alone is inadequate.
    Require its service too, and retain actual WindowServer runtime checks.
    No AMFI boot flag or other unverified configuration substitutes for this.
    """
    loaded=subprocess.check_output(['/usr/bin/kmutil','showloaded','--list-only'],text=True,timeout=15)
    if not any('com.dhinakg.AMFIPass (1.4.1)' in line for line in loaded.splitlines()) or len(nodes('AMFIPass'))!=1:
        raise ValueError('WindowServer signing dependency preflight failed: reviewed Sequoia-compatible AMFIPass 1.4.1 must be loaded with an active service. Boot flags and app Metal tests alone are insufficient. No security setting changed.')

CRASH_DIR=Path('/Library/Logs/DiagnosticReports')

def watch_crashes(report):
    # Snapshot before releasing the panel. Reports already on disk are history.
    report['desktop_crash_baseline']=sorted(p.name for p in CRASH_DIR.glob('WindowServer*.ips'))

def check_crashes(report,save):
    if report.get('desktop_armed') is not True:return
    baseline=set(report['desktop_crash_baseline'])
    for path in sorted(CRASH_DIR.glob('WindowServer*.ips')):
        if path.name in baseline:continue
        try:
            # IPS has a metadata JSON object followed by the crash JSON object.
            with path.open() as f:raw=f.read(8*1024*1024+1)
            if len(raw)>8*1024*1024:raise ValueError('WindowServer crash report exceeds inspection limit')
            _,end=json.JSONDecoder().raw_decode(raw)
            crash=json.loads(raw[end:])
        except (FileNotFoundError,json.JSONDecodeError):continue  # report still being written
        if crash.get('procName')!='WindowServer' or crash.get('bootSessionUUID')!=report.get('boot_session_uuid'):continue
        report['desktop_crash_report']=path.name;save()
        raise ValueError('WindowServer crashed during the one-shot display test; stop and collect '+path.name)

def nodes(name):
    raw=subprocess.check_output(['/usr/sbin/ioreg','-alr','-c',name],timeout=15)
    return plistlib.loads(raw) if raw.strip() else []

def sysctl(name,value=None):
    command=['/usr/sbin/sysctl','-n',name] if value is None else ['/usr/sbin/sysctl','-w',name+'='+str(value)]
    result=subprocess.check_output(command,text=True,timeout=5).strip()
    return int(result) if value is None else result

def boot_uuid():return subprocess.check_output(['/usr/sbin/sysctl','-n','kern.bootsessionuuid'],text=True,timeout=5).strip().upper()

def validated_accelerator():
    pci=claimed_hp(nodes('IOPCIDevice'))
    accelerators=[n for n in walk([pci]) if n.get('IOObjectClass')=='NMXAccel' or n.get('IOClass')=='NMXAccel']
    if len(accelerators)!=1:raise ValueError('one HP accelerator required')
    a=accelerators[0]
    if a.get('PhxHPDisplayABICompatible') is not True:raise ValueError('HP display ABI has not passed runtime size checks')
    if a.get('PhxHPDisplayPlanValid') is not True:raise ValueError('captured HP console/timing/reservation plan did not validate')
    data=a.get('PhxHPDisplayPlan')
    if not isinstance(data,bytes) or len(data)!=104:raise ValueError('missing display plan data')
    p=struct.unpack('<14I6Q',data)
    if p[:14]!=(1,3,1920,1200,7680,60000,2260,1968,2000,1240,1203,1209,1,0) or p[16:]!=(0x8000000000,0,9216000,168144000):
        raise ValueError('HP display plan differs from captured console')
    # Class size equality is necessary, not proof of private method ABI. Keep
    # this experiment scoped to the actual tested Sequoia family versions.
    loaded=subprocess.check_output(['/usr/bin/kmutil','showloaded','--list-only'],text=True,timeout=15)
    for identifier,version in [('com.apple.iokit.IOGraphicsFamily','599'),('com.apple.iokit.IOAcceleratorFamily2','485.2'),
                               ('com.apple.AppleGraphicsDeviceControl','8.1.10')]:
        if not any(identifier+' ('+version+')' in line for line in loaded.splitlines()):
            raise ValueError('unreviewed display family version: '+identifier)
    return a

PANEL={'PhxFBWidth':1920,'PhxFBHeight':1200,'PhxFBHTotal':2260,'PhxFBVTotal':1240,
       'PhxFBHSyncStart':1968,'PhxFBHSyncEnd':2000,'PhxFBVSyncStart':1203,'PhxFBVSyncEnd':1209,
       'PhxFBNominalPixelClockHz':168144000,'PhxFBRefreshMilliHz':60000}

def framebuffer():
    frames=nodes('PhxAMDFB')
    if not frames:return None
    if len(frames)!=1:raise ValueError('unexpected framebuffer count')
    f=frames[0]
    if f.get('PhxFBHP') is not True or f.get('PhxFBTimingCaptured') is not True:
        raise ValueError('framebuffer is not the validated HP console presenter')
    if any(f.get(k)!=v for k,v in PANEL.items()):raise ValueError('framebuffer timing differs from validated plan')
    return f

def unopened_held_framebuffer():
    f=framebuffer()
    if f is None:raise ValueError('one-shot framebuffer did not attach; no live takeover attempted')
    if any(n.get('IOObjectClass')=='IOFramebufferUserClient' for n in walk([f])):
        raise ValueError('WindowServer opened the panel before arming')
    if sysctl('debug.phxfb_hold')!=1:raise ValueError('framebuffer boot hold expired')
    return f

def wait_for_framebuffer(timeout=90,progress=None):
    deadline=time.monotonic()+timeout;last=None
    def phase(value):
        nonlocal last
        if value!=last and progress:progress(value)
        last=value
    while time.monotonic()<deadline:
        try:
            frames=nodes('PhxAMDFB')
            if not frames:phase('awaiting-early-framebuffer')
            elif len(frames)!=1:raise ValueError('unexpected framebuffer count')
            elif not all(k in frames[0] for k in list(PANEL)+['PhxFBHP','PhxFBTimingCaptured']):
                phase('awaiting-framebuffer-properties')
            else:
                # start() publishes properties before installing the hold sysctl.
                try:hold=sysctl('debug.phxfb_hold')
                except subprocess.CalledProcessError:phase('awaiting-framebuffer-hold')
                else:
                    if hold!=1:raise ValueError('framebuffer boot hold expired')
                    unopened_held_framebuffer();return
        except subprocess.TimeoutExpired:phase('awaiting-framebuffer-registry-snapshot')
        time.sleep(.5)
    raise ValueError('validated early framebuffer did not become ready before deadline')

def begin(package,state,folder,progress=None):
    request=state/REQUEST
    if not request.exists():
        if nodes('PhxAMDFB'):raise DisplayOwnershipError('HP framebuffer active without an authorized next-boot request')
        return False
    if request.is_symlink() or request.stat().st_uid!=0 or request.stat().st_mode&0o077:
        raise ValueError('unsafe next-boot request')
    config=json.loads(request.read_text())
    if config.get('format')!=1 or config.get('armed_from_boot')==boot_uuid():raise ValueError('next-boot request requires a reboot')
    if config.get('accelerator_uuid')!=macho_uuid(package/'Library/Extensions/PhxAccel.kext/Contents/MacOS/PhxAccel'):
        raise ValueError('next-boot accelerator differs from request')
    request.rename(folder/REQUEST)  # consumed, never automatically re-armed
    # Do not clear the request while System/Aux driver matching is pending.
    # GPU initialization remains forbidden until the validated held FB appears.
    try:
        wait_for_framebuffer(progress=progress)
        require_library_policy()
        nv=plistlib.loads(subprocess.check_output(['/usr/sbin/nvram','-xp'],timeout=5))
        if 'phxfb-boot' in nv:raise ValueError('attached framebuffer did not consume its one-shot')
    except (OSError,ValueError,subprocess.SubprocessError):
        nv=plistlib.loads(subprocess.check_output(['/usr/sbin/nvram','-xp'],timeout=5))
        if 'phxfb-boot' in nv:subprocess.run(['/usr/sbin/nvram','-d','phxfb-boot'],check=True,timeout=5)
        raise
    return True

def arm(report,save,allow,atomic):
    require_library_policy()
    validated_accelerator();unopened_held_framebuffer()
    report['desktop_phase']='registering-panel';save()
    sysctl('debug.nvaccelfb',1);time.sleep(1)
    if sysctl('debug.nvaccelfb')!=1:raise ValueError('display machine did not register a panel')
    if sysctl('debug.nvaccel_heads_piped')!=1:raise ValueError('HP console did not receive exactly one display pipe')
    sysctl('debug.nvaccel_iop',1);sysctl('debug.nvaccelfb',3);time.sleep(1)
    if sysctl('debug.nvaccel_iop')!=1:raise ValueError('display pipe transaction gate did not open')
    sysctl('debug.phxagdc',1);time.sleep(1)
    if sysctl('debug.phxagdc')!=1:raise ValueError('HP AGDC did not start')
    # Keep the existing scalar copy path for the first HP display experiment.
    # No new scanout allocation, display register programming or refresh change.
    sysctl('debug.nvaccel_iop_vsync',1)
    unopened_held_framebuffer()
    report['desktop_phase']='releasing-panel';save()
    watch_crashes(report)
    atomic(allow,DESKTOP)
    sysctl('debug.phxfb_hold',0)
    if sysctl('debug.phxfb_hold')!=0:raise ValueError('framebuffer hold did not release')
    report['desktop_armed']=True;report['desktop_phase']='awaiting-runtime-evidence';save()

def verify_present(report,save,timeout=120):
    # Registration is not rendering proof. Require actual presents and a live
    # WindowServer framebuffer client, then retain counters as evidence.
    start=sysctl('debug.nvaccel_iop_ok');deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        check_crashes(report,save)
        current=sysctl('debug.nvaccel_iop_ok');failed=sysctl('debug.nvaccel_iop_fail')
        f=framebuffer()
        client=f and any(n.get('IOObjectClass')=='IOFramebufferUserClient' for n in walk([f]))
        if failed:raise ValueError('display pipe reported failed transactions')
        if current>start and client:
            report.update(desktop_present_verified=True,desktop_present_count=current,
                          desktop_present_delta=current-start,desktop_failed_transactions=failed)
            save();return
        time.sleep(1)
    raise ValueError('no verified WindowServer display-pipe presents before deadline')

def fallback(report,save):
    """A consumed one-shot returns to firmware scanout on the next boot."""
    report['desktop_phase']='failed-reboot-to-firmware-required';save()
    # Only used by the opted-in next-boot experiment when PhxAMDFB owns the panel.
    # Never try to hot-detach a framebuffer or initialize a second GPU queue set.
    if nodes('PhxAMDFB'):
        report['firmware_fallback_reboot_requested']=True;save()
        subprocess.run(['/sbin/shutdown','-r','now'],check=True,timeout=10)
