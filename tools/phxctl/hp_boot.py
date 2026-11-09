#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Opt-in HP app acceleration at boot; never arms or restarts WindowServer."""
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile

RESTRICTED='# NullArc: built-in test tools only; automatic initialization disabled\n'
APPS='# NullArc: verified HP app acceleration; desktop remains on firmware framebuffer\n-WindowServer\n-mediaanalysisd\n-photoanalysisd\n-Spotlight\n*\n'

def atomic(path,text):
    fd,name=tempfile.mkstemp(prefix='.nullarc-',dir=path.parent)
    try:
        with os.fdopen(fd,'w') as f:f.write(text);f.flush();os.fsync(f.fileno())
        os.chmod(name,0o644);os.replace(name,path)
    finally:Path(name).unlink(missing_ok=True)

def boot(package,state,allow,status=None):
    state.mkdir(parents=True,exist_ok=True,mode=0o700)
    allow.parent.mkdir(parents=True,exist_ok=True)
    atomic(allow,RESTRICTED)
    if status:
        atomic(status,json.dumps({'automatic_initialization_attempted':False,'apps_enabled':False,
            'desktop_armed':False,'recorded_at':datetime.now(timezone.utc).isoformat()})+'\n')
    if (state/'disabled').exists():return 0
    pending=state/'pending'
    if pending.exists():
        (state/'disabled').touch()
        raise ValueError('previous initialization did not finish; disabled until local review')
    fd=os.open(pending,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600);os.close(fd)
    folder=Path(tempfile.mkdtemp(prefix='boot-',dir=state))
    command=[sys.executable,'-B',str(package/'gpu/phxctl/hp_bringup.py'),
             '--package',str(package),'--output',str(folder/'execution'),'--execute','--claim']
    report={'automatic_initialization_attempted':True,'desktop_armed':False}
    try:
        p=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
        try:stdout,stderr=p.communicate(timeout=300)
        except subprocess.TimeoutExpired:
            os.killpg(p.pid,signal.SIGKILL);p.communicate();raise ValueError('bootstrap timeout; reboot and review evidence')
        report.update(returncode=p.returncode,stdout=stdout,stderr=stderr)
        if p.returncode:raise ValueError('bootstrap failed; no application allow list enabled')
        evidence=json.loads((folder/'execution/result.json').read_text())
        if not all(evidence.get(k) is True for k in ('executed','native_compute_verified','native_render_verified','metal_verified')):
            raise ValueError('bootstrap did not prove native compute, render and Metal execution')
        atomic(allow,APPS)
        pending.unlink()
        report['apps_enabled']=True
    except (OSError,ValueError,subprocess.SubprocessError) as e:
        report['error']=str(e);(state/'disabled').touch();raise
    finally:
        (folder/'boot-result.json').write_text(json.dumps(report,indent=2)+'\n')
        if status:
            public={k:v for k,v in report.items() if k not in ('stdout','stderr')}
            public['recorded_at']=datetime.now(timezone.utc).isoformat()
            atomic(status,json.dumps(public,indent=2)+'\n')
    return 0

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--package',type=Path,required=True);a=ap.parse_args()
    if os.geteuid()!=0:ap.error('administrator required')
    try:raise SystemExit(boot(a.package.resolve(),Path('/var/db/nullarc-760m'),Path('/Library/GPUBundles/nvmtl-allow.txt'),Path('/Users/Shared/nullarc-hp-native-status.json')))
    except (OSError,ValueError,subprocess.SubprocessError) as e:ap.exit(1,str(e)+'\n')
