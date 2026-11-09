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
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.state=self.root/'state';self.allow=self.root/'allow'

    def process(self,code=0,metal=True):
        def spawn(command,**kwargs):
            folder=Path(command[command.index('--output')+1]);folder.mkdir()
            (folder/'result.json').write_text(json.dumps(dict(executed=True,native_compute_verified=True,native_render_verified=True,metal_verified=metal)))
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

    def test_success_exit_without_metal_evidence_is_refused(self):
        with patch.object(b.subprocess,'Popen',side_effect=self.process(metal=False)),self.assertRaises(ValueError):b.boot(self.root,self.state,self.allow)
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

if __name__=='__main__':unittest.main()
