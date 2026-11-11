#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""HP app acceleration, with a separately authorized one-shot display experiment."""
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import pwd
import hashlib
import plistlib
sys.path.insert(0,str(Path(__file__).resolve().parent))
from hp_bringup import wait_for_metal,macho_uuid,claimed_hp
import hp_windowserver as desktop

RESTRICTED='# NullArc: built-in test tools only; automatic initialization disabled\n'
APPS='# NullArc: verified HP app acceleration; desktop remains on firmware framebuffer\n-WindowServer\n-mediaanalysisd\n-photoanalysisd\n-Spotlight\n*\n'

def atomic(path,text):
    fd,name=tempfile.mkstemp(prefix='.nullarc-',dir=path.parent)
    try:
        with os.fdopen(fd,'w') as f:f.write(text);f.flush();os.fsync(f.fileno())
        os.chmod(name,0o644);os.replace(name,path)
    finally:Path(name).unlink(missing_ok=True)

def publish(status,report):
    if not status:return
    public={k:v for k,v in report.items() if k not in ('stdout','stderr','metal_stages')}
    if 'metal_stages' in report:
        public['metal_stages']=[{k:v for k,v in stage.items() if k in ('stage','returncode')} for stage in report['metal_stages']]
    public['recorded_at']=datetime.now(timezone.utc).isoformat()
    atomic(status,json.dumps(public,indent=2)+'\n')

def console_user(timeout=300,check=None):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        if check:check()
        uid=os.stat('/dev/console').st_uid
        if uid>0:
            user=pwd.getpwuid(uid)
            result=subprocess.run(['/bin/launchctl','print','gui/'+str(uid)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=5)
            if result.returncode==0:return user
        time.sleep(1)
    raise ValueError('no active console-user GUI session before deadline; native GPU retained, app access restricted')

def user_prefix(user,work):
    # launchctl changes the Mach/audit context, not credentials (launchctl(1)).
    # sudo supplies the target credentials/home and resets inherited variables.
    return ['/bin/launchctl','asuser',str(user.pw_uid),'/usr/bin/sudo','-n','-H','-u',user.pw_name,'--',
            '/usr/bin/env','XDG_CACHE_HOME='+str(work/'cache'),'NVMTL_AIRCACHE='+str(work/'aircache'),
            'NVMTL_LOG_PATH='+str(work/'plugin.log'),'PHX_RADV_DRIVER=/Library/GPUBundles/nvmtl/libvulkan_radeon.dylib']

def verify_console_metal(package,report,save):
    report['verification_phase']='awaiting-console-session';save()
    user=console_user(check=lambda:desktop.check_crashes(report,save)) if report.get('desktop_armed') else console_user()
    work=Path(tempfile.mkdtemp(prefix='nullarc-user-metal-',dir='/Users/Shared'))
    for p in (work,work/'cache',work/'aircache'):
        if p!=work:p.mkdir()
        p.chmod(0o700);os.chown(p,user.pw_uid,user.pw_gid)
    report['metal_workdir']=str(work)
    report['metal_validation_uid']=user.pw_uid
    report['verification_phase']='console-user-metal';report['metal_stages']=[];save()
    probe=package/'gpu/phxctl/mtlprobe';prefix=user_prefix(user,work)
    environment={k:v for k,v in os.environ.items() if k in ('PATH','HOME','TMPDIR','LANG','LC_ALL')}
    publication={'stage':'metal-hp-device','returncode':None,'attempts':[]}
    report['metal_stages'].append(publication);save()
    def record(attempt):publication['attempts'].append(attempt);save()
    r=wait_for_metal(probe,environment,record,prefix=prefix)
    desktop.check_crashes(report,save)
    publication.update(returncode=0,stdout=r.stdout,stderr=r.stderr);save()
    submitted=False
    try:
        for stage,args in [('metal-compute-readback',[]),('metal-render-readback',['render'])]:
            desktop.check_crashes(report,save)
            submitted=True
            entry={'stage':stage,'returncode':None};report['metal_stages'].append(entry);save()
            r=subprocess.run(prefix+[str(probe),'--hp']+args,capture_output=True,text=True,timeout=90,env=environment)
            entry.update(returncode=r.returncode,stdout=r.stdout,stderr=r.stderr);save()
            if r.returncode:raise ValueError(stage+' failed in console-user session')
    except (OSError,ValueError,subprocess.SubprocessError):
        if submitted:
            subprocess.run([str(package/'gpu/phxctl/phxctl'),'abort'],capture_output=True,timeout=5)
        raise
    report['metal_readbacks_verified']=True
    report['console_uid_after_validation']=os.stat('/dev/console').st_uid;save()
    if report['console_uid_after_validation']!=user.pw_uid:raise ValueError('console user changed during validation; app access remains restricted')
    report['metal_verified']=True;report['verification_phase']='complete';save()

def boot(package,state,allow,status=None):
    state.mkdir(parents=True,exist_ok=True,mode=0o700)
    allow.parent.mkdir(parents=True,exist_ok=True)
    atomic(allow,RESTRICTED)
    if status:
        atomic(status,json.dumps({'automatic_initialization_attempted':False,'apps_enabled':False,
            'desktop_armed':False,'boot_session_uuid':desktop.boot_uuid(),'recorded_at':datetime.now(timezone.utc).isoformat()})+'\n')
    if (state/'disabled').exists():return 0
    pending=state/'pending'
    if pending.exists():
        (state/'disabled').touch()
        raise ValueError('previous initialization did not finish; disabled until local review')
    fd=os.open(pending,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600);os.close(fd)
    folder=Path(tempfile.mkdtemp(prefix='boot-',dir=state))
    command=[sys.executable,'-B',str(package/'gpu/phxctl/hp_bringup.py'),
             '--package',str(package),'--output',str(folder/'execution'),'--execute','--claim','--defer-metal']
    report={'automatic_initialization_attempted':True,'desktop_armed':False,'boot_session_uuid':desktop.boot_uuid()}
    display_requested=(state/desktop.REQUEST).exists()
    def save():
        (folder/'boot-result.json').write_text(json.dumps(report,indent=2)+'\n')
        publish(status,report)
    def frame_progress(phase):report.update(desktop_phase=phase);save()
    try:
        display=desktop.begin(package,state,folder,progress=frame_progress)
        p=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
        try:stdout,stderr=p.communicate(timeout=300)
        except subprocess.TimeoutExpired:
            os.killpg(p.pid,signal.SIGKILL);p.communicate();raise ValueError('bootstrap timeout; reboot and review evidence')
        report.update(returncode=p.returncode,stdout=stdout,stderr=stderr)
        evidence_path=folder/'execution/result.json'
        evidence=json.loads(evidence_path.read_text()) if evidence_path.exists() else {}
        for key in ('native_compute_verified','native_render_verified','metal_verified'):
            report[key]=evidence.get(key) is True
        stages=evidence.get('stages',[])
        if stages:
            report['last_stage']=stages[-1].get('stage')
            failures=[s for s in stages if s.get('returncode')!=0]
            if failures:report['failed_stage']=failures[-1].get('stage')
        if evidence.get('error'):report['bootstrap_error']=evidence['error']
        if p.returncode:raise ValueError('bootstrap failed; no application allow list enabled')
        if not all(evidence.get(k) is True for k in ('executed','native_compute_verified','native_render_verified','accelerator_claimed')):
            raise ValueError('bootstrap did not prove native compute, render and accelerator claim')
        report['native_initialization_verified']=True;save()
        if display:
            desktop.arm(report,save,allow,atomic)
        verify_console_metal(package,report,save)
        if report.get('metal_verified') is not True:raise ValueError('console-user Metal verification missing')
        if (state/'disabled').exists():raise ValueError('service disabled during initialization; app access remains restricted')
        if display:desktop.verify_present(report,save)
        atomic(allow,desktop.DESKTOP if display else APPS)
        pending.unlink()
        report['apps_enabled']=True
    except (OSError,ValueError,subprocess.SubprocessError) as e:
        report['error']=str(e);(state/'disabled').touch();atomic(allow,RESTRICTED)
        if display_requested or isinstance(e,desktop.DisplayOwnershipError):desktop.fallback(report,save)
        raise
    finally:
        save()
    return 0

def verify_existing_native(package):
    subprocess.run([sys.executable,'-B',str(package/'package_manifest.py'),str(package)],check=True,timeout=30)
    nodes=plistlib.loads(subprocess.check_output(['/usr/sbin/ioreg','-ar','-c','PhxBringup']))
    if not any(n.get('phx-profile')=='hp-760m' and n.get('phx-stage')=='native-queues-ready' for n in nodes):
        raise ValueError('healthy native queues required; no recovery or reinitialization attempted')
    claimed_hp(plistlib.loads(subprocess.check_output(['/usr/sbin/ioreg','-ar','-c','IOPCIDevice'])))
    loaded=subprocess.check_output(['/usr/bin/kmutil','showloaded','--list-only'],text=True)
    for name,path in [('org.drip.PhxBringup','EFI/OC/Kexts/PhxBringup.kext/Contents/MacOS/PhxBringup'),
                      ('com.luuumi.PhxAccel','Library/Extensions/PhxAccel.kext/Contents/MacOS/PhxAccel')]:
        expected=macho_uuid(package/path)
        if not any(name in line and expected in line.upper() for line in loaded.splitlines()):raise ValueError('running module differs: '+name)
    for source,target in [('PhxGPU/NVMTLDriver.bundle/Contents/MacOS/NVMTLDriver','/Library/GPUBundles/NVMTLDriver.bundle/Contents/MacOS/NVMTLDriver'),
                          ('PhxGPU/NVMTLDriver.bundle/Contents/MacOS/libnvmtl_translate.dylib','/Library/GPUBundles/NVMTLDriver.bundle/Contents/MacOS/libnvmtl_translate.dylib'),
                          ('PhxGPU/nvmtl/libvulkan_radeon.dylib','/Library/GPUBundles/nvmtl/libvulkan_radeon.dylib')]:
        if hashlib.sha256((package/source).read_bytes()).digest()!=hashlib.sha256(Path(target).read_bytes()).digest():raise ValueError('installed runtime differs: '+target)

def resume_existing(package,state,allow,status=None):
    """Verify and enable apps on healthy existing queues; never initialize them."""
    if any((state/name).exists() for name in ('pending','disabled')):
        raise ValueError('review/back up the failed service and markers before verification-only recovery')
    atomic(allow,RESTRICTED)
    verify_existing_native(package)
    folder=Path(tempfile.mkdtemp(prefix='verification-',dir=state))
    report={'automatic_initialization_attempted':False,'native_initialization_retried':False,
            'native_readiness_verified':True,'metal_verified':False,'desktop_armed':False,'apps_enabled':False,
            'boot_session_uuid':desktop.boot_uuid()}
    def save():
        (folder/'verification-result.json').write_text(json.dumps(report,indent=2)+'\n');publish(status,report)
    try:
        verify_console_metal(package,report,save)
        if report.get('metal_verified') is not True:raise ValueError('Metal readbacks not verified')
        if (state/'disabled').exists():raise ValueError('disabled during verification')
        atomic(allow,APPS);report['apps_enabled']=True
    except (OSError,ValueError,subprocess.SubprocessError) as e:
        report['error']=str(e);(state/'disabled').touch();atomic(allow,RESTRICTED);raise
    finally:save()
    print('Existing native GPU verified; Metal compute/render passed; app access enabled. No reinitialization or reboot.')
    return 0

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--package',type=Path,required=True)
    ap.add_argument('--verify-existing',action='store_true');a=ap.parse_args()
    if os.geteuid()!=0:ap.error('administrator required')
    try:raise SystemExit((resume_existing if a.verify_existing else boot)(a.package.resolve(),Path('/var/db/nullarc-760m'),Path('/Library/GPUBundles/nvmtl-allow.txt'),Path('/Users/Shared/nullarc-hp-native-status.json')))
    except (OSError,ValueError,subprocess.SubprocessError) as e:ap.exit(1,str(e)+'\n')
