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

def nodes(name):
    raw=subprocess.check_output(['/usr/sbin/ioreg','-alr','-c',name],timeout=5)
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

def framebuffer():
    frames=nodes('PhxAMDFB')
    if not frames:return None
    if len(frames)!=1:raise ValueError('unexpected framebuffer count')
    f=frames[0]
    if f.get('PhxFBHP') is not True or f.get('PhxFBTimingCaptured') is not True:
        raise ValueError('framebuffer is not the validated HP console presenter')
    expected={'PhxFBWidth':1920,'PhxFBHeight':1200,'PhxFBHTotal':2260,'PhxFBVTotal':1240,
              'PhxFBHSyncStart':1968,'PhxFBHSyncEnd':2000,'PhxFBVSyncStart':1203,'PhxFBVSyncEnd':1209,
              'PhxFBNominalPixelClockHz':168144000,'PhxFBRefreshMilliHz':60000}
    if any(f.get(k)!=v for k,v in expected.items()):raise ValueError('framebuffer timing differs from validated plan')
    return f

def unopened_held_framebuffer():
    f=framebuffer()
    if f is None:raise ValueError('one-shot framebuffer did not attach; no live takeover attempted')
    if any(n.get('IOObjectClass')=='IOFramebufferUserClient' for n in walk([f])):
        raise ValueError('WindowServer opened the panel before arming')
    if sysctl('debug.phxfb_hold')!=1:raise ValueError('framebuffer boot hold expired')
    return f

def begin(package,state,folder):
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
    # The kext commits removal before attempting console attachment. A leftover
    # flag means it did not run; clear it before falling back to app mode.
    nv=plistlib.loads(subprocess.check_output(['/usr/sbin/nvram','-xp'],timeout=5))
    if 'phxfb-boot' in nv:
        subprocess.run(['/usr/sbin/nvram','-d','phxfb-boot'],check=True,timeout=5)
        raise ValueError('framebuffer one-shot was not consumed by the running kext')
    unopened_held_framebuffer()
    return True

def arm(report,save,allow,atomic):
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
    atomic(allow,DESKTOP)
    sysctl('debug.phxfb_hold',0)
    if sysctl('debug.phxfb_hold')!=0:raise ValueError('framebuffer hold did not release')
    report['desktop_armed']=True;report['desktop_phase']='awaiting-runtime-evidence';save()

def verify_present(report,save,timeout=120):
    # Registration is not rendering proof. Require actual presents and a live
    # WindowServer framebuffer client, then retain counters as evidence.
    start=sysctl('debug.nvaccel_iop_ok');deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
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
