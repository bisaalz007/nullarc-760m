#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Opt-in early HP framebuffer personality in the already-injected boot kext.

Changes only that kext's Info.plist, with backup. No executable, OpenCore config,
cache, NVRAM, security or live driver change. Default is --check.
"""
import argparse
import copy
import json
from pathlib import Path
import plistlib
import subprocess
import sys
import tempfile
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'tools'))
from package_manifest import verify,digest
from install_diagnostics import atomic_write,configuration
from collect_macos_evidence import EXPECTED

KEY='PhxFBEarlyHP'

def derive(bringup,accel):
    if bringup.get('CFBundleIdentifier')!='org.drip.PhxBringup' or bringup.get('OSBundleRequired')!='Root':
        raise ValueError('expected the existing Root PhxBringup publisher')
    p=copy.deepcopy(accel.get('IOKitPersonalities',{}).get('PhxFB',{}))
    wanted={'CFBundleIdentifier':'com.luuumi.PhxAccel','IOClass':'PhxAMDFB','IOProviderClass':'IOPCIDevice',
            'IOPCIPrimaryMatch':'0x19001002','IOMatchCategory':'IOFramebuffer','IOProbeScore':60000}
    if p!=wanted:raise ValueError('unreviewed framebuffer personality')
    # Apple OSKext supports personalities referencing another kext's code. Only
    # metadata is published early; graphics symbols remain in System/Aux KC.
    p['CFBundleIdentifierKernel']=p['CFBundleIdentifier']
    p['IOPersonalityPublisher']=bringup['CFBundleIdentifier']
    p['IOPropertyMatch']={k:v.to_bytes(4,'little') for k,v in EXPECTED.items()}
    result=copy.deepcopy(bringup);table=result.get('IOKitPersonalities')
    if not isinstance(table,dict):raise ValueError('missing publisher personalities')
    if KEY in table and table[KEY]!=p:raise ValueError('existing early personality differs')
    table[KEY]=p
    return result

def install(package,oc,apply=False):
    verify(package)
    policy=subprocess.check_output([sys.executable,'-B',str(package/'collect_macos_evidence.py'),'--target-policy'],text=True).strip()
    if policy!='hp-diagnostic-only':raise ValueError('exact captured HP identity required')
    original_config,config,entries=configuration(oc)
    entry=[e for e in entries if e.get('BundlePath')=='PhxBringup.kext' and e.get('Enabled') is True]
    if len(entry)!=1 or entry[0].get('ExecutablePath')!='Contents/MacOS/PhxBringup':raise ValueError('existing enabled PhxBringup injection required')
    bundle=oc/'Kexts/PhxBringup.kext';info=bundle/'Contents/Info.plist';binary=bundle/'Contents/MacOS/PhxBringup'
    reference=package/'EFI/OC/Kexts/PhxBringup.kext/Contents/MacOS/PhxBringup'
    code_hash=digest(binary)
    if code_hash!=digest(reference):raise ValueError('USB bring-up executable differs from verified package')
    original=info.read_bytes();before=plistlib.loads(original)
    accel=plistlib.loads((package/'Library/Extensions/PhxAccel.kext/Contents/Info.plist').read_bytes())
    after=derive(before,accel)
    if not apply:return {'checked':True,'changed':False,'executable_sha256':code_hash}
    if after==before:return {'checked':True,'changed':False,'already_installed':True}
    backup=Path(tempfile.mkdtemp(prefix='.nullarc-early-match-backup-',dir=oc))
    (backup/'Info.plist').write_bytes(original)
    encoded=plistlib.dumps(after,sort_keys=False)
    try:
        if info.read_bytes()!=original or (oc/'config.plist').read_bytes()!=original_config:raise ValueError('EFI changed during preparation')
        atomic_write(info,encoded)
        if info.read_bytes()!=encoded or digest(binary)!=code_hash or (oc/'config.plist').read_bytes()!=original_config:
            raise ValueError('early personality readback mismatch')
    except BaseException:
        if info.read_bytes()==encoded:atomic_write(info,original)
        raise
    report={'checked':True,'changed':True,'backup':str(backup),'executable_sha256':code_hash,
            'open_core_config_changed':False,'nvram_changed':False,'personality':KEY,'hardware_writes':False}
    (backup/'receipt.json').write_text(json.dumps(report,indent=2)+'\n')
    return report

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--package',type=Path,required=True);ap.add_argument('--oc',type=Path,required=True);ap.add_argument('--install',action='store_true');a=ap.parse_args()
    try:print(json.dumps(install(a.package.resolve(),a.oc.resolve(),a.install),indent=2))
    except (OSError,ValueError,subprocess.SubprocessError) as e:ap.exit(1,str(e)+'\n')
