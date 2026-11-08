from pathlib import Path
import struct
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from macos_target import inspect,verify_tree

def image(major,kind=6,cpu=0x01000007):
    command=struct.pack('<6I',0x32,24,1,major<<16,26<<16,0)
    return struct.pack('<8I',0xfeedfacf,cpu,3,kind,1,len(command),0,0)+command

class DeploymentTargetTests(unittest.TestCase):
    def test_copied_dependency_above_target_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'plugin').write_bytes(image(15));(p/'LLVM.dylib').write_bytes(image(14))
            self.assertEqual(len(verify_tree(p,'15.0')),2)
            (p/'libelf.dylib').write_bytes(image(26))
            with self.assertRaisesRegex(ValueError,'requires macOS'):verify_tree(p,'15.0')
            self.assertEqual(len(verify_tree(p,'26.0')),3)

    def test_malformed_architecture_and_platform_refused(self):
        for b in (image(15)[:40],image(15,cpu=0x0100000c),image(15)[:32]+struct.pack('<II',0x32,4),
                  image(15)[:40]+struct.pack('<I',2)+image(15)[44:]):
            with self.assertRaises(ValueError):inspect(b)
        self.assertIsNone(inspect(b'not a native binary'))

    def test_universal_x86_slice_and_kext_without_deployment_command(self):
        thin=image(15);fat=struct.pack('>7I',0xcafebabe,1,0x01000007,3,28,len(thin),0)+thin
        self.assertEqual(inspect(fat)['minimum_macos'],(15,0,0))
        kext=struct.pack('<8I',0xfeedfacf,0x01000007,3,11,0,0,0,0)
        self.assertIsNone(inspect(kext)['minimum_macos'])

if __name__=='__main__':unittest.main()
