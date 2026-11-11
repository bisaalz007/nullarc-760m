import importlib.util
from pathlib import Path
import plistlib
import subprocess
import unittest
from unittest.mock import patch

SPEC=importlib.util.spec_from_file_location('hp_bringup',Path(__file__).resolve().parents[1]/'tools/phxctl/hp_bringup.py')
h=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(h)
READY=plistlib.dumps([{'phx-profile':'hp-760m','phx-stage':'native-queues-ready'}])
def pci(plugin=True):
    accelerator={'IOObjectClass':'NMXAccel'}
    if plugin:accelerator['MetalPluginName']='NVMTLDriver'
    return plistlib.dumps([dict(h.EXPECTED,**{'nmxgpu-claimed':True,'phx-diagnostic-only':False,'IORegistryEntryChildren':[accelerator]})])
def registry(args,**kwargs):return pci() if args[-1]=='IOPCIDevice' else READY

class PublicationTests(unittest.TestCase):
    def test_delayed_catalogue_retries_only_device_enumeration(self):
        attempts=[]
        responses=[subprocess.CompletedProcess([],75,'devices: 0\nno Metal device\n',''),subprocess.CompletedProcess([],0,'HP PCI identity verified','')]
        with patch.object(h.subprocess,'check_output',side_effect=registry),patch.object(h.subprocess,'run',side_effect=responses) as run,patch.object(h.time,'sleep'):
            self.assertEqual(h.wait_for_metal(Path('/mtlprobe'),{},attempts.append).returncode,0)
        self.assertEqual([a['returncode'] for a in attempts],[75,0])
        self.assertTrue(all(call.args[0]==['/mtlprobe','--hp','list'] for call in run.call_args_list))

    def test_real_failure_is_not_retried(self):
        for code,error in [(1,''),(75,'native transport failed')]:
            with self.subTest(code=code,error=error),patch.object(h.subprocess,'check_output',side_effect=registry),patch.object(h.subprocess,'run',return_value=subprocess.CompletedProcess([],code,'',error)) as run,self.assertRaises(ValueError):
                h.wait_for_metal(Path('/mtlprobe'),{},lambda a:None)
            self.assertEqual(run.call_count,1)

    def test_registry_timeout_retries_snapshot_without_submitting_work(self):
        attempts=[];reads=[subprocess.TimeoutExpired(['ioreg'],15),READY,pci()]
        with patch.object(h.subprocess,'check_output',side_effect=reads) as read,patch.object(h.subprocess,'run',return_value=subprocess.CompletedProcess([],0,'HP device','')) as run,patch.object(h.time,'sleep'):
            h.wait_for_metal(Path('/mtlprobe'),{},attempts.append)
        self.assertEqual(attempts[0]['state'],'awaiting-registry-snapshot');run.assert_called_once()
        self.assertTrue(all(0<call.kwargs['timeout']<=15 for call in read.call_args_list))

    def test_metal_probe_timeout_is_not_retried(self):
        with patch.object(h.subprocess,'check_output',side_effect=registry),patch.object(h.subprocess,'run',side_effect=subprocess.TimeoutExpired(['mtlprobe'],30)) as run,self.assertRaises(subprocess.TimeoutExpired):
            h.wait_for_metal(Path('/mtlprobe'),{},lambda a:None)
        run.assert_called_once()

    def test_lost_driver_stops_before_metal(self):
        lost=plistlib.dumps([{'phx-profile':'hp-760m','phx-stage':'device-lost'}])
        with patch.object(h.subprocess,'check_output',return_value=lost),patch.object(h.subprocess,'run') as run,self.assertRaises(ValueError):
            h.wait_for_metal(Path('/mtlprobe'),{},lambda a:None)
        run.assert_not_called()

    def test_deadline_is_bounded(self):
        with patch.object(h.time,'monotonic',side_effect=[0,91]),patch.object(h.subprocess,'run') as run,self.assertRaisesRegex(ValueError,'timed out'):
            h.wait_for_metal(Path('/mtlprobe'),{},lambda a:None)
        run.assert_not_called()

    def test_withheld_plugin_is_waited_for_before_any_metal_call(self):
        reads=iter([pci(False),pci(True)]);attempts=[]
        def read(args,**kwargs):
            if args[-1]=='IOPCIDevice':
                self.assertIn('-alr',args)
                return next(reads)
            return READY
        with patch.object(h.subprocess,'check_output',side_effect=read),patch.object(h.subprocess,'run',return_value=subprocess.CompletedProcess([],0,'HP device','')) as run,patch.object(h.time,'sleep'):
            h.wait_for_metal(Path('/mtlprobe'),{},attempts.append)
        run.assert_called_once();self.assertEqual(attempts[0]['state'],'awaiting-metal-plugin-property')

    def test_wrong_pci_identity_never_reaches_metal(self):
        wrong=plistlib.dumps([dict(h.EXPECTED,**{'device-id':0x15bf})])
        with patch.object(h.subprocess,'check_output',side_effect=lambda args,**kw:wrong if args[-1]=='IOPCIDevice' else READY),patch.object(h.subprocess,'run') as run,self.assertRaisesRegex(ValueError,'PCI identity'):
            h.wait_for_metal(Path('/mtlprobe'),{},lambda a:None)
        run.assert_not_called()

class RegistryReadinessTests(unittest.TestCase):
    def test_boot_waits_for_empty_and_malformed_registry_plists(self):
        ready={'phx-profile':'hp-760m','phx-build':39,'phx-stage':'profile-diagnostic-only'}
        replies=[b'',b'not a plist',plistlib.dumps([ready])]
        with patch.object(h.subprocess,'check_output',side_effect=replies) as read,patch.object(h.time,'sleep') as sleep,patch.object(h.subprocess,'run') as gpu:
            self.assertEqual(h.wait_for_phxbringup(),ready)
        self.assertEqual(read.call_count,3)
        self.assertEqual(sleep.call_count,2)
        self.assertTrue(all(0<call.kwargs['timeout']<=10 for call in read.call_args_list))
        gpu.assert_not_called()

    def test_boot_waits_for_hp_profile_and_published_stage(self):
        partial={'phx-profile':'hp-760m','phx-build':39}
        ready=dict(partial,**{'phx-stage':'profile-diagnostic-only'})
        replies=[plistlib.dumps([]),plistlib.dumps([partial]),plistlib.dumps([ready])]
        with patch.object(h.subprocess,'check_output',side_effect=replies) as read,patch.object(h.time,'sleep'):
            self.assertEqual(h.wait_for_phxbringup(),ready)
        self.assertEqual(read.call_count,3)

    def test_boot_registry_timeout_is_bounded_and_halts_pre_gpu(self):
        with patch.object(h.time,'monotonic',side_effect=[0,0,0,91]),patch.object(h.subprocess,'check_output',return_value=b'') as read,patch.object(h.time,'sleep'),patch.object(h.subprocess,'run') as gpu:
            with self.assertRaisesRegex(ValueError,'PhxBringup registry unavailable after 90s'):
                h.wait_for_phxbringup()
        read.assert_called_once()
        gpu.assert_not_called()

    def test_wrong_phx_build_is_not_waited_out(self):
        old=plistlib.dumps([{'phx-profile':'hp-760m','phx-build':38,'phx-stage':'profile-diagnostic-only'}])
        with patch.object(h.subprocess,'check_output',return_value=old) as read,patch.object(h.time,'sleep') as sleep,self.assertRaisesRegex(ValueError,'build 39'):
            h.wait_for_phxbringup()
        read.assert_called_once()
        sleep.assert_not_called()

    def test_duplicate_hp_services_are_rejected(self):
        node={'phx-profile':'hp-760m','phx-build':39,'phx-stage':'profile-diagnostic-only'}
        with patch.object(h.subprocess,'check_output',return_value=plistlib.dumps([node,node])),patch.object(h.time,'sleep') as sleep,self.assertRaisesRegex(ValueError,'multiple HP'):
            h.wait_for_phxbringup()
        sleep.assert_not_called()


if __name__=='__main__':unittest.main()
