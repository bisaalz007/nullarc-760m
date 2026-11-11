"""Metadata-only update and rollback fixtures; no real kext loading."""
import json
import os
from pathlib import Path
import plistlib
import shutil
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'install'))
import fix_hp_acpi_dependency as f
from package_manifest import write,inventory

class DependencyTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.package=self.root/'old';self.bundle=self.root/'fixed.kext';self.parent=self.root/'installed';self.parent.mkdir()
        self.state=self.root/'state';self.state.mkdir();self.target=self.root/'PhxAccel.kext';self.daemon=self.root/'daemon.plist'
        self.relative='Library/Extensions/PhxAccel.kext'
        self.info={'OSBundleLibraries':{'com.apple.iokit.IOPCIFamily':'1.0'}}
        program=struct.pack('<8I',0xfeedfacf,0x01000007,3,11,1,16,0,0)+struct.pack('<4I',0x1d,16,64,16)+bytes(16)
        for bundle,dep,sig in ((self.package/self.relative,False,b'A'*16),(self.bundle,True,b'B'*16)):
            p=bundle/'Contents/MacOS';p.mkdir(parents=True)
            info=plistlib.loads(plistlib.dumps(self.info))
            if dep:info['OSBundleLibraries']['com.apple.iokit.IOACPIFamily']='1.0'
            (p.parent/'Info.plist').write_bytes(plistlib.dumps(info));(p/'PhxAccel').write_bytes(program+sig)
        write(self.package,{'test_fixture':True});shutil.copytree(self.package/self.relative,self.target)
        self.config={'Label':'local.nullarc.hp-native','ProgramArguments':['/usr/bin/python3','-B',str(self.package/'gpu/phxctl/hp_boot.py'),'--package',str(self.package)]}
        self.original=plistlib.dumps(self.config);self.daemon.write_bytes(self.original)
    def repair(self):return f.repair(self.package,self.bundle,self.parent,self.daemon,self.target,self.state)
    def test_success_preserves_original_package_and_program(self):
        before=inventory(self.package)
        with patch.object(f.os,'chown'),patch.object(f.subprocess,'run'),patch.object(f.aux,'inspect',return_value={f.aux.IDENTIFIER:{'uuid':'old'}}),patch.object(f.aux,'update') as update:
            new=self.repair()
        self.assertEqual(inventory(self.package),before);f.aux.validate_acpi_patch(self.package,new)
        self.assertEqual(update.call_args.kwargs['failure_package'],self.package)
        self.assertEqual(inventory(self.target),inventory(new/self.relative))
    def test_candidate_failure_restores_bundle_and_daemon(self):
        with patch.object(f.os,'chown'),patch.object(f.subprocess,'run'),patch.object(f.aux,'inspect',return_value={f.aux.IDENTIFIER:{'uuid':'old'}}),patch.object(f.aux,'update',side_effect=[None,ValueError('link failed')]),self.assertRaisesRegex(ValueError,'link failed'):
            self.repair()
        self.assertEqual(inventory(self.target),inventory(self.package/self.relative));self.assertEqual(self.daemon.read_bytes(),self.original)
    def test_resigning_cannot_hide_program_changes(self):
        a=(self.package/self.relative/'Contents/MacOS/PhxAccel').read_bytes()
        b=bytearray((self.bundle/'Contents/MacOS/PhxAccel').read_bytes());b[60]^=1
        self.assertNotEqual(f.aux.unsigned_prefix(a),f.aux.unsigned_prefix(b))
    def test_wrong_dependency_or_extra_component_refused(self):
        new=self.root/'new';shutil.copytree(self.package,new);shutil.rmtree(new/self.relative);shutil.copytree(self.bundle,new/self.relative)
        f.aux.validate_acpi_patch(self.package,new)
        (new/'unexpected').write_text('other change')
        with self.assertRaises(ValueError):f.aux.validate_acpi_patch(self.package,new)
        (new/'unexpected').unlink()
        p=new/self.relative/'Contents/Info.plist';info=plistlib.loads(p.read_bytes());info['OSBundleLibraries']['com.apple.iokit.IOACPIFamily']='2.0';p.write_bytes(plistlib.dumps(info))
        with self.assertRaises(ValueError):f.aux.validate_acpi_patch(self.package,new)

if __name__=='__main__':unittest.main()
