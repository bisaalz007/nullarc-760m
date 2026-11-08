from pathlib import Path
import os
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]

class BringupPreflightTests(unittest.TestCase):
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
