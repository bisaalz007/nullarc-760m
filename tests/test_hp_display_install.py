"""Transactional display-module staging against temporary files only."""
import importlib.util
from pathlib import Path
import plistlib
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'));sys.path.insert(0,str(ROOT/'install'))
from package_manifest import write,verify,inventory
import install_hp_windowserver as i

class InstallTests(unittest.TestCase):
    def test_arm_requires_current_boot_native_readiness_and_metal_readbacks(self):
        status={'native_readiness_verified':True,'metal_verified':True,'apps_enabled':True,'boot_session_uuid':'current'}
        i.validate_current_apps(status,'current')
        for key in ('native_readiness_verified','metal_verified','apps_enabled'):
            bad=dict(status);bad[key]=False
            with self.assertRaises(ValueError):i.validate_current_apps(bad,'current')
        with self.assertRaises(ValueError):i.validate_current_apps(status,'other')

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.package=self.root/'new';self.old=self.root/'old';self.parent=self.root/'installed';self.parent.mkdir()
        self.state=self.root/'state';self.state.mkdir();self.target=self.root/'PhxAccel.kext'
        for package,binary in ((self.old,b'old-module'),(self.package,b'new-module')):
            path=package/'Library/Extensions/PhxAccel.kext/Contents/MacOS';path.mkdir(parents=True);(path/'PhxAccel').write_bytes(binary)
            write(package,{'test_fixture':True})
        shutil.copytree(self.old/'Library/Extensions/PhxAccel.kext',self.target)
        self.daemon=self.root/'daemon.plist';self.config={'Label':'fixture','ProgramArguments':['old']}
        self.original=plistlib.dumps(self.config);self.daemon.write_bytes(self.original)
        owner=patch.object(i.os,'chown');owner.start();self.addCleanup(owner.stop)
    def stage(self):
        return i.stage_module(self.package,self.old,self.daemon,self.state,self.parent,self.target,
                              self.package/'Library/Extensions/PhxAccel.kext',self.original,self.config)
    def test_staging_keeps_backup_and_updates_only_next_boot_package(self):
        with patch.object(i.subprocess,'run') as run:backup,destination=self.stage()
        run.assert_not_called();verify(destination)
        self.assertEqual(inventory(backup/'PhxAccel.kext'),inventory(self.old/'Library/Extensions/PhxAccel.kext'))
        self.assertEqual(inventory(self.target),inventory(self.package/'Library/Extensions/PhxAccel.kext'))
        self.assertEqual(plistlib.loads(self.daemon.read_bytes())['ProgramArguments'][-1],str(destination))
    def test_failed_daemon_write_restores_module(self):
        with patch.object(i,'atomic_write',side_effect=OSError('injected write failure')),self.assertRaises(OSError):self.stage()
        self.assertEqual(inventory(self.target),inventory(self.old/'Library/Extensions/PhxAccel.kext'))
        self.assertEqual(self.daemon.read_bytes(),self.original);self.assertEqual(list(self.parent.iterdir()),[])
    def test_tampered_package_does_not_replace_module(self):
        (self.package/'unexpected').write_text('tampered')
        with self.assertRaises(ValueError):self.stage()
        self.assertEqual(inventory(self.target),inventory(self.old/'Library/Extensions/PhxAccel.kext'))
        self.assertEqual(self.daemon.read_bytes(),self.original)
    def test_concurrent_service_edit_is_preserved(self):
        edited=plistlib.dumps({'Label':'concurrent edit'});self.daemon.write_bytes(edited)
        with self.assertRaisesRegex(ValueError,'changed during staging'):self.stage()
        self.assertEqual(self.daemon.read_bytes(),edited)
        self.assertEqual(inventory(self.target),inventory(self.old/'Library/Extensions/PhxAccel.kext'))

if __name__=='__main__':unittest.main()
