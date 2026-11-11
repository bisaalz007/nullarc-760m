"""Failure/order checks only; synthetic IORegistry data is not display evidence."""
import importlib.util
import json
from pathlib import Path
import plistlib
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/phxctl'))
import hp_windowserver as d
REAL_POLICY=d.require_library_policy

class DisplayTests(unittest.TestCase):
    def setUp(self):
        policy=patch.object(d,'require_library_policy');self.policy=policy.start();self.addCleanup(policy.stop)

    def test_policy_requires_supported_loaded_version_and_active_service(self):
        # Exercise the actual guard separately from the arm-order fixtures.
        with patch.object(d,'require_library_policy',new=REAL_POLICY):
            for loaded,services in (('com.dhinakg.AMFIPass (1.3.1)',[{}]),('amfi=0x80',[]),('com.dhinakg.AMFIPass (1.4.1)',[])):
                with self.subTest(loaded=loaded),patch.object(d.subprocess,'check_output',return_value=loaded),patch.object(d,'nodes',return_value=services),self.assertRaisesRegex(ValueError,'signing dependency'):
                    d.require_library_policy()
            with patch.object(d.subprocess,'check_output',side_effect=['com.dhinakg.AMFIPass (1.4.1)','amfi=0x80 amfi_get_out_of_my_way=0x1']),patch.object(d,'nodes',return_value=[{}]):
                d.require_library_policy()

    def test_active_amfipass_without_full_reviewed_boot_flags_is_refused(self):
        with patch.object(d,'require_library_policy',new=REAL_POLICY),patch.object(d,'nodes',return_value=[{}]):
            for args in ('-v','amfi=0x80','amfi_get_out_of_my_way=0x1','amfi=0x80 amfi=0 amfi_get_out_of_my_way=0x1'):
                with self.subTest(args=args),patch.object(d.subprocess,'check_output',side_effect=['com.dhinakg.AMFIPass (1.4.1)',args]),self.assertRaisesRegex(ValueError,'actual boot'):
                    d.require_library_policy()

    def test_policy_failure_prevents_all_display_controls(self):
        self.policy.side_effect=ValueError('library-validation')
        with patch.object(d,'sysctl') as control,self.assertRaises(ValueError):
            d.arm({},lambda:None,Path('fixture'),lambda *args:self.fail('must not change allow list'))
        control.assert_not_called()

    def test_crash_monitor_ignores_history_partial_and_other_boot(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(d,'CRASH_DIR',Path(tmp)):
            root=Path(tmp);(root/'WindowServer-old.ips').write_text('history')
            report={'boot_session_uuid':'current'};d.watch_crashes(report);report['desktop_armed']=True
            path=root/'WindowServer-new.ips';path.write_text('{}\n{"procName":')
            d.check_crashes(report,lambda:None)
            path.write_text('{}\n'+json.dumps({'procName':'WindowServer','bootSessionUUID':'previous'}))
            d.check_crashes(report,lambda:None)
            path.write_text('{}\n'+json.dumps({'procName':'WindowServer','bootSessionUUID':'current'}))
            saved=[]
            with self.assertRaisesRegex(ValueError,'WindowServer crashed'):d.check_crashes(report,lambda:saved.append(True))
            self.assertEqual(report['desktop_crash_report'],path.name);self.assertEqual(saved,[True])

    def test_app_only_does_not_inspect_display_crashes(self):
        with patch.object(d,'CRASH_DIR') as directory:d.check_crashes({},lambda:None)
        directory.glob.assert_not_called()

    def test_waits_for_delayed_and_partial_framebuffer_publication(self):
        ready=dict(d.PANEL,PhxFBHP=True,PhxFBTimingCaptured=True);progress=[]
        with patch.object(d,'nodes',side_effect=[[],[{'PhxFBHP':True}],[ready]]),patch.object(d,'sysctl',return_value=1),patch.object(d,'unopened_held_framebuffer') as held,patch.object(d.time,'sleep'):
            d.wait_for_framebuffer(progress=progress.append)
        held.assert_called_once();self.assertEqual(progress,['awaiting-early-framebuffer','awaiting-framebuffer-properties'])

    def test_wait_deadline_does_not_issue_gpu_commands(self):
        with patch.object(d.time,'monotonic',side_effect=[0,91]),patch.object(d.subprocess,'run') as run,self.assertRaisesRegex(ValueError,'deadline'):
            d.wait_for_framebuffer()
        run.assert_not_called()

    def test_expired_framebuffer_hold_is_not_rearmed(self):
        ready=dict(d.PANEL,PhxFBHP=True,PhxFBTimingCaptured=True)
        with patch.object(d,'nodes',return_value=[ready]),patch.object(d,'sysctl',return_value=0) as control,self.assertRaisesRegex(ValueError,'expired'):
            d.wait_for_framebuffer()
        self.assertEqual(control.call_args.args,('debug.phxfb_hold',))

    def test_empty_ioreg_is_not_misparsed_as_plist(self):
        with patch.object(d.subprocess,'check_output',return_value=b''):self.assertEqual(d.nodes('PhxAMDFB'),[])

    def test_no_request_never_arms(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(d,'nodes',return_value=[]),patch.object(d,'sysctl') as write:
            self.assertFalse(d.begin(Path(tmp),Path(tmp),Path(tmp)))
            write.assert_not_called()

    def test_unrequested_framebuffer_requires_fallback(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(d,'nodes',return_value=[{}]),self.assertRaises(d.DisplayOwnershipError):
            d.begin(Path(tmp),Path(tmp),Path(tmp))

    def test_runtime_plan_requires_exact_version_geometry_and_family(self):
        plan=struct.pack('<14I6Q',1,3,1920,1200,7680,60000,2260,1968,2000,1240,1203,1209,1,0,
                         0x2b0000000,0x260000000,0x8000000000,0,9216000,168144000)
        a={'IOObjectClass':'NMXAccel','PhxHPDisplayABICompatible':True,'PhxHPDisplayPlanValid':True,'PhxHPDisplayPlan':plan}
        loaded='\n'.join(k+' ('+v+')' for k,v in [('com.apple.iokit.IOGraphicsFamily','599'),('com.apple.iokit.IOAcceleratorFamily2','485.2'),('com.apple.AppleGraphicsDeviceControl','8.1.10')])
        with patch.object(d,'nodes',return_value=[]),patch.object(d,'claimed_hp',return_value={'IORegistryEntryChildren':[a]}),patch.object(d.subprocess,'check_output',return_value=loaded):
            self.assertIs(d.validated_accelerator(),a)
            a['PhxHPDisplayABICompatible']=False
            with self.assertRaisesRegex(ValueError,'ABI'):d.validated_accelerator()
            a['PhxHPDisplayABICompatible']=True;a['PhxHPDisplayPlan']=plan[:-1]
            with self.assertRaisesRegex(ValueError,'plan data'):d.validated_accelerator()
            a['PhxHPDisplayPlan']=plan
            with patch.object(d.subprocess,'check_output',return_value=loaded.replace('485.2','486')):
                with self.assertRaisesRegex(ValueError,'family'):d.validated_accelerator()

    def test_arm_order_releases_only_after_positive_checks(self):
        events=[];values={'debug.nvaccelfb':1,'debug.nvaccel_heads_piped':1,'debug.nvaccel_iop':1,'debug.phxagdc':1,'debug.phxfb_hold':0,
                         'debug.phxfb_alias':0,'debug.nvaccel_iop_sse':1}
        def control(name,value=None):
            events.append((name,value));return values.get(name,0) if value is None else ''
        with patch.object(d,'validated_accelerator'),patch.object(d,'unopened_held_framebuffer'),patch.object(d,'sysctl',side_effect=control),patch.object(d.time,'sleep'),patch.object(d.subprocess,'check_output',return_value='SSE SSE2 SSE4.1'):
            report={};d.arm(report,lambda:None,Path('fixture'),lambda *args:events.append(('allow',None)))
        self.assertTrue(report['desktop_armed'])
        self.assertLess(events.index(('debug.phxagdc',1)),events.index(('allow',None)))
        self.assertLess(events.index(('allow',None)),events.index(('debug.phxfb_hold',0)))
        self.assertLess(events.index(('debug.phxfb_alias',0)),events.index(('allow',None)))
        self.assertEqual(report['desktop_copy_settings'],{'scanout_mapping':'pci-aperture','streaming_copy':True})

    def test_copy_settings_follow_actual_cpu_features(self):
        for features,expected in (('SSE SSE4.1 AVX',1),('SSE SSE2',0)):
            values={'debug.phxfb_alias':0,'debug.nvaccel_iop_sse':expected}
            def control(name,value=None):return values[name] if value is None else ''
            with patch.object(d.subprocess,'check_output',return_value=features),patch.object(d,'sysctl',side_effect=control) as settings:
                result=d.configure_copy()
            self.assertEqual(result['streaming_copy'],bool(expected))
            self.assertEqual(settings.call_args_list[0].args,('debug.phxfb_alias',0))

    def test_copy_setting_mismatch_stops_before_panel_release(self):
        with patch.object(d.subprocess,'check_output',return_value='SSE4.1'),patch.object(d,'sysctl',return_value=1),self.assertRaisesRegex(ValueError,'readback'):
            d.configure_copy()

    def test_failed_pipe_registration_does_not_allow_or_release(self):
        events=[]
        def control(name,value=None):events.append((name,value));return 0
        with patch.object(d,'validated_accelerator'),patch.object(d,'unopened_held_framebuffer'),patch.object(d,'sysctl',side_effect=control),patch.object(d.time,'sleep'),self.assertRaises(ValueError):
            d.arm({},lambda:None,Path('fixture'),lambda *args:self.fail('must not allow WindowServer'))
        self.assertNotIn(('debug.phxfb_hold',0),events)

    def test_hold_and_existing_framebuffer_client_are_hard_failures(self):
        with patch.object(d,'framebuffer',return_value={'IORegistryEntryChildren':[{'IOObjectClass':'IOFramebufferUserClient'}]}),patch.object(d,'sysctl') as control,self.assertRaisesRegex(ValueError,'before arming'):
            d.unopened_held_framebuffer()
        control.assert_not_called()
        with patch.object(d,'framebuffer',return_value={}),patch.object(d,'sysctl',return_value=0),self.assertRaisesRegex(ValueError,'expired'):
            d.unopened_held_framebuffer()

    def test_present_counter_alone_is_not_success(self):
        with patch.object(d,'sysctl',return_value=10),patch.object(d,'framebuffer',return_value={}),patch.object(d.time,'monotonic',side_effect=[0,121]),self.assertRaisesRegex(ValueError,'no verified'):
            d.verify_present({},lambda:None)

    def test_failed_display_boot_reboots_only_if_custom_framebuffer_owns_panel(self):
        sample='debug.nvaccel_iop_copy_us_max: 21000\ndebug.nvaccel_iop_gap2: 25\n'
        for nodes,expected in (([],0),([{}],1)):
            with patch.object(d,'nodes',return_value=nodes),patch.object(d,'sysctl',return_value=0),patch.object(d.subprocess,'run') as run,patch.object(d.subprocess,'check_output',return_value=sample):
                report={}
                d.fallback(report,lambda:None);self.assertEqual(run.call_count,expected)
                if expected:
                    self.assertEqual(run.call_args.args[0],['/sbin/shutdown','-r','now'])
                    self.assertEqual(report['desktop_failure_timing'],{'nvaccel_iop_copy_us_max':21000,'nvaccel_iop_gap2':25})

    def test_counter_read_failure_cannot_prevent_firmware_fallback(self):
        with patch.object(d,'nodes',return_value=[{}]),patch.object(d,'sysctl',side_effect=ValueError('counter unavailable')),patch.object(d.subprocess,'run') as run,patch.object(d.subprocess,'check_output',side_effect=d.subprocess.TimeoutExpired('sysctl',2)):
            report={};d.fallback(report,lambda:None)
        run.assert_called_once();self.assertEqual(len(report['desktop_failure_counters']),4)
        self.assertIn('read_error',report['desktop_failure_timing'])

    def test_refuses_to_overwrite_existing_permanent_authorization(self):
        with tempfile.TemporaryDirectory() as tmp:
            existing=Path(tmp)/d.PERSISTENT
            existing.write_text('prior authorization')
            with self.assertRaises(FileExistsError):
                d._write_root_record(existing,{'format':1})
            self.assertEqual(existing.read_text(),'prior authorization')

    def test_arm_next_boot_creates_private_request_and_checks_nvram(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(d,'boot_uuid',return_value='CURRENT'),patch.object(d,'_nvram',side_effect=[{}, {'phxfb-boot':b'1'}]),patch.object(d.subprocess,'run') as run:
            state=Path(tmp);d.arm_next_boot(state,'ACCEL-UUID')
            self.assertEqual(json.loads((state/d.REQUEST).read_text()),
                             {'format':1,'armed_from_boot':'CURRENT','accelerator_uuid':'ACCEL-UUID'})
            self.assertEqual((state/d.REQUEST).stat().st_mode&0o777,0o600)
            run.assert_called_once_with(['/usr/sbin/nvram','phxfb-boot=1'],check=True,timeout=5)

    def test_rearm_only_for_matching_permanent_authorization(self):
        with tempfile.TemporaryDirectory() as tmp:
            state=Path(tmp)
            with patch.object(d,'arm_next_boot') as arm:
                self.assertFalse(d.rearm_if_permanent(state,state))
                arm.assert_not_called()
            (state/d.PERSISTENT).write_text('{}')
            with patch.object(d,'_read_root_record',return_value={'format':1,'accelerator_uuid':'MATCH'}),patch.object(d,'macho_uuid',return_value='MATCH'),patch.object(d,'arm_next_boot') as arm:
                self.assertTrue(d.rearm_if_permanent(state,state))
                arm.assert_called_once_with(state,'MATCH')
            with patch.object(d,'_read_root_record',return_value={'format':1,'accelerator_uuid':'OTHER'}),patch.object(d,'macho_uuid',return_value='MATCH'),patch.object(d,'arm_next_boot') as arm,self.assertRaisesRegex(ValueError,'differs'):
                d.rearm_if_permanent(state,state)
            arm.assert_not_called()

    def test_failed_nvram_arm_removes_request_and_preserves_error(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(d,'boot_uuid',return_value='CURRENT'),patch.object(d,'_nvram',side_effect=[{},{}]),patch.object(d.subprocess,'run',side_effect=ValueError('nvram write failed')):
            state=Path(tmp)
            with self.assertRaisesRegex(ValueError,'nvram write failed'):
                d.arm_next_boot(state,'ACCEL-UUID')
            self.assertFalse((state/d.REQUEST).exists())

    def test_cancel_persistence_clears_next_boot_request_and_nvram(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(d,'_nvram',side_effect=[{'phxfb-boot':b'1'},{}]),patch.object(d.subprocess,'run') as run:
            state=Path(tmp)
            (state/d.PERSISTENT).write_text('{}');(state/d.REQUEST).write_text('{}')
            d.cancel_persistence(state)
            self.assertFalse((state/d.PERSISTENT).exists())
            self.assertFalse((state/d.REQUEST).exists())
            run.assert_called_once_with(['/usr/sbin/nvram','-d','phxfb-boot'],check=True,timeout=5)

    def test_lost_rearm_request_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(d,'nodes',return_value=[]):
            state=Path(tmp);(state/d.PERSISTENT).touch()
            with self.assertRaisesRegex(d.DisplayOwnershipError,'lost its next-boot request'):
                d.begin(state,state,state)

if __name__=='__main__':unittest.main()
