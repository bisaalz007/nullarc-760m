#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Explicit HP engine experiment. Default is preflight; --execute touches hardware.

No reboot, boot daemon, NVRAM/display takeover or security-setting change. Every
stage is bounded; failure stops, saves evidence and marks bootstrap lost. Native
probes refuse mocks and must pass before the optional accelerator claim.
"""
import argparse
import json
import os
from pathlib import Path
import plistlib
import struct
import subprocess
import sys
import time
import uuid

def macho_uuid(path):
    data=path.read_bytes()
    if data[:4]!=b'\xcf\xfa\xed\xfe':raise ValueError('expected x86_64 Mach-O')
    offset=32
    for _ in range(struct.unpack_from('<I',data,16)[0]):
        command,size=struct.unpack_from('<II',data,offset)
        if size<8 or size>len(data)-offset:raise ValueError('invalid Mach-O command')
        if command==0x1b:return str(uuid.UUID(bytes=data[offset+8:offset+24])).upper()
        offset+=size
    raise ValueError('missing Mach-O UUID')

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--package',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--execute',action='store_true')
    ap.add_argument('--claim',action='store_true',help='claim accelerator only after both native shader probes pass')
    a=ap.parse_args();root=a.package.resolve();tools=root/'gpu/phxctl';firmware=root/'gpu/fw'
    if a.claim and not a.execute:ap.error('--claim requires --execute')
    if a.execute and os.geteuid()!=0:ap.error('local administrator authentication is required')
    if any(k.startswith('RADV_DARWIN_MOCK') for k in os.environ):ap.error('mock transport is forbidden')
    a.output.mkdir(parents=True,exist_ok=False,mode=0o700)
    report={'stages':[],'executed':False,'native_compute_verified':False,'native_render_verified':False,
            'metal_verified':False,'display_takeover_requested':False,'source_package':str(root)}
    began=False
    env={k:v for k,v in os.environ.items() if k in ('PATH','HOME','TMPDIR','LANG','LC_ALL')}
    env['PHX_RADV_DRIVER']=str(root/'PhxGPU/nvmtl/libvulkan_radeon.dylib')
    def save():
        path=a.output/'result.json'
        path.write_text(json.dumps(report,indent=2)+'\n');path.chmod(0o600)
    def run(stage,args,timeout=30,environment=env):
        start=time.monotonic()
        r=subprocess.run([str(v) for v in args],capture_output=True,text=True,timeout=timeout,env=environment)
        report['stages'].append({'stage':stage,'returncode':r.returncode,'seconds':time.monotonic()-start,
                                 'stdout':r.stdout,'stderr':r.stderr})
        save()
        if r.returncode:raise ValueError(f'{stage} failed; inspect result.json; no later stage attempted')
        print(stage+': passed',flush=True)
        return r.stdout
    try:
        run('package-hashes',[sys.executable,root/'package_manifest.py',root])
        for name in ('store.spv','vertex.spv','fragment.spv'):
            code=(root/'validation'/name).read_bytes()
            if len(code)<20 or len(code)%4 or code[:4]!=b'\x03\x02\x23\x07':raise ValueError('invalid or missing native shader fixture')
        plan=run('firmware-plan',[tools/'phxfw','--phoenix-plan',firmware])
        entries=[line.split('\t') for line in plan.splitlines()]
        if len(entries)!=18 or any(len(e)!=5 or Path(e[0]).name!=e[0] for e in entries):raise ValueError('invalid complete firmware plan')
        pcs=run('firmware-entry-points',[tools/'phxfw','--mes-start-pcs',firmware]).split()
        if len(pcs)!=2:raise ValueError('missing scheduler/KIQ entry points')
        env.update(MESBOOT_SCHED_PC=pcs[0],MESBOOT_KIQ_PC=pcs[1])
        registry=plistlib.loads(subprocess.check_output(['/usr/sbin/ioreg','-ar','-c','PhxBringup']))
        service=next((p for p in registry if p.get('phx-profile')=='hp-760m'),None)
        if not service or service.get('phx-build',0)<39:raise ValueError('running build 39+ required')
        expected=macho_uuid(root/'EFI/OC/Kexts/PhxBringup.kext/Contents/MacOS/PhxBringup')
        loaded=run('loaded-kernel-uuid',['/usr/bin/kmutil','showloaded','--list-only'])
        matching=[line for line in loaded.splitlines() if 'org.drip.PhxBringup' in line]
        if not any(expected in line.upper() for line in matching):raise ValueError('running PhxBringup UUID differs from packet')
        report['bringup_uuid']=expected
        if a.claim:
            accel=macho_uuid(root/'Library/Extensions/PhxAccel.kext/Contents/MacOS/PhxAccel')
            if not any(accel in line.upper() and 'com.luuumi.PhxAccel' in line for line in loaded.splitlines()):
                raise ValueError('new accelerator UUID must be loaded before --claim')
        if not a.execute:report['preflight_passed']=True;return
        if service.get('phx-stage')!='profile-diagnostic-only':raise ValueError('fresh diagnostic boot required; no retry after partial initialization')
        report['executed']=True;began=True
        run('exclusive-memory-claim',[tools/'phxctl','begin-hp'])
        run('psp-ring',[tools/'phxctl','psp','create','0x1100000'])
        toc=entries[0]
        if int(toc[3])!=0 or int(toc[4])!=0:raise ValueError('TOC must be staged at firmware offset zero')
        run('toc-stage',[tools/'phxctl','stage',firmware/toc[0],toc[1],toc[2],toc[4]])
        run('toc-required-tmr',[tools/'phxctl','toc',toc[2]])
        run('exclusive-tmr-setup',[tools/'phxctl','tmr'])
        for i,e in enumerate(entries[1:]):
            run(f'firmware-{i}-{e[3]}',[tools/'phxctl','loadfw',firmware/e[0],e[1],e[2],e[3],e[4]])
        run('firmware-autoload',[tools/'phxctl','autoload'])
        for message,arg in [('0x3','0'),('0x2','0'),('0x16','1')]:
            run('smu-'+message,[tools/'phxctl','smu',message,arg])
        time.sleep(2)
        for register,value in [('0xde0','1'),('0xa802','0'),('0xa803','0x01000000')]:
            run('cp-'+register,[tools/'phxctl','wreg',register,value])
        run('owned-gart',[tools/'mesboot','gart'])
        run('mes-firmware-start',[tools/'mesboot','mes'])
        env.update(MESBOOT_MC='1',MESBOOT_CS='1',ADOPT='1',MESBOOT_GFX='1',ADOPT_GFX='1')
        run('mes-queues-and-command-readbacks',[tools/'mesboot','kiqsched'],timeout=60)
        run('native-compute-readback',[tools/'vkprobe-native','--hp'],timeout=60)
        run('native-translated-compute-readback',[tools/'vkprobe-native','--hp','--translated-store',root/'validation/store.spv'],timeout=60)
        report['native_compute_verified']=True;save()
        run('native-translated-render-readback',[tools/'render-native',root/'validation/vertex.spv',root/'validation/fragment.spv'],timeout=60)
        report['native_render_verified']=True;save()
        if a.claim:run('accelerator-claim',[tools/'mesboot','claim'])
    except (ValueError,OSError,subprocess.SubprocessError) as e:
        report['error']=str(e)
        if began:
            try:subprocess.run([str(tools/'phxctl'),'abort'],capture_output=True,timeout=5)
            except (OSError,subprocess.SubprocessError):pass
        print(str(e),file=sys.stderr)
        return 1
    finally:
        save()
        if os.geteuid()==0:
            try:uid=int(os.environ.get('SUDO_UID','0'));gid=int(os.environ.get('SUDO_GID','0'))
            except ValueError:uid=gid=0
            if 0<uid<2**32 and 0<=gid<2**32:
                os.chown(a.output/'result.json',uid,gid);os.chown(a.output,uid,gid)
        print('REPORT: '+str(a.output/'result.json'),flush=True)
    return 0

if __name__=='__main__':raise SystemExit(main())
