import importlib.util
from pathlib import Path
import plistlib
import sys
import struct
import tempfile
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'tools'))
from package_manifest import write, verify
spec = importlib.util.spec_from_file_location('diagnostic_install', REPO / 'install/install_diagnostics.py')
installer = importlib.util.module_from_spec(spec); spec.loader.exec_module(installer)


class DiagnosticInstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.package = root / 'package'; self.package.mkdir()
        kext = self.package / 'EFI/OC/Kexts/PhxBringup.kext/Contents/MacOS'
        kext.mkdir(parents=True)
        # Minimal Mach-O metadata fixture; not a runtime-loadability test.
        (kext / 'PhxBringup').write_bytes(struct.pack('<8I',0xfeedfacf,0x01000007,3,11,1,8,0,0)+bytes(8))
        (kext.parent / 'Info.plist').write_bytes((REPO/'src/phxbringup/Info.plist').read_bytes())
        write(self.package, {'test_fixture': True})
        self.oc = root / 'EFI/OC'; self.oc.mkdir(parents=True)
        self.original = plistlib.dumps({'Kernel': {'Add': [{'BundlePath':'Lilu.kext', 'Enabled':True}]}, 'Unrelated':'preserve'})
        (self.oc / 'config.plist').write_bytes(self.original)

    def test_check_then_install_remove(self):
        result = installer.install(self.package, self.oc)
        self.assertFalse(result['changes_written'])
        self.assertFalse((self.oc / 'Kexts').exists())
        result = installer.install(self.package, self.oc, check=False)
        config = plistlib.loads((self.oc / 'config.plist').read_bytes())
        self.assertEqual(config['Unrelated'], 'preserve')
        self.assertEqual(config['Kernel']['Add'][0]['BundlePath'], 'Lilu.kext')
        self.assertEqual(config['Kernel']['Add'][1]['BundlePath'], 'PhxBringup.kext')
        installer.remove(self.oc, Path(result['backup']), check=False)
        self.assertEqual((self.oc / 'config.plist').read_bytes(), self.original)
        self.assertFalse((self.oc / 'Kexts/PhxBringup.kext').exists())

    def test_restore_existing_kext(self):
        path = self.oc / 'Kexts/PhxBringup.kext'; path.mkdir(parents=True)
        (path / 'original').write_bytes(b'original')
        result = installer.install(self.package, self.oc, check=False)
        installer.remove(self.oc, Path(result['backup']), check=False)
        self.assertEqual((path / 'original').read_bytes(), b'original')

    def test_mid_install_failure_rolls_back(self):
        with patch.object(installer, 'atomic_write', side_effect=OSError('injected config write failure')):
            with self.assertRaises(OSError): installer.install(self.package, self.oc, check=False)
        self.assertEqual((self.oc / 'config.plist').read_bytes(), self.original)
        self.assertFalse((self.oc / 'Kexts/PhxBringup.kext').exists())

    def test_tampering_and_later_edits_rejected(self):
        (self.package / 'extra').write_text('unrecorded file')
        with self.assertRaises(ValueError): installer.install(self.package, self.oc, check=False)
        (self.package / 'extra').unlink()
        result = installer.install(self.package, self.oc, check=False)
        later = plistlib.dumps({'Kernel': {'Add': []}, 'Unrelated':'later user edit'})
        (self.oc / 'config.plist').write_bytes(later)
        with self.assertRaises(ValueError): installer.remove(self.oc, Path(result['backup']), check=False)
        self.assertEqual((self.oc / 'config.plist').read_bytes(), later)

    def test_invalid_kext_rejected_before_efi_changes(self):
        binary=self.package/'EFI/OC/Kexts/PhxBringup.kext/Contents/MacOS/PhxBringup'
        binary.write_bytes(b'not a kext')
        write(self.package, {'test_fixture':True})
        with self.assertRaises(ValueError): installer.install(self.package,self.oc,check=False)
        self.assertFalse((self.oc/'Kexts').exists())
        self.assertEqual((self.oc/'config.plist').read_bytes(),self.original)

    def test_package_symlink_and_false_claim_rejected(self):
        (self.package / 'link').symlink_to(self.oc / 'config.plist')
        with self.assertRaises(ValueError): verify(self.package)
        (self.package / 'link').unlink()
        p = self.package / 'package-manifest.json'
        p.write_text(p.read_text().replace('"acceleration_verified": false', '"acceleration_verified": true'))
        with self.assertRaises(ValueError): verify(self.package)


if __name__ == '__main__': unittest.main()
