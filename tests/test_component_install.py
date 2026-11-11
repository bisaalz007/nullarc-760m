from pathlib import Path
import importlib.util
import plistlib
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from package_manifest import write
spec=importlib.util.spec_from_file_location('component_install',ROOT/'install/install_components.py')
c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)

class ComponentTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.package=Path(self.tmp.name)/'package';self.package.mkdir()
        self.root=Path(self.tmp.name)/'root';self.root.mkdir()
        for src in c.TARGETS:
            p=self.package/src;p.mkdir(parents=True);(p/'file').write_text('new component')
        for dst in c.DESTINATIONS:
            p=self.root/dst;p.mkdir(parents=True);(p/'file').write_text('original component')
        write(self.package,{'minimum_macos':'15.0'})

    def test_check_install_restore_and_disabled_boot(self):
        self.assertFalse(c.install(self.package,self.root)['changes_written'])
        r=c.install(self.package,self.root,check=False)
        self.assertTrue((self.root/'Users/Shared/gpu/phxboot-off').exists())
        self.assertFalse(r['WindowServer_armed']);self.assertTrue(r['loaded_kernel_unchanged'])
        c.restore(Path(r['backup']),self.root)
        for dst in c.DESTINATIONS:self.assertEqual((self.root/dst/'file').read_text(),'original component')

    def test_mid_install_failure_restores_prior_components(self):
        original=c.shutil.copytree;calls=0
        def copy(*a,**kw):
            nonlocal calls
            calls+=1
            if calls==2:raise OSError('injected second copy failure')
            return original(*a,**kw)
        with patch.object(c.shutil,'copytree',side_effect=copy),self.assertRaises(OSError):
            c.install(self.package,self.root,check=False)
        for dst in c.DESTINATIONS:self.assertEqual((self.root/dst/'file').read_text(),'original component')

    def test_fresh_files_archives_existing_native_service_and_restores(self):
        daemon=self.root/'Library/LaunchDaemons/local.nullarc.hp-native.plist'
        daemon.parent.mkdir(parents=True)
        old='/Library/Application Support/NullArc760M/package-old'
        config={'Label':'local.nullarc.hp-native','ProgramArguments':
            ['/usr/bin/python3','-B',old+'/gpu/phxctl/hp_boot.py','--package',old]}
        daemon.write_bytes(plistlib.dumps(config))
        with self.assertRaisesRegex(ValueError,'HP native boot service already exists'):
            c.install(self.package,self.root,check=False)
        preflight=c.install(self.package,self.root,check=True,fresh=True)
        self.assertTrue(preflight['existing_native_service_will_be_archived'])
        result=c.install(self.package,self.root,check=False,fresh=True)
        self.assertFalse(daemon.exists())
        self.assertTrue((Path(result['backup'])/'previous-hp-native.plist').exists())
        self.assertEqual((self.root/c.DESTINATIONS[1]/'file').read_text(),'new component')
        self.assertFalse(result['WindowServer_armed'])
        restored=c.restore(Path(result['backup']),self.root)
        self.assertTrue(restored['previous_boot_service_restored'])
        self.assertEqual(daemon.read_bytes(),plistlib.dumps(config))
        self.assertEqual((self.root/c.DESTINATIONS[1]/'file').read_text(),'original component')

    def test_fresh_files_rejects_unknown_service(self):
        daemon=self.root/'Library/LaunchDaemons/local.nullarc.hp-native.plist'
        daemon.parent.mkdir(parents=True);daemon.write_bytes(plistlib.dumps({'Label':'other-service'}))
        with self.assertRaisesRegex(ValueError,'unexpected HP native service'):
            c.install(self.package,self.root,check=False,fresh=True)
        self.assertEqual((self.root/c.DESTINATIONS[1]/'file').read_text(),'original component')

    def test_fresh_files_restores_service_if_copy_fails(self):
        daemon=self.root/'Library/LaunchDaemons/local.nullarc.hp-native.plist'
        daemon.parent.mkdir(parents=True)
        old='/Library/Application Support/NullArc760M/package-old'
        daemon.write_bytes(plistlib.dumps({'Label':'local.nullarc.hp-native','ProgramArguments':
            ['/usr/bin/python3','-B',old+'/gpu/phxctl/hp_boot.py','--package',old]}))
        original=c.shutil.copytree
        def fail(*args,**kwargs):
            if args[0]==self.package/c.TARGETS[1]:raise OSError('injected fresh copy failure')
            return original(*args,**kwargs)
        with patch.object(c.shutil,'copytree',side_effect=fail),self.assertRaisesRegex(OSError,'injected fresh copy failure'):
            c.install(self.package,self.root,check=False,fresh=True)
        self.assertTrue(daemon.exists())
        for dst in c.DESTINATIONS:
            self.assertEqual((self.root/dst/'file').read_text(),'original component')

    def test_later_edits_and_existing_boot_daemon_refused(self):
        r=c.install(self.package,self.root,check=False)
        (self.root/c.DESTINATIONS[0]/'file').write_text('later user edit')
        with self.assertRaises(ValueError):c.restore(Path(r['backup']),self.root)
        p=self.root/'Library/LaunchDaemons/local.phxboot.plist';p.parent.mkdir(parents=True);p.touch()
        with self.assertRaises(ValueError):c.install(self.package,self.root,check=False)

if __name__=='__main__':unittest.main()
