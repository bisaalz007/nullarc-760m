from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
TOOL = REPO / 'build/tools/phxfw'

class FirmwarePlanTests(unittest.TestCase):
    def run_tool(self, *args):
        return subprocess.run([str(TOOL), *map(str,args)], capture_output=True, text=True, timeout=5)

    def test_mes_explicit_offsets_and_no_partial_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/'mes.bin'
            b = bytearray(2048)
            struct.pack_into('<IIHHHHIIII10I', b, 0, len(b), 72, 1, 0, 11, 0, 0, 1792, 256, 0,
                             0, 512, 256, 0, 512, 1024, 0, 0, 0, 0)
            p.write_bytes(b)
            r = self.run_tool('--inspect-mes','scheduler',p)
            self.assertEqual(r.returncode,0,r.stderr)
            self.assertIn('"offset":1024',r.stdout)
            struct.pack_into('<I', b, 52, 512) # data overlaps code
            p.write_bytes(b)
            r = self.run_tool('--inspect-mes','scheduler',p)
            self.assertNotEqual(r.returncode,0); self.assertEqual(r.stdout,'')
            r = self.run_tool('--phoenix-plan',tmp)
            self.assertNotEqual(r.returncode,0); self.assertEqual(r.stdout,'')

    def test_mes_entry_points_are_independent_and_complete(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for name,pc in [('gc_11_0_1_mes_2.bin',0xfffffffff0005000),('gc_11_0_1_mes1.bin',0xfffffffff0006000)]:
                b=bytearray(2048)
                struct.pack_into('<IIHHHHIIII10I',b,0,len(b),72,1,0,11,0,0,1792,256,0,
                                 0,512,256,0,512,1024,pc&0xffffffff,pc>>32,0,0)
                (root/name).write_bytes(b)
            r=self.run_tool('--mes-start-pcs',root)
            self.assertEqual(r.returncode,0,r.stderr)
            self.assertEqual(r.stdout.strip(),'0xfffffffff0005000 0xfffffffff0006000')
            (root/'gc_11_0_1_mes1.bin').unlink()
            r=self.run_tool('--mes-start-pcs',root)
            self.assertNotEqual(r.returncode,0);self.assertEqual(r.stdout,'')

    def test_fixture_plan_then_missing_final_file(self):
        fixtures = REPO/'tests/fixtures/phoenix'
        if not (fixtures/'psp_13_0_4_toc.bin').exists():
            self.skipTest('run make fixtures for complete firmware preflight')
        with tempfile.TemporaryDirectory() as tmp:
            shutil.copytree(fixtures,Path(tmp)/'fw')
            fw = Path(tmp)/'fw'
            r = self.run_tool('--phoenix-plan',fw)
            self.assertEqual(r.returncode,0,r.stderr)
            rows = [line.split('\t') for line in r.stdout.splitlines()]
            self.assertEqual(len(rows),18)
            self.assertEqual(rows[0][0],'psp_13_0_4_toc.bin')
            self.assertEqual(rows[-1][3],'8') # RLC_G last, preserves load ordering
            (fw/'gc_11_0_1_rlc.bin').unlink()
            r = self.run_tool('--phoenix-plan',fw)
            self.assertNotEqual(r.returncode,0); self.assertEqual(r.stdout,'')

if __name__ == '__main__': unittest.main()
