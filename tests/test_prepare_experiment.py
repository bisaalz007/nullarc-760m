#!/usr/bin/env python3
"""Validate the OS command boundary without loading a kernel extension."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

SPEC=importlib.util.spec_from_file_location('prepare_experiment',Path(__file__).resolve().parents[1]/'install/prepare_experiment.py')
MODULE=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

class PrepareExperimentTests(unittest.TestCase):
    def simulate(self,help_text='--load-style start-only, match-only, start-and-match',load_code=0):
        with tempfile.TemporaryDirectory() as tmp:
            output=Path(tmp)/'report'
            calls=[]
            def run(args,**kwargs):
                calls.append(args)
                if args[:3]==['/usr/bin/kmutil','load','--help']:
                    return subprocess.CompletedProcess(args,0,help_text,'')
                if args[:2]==['/usr/bin/kmutil','load']:
                    # Model the verified Sequoia CLI: unsupported options fail.
                    valid=args[2:]==['--bundle-path','/Library/Extensions/PhxAccel.kext','--load-style','start-only']
                    return subprocess.CompletedProcess(args,load_code if valid else 1,'',
                        'KMErrorDomain Code=28 requires reboot' if valid and load_code else '' if valid else 'Unknown option')
                return subprocess.CompletedProcess(args,0,'','')
            argv=['prepare_experiment.py','--package',tmp,'--oc',tmp,'--output',str(output),'--execute']
            with patch.object(MODULE.sys,'argv',argv),patch.object(MODULE.os,'geteuid',return_value=0),patch.dict(MODULE.os.environ,{},clear=True),patch.object(MODULE.subprocess,'run',side_effect=run),contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
                status=MODULE.main()
            return status,json.loads((output/'result.json').read_text()),calls

    def test_supported_style_and_capabilities_before_copy(self):
        status,report,calls=self.simulate()
        self.assertEqual(status,0)
        self.assertTrue(report['files_staged'])
        self.assertLess(next(i for i,c in enumerate(calls) if '--help' in c),next(i for i,c in enumerate(calls) if c[1:]==['--components']))
        self.assertFalse(report['gpu_initialization_attempted'])
        self.assertFalse(report['accelerator_loaded_verified'])

    def test_unsupported_cli_stops_before_copy(self):
        status,report,calls=self.simulate('older CLI without load style')
        self.assertEqual(status,1)
        self.assertFalse(any(c[1:]==['--components'] for c in calls))
        self.assertNotIn('files_staged',report)

    def test_reboot_request_is_not_loaded_verification(self):
        status,report,_=self.simulate(load_code=1)
        self.assertEqual(status,0)
        self.assertTrue(report['macos_approval_or_reboot_required'])
        self.assertFalse(report['accelerator_loaded_verified'])

if __name__=='__main__':unittest.main()
