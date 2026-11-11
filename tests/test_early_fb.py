"""Early matching metadata and EFI transaction tests; no live driver changes."""
from pathlib import Path
import copy
import plistlib
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'install'))
import install_early_fb as e
from package_manifest import write

class EarlyTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.package=self.root/'package';self.oc=self.root/'OC';(self.oc/'Kexts').mkdir(parents=True)
        self.base=plistlib.loads((ROOT/'src/phxbringup/Info.plist').read_bytes())
        self.accel=plistlib.loads((ROOT/'src/phxaccel/Info.plist').read_bytes())
        k=self.package/'EFI/OC/Kexts/PhxBringup.kext/Contents';(k/'MacOS').mkdir(parents=True)
        (k/'Info.plist').write_bytes(plistlib.dumps(self.base));(k/'MacOS/PhxBringup').write_bytes(b'unchanged program fixture')
        a=self.package/'Library/Extensions/PhxAccel.kext/Contents';a.mkdir(parents=True);(a/'Info.plist').write_bytes(plistlib.dumps(self.accel))
        write(self.package,{'test_fixture':True});shutil.copytree(k.parent,self.oc/'Kexts/PhxBringup.kext')
        self.config=plistlib.dumps({'Kernel':{'Add':[{'BundlePath':'PhxBringup.kext','Enabled':True,'ExecutablePath':'Contents/MacOS/PhxBringup'}]},'Preserve':{'boot-args':'unchanged'}})
        (self.oc/'config.plist').write_bytes(self.config)
    def test_foreign_personality_requests_actual_code_and_only_exact_hp(self):
        before=copy.deepcopy(self.base);after=e.derive(self.base,self.accel)
        p=after['IOKitPersonalities'].pop(e.KEY)
        self.assertEqual(self.base,before);self.assertEqual(after,before)
        self.assertEqual(p['CFBundleIdentifierKernel'],'com.luuumi.PhxAccel')
        self.assertEqual(p['IOPersonalityPublisher'],'org.drip.PhxBringup')
        self.assertEqual(p['IOPropertyMatch'],{k:v.to_bytes(4,'little') for k,v in e.EXPECTED.items()})
        self.assertNotIn('nmxgpu-claimed',p['IOPropertyMatch']);self.assertNotIn('CFBundleExecutable',p)
    def test_install_backup_readback_and_no_config_or_binary_change(self):
        b=self.oc/'Kexts/PhxBringup.kext/Contents';original=(b/'Info.plist').read_bytes()
        with patch.object(e.subprocess,'check_output',return_value='hp-diagnostic-only\n'):
            r=e.install(self.package,self.oc,True)
            self.assertTrue(r['changed']);self.assertEqual((Path(r['backup'])/'Info.plist').read_bytes(),original)
            self.assertFalse(e.install(self.package,self.oc,True)['changed'])
        self.assertEqual((self.oc/'config.plist').read_bytes(),self.config)
        self.assertEqual((b/'MacOS/PhxBringup').read_bytes(),b'unchanged program fixture')
    def test_dry_run_does_not_write(self):
        b=self.oc/'Kexts/PhxBringup.kext/Contents';original=(b/'Info.plist').read_bytes()
        with patch.object(e.subprocess,'check_output',return_value='hp-diagnostic-only\n'):
            self.assertFalse(e.install(self.package,self.oc)['changed'])
        self.assertEqual((b/'Info.plist').read_bytes(),original);self.assertFalse(list(self.oc.glob('.nullarc-*')))
    def test_modified_code_or_foreign_existing_metadata_refused(self):
        b=self.oc/'Kexts/PhxBringup.kext/Contents';(b/'MacOS/PhxBringup').write_bytes(b'other code')
        with patch.object(e.subprocess,'check_output',return_value='hp-diagnostic-only\n'),self.assertRaises(ValueError):e.install(self.package,self.oc,True)
        bad=copy.deepcopy(self.base);bad['IOKitPersonalities'][e.KEY]={'unexpected':True}
        with self.assertRaises(ValueError):e.derive(bad,self.accel)

if __name__=='__main__':unittest.main()
