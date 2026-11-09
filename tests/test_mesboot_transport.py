from pathlib import Path
import os
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]

class MesbootTransportTests(unittest.TestCase):
    def test_actual_tool_stops_on_transport_shape_and_mes_timeout(self):
        with tempfile.TemporaryDirectory() as tmp:
            binary=Path(tmp)/'mesboot-mock'
            subprocess.run(['cc','-std=gnu11','-Wall','-Wextra','-Werror','-I'+str(ROOT/'tests/mocks'),
                            str(ROOT/'tools/phxctl/mesboot.c'),'-o',str(binary)],check=True)
            clean={k:v for k,v in os.environ.items() if not k.startswith(('MESBOOT_','ADOPT'))}
            clean.update(MESBOOT_SCHED_PC='0xfffffffff0005000',MESBOOT_KIQ_PC='0xfffffffff0005000')
            cases=[('dump','MESBOOT_TEST_FAIL','0'),('dump','MESBOOT_TEST_SHORT','0'),
                   ('dump','MESBOOT_TEST_FAIL','31'),('dump','MESBOOT_TEST_SHORT','31'),
                   ('dump','MESBOOT_TEST_FAIL','2'),('dump','MESBOOT_TEST_SHORT','2'),
                   ('gart','MESBOOT_TEST_FAIL','109'),('claim','MESBOOT_TEST_FAIL','113'),
                   ('sched',None,None),('unknown',None,None)]
            for step,key,value in cases:
                with self.subTest(step=step,key=key,value=value):
                    env=dict(clean)
                    if key:env[key]=value
                    r=subprocess.run([str(binary),step],env=env,capture_output=True,text=True,timeout=10)
                    self.assertNotEqual(r.returncode,0,r.stdout+r.stderr)
                    if step=='unknown':self.assertNotIn('test-call:',r.stdout)
                    elif step=='sched':
                        self.assertIn('MES completion timeout',r.stderr)
                        self.assertNotIn('test-call:112',r.stdout)
                        self.assertNotIn('test-call:113',r.stdout)
                    else:
                        self.assertIn('transport/reply',r.stderr)
                        self.assertEqual(r.stdout.count('test-call:'+value+'\n'),1)
            for mode in ('hp','different','invalid','lost'):
                env=dict(clean,MESBOOT_TEST_MEMORY=mode)
                for step in ('gart','mes','claim','db'):
                    args=[str(binary),step]+(['0','0'] if step=='db' else [])
                    r=subprocess.run(args,env=env,capture_output=True,text=True,timeout=10)
                    self.assertNotEqual(r.returncode,0,r.stdout+r.stderr)
                    self.assertEqual(r.stdout.splitlines(),['test-call:0','test-call:31','test-call:33'] if mode=='different' else ['test-call:0','test-call:31'])
                r=subprocess.run([str(binary),'layout'],env=env,capture_output=True,text=True,timeout=10)
                self.assertEqual(r.returncode,1 if mode=='invalid' else 0,r.stdout+r.stderr)
                if mode=='hp':self.assertIn('physical=0x260000000 size=0x20000000',r.stdout)

if __name__=='__main__':unittest.main()
