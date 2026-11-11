#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Backed-up metadata-only ACPI dependency repair plus verified aux update."""
import argparse
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import tempfile
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'tools'))
from package_manifest import verify,write,inventory,digest
from install_diagnostics import atomic_write
import update_hp_aux as aux

def repair(package,bundle,parent,daemon,target,state):
    verify(package)
    original=daemon.read_bytes();config=plistlib.loads(original)
    expected=['/usr/bin/python3','-B',str(package/'gpu/phxctl/hp_boot.py'),'--package',str(package)]
    if config.get('ProgramArguments')!=expected:raise ValueError('service package differs')
    relative='Library/Extensions/PhxAccel.kext'
    if inventory(target)!=inventory(package/relative):raise ValueError('installed bundle differs')
    subprocess.run(['/usr/bin/codesign','--verify','--strict',str(bundle)],check=True,timeout=15)
    aux.update(package,state,False)  # reviewed idle/cache/failure preflight
    before_uuid=aux.inspect(aux.KC)[aux.IDENTIFIER]['uuid']
    backup=Path(tempfile.mkdtemp(prefix='acpi-dependency-',dir=state))
    (backup/'daemon.plist').write_bytes(original);shutil.copytree(target,backup/'PhxAccel.kext')
    destination=Path(tempfile.mkdtemp(prefix='package-acpi-',dir=parent));destination.rmdir()
    config=dict(config)
    config['ProgramArguments']=['/usr/bin/python3','-B',str(destination/'gpu/phxctl/hp_boot.py'),'--package',str(destination)]
    report={'original_package':str(package),'new_package':str(destination),'backup':str(backup),'compiled_code_changed':False,
            'windowserver_armed':False,'security_settings_changed':False}
    def save():(backup/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    changed=False
    try:
        shutil.copytree(package,destination);shutil.rmtree(destination/relative);shutil.copytree(bundle,destination/relative)
        aux.validate_acpi_patch(package,destination)
        metadata=json.loads((destination/'package-manifest.json').read_text())
        metadata['accel_metadata_patch']={'dependency':'com.apple.iokit.IOACPIFamily','minimum_version':'1.0',
                                        'original_manifest_sha256':digest(package/'package-manifest.json'),
                                        'program_bytes_unchanged':True}
        write(destination,metadata);verify(destination)
        for p in [destination]+list(destination.rglob('*')):
            if p.is_symlink():raise ValueError('symlink in staged package')
            os.chown(p,0,0);p.chmod(p.stat().st_mode&0o755)
        with tempfile.TemporaryDirectory(prefix='.nullarc-acpi-',dir=target.parent) as tmp:
            staged=Path(tmp)/'PhxAccel.kext';shutil.copytree(destination/relative,staged)
            if daemon.read_bytes()!=original or inventory(target)!=inventory(package/relative):raise ValueError('installation changed during staging')
            target.rename(Path(tmp)/'previous.kext');changed=True;staged.rename(target)
        atomic_write(daemon,plistlib.dumps(config));daemon.chmod(0o644)
        if inventory(target)!=inventory(destination/relative) or plistlib.loads(daemon.read_bytes())!=config:raise ValueError('installation readback mismatch')
        report['metadata_staged']=True;save()
        aux.update(destination,state,True,failure_package=package)
        report['auxiliary_update_verified']=True;save()
        print('Dependency repair completed; unchanged driver code, new package: '+str(destination))
        print('Backup: '+str(backup))
        return destination
    except BaseException as e:
        report['error']=str(e)
        try:
            current=aux.inspect(aux.KC)[aux.IDENTIFIER]['uuid']
            if current==before_uuid:
                if changed and inventory(target)==inventory(destination/relative):
                    shutil.rmtree(target);shutil.copytree(backup/'PhxAccel.kext',target)
                if daemon.read_bytes()==plistlib.dumps(config):atomic_write(daemon,original)
                report['metadata_rolled_back']=True
            else:report['metadata_retained_for_published_collection']=True
        except Exception as review:report['rollback_review_required']=str(review)
        save();raise

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--package',type=Path,required=True);ap.add_argument('--bundle',type=Path,required=True);a=ap.parse_args()
    if os.geteuid()!=0:ap.error('local administrator authentication required')
    try:repair(a.package.resolve(),a.bundle.resolve(),Path('/Library/Application Support/NullArc760M'),
               Path('/Library/LaunchDaemons/local.nullarc.hp-native.plist'),Path('/Library/Extensions/PhxAccel.kext'),Path('/var/db/nullarc-760m'))
    except (OSError,ValueError,subprocess.SubprocessError) as e:ap.exit(1,str(e)+'\n')
