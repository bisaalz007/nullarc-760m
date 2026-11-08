#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Read-only Linux companion capture. Requires the normal amdgpu driver.

No module unload/reload, firmware loading, register access, GPU reset, or debugfs
mount is performed. Missing/privileged data is recorded explicitly.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess

MAX_FILE = 8 * 1024 * 1024
SYSFS_FILES = ('vendor','device','revision','subsystem_vendor','subsystem_device','class','resource',
 'mem_info_vram_total','mem_info_vis_vram_total','mem_info_gtt_total','vbios_version','pp_dpm_sclk','pp_dpm_mclk')
DEBUG_FILES = ('name','amdgpu_firmware_info','amdgpu_vram_mm','amdgpu_gtt_mm')


def copy_attribute(source, target, errors):
    try:
        with source.open('rb') as f: data = f.read(MAX_FILE + 1)
        if len(data) > MAX_FILE: raise ValueError('attribute exceeds capture limit')
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    except (OSError, ValueError) as e:
        errors.append({'path':str(source),'error':str(e)})


def copy_sysfs(device, dest, errors):
    for name in SYSFS_FILES: copy_attribute(device/name, dest/name, errors)
    ip = device/'ip_discovery'
    if not ip.is_dir():
        errors.append({'path':str(ip),'error':'IP discovery sysfs is unavailable'})
        return
    for path in sorted(ip.rglob('*')):
        if path.is_file() and path.resolve().is_relative_to(ip.resolve()):
            copy_attribute(path, dest/'ip_discovery'/path.relative_to(ip), errors)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--device', type=Path, required=True, help='/dev/dri/renderD128 for the HP')
    ap.add_argument('--collector', type=Path, required=True, help='compiled collect.c executable')
    ap.add_argument('--output', type=Path, required=True)
    a = ap.parse_args()
    st = a.device.stat()
    if not stat.S_ISCHR(st.st_mode): ap.error('expected a DRM character device')
    device = (Path('/sys/dev/char')/f'{os.major(st.st_rdev)}:{os.minor(st.st_rdev)}'/'device').resolve(strict=True)
    bdf = device.name
    if not re.fullmatch(r'[0-9a-f]{4}:[0-9a-f]{2}:[0-9a-f]{2}\.[0-7]', bdf): ap.error('DRM device has no PCI parent')
    ids = {key:int((device/name).read_text(),16) for key,name in [('vendor','vendor'),('device','device'),
        ('revision','revision'),('subvendor','subsystem_vendor'),('subdevice','subsystem_device')]}
    if ids != {'vendor':0x1002,'device':0x1900,'revision':0xca,'subvendor':0x103c,'subdevice':0x8c6a}:
        ap.error('DRM node is not the exact captured HP PCI identity')
    a.output.mkdir(parents=True, exist_ok=False)
    errors = []
    result = subprocess.run([str(a.collector.resolve()),str(a.device)],capture_output=True)
    (a.output/'profile.json').write_bytes(result.stdout)
    (a.output/'hw-ip.txt').write_bytes(result.stderr)
    if result.returncode: errors.append({'step':'DRM INFO query','returncode':result.returncode})
    copy_sysfs(device,a.output/'sysfs',errors)
    debug = Path('/sys/kernel/debug/dri')
    found_debug = False
    try:
        for node in debug.iterdir():
            try: name = (node/'name').read_text()
            except OSError: continue
            if bdf not in name: continue
            found_debug = True
            for filename in DEBUG_FILES: copy_attribute(node/filename,a.output/'debugfs'/filename,errors)
    except OSError as e: errors.append({'path':str(debug),'error':str(e)})
    if not found_debug: errors.append({'step':'debugfs','error':'target debugfs unavailable; root may be required'})
    log = subprocess.run(['dmesg','--color=never'],capture_output=True,text=True)
    if log.returncode: errors.append({'step':'dmesg','error':log.stderr.strip()})
    else:
        relevant = [line for line in log.stdout.splitlines() if re.search(r'amdgpu|'+re.escape(bdf[5:]),line,re.I)]
        (a.output/'amdgpu-dmesg.txt').write_text('\n'.join(relevant)+'\n')
    candidates = []
    fw = Path('/lib/firmware/amdgpu')
    if fw.is_dir():
        for path in sorted(fw.iterdir()):
            if not path.is_file() or not path.name.startswith(('gc_11_','psp_13_','sdma_6_','dcn_3_1_4')): continue
            try:
                data = path.read_bytes()
                candidates.append({'name':path.name,'size':len(data),'sha256':hashlib.sha256(data).hexdigest()})
            except OSError as e: errors.append({'path':str(path),'error':str(e)})
    (a.output/'firmware-files.json').write_text(json.dumps({'meaning':'candidate files present; not proof of loading',
        'files':candidates},indent=2)+'\n')
    report = {'format':1,'captured_at':datetime.now(timezone.utc).isoformat(),'pci':ids,'bdf':bdf,
        'kernel':os.uname().release,'os_release':Path('/etc/os-release').read_text(),
        'register_access':False,'driver_reloaded':False,'errors':errors}
    (a.output/'capture.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'output':str(a.output),'pci':ids,'errors':len(errors),'read_only':True}))
    return result.returncode


if __name__ == '__main__': raise SystemExit(main())
