#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Explicit, backed-up NullArc AMFI boot-option experiment; default is read-only.

This relaxes system-wide signing policy. It does not enable GPU initialization,
arm a display boot, or establish that Sequoia honors the requested policy.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import plistlib
import shlex
import subprocess
import sys
import tempfile

GUID='7C436110-AB2A-4BBB-A880-FE41995C9F82'
FLAGS=('amfi=0x80','amfi_get_out_of_my_way=0x1','-amfipassbeta','phxdebug=1')
REFERENCE='https://github.com/luuumi-dev/nullarc/blob/main/docs/INSTALL.md'

def derive(config):
    result=copy.deepcopy(config)
    nv=result['NVRAM'];values=nv['Add'][GUID];before=values.get('boot-args')
    if not isinstance(before,str):raise ValueError('existing boot-args string required')
    if 'boot-args' not in nv.get('Delete',{}).get(GUID,[]):raise ValueError('existing NVRAM Delete must already replace boot-args')
    csr=values.get('csr-active-config')
    # Preserve the HP's existing SIP bits; do not copy another machine's mask.
    if not isinstance(csr,bytes) or len(csr)!=4 or int.from_bytes(csr,'little')&0x87f!=0x87f:
        raise ValueError('existing SIP configuration does not cover NullArc requirements; separate review needed')
    if result['Misc']['Security'].get('SecureBootModel')!='Disabled':raise ValueError('SecureBootModel requires separate review')
    if result['Misc']['Security'].get('Vault')!='Optional':raise ValueError('OpenCore vault configuration requires separate review')
    tokens=shlex.split(before);missing=[]
    for flag in FLAGS:
        key=flag.split('=')[0]
        found=[x for x in tokens if x.split('=')[0]==key]
        if found and found!=[flag]:raise ValueError('conflicting/duplicate existing option: '+key)
        if not found:missing.append(flag)
    values['boot-args']=before+(' '+' '.join(missing) if missing else '')
    return result

def configure(package,oc,apply=False):
    sys.path.insert(0,str(package))
    from package_manifest import verify
    from install_diagnostics import atomic_write,configuration
    verify(package)
    policy=subprocess.check_output([sys.executable,'-B',str(package/'collect_macos_evidence.py'),'--target-policy'],text=True,timeout=30).strip()
    if policy!='hp-diagnostic-only':raise ValueError('exact captured HP identity required')
    boot=subprocess.check_output(['/usr/sbin/sysctl','-n','kern.bootsessionuuid'],text=True,timeout=5).strip().upper()
    status=json.loads(Path('/Users/Shared/nullarc-hp-native-status.json').read_text())
    if status.get('boot_session_uuid')!=boot or any(status.get(k) is not False for k in ('automatic_initialization_attempted','apps_enabled','desktop_armed')):
        raise ValueError('idle disabled fallback boot required')
    for name in ('PhxAMDFB','NMXAccel'):
        raw=subprocess.check_output(['/usr/sbin/ioreg','-ar','-c',name],timeout=15)
        if raw.strip() and plistlib.loads(raw):raise ValueError('custom GPU/display service active')
    nv=plistlib.loads(subprocess.check_output(['/usr/sbin/nvram','-xp'],timeout=5))
    if 'phxfb-boot' in nv:raise ValueError('display must remain unarmed for the policy-only reboot')
    original,config,entries=configuration(oc)
    for name in ('Lilu.kext','AMFIPass.kext','PhxBringup.kext'):
        if len([e for e in entries if e.get('BundlePath')==name and e.get('Enabled') is True])!=1:
            raise ValueError('existing enabled dependency required: '+name)
    info=plistlib.loads((oc/'Kexts/PhxBringup.kext/Contents/Info.plist').read_bytes())
    if 'PhxFBEarlyHP' in info.get('IOKitPersonalities',{}):raise ValueError('remove reviewed early display opt-in before policy-only test')
    after=derive(config)
    report={'reference':REFERENCE,'before':config['NVRAM']['Add'][GUID]['boot-args'],
            'after':after['NVRAM']['Add'][GUID]['boot-args'],'applied':False,
            'gpu_initialization_enabled':False,'display_armed':False,'policy_effect_verified':False}
    if not apply or after==config:return report
    backup=Path(tempfile.mkdtemp(prefix='.nullarc-amfi-policy-backup-',dir=oc))
    (backup/'config.plist').write_bytes(original)
    encoded=plistlib.dumps(after,sort_keys=False);path=oc/'config.plist'
    try:
        if path.read_bytes()!=original:raise ValueError('OpenCore config changed during preparation')
        atomic_write(path,encoded)
        if path.read_bytes()!=encoded or plistlib.loads(path.read_bytes())!=after:raise ValueError('policy readback mismatch')
    except BaseException:
        if path.read_bytes()==encoded:atomic_write(path,original)
        raise
    report.update(applied=True,backup=str(backup),before_sha256=hashlib.sha256(original).hexdigest(),after_sha256=hashlib.sha256(encoded).hexdigest())
    (backup/'receipt.json').write_text(json.dumps(report,indent=2)+'\n')
    return report

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--package',type=Path,required=True);ap.add_argument('--oc',type=Path,required=True)
    ap.add_argument('--apply-upstream-policy',action='store_true',help='explicitly apply the system-wide relaxed signing-policy experiment')
    a=ap.parse_args()
    try:print(json.dumps(configure(a.package.resolve(),a.oc.resolve(),a.apply_upstream_policy),indent=2))
    except (OSError,ValueError,KeyError,subprocess.SubprocessError) as e:ap.exit(1,str(e)+'\n')
