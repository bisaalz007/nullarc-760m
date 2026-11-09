#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Read-only, bounded HP reservation/firmware evidence from a running amdgpu.

Does not unload drivers, mount debugfs, trace/reinitialize hardware or submit
commands. Optional --dcn-profile reads documented configuration registers through
amdgpu's read-only debugfs descriptor. Linux allocations are not macOS ownership.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess
import os
import struct

LIMIT=8*1024*1024

def read(path,errors):
    try:
        with path.open('rb') as f:data=f.read(LIMIT+1)
        if len(data)>LIMIT:raise ValueError('capture limit exceeded')
        return data.decode('utf-8',errors='replace')
    except (OSError,ValueError) as e:
        errors.append({'path':str(path),'error':str(e)})
        return None

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--bdf',default='0000:03:00.0');ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--dcn-profile',type=Path,help='pinned HP DCN configuration-register profile (optional reads)')
    a=ap.parse_args()
    if not re.fullmatch(r'[0-9a-f]{4}:[0-9a-f]{2}:[0-9a-f]{2}\.[0-7]',a.bdf):ap.error('invalid PCI BDF')
    pci=Path('/sys/bus/pci/devices')/a.bdf
    expected={'vendor':0x1002,'device':0x1900,'revision':0xca,'subsystem_vendor':0x103c,'subsystem_device':0x8c6a}
    if any(int((pci/k).read_text(),16)!=v for k,v in expected.items()):ap.error('not the exact HP profile')
    if (pci/'driver').resolve().name!='amdgpu':ap.error('normal amdgpu driver must already be bound')
    errors=[];root=Path('/sys/kernel/debug/dri')/a.bdf
    data={'format':1,'bdf':a.bdf,'pci':expected,'kernel':subprocess.check_output(['uname','-r'],text=True).strip(),
          'source_os':'Linux','macos_memory_ownership_established':False,'collector_gpu_commands_submitted':False,
          'driver_reload_or_register_access':False,'debugfs':{},'sysfs':{},'parameters':{}}
    for n in ['name','amdgpu_firmware_info','amdgpu_vram_mm','amdgpu_gtt_mm']:
        data['debugfs'][n]=read(root/n,errors)
    for n in ['resource','mem_info_vram_total','mem_info_vis_vram_total','mem_info_gtt_total','vbios_version']:
        data['sysfs'][n]=read(pci/n,errors)
    for n in ['mes','mes_kiq','dc','ip_block_mask']:
        data['parameters'][n]=read(Path('/sys/module/amdgpu/parameters')/n,errors)
    r=subprocess.run(['dmesg','--color=never'],capture_output=True,text=True,timeout=15)
    if r.returncode:errors.append({'step':'dmesg','error':r.stderr.strip()})
    relevant=[s for s in r.stdout.splitlines() if 'amdgpu' in s.lower() and
              re.search(r'reserve|TMR|VRAM:|GART:|mes_|kiq|psp|firmware',s,re.I)]
    data['initialization_log']=relevant
    tmrs=[]
    for line in relevant:
        m=re.search(r'reserve (0x[0-9a-f]+) from (0x[0-9a-f]+) for PSP TMR',line,re.I)
        if m:tmrs.append({'bytes':int(m[1],16),'linux_mc_address':int(m[2],16)})
    data['linux_psp_tmr_allocations']=tmrs;data['errors']=errors
    if a.dcn_profile:
        profile=json.loads(a.dcn_profile.read_text())
        if profile['version']!=[3,1,4] or profile['hw_id']!=271:ap.error('expected DCN 3.1.4 profile')
        for reg in profile['registers']:
            if reg['base_index']!=2 or reg['segment_base']!=0x34c0 or reg['dword']!=0x34c0+reg['offset'] or not 0<=reg['dword']<0x20000:
                ap.error('invalid documented register profile')
        fd=os.open(root/'amdgpu_regs',os.O_RDONLY)
        try:
            samples=[]
            for _ in range(2):
                sample=[]
                for reg in profile['registers']:
                    raw=os.pread(fd,4,reg['dword']*4)
                    if len(raw)!=4:raise ValueError('short DCN register reply')
                    sample.append({'name':reg['name'],'dword':reg['dword'],'value':struct.unpack('<I',raw)[0]})
                samples.append(sample)
            data['dcn_samples']=samples
            data['driver_reload_or_register_access']=True
            data['register_writes']=False
        finally:os.close(fd)
    with a.output.open('x') as f:json.dump(data,f,indent=2);f.write('\n')
    print(f'Saved {a.output}; Linux allocations only, no macOS ownership claim')

if __name__=='__main__':main()
