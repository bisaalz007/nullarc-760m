#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Back up and stage a matching experimental packet; never initializes the GPU."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--package',type=Path,required=True);ap.add_argument('--oc',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True);ap.add_argument('--execute',action='store_true')
    a=ap.parse_args();root=a.package.resolve()
    if a.execute and os.geteuid()!=0:ap.error('local administrator authentication required')
    a.output.mkdir(parents=True,exist_ok=False,mode=0o700)
    report={'stages':[],'gpu_initialization_attempted':False,'accelerator_loaded_verified':False}
    def save():
        p=a.output/'result.json';p.write_text(json.dumps(report,indent=2)+'\n');p.chmod(0o600)
    def run(name,args,allow_load_refusal=False):
        r=subprocess.run([str(x) for x in args],cwd=root,capture_output=True,text=True,timeout=180)
        report['stages'].append({'stage':name,'returncode':r.returncode,'stdout':r.stdout,'stderr':r.stderr});save()
        refusal=allow_load_refusal and any(token in r.stdout+r.stderr for token in ['KMErrorDomain Code=27','KMErrorDomain Code=28'])
        if r.returncode and not refusal:raise ValueError(name+' failed; inspect result.json before rebooting')
        if refusal:report['macos_approval_or_reboot_required']=True
        print(name+(': OS approval/reboot required' if refusal else ': passed'),flush=True)
        return r.stdout+r.stderr
    try:
        run('component-preflight',[root/'install.sh','--components','--check'])
        run('usb-efi-preflight',[root/'install.sh','--diagnostics','--oc',a.oc,'--check'])
        if a.execute:
            help_text=run('accelerator-load-capabilities',['/usr/bin/kmutil','load','--help'])
            if '--load-style' not in help_text or 'start-only' not in help_text:
                raise ValueError('kmutil start-only load style unavailable; no files installed')
            run('component-backup-and-copy',[root/'install.sh','--components'])
            run('usb-efi-backup-and-copy',[root/'install.sh','--diagnostics','--oc',a.oc])
            run('accelerator-update-request',['/usr/bin/kmutil','load','--bundle-path','/Library/Extensions/PhxAccel.kext','--load-style','start-only'],True)
            report['files_staged']=True
    except (OSError,ValueError,subprocess.SubprocessError) as e:
        report['error']=str(e);print(str(e),file=sys.stderr);return 1
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
