import importlib.util
from pathlib import Path
import plistlib
import subprocess
import unittest
from unittest.mock import patch

SPEC=importlib.util.spec_from_file_location('hp_bringup',Path(__file__).resolve().parents[1]/'tools/phxctl/hp_bringup.py')
h=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(h)
READY=plistlib.dumps([{'phx-profile':'hp-760m','phx-stage':'native-queues-ready'}])

class PublicationTests(unittest.TestCase):
    def test_delayed_catalogue_retries_only_device_enumeration(self):
        attempts=[]
        responses=[subprocess.CompletedProcess([],75,'devices: 0\nno Metal device\n',''),subprocess.CompletedProcess([],0,'HP PCI identity verified','')]
        with patch.object(h.subprocess,'check_output',return_value=READY),patch.object(h.subprocess,'run',side_effect=responses) as run,patch.object(h.time,'sleep'):
            self.assertEqual(h.wait_for_metal(Path('/mtlprobe'),{},attempts.append).returncode,0)
        self.assertEqual([a['returncode'] for a in attempts],[75,0])
        self.assertTrue(all(call.args[0]==['/mtlprobe','--hp','list'] for call in run.call_args_list))

    def test_real_failure_is_not_retried(self):
        for code,error in [(1,''),(75,'native transport failed')]:
            with self.subTest(code=code,error=error),patch.object(h.subprocess,'check_output',return_value=READY),patch.object(h.subprocess,'run',return_value=subprocess.CompletedProcess([],code,'',error)) as run,self.assertRaises(ValueError):
                h.wait_for_metal(Path('/mtlprobe'),{},lambda a:None)
            self.assertEqual(run.call_count,1)

    def test_lost_driver_stops_before_metal(self):
        lost=plistlib.dumps([{'phx-profile':'hp-760m','phx-stage':'device-lost'}])
        with patch.object(h.subprocess,'check_output',return_value=lost),patch.object(h.subprocess,'run') as run,self.assertRaises(ValueError):
            h.wait_for_metal(Path('/mtlprobe'),{},lambda a:None)
        run.assert_not_called()

    def test_deadline_is_bounded(self):
        with patch.object(h.time,'monotonic',side_effect=[0,31]),patch.object(h.subprocess,'run') as run,self.assertRaisesRegex(ValueError,'timed out'):
            h.wait_for_metal(Path('/mtlprobe'),{},lambda a:None)
        run.assert_not_called()

if __name__=='__main__':unittest.main()
