from pathlib import Path
import base64
import importlib.util
import json
import os
import plistlib
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from package_manifest import write

class ReleaseInstallTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        root=Path(self.tmp.name);self.package=root/'release';self.package.mkdir()
        for src in ('install/install.sh','install/uninstall.sh','install/install_diagnostics.py',
                    'tools/package_manifest.py','tools/collect_macos_evidence.py'):
            shutil.copy2(ROOT/src,self.package/Path(src).name)
        kext=self.package/'EFI/OC/Kexts/PhxBringup.kext/Contents/MacOS';kext.mkdir(parents=True)
        (kext/'PhxBringup').write_bytes(struct.pack('<8I',0xfeedfacf,0x01000007,3,11,1,8,0,0)+bytes(8))
        shutil.copy2(ROOT/'src/phxbringup/Info.plist',kext.parent/'Info.plist')
        write(self.package,{'test_fixture':True})
        self.oc=root/'EFI/OC';self.oc.mkdir(parents=True)
        self.original=plistlib.dumps({'Kernel':{'Add':[]},'Preserve':'original'})
        (self.oc/'config.plist').write_bytes(self.original)
        bindir=root/'bin';bindir.mkdir();self.marker=root/'unexpected-system-write'
        ids={'vendor-id':0x1002,'device-id':0x1900,'revision-id':0xca,'subsystem-vendor-id':0x103c,'subsystem-id':0x8c6a}
        data=base64.b64encode(plistlib.dumps([{k:v.to_bytes(4,'little') for k,v in ids.items()}])).decode()
        (bindir/'ioreg').write_text('#!/usr/bin/env python3\nimport os,sys,base64\nsys.stdout.buffer.write(b"invalid" if os.getenv("BROKEN_IOREG") else base64.b64decode("'+data+'"))\n')
        (bindir/'id').write_text('#!/bin/sh\necho 0\n')
        for name in ('sw_vers','nvram','csrutil','kmutil','ditto','install'):
            (bindir/name).write_text('#!/bin/sh\ntouch "'+str(self.marker)+'"\nexit 99\n')
        for p in bindir.iterdir():p.chmod(0o755)
        self.env=dict(os.environ,PATH=str(bindir)+':'+os.environ['PATH'])

    def run_installer(self,*args,env=None,uninstall=False):
        return subprocess.run(['bash',str(self.package/('uninstall.sh' if uninstall else 'install.sh')),*map(str,args)],
            env=env or self.env,text=True,capture_output=True,timeout=10)

    def test_shell_diagnostic_install_remove_roundtrip(self):
        r=self.run_installer('--diagnostics','--oc',self.oc,'--check')
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        self.assertEqual((self.oc/'config.plist').read_bytes(),self.original)
        r=self.run_installer('--diagnostics','--oc',self.oc)
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        backup=json.loads(r.stdout[r.stdout.index('{'):])['backup']
        r=self.run_installer('--diagnostics','--oc',self.oc,'--backup',backup,uninstall=True)
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        self.assertEqual((self.oc/'config.plist').read_bytes(),self.original)
        self.assertFalse(self.marker.exists())

    def test_hp_windowserver_refused_without_loaded_profile_marker(self):
        for args in (('--windowserver',),('--check','--windowserver')):
            r=self.run_installer(*args)
            self.assertNotEqual(r.returncode,0)
            self.assertIn('HP Radeon 760M',r.stderr)
            self.assertFalse(self.marker.exists())

    def test_direct_python_diagnostic_check_does_not_create_package_bytecode(self):
        for _ in range(2):
            r=subprocess.run([sys.executable,str(self.package/'install_diagnostics.py'),
                              '--oc',str(self.oc),'--check'],capture_output=True,text=True,timeout=10)
            self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        self.assertFalse((self.package/'__pycache__').exists())

    def test_unknown_target_and_tampered_package_fail_before_system_changes(self):
        r=self.run_installer('--windowserver',env=dict(self.env,BROKEN_IOREG='1'))
        self.assertNotEqual(r.returncode,0)
        self.assertFalse(self.marker.exists())
        (self.package/'extra').write_text('tampered')
        r=self.run_installer('--diagnostics','--oc',self.oc)
        self.assertNotEqual(r.returncode,0)
        self.assertEqual((self.oc/'config.plist').read_bytes(),self.original)

    def test_zip_preserves_executable_mode_and_handles_old_dependency_times(self):
        spec=importlib.util.spec_from_file_location('release_builder',ROOT/'tools/release/build_release.py')
        builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)
        p=self.package/'install.sh';p.chmod(0o755);os.utime(p,(0,0))
        archive=Path(self.tmp.name)/'release.zip'
        builder.zip_tree(self.package,archive,'release')
        with zipfile.ZipFile(archive) as z:
            self.assertTrue((z.getinfo('release/install.sh').external_attr>>16)&0o111)
            self.assertEqual(z.read('release/install.sh'),p.read_bytes())

if __name__=='__main__':unittest.main()
