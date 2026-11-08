from pathlib import Path
import os
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]

class BringupPreflightTests(unittest.TestCase):
    def test_firmware_preflight_failure_precedes_watchdog(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);bin_dir=root/'bin';bin_dir.mkdir()
            (bin_dir/'ioreg').write_text('#!/bin/sh\necho \'"phx-build" = 34\'\n')
            (bin_dir/'sudo').write_text('#!/bin/sh\ntouch "'+str(root/'unexpected-sudo')+'"\nexit 99\n')
            fw=root/'gpu/phxctl/phxfw';fw.parent.mkdir(parents=True)
            fw.write_text('#!/bin/sh\necho invalid-firmware >&2\nexit 1\n')
            for p in (bin_dir/'ioreg',bin_dir/'sudo',fw):p.chmod(0o755)
            r=subprocess.run(['bash',str(REPO/'tools/phxctl/bringup5.sh')],capture_output=True,text=True,
                             env=dict(os.environ,HOME=str(root),PATH=str(bin_dir)+':/usr/bin:/bin'),timeout=5)
            self.assertEqual(r.returncode,1,r.stdout+r.stderr)
            self.assertIn('invalid-firmware',r.stderr)
            self.assertFalse((root/'unexpected-sudo').exists())

    def test_refusal_precedes_watchdog_or_hardware_access(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            marker=root/'unexpected-sudo'
            sudo=root/'sudo';sudo.write_text('#!/bin/sh\necho called > "'+str(marker)+'"\nexit 99\n');sudo.chmod(0o755)
            for registry in ('', '"phx-build" = 34\n"phx-stage" = "profile-diagnostic-only"',
                             '"phx-build" = 34\n"phx-stage" = "device-lost"'):
                ioreg=root/'ioreg';ioreg.write_text('#!/bin/sh\ncat <<\'REG\'\n'+registry+'\nREG\n');ioreg.chmod(0o755)
                for name in ('bringup5.sh','full.sh'):
                    with self.subTest(stage=registry,script=name):
                        r=subprocess.run(['bash',str(REPO/'tools/phxctl'/name)],capture_output=True,text=True,
                                         env=dict(os.environ,PATH=str(root)+':/usr/bin:/bin'),timeout=5)
                        self.assertEqual(r.returncode,1,r.stdout+r.stderr)
                        self.assertFalse(marker.exists())

if __name__=='__main__':unittest.main()
