"""Actual capture CLI with mock IOKit; verifies file/transport handling, not root access or firmware."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest
import json

ROOT=Path(__file__).resolve().parents[1]

class VbiosTransportTests(unittest.TestCase):
    def test_actual_psp_cli_toc_size_and_failure_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            binary=Path(tmp)/'phxctl'
            subprocess.run(['cc','-std=gnu11','-Wall','-Wextra','-Werror','-I'+str(ROOT/'tests/mocks'),
                            str(ROOT/'tools/phxctl/phxctl.c'),'-o',str(binary)],check=True)
            clean={k:v for k,v in os.environ.items() if not k.startswith(('MESBOOT_','PSP_TEST_'))}
            r=subprocess.run([str(binary),'toc','4096'],env=clean,capture_output=True,text=True)
            self.assertEqual(r.returncode,0,r.stderr)
            self.assertIn('test-psp-ctl:3:4096',r.stdout)
            self.assertIn('required TMR bytes 0x4000000',r.stdout)
            for env in [dict(clean,MESBOOT_TEST_FAIL='106'),dict(clean,MESBOOT_TEST_SHORT='106'),
                        dict(clean,PSP_TEST_STATUS='256'),dict(clean,PSP_TEST_TMR_BYTES='0')]:
                r=subprocess.run([str(binary),'toc','4096'],env=env,capture_output=True,text=True)
                self.assertNotEqual(r.returncode,0,r.stdout)
            for value in ['0','-1','nonsense','4294967296']:
                r=subprocess.run([str(binary),'toc',value],env=clean,capture_output=True,text=True)
                self.assertNotEqual(r.returncode,0,r.stdout)
                self.assertNotIn('test-call:106',r.stdout)

    def test_scanout_read_only_transport_and_wrong_gpu_refusal(self):
        with tempfile.TemporaryDirectory() as tmp:
            binary=Path(tmp)/'phxprofile'
            subprocess.run(['cc','-std=gnu11','-Wall','-Wextra','-Werror','-I'+str(ROOT/'tests/mocks'),
                            str(ROOT/'tools/phxctl/phxprofile.c'),'-o',str(binary)],check=True)
            clean={k:v for k,v in os.environ.items() if not k.startswith(('MESBOOT_','SUDO_'))}
            r=subprocess.run([str(binary),'--scanout'],env=clean,capture_output=True,text=True)
            self.assertEqual(r.returncode,0,r.stderr)
            report=json.loads(r.stdout[r.stdout.index('{'):])
            self.assertEqual([len(s) for s in report['samples']],[48,48])
            self.assertFalse(report['register_writes'])
            self.assertNotIn('test-call:108',r.stdout)
            for env in [dict(clean,MESBOOT_TEST_OTHER_GPU='1'),dict(clean,MESBOOT_TEST_FAIL='2'),
                        dict(clean,MESBOOT_TEST_SHORT='2')]:
                r=subprocess.run([str(binary),'--scanout'],env=env,capture_output=True,text=True)
                self.assertNotEqual(r.returncode,0,r.stderr)
                self.assertNotIn('{',r.stdout)
                self.assertLessEqual(r.stdout.count('test-call:2\n'),1)

    def test_dump_shape_failure_cleanup_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp=Path(tmp);binary=tmp/'phxprofile'
            subprocess.run(['cc','-std=gnu11','-Wall','-Wextra','-Werror','-I'+str(ROOT/'tests/mocks'),
                            str(ROOT/'tools/phxctl/phxprofile.c'),'-o',str(binary)],check=True)
            clean={k:v for k,v in os.environ.items() if not k.startswith(('MESBOOT_','SUDO_'))}
            dest=tmp/'rom.bin'
            r=subprocess.run([str(binary),'--dump-vbios',str(dest)],env=clean,capture_output=True,text=True)
            self.assertEqual(r.returncode,0,r.stderr)
            self.assertEqual(dest.read_bytes(),bytes(512))
            self.assertEqual(dest.stat().st_mode&0o777,0o600)
            dest.write_bytes(b'keep original')
            r=subprocess.run([str(binary),'--dump-vbios',str(dest)],env=clean,capture_output=True,text=True)
            self.assertNotEqual(r.returncode,0)
            self.assertEqual(dest.read_bytes(),b'keep original')
            self.assertNotIn('test-call:32',r.stdout)
            dest.unlink()
            for key,selector in [('MESBOOT_TEST_FAIL','0'),('MESBOOT_TEST_SHORT','0'),
                                 ('MESBOOT_TEST_FAIL','32'),('MESBOOT_TEST_SHORT','32')]:
                r=subprocess.run([str(binary),'--dump-vbios',str(dest)],env=dict(clean,**{key:selector}),
                                 capture_output=True,text=True)
                self.assertNotEqual(r.returncode,0,r.stdout+r.stderr)
                self.assertFalse(dest.exists())

if __name__=='__main__':unittest.main()
