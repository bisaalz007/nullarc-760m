from pathlib import Path
import json
import sys
import tempfile
import unittest
from unittest.mock import patch
REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO/'tools'))
import build_stack
from package_manifest import digest

class BuildReceiptTests(unittest.TestCase):
    def test_wrong_input_stale_source_and_changed_artifact_rejected(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(build_stack,'REPO',Path(tmp)):
            root=Path(tmp);mesa=root/'mesa';source=root/'src/component.cpp'
            source.parent.mkdir(parents=True);source.write_text('source fixture')
            tool=root/'tools/phxctl/phxfw.cpp';tool.parent.mkdir(parents=True);tool.write_text('tool fixture')
            metal=root/'tools/mtlprobe/mtlprobe.m';metal.parent.mkdir(parents=True);metal.write_text('Metal fixture')
            for path in build_stack.required_artifacts(mesa):
                path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'compiled-artifact fixture')
            receipt={'source_inputs':build_stack.source_inputs(),'minimum_macos':'26.0',
                'artifacts':{str(p):digest(p) for p in build_stack.required_artifacts(mesa)}}
            (root/'build/stack-build.json').write_text(json.dumps(receipt))
            build_stack.verify_build_receipt(mesa)
            with self.assertRaisesRegex(ValueError,'deployment target'):
                build_stack.verify_build_receipt(mesa,'15.0')
            with self.assertRaisesRegex(ValueError,'selected build inputs'):
                build_stack.verify_build_receipt(mesa,mesa_build=root/'another-build')
            with self.assertRaisesRegex(ValueError,'selected build inputs'):
                build_stack.verify_build_receipt(root/'another-mesa')
            source.write_text('modified source')
            with self.assertRaisesRegex(ValueError,'stale'):
                build_stack.verify_build_receipt(mesa)
            source.write_text('source fixture')
            tool.write_text('changed tool source')
            with self.assertRaisesRegex(ValueError,'stale'):
                build_stack.verify_build_receipt(mesa)
            tool.write_text('tool fixture')
            metal.write_text('changed Metal probe')
            with self.assertRaisesRegex(ValueError,'stale'):
                build_stack.verify_build_receipt(mesa)
            metal.write_text('Metal fixture')
            (root/'build/translator/nvmtl-translator-source.tar.gz').write_bytes(b'wrong corresponding source')
            with self.assertRaisesRegex(ValueError,'artifact differs'):
                build_stack.verify_build_receipt(mesa)

if __name__=='__main__':unittest.main()
