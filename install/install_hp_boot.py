#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Stage an opt-in HP app-only boot service after verifying the installed stack."""
import argparse
import hashlib
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'tools'));sys.path.insert(0,str(HERE))
from package_manifest import verify

def preflight(package):
    document=verify(package)
    if document.get('minimum_macos')!='15.0' or not subprocess.check_output(['sw_vers','-productVersion'],text=True).startswith('15.'):
        raise ValueError('this HP boot service requires the Sequoia package and macOS 15')
    policy=subprocess.check_output([sys.executable,'-B',str(package/'collect_macos_evidence.py'),'--target-policy'],text=True).strip()
    if policy!='hp-diagnostic-only':raise ValueError('exact captured HP PCI identity required')
    services=plistlib.loads(subprocess.check_output(['ioreg','-ar','-c','PhxBringup']))
    if not any(s.get('phx-profile')=='hp-760m' and s.get('phx-build',0)>=39 and s.get('phx-stage')=='native-queues-ready' for s in services):
        raise ValueError('first complete the explicit native bootstrap in this boot')
    for source,dest in [('EFI/OC/Kexts/PhxBringup.kext/Contents/MacOS/PhxBringup','/Volumes/EFI/EFI/OC/Kexts/PhxBringup.kext/Contents/MacOS/PhxBringup'),
            ('Library/Extensions/PhxAccel.kext/Contents/MacOS/PhxAccel','/Library/Extensions/PhxAccel.kext/Contents/MacOS/PhxAccel'),
            ('PhxGPU/NVMTLDriver.bundle/Contents/MacOS/NVMTLDriver','/Library/GPUBundles/NVMTLDriver.bundle/Contents/MacOS/NVMTLDriver'),
            ('PhxGPU/NVMTLDriver.bundle/Contents/MacOS/libnvmtl_translate.dylib','/Library/GPUBundles/NVMTLDriver.bundle/Contents/MacOS/libnvmtl_translate.dylib'),
            ('PhxGPU/nvmtl/libvulkan_radeon.dylib','/Library/GPUBundles/nvmtl/libvulkan_radeon.dylib')]:
        if hashlib.sha256((package/source).read_bytes()).digest()!=hashlib.sha256(Path(dest).read_bytes()).digest():
            raise ValueError('installed binary differs: '+dest+'; do not enable automatic initialization')
    if Path('/Library/LaunchDaemons/local.phxboot.plist').exists():raise ValueError('reference boot daemon already installed; resolve conflict first')
    for name in ('hp_boot.py','hp_bringup.py','mtlprobe'):
        if not (package/'gpu/phxctl'/name).is_file():raise ValueError('missing HP tool: '+name)
    sys.path.insert(0,str(package/'gpu/phxctl'))
    from hp_bringup import macho_uuid
    expected=macho_uuid(package/'Library/Extensions/PhxAccel.kext/Contents/MacOS/PhxAccel')
    loaded=subprocess.check_output(['kmutil','showloaded','--list-only'],text=True)
    if not any('com.luuumi.PhxAccel' in line and expected in line.upper() for line in loaded.splitlines()):
        raise ValueError('running accelerator UUID differs from package')
    with tempfile.TemporaryDirectory(prefix='nullarc-hp-preflight-') as tmp:
        subprocess.run([sys.executable,'-B',str(package/'gpu/phxctl/hp_bringup.py'),'--package',str(package),'--output',str(Path(tmp)/'report')],check=True,timeout=60)
    return document

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--package',type=Path,required=True);ap.add_argument('--install',action='store_true');a=ap.parse_args()
    package=a.package.resolve();document=preflight(package)
    if not a.install:print('HP native boot preflight passed; no files changed or GPU commands submitted');return
    if os.geteuid()!=0:raise ValueError('local administrator authentication required')
    daemon=Path('/Library/LaunchDaemons/local.nullarc.hp-native.plist')
    if daemon.exists() or daemon.is_symlink():raise ValueError('HP boot daemon exists; refusing to replace a previous installation')
    state=Path('/var/db/nullarc-760m')
    if (state/'pending').exists() or (state/'disabled').exists():raise ValueError('prior boot failure/disable marker requires local review')
    # Prove the current installed public Metal API before any persistent changes.
    with tempfile.TemporaryDirectory(prefix='nullarc-hp-metal-') as tmp:
        env={k:v for k,v in os.environ.items() if k in ('PATH','HOME','TMPDIR','LANG','LC_ALL')}
        for name in ('cache','aircache'):(Path(tmp)/name).mkdir()
        env.update(XDG_CACHE_HOME=str(Path(tmp)/'cache'),NVMTL_AIRCACHE=str(Path(tmp)/'aircache'),NVMTL_LOG_PATH=str(Path(tmp)/'plugin.log'))
        for mode in (['list'],[],['render']):
            subprocess.run([str(package/'gpu/phxctl/mtlprobe'),'--hp']+mode,check=True,timeout=90,env=env)
    parent=Path('/Library/Application Support/NullArc760M')
    if parent.is_symlink():raise ValueError('symlinked service directory refused')
    parent.mkdir(parents=True,exist_ok=True)
    if parent.stat().st_uid!=0 or parent.stat().st_mode&0o022:raise ValueError('service directory must be root-owned and not writable by group/others')
    destination=parent/('package-'+hashlib.sha256((package/'package-manifest.json').read_bytes()).hexdigest()[:16])
    if destination.exists():raise ValueError('staged package already exists; review before retry')
    with tempfile.TemporaryDirectory(prefix='.stage-',dir=parent) as tmp:
        staged=Path(tmp)/'package';shutil.copytree(package,staged);verify(staged)
        for p in [staged]+list(staged.rglob('*')):
            if p.is_symlink():raise ValueError('symlink in service package')
            os.chown(p,0,0);p.chmod(p.stat().st_mode&0o755)
        staged.rename(destination)
    config={'Label':'local.nullarc.hp-native','ProgramArguments':['/usr/bin/python3','-B',str(destination/'gpu/phxctl/hp_boot.py'),'--package',str(destination)],'RunAtLoad':True,'LaunchOnlyOnce':True,'StandardOutPath':'/var/log/nullarc-hp-native.log','StandardErrorPath':'/var/log/nullarc-hp-native.log'}
    wrote=False
    try:
        with daemon.open('xb') as f:
            wrote=True;f.write(plistlib.dumps(config));f.flush();os.fsync(f.fileno())
        daemon.chmod(0o644)
    except BaseException:
        if wrote:daemon.unlink(missing_ok=True)
        shutil.rmtree(destination);raise
    print('Installed HP app-only boot service for next boot; no immediate initialization, reboot or WindowServer arming.')
    print('Package: '+str(destination))

if __name__=='__main__':
    try:main()
    except (OSError,ValueError,subprocess.SubprocessError) as e:raise SystemExit(str(e))
