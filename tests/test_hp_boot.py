from pathlib import Path
import importlib.util
import json
import tempfile
import unittest
from unittest.mock import patch

SPEC=importlib.util.spec_from_file_location('hp_boot',Path(__file__).resolve().parents[1]/'tools/phxctl/hp_boot.py')
b=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(b)

class BootTests(unittest.TestCase):
    def setUp(self):
        bootid=patch.object(b.desktop,'boot_uuid',return_value='TEST-BOOT');bootid.start();self.addCleanup(bootid.stop)
        display=patch.object(b.desktop,'begin',return_value=False);display.start();self.addCleanup(display.stop)
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.state=self.root/'state';self.allow=self.root/'allow'
        self.real_metal=b.verify_console_metal
        def verified(package,report,save):report['metal_verified']=True;save()
        self.metal_patch=patch.object(b,'verify_console_metal',side_effect=verified)
        self.metal=self.metal_patch.start();self.addCleanup(self.metal_patch.stop)

    def process(self,code=0,metal=True,extra=None):
        def spawn(command,**kwargs):
            folder=Path(command[command.index('--output')+1]);folder.mkdir()
            evidence=dict(executed=True,native_compute_verified=True,native_render_verified=True,accelerator_claimed=True,metal_verified=metal)
            evidence.update(extra or {})
            (folder/'result.json').write_text(json.dumps(evidence))
            class Process:
                returncode=code
                def communicate(self,**kwargs):return ('bootstrap log','')
            return Process()
        return spawn

    def test_success_requires_all_readbacks_and_denies_desktop(self):
        with patch.object(b.subprocess,'Popen',side_effect=self.process()):b.boot(self.root,self.state,self.allow)
        text=self.allow.read_text()
        self.assertLess(text.index('-WindowServer'),text.index('*'))
        self.assertFalse((self.state/'pending').exists())
        self.assertFalse((self.state/'disabled').exists())

    def test_interrupted_boot_disables_without_retry(self):
        self.state.mkdir();(self.state/'pending').touch()
        with patch.object(b.subprocess,'Popen') as spawn,self.assertRaises(ValueError):b.boot(self.root,self.state,self.allow)
        spawn.assert_not_called();self.assertTrue((self.state/'disabled').exists())
        self.assertNotIn('*',self.allow.read_text())

    def test_failed_process_preserves_pending_and_disables(self):
        with patch.object(b.subprocess,'Popen',side_effect=self.process(code=1)),self.assertRaises(ValueError):b.boot(self.root,self.state,self.allow)
        self.assertTrue((self.state/'pending').exists());self.assertTrue((self.state/'disabled').exists())
        self.assertNotIn('*',self.allow.read_text())

    def test_success_exit_without_native_evidence_is_refused(self):
        with patch.object(b.subprocess,'Popen',side_effect=self.process(extra={'accelerator_claimed':False})),self.assertRaises(ValueError):b.boot(self.root,self.state,self.allow)
        self.metal.assert_not_called()
        self.assertNotIn('*',self.allow.read_text())

    def test_disabled_service_does_not_start_gpu(self):
        self.state.mkdir();(self.state/'disabled').touch()
        with patch.object(b.subprocess,'Popen') as spawn:self.assertEqual(b.boot(self.root,self.state,self.allow),0)
        spawn.assert_not_called()

    def test_interrupted_boot_clears_stale_success_status(self):
        self.state.mkdir();(self.state/'pending').touch()
        status=self.root/'status.json';status.write_text('{"apps_enabled":true}')
        with patch.object(b.subprocess,'Popen'),self.assertRaises(ValueError):b.boot(self.root,self.state,self.allow,status)
        self.assertFalse(json.loads(status.read_text())['apps_enabled'])

    def test_failed_stage_is_public_without_raw_process_output(self):
        status=self.root/'status.json'
        extra={'error':'metal-compute-readback failed','stages':[{'stage':'native-compute-readback','returncode':0},{'stage':'metal-compute-readback','returncode':1}]}
        with patch.object(b.subprocess,'Popen',side_effect=self.process(code=1,metal=False,extra=extra)),self.assertRaises(ValueError):b.boot(self.root,self.state,self.allow,status)
        report=json.loads(status.read_text())
        self.assertEqual(report['failed_stage'],'metal-compute-readback')
        self.assertTrue(report['native_compute_verified']);self.assertFalse(report['metal_verified'])
        self.assertNotIn('stdout',report);self.assertNotIn('stderr',report)

    def test_disable_during_initialization_prevents_app_enable(self):
        spawn=self.process()
        def disable(*args,**kwargs):
            (self.state/'disabled').touch()
            return spawn(*args,**kwargs)
        with patch.object(b.subprocess,'Popen',side_effect=disable),self.assertRaises(ValueError):b.boot(self.root,self.state,self.allow)
        self.assertNotIn('*',self.allow.read_text())

    def test_catalogue_failure_retains_native_state_without_abort(self):
        self.metal.side_effect=ValueError('no console-user Metal device')
        with patch.object(b.subprocess,'Popen',side_effect=self.process(metal=False)),patch.object(b.subprocess,'run') as run,self.assertRaises(ValueError):b.boot(self.root,self.state,self.allow)
        run.assert_not_called()
        self.assertTrue((self.state/'disabled').exists());self.assertNotIn('*',self.allow.read_text())

    def test_console_prefix_changes_both_bootstrap_and_credentials(self):
        from types import SimpleNamespace
        prefix=b.user_prefix(SimpleNamespace(pw_uid=501,pw_name='fixture-user'),self.root)
        self.assertEqual(prefix[:9],['/bin/launchctl','asuser','501','/usr/bin/sudo','-n','-H','-u','fixture-user','--'])
        self.assertIn('NVMTL_AIRCACHE='+str(self.root/'aircache'),prefix)

    def test_root_boot_defers_metal_until_console_validation(self):
        with patch.object(b.subprocess,'Popen',side_effect=self.process(metal=False)) as spawn:b.boot(self.root,self.state,self.allow)
        self.assertIn('--defer-metal',spawn.call_args.args[0]);self.metal.assert_called_once()

    def test_opted_in_display_is_armed_before_waiting_for_gui(self):
        events=[]
        self.metal.side_effect=lambda *args: (events.append('metal'),args[1].update(metal_verified=True))
        with patch.object(b.desktop,'begin',return_value=True),patch.object(b.desktop,'arm',side_effect=lambda *args:events.append('arm')),patch.object(b.desktop,'verify_present',side_effect=lambda *args:events.append('present')),patch.object(b.subprocess,'Popen',side_effect=self.process()):
            b.boot(self.root,self.state,self.allow)
        self.assertEqual(events,['arm','metal','present']);self.assertIn('!WindowServer',self.allow.read_text())

    def test_failed_display_arm_restricts_apps_and_requests_fallback(self):
        self.state.mkdir();(self.state/b.desktop.REQUEST).write_text('{}')
        with patch.object(b.desktop,'begin',return_value=True),patch.object(b.desktop,'arm',side_effect=ValueError('display failed')),patch.object(b.desktop,'fallback') as fallback,patch.object(b.subprocess,'Popen',side_effect=self.process()),self.assertRaises(ValueError):
            b.boot(self.root,self.state,self.allow)
        fallback.assert_called_once();self.metal.assert_not_called();self.assertNotIn('*',self.allow.read_text())

    def test_display_dependency_failure_prevents_native_initialization(self):
        self.state.mkdir();(self.state/b.desktop.REQUEST).write_text('{}')
        with patch.object(b.desktop,'begin',side_effect=ValueError('signing dependency')),patch.object(b.desktop,'fallback') as fallback,patch.object(b.subprocess,'Popen') as spawn,self.assertRaises(ValueError):
            b.boot(self.root,self.state,self.allow)
        spawn.assert_not_called();fallback.assert_called_once();self.metal.assert_not_called()
        self.assertTrue((self.state/'disabled').exists())

    def test_console_session_deadline_does_not_submit_commands(self):
        with patch.object(b.time,'monotonic',side_effect=[0,301]),patch.object(b.subprocess,'run') as run,self.assertRaisesRegex(ValueError,'console-user'):
            b.console_user()
        run.assert_not_called()

    def test_display_crash_stops_console_wait_before_another_launch_check(self):
        with patch.object(b.time,'monotonic',side_effect=[0,1]),patch.object(b.subprocess,'run') as run,self.assertRaisesRegex(ValueError,'WindowServer crashed'):
            b.console_user(check=lambda: (_ for _ in ()).throw(ValueError('WindowServer crashed')))
        run.assert_not_called()

    def console_test(self,failure=None):
        from types import SimpleNamespace
        work=self.root/'console-work';work.mkdir()
        report={};user=SimpleNamespace(pw_uid=501,pw_gid=20,pw_name='fixture-user')
        actual_stat=b.os.stat
        def stat(path,*args,**kwargs):return SimpleNamespace(st_uid=0 if failure=='console-change' else 501) if str(path)=='/dev/console' else actual_stat(path,*args,**kwargs)
        def command(args,**kwargs):
            from subprocess import CompletedProcess
            return CompletedProcess(args,2 if failure=='compute' and args[-1]=='--hp' else 0,'readback fixture','')
        # These are command-boundary fixtures, not simulated hardware evidence.
        real_verify=self.real_metal
        with patch.object(b,'console_user',return_value=user),patch.object(b.tempfile,'mkdtemp',return_value=str(work)),patch.object(b.os,'chown'),patch.object(b.os,'stat',side_effect=stat),patch.object(b,'wait_for_metal') as wait,patch.object(b.subprocess,'run',side_effect=command) as run:
            from subprocess import CompletedProcess
            wait.return_value=CompletedProcess([],0,'HP device fixture','')
            if failure=='catalogue':wait.side_effect=ValueError('empty catalogue')
            error=None
            try:real_verify(self.root,report,lambda:None)
            except ValueError as e:error=e
            return report,wait,run,error

    def test_console_checks_use_user_context_for_both_shader_probes(self):
        report,wait,run,error=self.console_test()
        self.assertIsNone(error);self.assertTrue(report['metal_verified'])
        self.assertEqual(wait.call_args.kwargs['prefix'][:3],['/bin/launchctl','asuser','501'])
        self.assertEqual(run.call_count,2)
        self.assertTrue(all(c.args[0][:3]==['/bin/launchctl','asuser','501'] for c in run.call_args_list))

    def test_console_catalogue_absence_does_not_abort_ready_gpu(self):
        report,wait,run,error=self.console_test('catalogue')
        self.assertIsNotNone(error);run.assert_not_called();self.assertNotIn('metal_verified',report)

    def test_shader_failure_aborts_and_never_sets_verified(self):
        report,wait,run,error=self.console_test('compute')
        self.assertIsNotNone(error);self.assertNotIn('metal_verified',report)
        self.assertEqual(run.call_args.args[0],[str(self.root/'gpu/phxctl/phxctl'),'abort'])

    def test_console_change_retains_readback_evidence_without_enabling_apps(self):
        report,wait,run,error=self.console_test('console-change')
        self.assertIsNotNone(error);self.assertTrue(report['metal_readbacks_verified'])
        self.assertEqual(report['metal_validation_uid'],501);self.assertEqual(report['console_uid_after_validation'],0)
        self.assertNotIn('metal_verified',report)

    def test_existing_queue_verification_never_launches_native_initialization(self):
        self.state.mkdir();status=self.root/'status.json'
        with patch.object(b,'verify_existing_native'),patch.object(b.subprocess,'Popen') as spawn:
            b.resume_existing(self.root,self.state,self.allow,status)
        spawn.assert_not_called();report=json.loads(status.read_text())
        self.assertFalse(report['native_initialization_retried']);self.assertTrue(report['metal_verified']);self.assertTrue(report['apps_enabled'])

    def test_existing_queue_recovery_requires_reviewed_markers(self):
        self.state.mkdir();(self.state/'disabled').touch()
        with patch.object(b,'verify_existing_native') as validate,self.assertRaises(ValueError):b.resume_existing(self.root,self.state,self.allow)
        validate.assert_not_called();self.metal.assert_not_called()

    def test_lost_driver_refuses_existing_queue_verification(self):
        import plistlib
        lost=plistlib.dumps([{'phx-profile':'hp-760m','phx-stage':'device-lost'}])
        with patch.object(b.subprocess,'run'),patch.object(b.subprocess,'check_output',return_value=lost),self.assertRaisesRegex(ValueError,'healthy native queues'):
            b.verify_existing_native(self.root)
        self.metal.assert_not_called()

if __name__=='__main__':unittest.main()
