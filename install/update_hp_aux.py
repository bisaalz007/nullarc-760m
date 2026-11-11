#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Replace a stale HP auxiliary collection after the reviewed UUID-only failure.

Builds only an auxiliary candidate against the running volume's existing boot
and system collections. No approval bypass, EFI/security/NVRAM changes, GPU
initialization or automatic reboot. --update requires local root authentication.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'tools'))
from package_manifest import verify,inventory,digest
from install_diagnostics import atomic_write

IDENTIFIER='com.luuumi.PhxAccel'
KC=Path('/Library/KernelCollections/AuxiliaryKernelExtensions.kc')
UUID=r'[0-9A-Fa-f]{8}(?:-[0-9A-Fa-f]{4}){3}-[0-9A-Fa-f]{12}'

def extensions(text):
    entries={}
    for line in text.splitlines():
        if not line.strip() or line.strip()=='Extension Information:':continue
        m=re.fullmatch(r'([^\s]+)\s+([^\s]+)\s+(/.+?\.kext)(?:\s+\(('+UUID+r')\))?\s*',line)
        if not m:raise ValueError('unrecognized collection entry: '+line)
        name,version,path,uuid=m.groups()
        if name in entries:raise ValueError('duplicate collection identifier: '+name)
        if not path.startswith(('/Library/Extensions/','/Library/Apple/System/Library/Extensions/')):
            raise ValueError('unexpected auxiliary source: '+path)
        entries[name]={'version':version,'path':path,'uuid':uuid.upper() if uuid else None}
    if IDENTIFIER not in entries:raise ValueError('accelerator absent from auxiliary collection')
    return entries

def inspect(path):
    return extensions(subprocess.check_output(['/usr/bin/kmutil','inspect','-a','x86_64','-A',str(path),
        '--show-kext-uuids','--no-header'],text=True,timeout=30))

def validate_candidate(before,after,expected):
    if set(before)!=set(after):raise ValueError('auxiliary extension set changed')
    for name in before:
        wanted=dict(before[name])
        if name==IDENTIFIER:wanted['uuid']=expected
        if after[name]!=wanted:raise ValueError('unexpected candidate extension: '+name)

def validate_failure(status,evidence,package,boot):
    if (status.get('boot_session_uuid')!=boot or status.get('last_stage')!='loaded-kernel-uuid' or
        status.get('bootstrap_error')!='new accelerator UUID must be loaded before --claim' or
        status.get('native_compute_verified') is not False or status.get('native_render_verified') is not False or
        evidence.get('source_package')!=str(package) or evidence.get('executed') is not False or
        evidence.get('error')!='new accelerator UUID must be loaded before --claim'):
        raise ValueError('failure differs from the reviewed pre-initialization UUID mismatch')
    stages=evidence.get('stages',[])
    # showloaded itself succeeds; the following explicit UUID comparison fails.
    if not stages or stages[-1].get('stage')!='loaded-kernel-uuid':
        raise ValueError('missing failed UUID stage')
    if any(s.get('returncode')!=0 for s in stages):raise ValueError('bootstrap command failed before UUID comparison')

def publish(candidate,target,backup,original_hash):
    if digest(target)!=original_hash:raise ValueError('auxiliary collection changed during build')
    shutil.copy2(target,backup/'AuxiliaryKernelExtensions.kc')
    fd,name=tempfile.mkstemp(prefix='.nullarc-aux-',dir=target.parent);os.close(fd);stage=Path(name)
    try:
        shutil.copy2(candidate,stage);os.chown(stage,0,0)
        with stage.open('rb') as f:os.fsync(f.fileno())
        if digest(stage)!=digest(candidate) or digest(target)!=original_hash:raise ValueError('collection publish check failed')
        os.replace(stage,target)
        if digest(target)!=digest(candidate):raise ValueError('published collection readback mismatch')
    finally:stage.unlink(missing_ok=True)

def update(package,state,apply=False):
    verify(package)
    sys.path.insert(0,str(package/'gpu/phxctl'))
    from hp_bringup import macho_uuid
    import hp_windowserver as display
    boot=display.boot_uuid()
    if not subprocess.check_output(['/usr/bin/sw_vers','-productVersion'],text=True).startswith('15.'):
        raise ValueError('Sequoia required')
    if subprocess.check_output([sys.executable,'-B',str(package/'collect_macos_evidence.py'),'--target-policy'],text=True).strip()!='hp-diagnostic-only':
        raise ValueError('exact captured HP identity required')
    if display.nodes('NMXAccel') or display.nodes('PhxAMDFB'):raise ValueError('accelerator/framebuffer active; no collection repair')
    if not any(n.get('phx-profile')=='hp-760m' and n.get('phx-stage')=='profile-diagnostic-only' for n in display.nodes('PhxBringup')):
        raise ValueError('idle diagnostic HP required')
    if 'phxfb-boot' in plistlib.loads(subprocess.check_output(['/usr/sbin/nvram','-xp'])):raise ValueError('framebuffer arming present')
    status=json.loads(Path('/Users/Shared/nullarc-hp-native-status.json').read_text())
    reports=[p for p in state.glob('boot-*/boot-result.json') if json.loads(p.read_text()).get('boot_session_uuid')==boot]
    if len(reports)!=1:raise ValueError('one protected current-boot report required')
    evidence=json.loads((reports[0].parent/'execution/result.json').read_text())
    validate_failure(status,evidence,package,boot)
    for name in ('pending','disabled'):
        if not (state/name).is_file() or (state/name).is_symlink():raise ValueError('reviewed failure markers missing')
    before=inspect(KC);original_hash=digest(KC)
    source=package/'Library/Extensions/PhxAccel.kext'
    if inventory(source)!=inventory(Path('/Library/Extensions/PhxAccel.kext')):raise ValueError('installed accelerator differs from immutable package')
    expected=macho_uuid(source/'Contents/MacOS/PhxAccel')
    loaded=subprocess.check_output(['/usr/bin/kmutil','showloaded','--list-only'],text=True)
    rows=[line for line in loaded.splitlines() if IDENTIFIER+' (' in line]
    if len(rows)!=1 or int(rows[0].split()[1])!=0 or not before[IDENTIFIER]['uuid'] or before[IDENTIFIER]['uuid'] not in rows[0].upper():
        raise ValueError('running idle module must match the stale collection')
    if before[IDENTIFIER]['uuid']==expected:raise ValueError('collection already contains new UUID; investigate boot source')
    sources={entry['path']:inventory(Path(entry['path'])) for entry in before.values()}
    if not apply:print('Reviewed UUID-only failure; idle old module and stale auxiliary collection confirmed. No changes.');return
    if os.geteuid()!=0:raise ValueError('local administrator authentication required')
    backup=Path(tempfile.mkdtemp(prefix='aux-update-',dir=state))
    candidate=backup/'candidate.kc'
    command=['/usr/bin/kmutil','create','-n','aux','--volume-root','/',
        '--kernel','/System/Library/Kernels/kernel',
        '-B','/System/Library/KernelCollections/BootKernelExtensions.kc',
        '-S','/System/Library/KernelCollections/SystemKernelExtensions.kc',
        '--repository','/Library/Extensions','--repository','/Library/Apple/System/Library/Extensions',
        '--explicit-only','--allow-missing-kdk']
    # The documented missing-KDK option is scoped to this aux-only build against
    # existing exact-system collections, as in the repository's kinst.sh. Unlike
    # that reference script, do NOT use -z/--no-authorization or replace boot/sys.
    for entry in before.values():command+=['--bundle-path',entry['path']]
    command+=['-A',str(candidate)]
    report={'boot_session_uuid':boot,'expected_accelerator_uuid':expected,'command':command,'published':False,
            'gpu_commands_submitted':False,'windowserver_armed':False,'backup':str(backup)}
    def save():(backup/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    try:
        r=subprocess.run(command,capture_output=True,text=True,timeout=180)
        report.update(returncode=r.returncode,stdout=r.stdout,stderr=r.stderr);save()
        if r.returncode:raise ValueError('auxiliary candidate build failed; nothing published: '+r.stderr.strip())
        after=inspect(candidate);validate_candidate(before,after,expected)
        if display.boot_uuid()!=boot:raise ValueError('boot changed during build')
        if any(inventory(Path(path))!=files for path,files in sources.items()):raise ValueError('source extensions changed during build')
        report['candidate_entries']=after;save()
        publish(candidate,KC,backup,original_hash);report['published']=True;save()
        validate_candidate(before,inspect(KC),expected)
        # Preserve the failure and its markers. Only this exact pre-GPU mismatch
        # permits enabling the next boot; never retry initialization in this boot.
        moved=[]
        try:
            for name in ('pending','disabled'):(state/name).rename(backup/name);moved.append(name)
        except BaseException:
            for name in reversed(moved):(backup/name).rename(state/name)
            raise
        report['next_boot_enabled']=True;save()
        print('Auxiliary collection updated and verified: '+expected)
        print('All other auxiliary extensions preserved. Next app-only boot enabled; no current GPU initialization or reboot.')
        print('Backup: '+str(backup))
    except BaseException as e:report['error']=str(e);save();raise

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--package',type=Path,required=True);ap.add_argument('--update',action='store_true');a=ap.parse_args()
    try:update(a.package.resolve(),Path('/var/db/nullarc-760m'),a.update)
    except (OSError,ValueError,subprocess.SubprocessError) as e:ap.exit(1,str(e)+'\n')
