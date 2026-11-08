"""Actual capture CLI with mock IOKit; verifies file/transport handling, not root access or firmware."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]

class VbiosTransportTests(unittest.TestCase):
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
