#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Read the existing HP firmware display timing. No modesetting or GPU commands."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import subprocess
import time

def decode_timing(profile,first,second,elapsed_ns):
    definitions={r['name']:r for r in profile['registers']}
    def value(suffix,field):
        name='regOTG0_OTG_'+suffix;r=definitions[name];prefix=name[3:]+'__'+field
        return (second[name]&r['fields'][prefix+'_MASK'])>>r['fields'][prefix+'__SHIFT']
    for name in definitions:
        if name!='regOTG0_OTG_STATUS_FRAME_COUNT' and first[name]!=second[name]:raise ValueError('timing changed during capture: '+name)
    if not value('CONTROL','OTG_MASTER_EN'):raise ValueError('OTG0 is not enabled')
    if value('INTERLACE_CONTROL','OTG_INTERLACE_ENABLE'):raise ValueError('interlaced timing is not supported by this decoder')
    out={}
    for axis in ('H','V'):
        total=value(axis+'_TOTAL','OTG_'+axis+'_TOTAL')+1
        start=value(axis+'_BLANK_START_END','OTG_'+axis+'_BLANK_START')
        end=value(axis+'_BLANK_START_END','OTG_'+axis+'_BLANK_END')
        sync_start=value(axis+'_SYNC_A','OTG_'+axis+'_SYNC_A_START')
        sync_end=value(axis+'_SYNC_A','OTG_'+axis+'_SYNC_A_END')
        if sync_start or not (0<=end<start<total) or not (0<sync_end<=end):raise ValueError('unsupported '+axis+' timing coordinates')
        active=start-end;front=total-start
        out[axis.lower()]={'active':active,'total':total,'front_porch':front,'sync_width':sync_end,
                          'sync_start':active+front,'sync_end':active+front+sync_end,
                          'sync_positive':not bool(value(axis+'_SYNC_A_CNTL','OTG_'+axis+'_SYNC_A_POL'))}
    frames=(value('STATUS_FRAME_COUNT','OTG_FRAME_COUNT')-(first['regOTG0_OTG_STATUS_FRAME_COUNT']&0xffffff))&0xffffff
    if elapsed_ns<=0 or frames<1:raise ValueError('no measurable OTG frame progress')
    out.update(frame_count_delta=frames,elapsed_ns=elapsed_ns,estimated_refresh_millihz=frames*10**12//elapsed_ns)
    out['estimated_pixel_clock_hz']=out['h']['total']*out['v']['total']*frames*10**9//elapsed_ns
    out['pixel_clock_measured_directly']=False
    return out

def read_registers(tool,profile):
    registers=profile['registers'];addresses=[r['dword'] for r in registers]
    if len(registers)!=14 or len(set(addresses))!=14 or any(r['base_index']!=2 or r['segment_base']!=0x34c0 or r['dword']!=r['segment_base']+r['offset'] for r in registers):
        raise ValueError('unexpected documented DCN 3.1.4 register table')
    before=time.monotonic_ns()
    raw=subprocess.check_output([str(tool),'regs']+[hex(a) for a in addresses],text=True,timeout=15)
    after=time.monotonic_ns();values={}
    for line in raw.splitlines():
        match=re.fullmatch(r'0x([0-9a-fA-F]+): 0x([0-9a-fA-F]+)',line.strip())
        if not match:raise ValueError('unexpected register response: '+line)
        address,value=(int(s,16) for s in match.groups())
        if address in values or value==0xffffffff:raise ValueError('invalid register response')
        values[address]=value
    if set(values)!=set(addresses):raise ValueError('missing/extra register response')
    return {'timestamp_ns':(before+after)//2,'read_interval_ns':[before,after],
            'registers':{r['name']:values[r['dword']] for r in registers}}

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--profile',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
    if os.geteuid()!=0:ap.error('administrator required for the existing read-register selector')
    package=Path(plistlib.loads(Path('/Library/LaunchDaemons/local.nullarc.hp-native.plist').read_bytes())['ProgramArguments'][-1])
    if package.parent!=Path('/Library/Application Support/NullArc760M'):raise ValueError('unexpected native package location')
    nodes=plistlib.loads(subprocess.check_output(['/usr/sbin/ioreg','-ar','-c','PhxBringup']))
    if not any(n.get('phx-profile')=='hp-760m' and n.get('phx-stage')=='native-queues-ready' for n in nodes):raise ValueError('healthy HP native service required')
    profile=json.loads(a.profile.read_text())
    first=read_registers(package/'gpu/phxctl/phxctl',profile);time.sleep(1)
    second=read_registers(package/'gpu/phxctl/phxctl',profile)
    report={'format':1,'profile_sha256':hashlib.sha256(a.profile.read_bytes()).hexdigest(),
            'register_writes':False,'gpu_commands_submitted':False,'samples':[first,second]}
    try:report['timing']=decode_timing(profile,first['registers'],second['registers'],second['timestamp_ns']-first['timestamp_ns'])
    except (ValueError,KeyError) as e:report['timing_decode_error']=str(e)
    with a.output.open('x') as f:json.dump(report,f,indent=2);f.write('\n')
    a.output.chmod(0o600)
    uid=int(os.environ.get('SUDO_UID','0'));gid=int(os.environ.get('SUDO_GID','0'))
    if 0<uid<2**32 and 0<=gid<2**32:os.chown(a.output,uid,gid)
    print('Read-only display capture: '+str(a.output))
if __name__=='__main__':main()
