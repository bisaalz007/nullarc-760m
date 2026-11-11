from pathlib import Path
import importlib.util
import json
import plistlib
import shutil
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from package_manifest import write
SPEC=importlib.util.spec_from_file_location('recover_hp_boot',ROOT/'install/recover_hp_boot.py')
r=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(r)

class RecoveryTests(unittest.TestCase):
    def display_failure(self):
        return {'boot_session_uuid':'failed','desktop_armed':True,'firmware_fallback_reboot_requested':True,
                'native_initialization_verified':True,'metal_verified':False,
                'error':'no active console-user GUI session before deadline; native GPU retained, app access restricted'}

    def display_evidence(self):
        return dict(executed=True,native_compute_verified=True,native_render_verified=True,
                    accelerator_claimed=True,metal_deferred=True,metal_verified=False,
                    stages=[{'stage':'accelerator-claim','returncode':0}],source_package=str(self.old))

    def test_display_fallback_requires_new_boot_and_successful_previous_native_tests(self):
        folder=self.state/'boot-fixture'
        (folder/'windowserver-next-boot.json').write_text(json.dumps({'format':1,'accelerator_uuid':'expected','armed_from_boot':'origin'}))
        supervisor=self.display_failure();evidence=self.display_evidence()
        r.validate_display_fallback(supervisor,evidence,folder,'current','expected')
        with self.assertRaises(ValueError):r.validate_display_fallback(supervisor,evidence,folder,'failed','expected')
        with self.assertRaises(ValueError):r.validate_display_fallback(supervisor,evidence,folder,'current','other')
        evidence['native_render_verified']=False
        with self.assertRaises(ValueError):r.validate_display_fallback(supervisor,evidence,folder,'current','expected')

    def test_idle_fallback_stages_only_without_gpu_commands(self):
        folder=self.state/'boot-fixture'
        (folder/'boot-result.json').write_text(json.dumps(self.display_failure()))
        (folder/'execution/result.json').write_text(json.dumps(self.display_evidence()))
        (folder/'windowserver-next-boot.json').write_text(json.dumps({'format':1,'accelerator_uuid':'expected','armed_from_boot':'origin'}))
        display=SimpleNamespace(require_library_policy=lambda:None,REQUEST='windowserver-next-boot.json',
            nodes=lambda name:[{'phx-profile':'hp-760m','phx-stage':'profile-diagnostic-only'}] if name=='PhxBringup' else [])
        with self.stat,patch.object(r.os,'chown'),patch.dict(sys.modules,{'hp_bringup':SimpleNamespace(macho_uuid=lambda p:'expected'),'hp_windowserver':display}),patch.object(r.subprocess,'check_output',side_effect=['current',plistlib.dumps({})]),patch.object(r.subprocess,'run') as run:
            r.recover(self.new,self.daemon,self.state,self.parent,after_display_fallback=True)
        run.assert_not_called();self.assertFalse((self.state/'disabled').exists())

    def test_fallback_refuses_an_active_accelerator_before_marker_changes(self):
        display=SimpleNamespace(require_library_policy=lambda:None,nodes=lambda name:[{}])
        with patch.dict(sys.modules,{'hp_bringup':SimpleNamespace(macho_uuid=lambda p:'expected'),'hp_windowserver':display}),patch.object(r.subprocess,'check_output',return_value='current'),self.assertRaisesRegex(ValueError,'idle'):
            r.recover(self.new,self.daemon,self.state,self.parent,after_display_fallback=True)
        self.assertEqual(self.daemon.read_bytes(),self.original);self.assertTrue((self.state/'disabled').exists())

    def test_pre_gpu_display_failure_requires_no_execution_and_this_boot(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);request={'format':1,'accelerator_uuid':'expected','armed_from_boot':'previous'}
            (folder/'windowserver-next-boot.json').write_text(json.dumps(request))
            status={'boot_session_uuid':'current','error':'framebuffer one-shot was not consumed by the running kext',
                    'automatic_initialization_attempted':True,'desktop_armed':False}
            r.validate_before_gpu(status,folder,'current','expected')
            with self.assertRaises(ValueError):r.validate_before_gpu(status,folder,'other','expected')
            with self.assertRaises(ValueError):r.validate_before_gpu(status,folder,'current','different')
            (folder/'execution').mkdir()
            with self.assertRaises(ValueError):r.validate_before_gpu(status,folder,'current','expected')

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        root=Path(self.tmp.name);self.parent=root/'service';self.parent.mkdir()
        self.old=self.parent/'old';self.old.mkdir();self.new=root/'new'
        for name in r.NATIVE:
            path=self.old/name
            if name.endswith(('.kext','.bundle','nvmtl','fw','validation')):path=path/'fixture'
            path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'unchanged execution fixture')
        self.new.mkdir();shutil.copytree(self.old,self.new,dirs_exist_ok=True)
        for p in (self.old,self.new):write(p,{'minimum_macos':'15.0'})
        self.daemon=root/'daemon.plist';self.original=plistlib.dumps({'Label':'local.nullarc.hp-native','RunAtLoad':True,'ProgramArguments':['/usr/bin/python3','-B',str(self.old/'gpu/phxctl/hp_boot.py'),'--package',str(self.old)]})
        self.daemon.write_bytes(self.original)
        self.state=root/'state';self.state.mkdir()
        for name in ('pending','disabled'):(self.state/name).touch()
        report=self.state/'boot-fixture/execution';report.mkdir(parents=True)
        self.evidence={'source_package':str(self.old),'native_compute_verified':True,'native_render_verified':True,'metal_verified':False,'stages':[{'stage':'metal-hp-device','returncode':1,'stdout':'devices: 0\nno Metal device\n','stderr':''}]}
        (report/'result.json').write_text(json.dumps(self.evidence))
        actual_stat=Path.stat
        parent=self.parent
        self.stat=patch.object(Path,'stat',lambda p,*a,**k:SimpleNamespace(st_uid=0,st_mode=0o755) if p==parent else actual_stat(p,*a,**k))

    def test_known_failure_updates_only_next_boot_and_backs_up(self):
        with self.stat,patch.object(r.os,'chown'):r.recover(self.new,self.daemon,self.state,self.parent)
        self.assertNotEqual(self.daemon.read_bytes(),self.original)
        backup=next(self.state.glob('recovery-*'))
        self.assertEqual((backup/'daemon.plist').read_bytes(),self.original)
        self.assertTrue((backup/'pending').exists());self.assertTrue((backup/'disabled').exists())
        self.assertTrue((self.state/'boot-fixture/execution/result.json').exists())

    def test_changed_native_binary_is_refused_before_update(self):
        (self.new/'gpu/phxctl/mesboot').write_bytes(b'different native code');write(self.new,{'minimum_macos':'15.0'})
        with self.stat,patch.object(r.os,'chown'),self.assertRaisesRegex(ValueError,'native execution component changed'):r.recover(self.new,self.daemon,self.state,self.parent)
        self.assertEqual(self.daemon.read_bytes(),self.original);self.assertTrue((self.state/'pending').exists())

    def test_unreviewed_failure_is_refused(self):
        self.evidence['stages'][-1]['stderr']='GPU failed'
        with self.assertRaises(ValueError):r.validate_failure(self.evidence)

    def test_empty_catalogue_deadline_is_reviewed_but_probe_errors_are_not(self):
        self.evidence['error']='HP Metal device publication timed out'
        last=self.evidence['stages'][-1];last['returncode']=None
        last['attempts']=[{'returncode':75,'stdout':'devices: 0\nno Metal device\n','stderr':''}]
        r.validate_failure(self.evidence)
        last['attempts'][0]['stderr']='native transport failure'
        with self.assertRaises(ValueError):r.validate_failure(self.evidence)

    def test_supervisor_enumeration_timeout_is_recoverable_but_shader_timeout_is_not(self):
        self.evidence.update(accelerator_claimed=True,metal_deferred=True)
        self.evidence['stages']=[{'stage':'accelerator-claim','returncode':0}]
        supervisor={'native_initialization_verified':True,'metal_verified':False,'error':'device probe timed out','metal_stages':[{'stage':'metal-hp-device','returncode':None}]}
        r.validate_failure(self.evidence,supervisor)
        supervisor['metal_stages'][0]['stage']='metal-compute-readback'
        with self.assertRaises(ValueError):r.validate_failure(self.evidence,supervisor)

    def test_marker_move_failure_rolls_back_configuration_and_marker(self):
        rename=Path.rename
        def fail(path,target):
            if path==self.state/'disabled':raise OSError('injected marker move failure')
            return rename(path,target)
        with self.stat,patch.object(r.os,'chown'),patch.object(Path,'rename',fail),self.assertRaises(OSError):r.recover(self.new,self.daemon,self.state,self.parent)
        self.assertEqual(self.daemon.read_bytes(),self.original)
        self.assertTrue((self.state/'pending').exists());self.assertTrue((self.state/'disabled').exists())
        self.assertFalse(list(self.parent.glob('package-update-*')))

if __name__=='__main__':unittest.main()
