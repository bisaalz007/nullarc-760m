"""Auxiliary collection identity and publication tests; no kernel operations."""
from pathlib import Path
import sys
import json
import os
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'install'))
import update_hp_aux as u

OLD='535B5212-AD0C-34E1-9F0F-489176793105'
NEW='633BB085-1049-336E-B87E-C1626D9B5417'
TEXT='Extension Information:\ncom.luuumi.PhxAccel\t0.1\t/Library/Extensions/PhxAccel.kext\t('+OLD+')\ncom.apple.driver.AppleMobileDevice\t4.0\t/Library/Apple/System/Library/Extensions/AppleMobileDevice.kext\t\n'
class AuxTests(unittest.TestCase):
    def test_parser_preserves_uuidless_extension(self):
        e=u.extensions(TEXT);self.assertIsNone(e['com.apple.driver.AppleMobileDevice']['uuid']);self.assertEqual(e[u.IDENTIFIER]['uuid'],OLD)
    def test_parser_refuses_duplicate_unexpected_path_or_partial_output(self):
        for bad in (TEXT+TEXT,TEXT.replace('/Library/Extensions/','/tmp/'),TEXT+'unexpected log output\n'):
            with self.assertRaises(ValueError):u.extensions(bad)
    def test_candidate_only_changes_accelerator_uuid(self):
        before=u.extensions(TEXT);after=u.extensions(TEXT.replace(OLD,NEW));u.validate_candidate(before,after,NEW)
        after.pop('com.apple.driver.AppleMobileDevice')
        with self.assertRaises(ValueError):u.validate_candidate(before,after,NEW)
    def test_candidate_wrong_version_path_or_uuid_refused(self):
        for bad in (TEXT,TEXT.replace(OLD,NEW).replace('\t0.1\t','\t0.2\t'),TEXT.replace(OLD,NEW).replace('AppleMobileDevice.kext','Different.kext')):
            with self.assertRaises(ValueError):u.validate_candidate(u.extensions(TEXT),u.extensions(bad),NEW)
    def test_failure_must_precede_hardware_execution(self):
        status={'boot_session_uuid':'boot','last_stage':'loaded-kernel-uuid','bootstrap_error':'new accelerator UUID must be loaded before --claim',
                'native_compute_verified':False,'native_render_verified':False}
        evidence={'source_package':'/package','executed':False,'error':'new accelerator UUID must be loaded before --claim',
                  'stages':[{'stage':'preflight','returncode':0},{'stage':'loaded-kernel-uuid','returncode':0}]}
        u.validate_failure(status,evidence,Path('/package'),'boot')
        for key,value in [('executed',True),('source_package','/other')]:
            bad=dict(evidence);bad[key]=value
            with self.assertRaises(ValueError):u.validate_failure(status,bad,Path('/package'),'boot')
        with self.assertRaises(ValueError):u.validate_failure(status,evidence,Path('/package'),'another-boot')
    def test_publish_backs_up_exact_previous_collection(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(u.os,'chown'):
            root=Path(tmp);old=root/'old.kc';new=root/'new.kc';backup=root/'backup';backup.mkdir()
            old.write_bytes(b'old');new.write_bytes(b'new');u.publish(new,old,backup,u.digest(old))
            self.assertEqual(old.read_bytes(),b'new');self.assertEqual((backup/'AuxiliaryKernelExtensions.kc').read_bytes(),b'old')
    def failure_report(self,state,name,executed=False):
        folder=state/name;(folder/'execution').mkdir(parents=True)
        status={'boot_session_uuid':name,'last_stage':'loaded-kernel-uuid','bootstrap_error':'new accelerator UUID must be loaded before --claim',
                'native_compute_verified':False,'native_render_verified':False}
        evidence={'source_package':'/package','executed':executed,'error':status['bootstrap_error'],
                  'stages':[{'stage':'loaded-kernel-uuid','returncode':0}]}
        path=folder/'boot-result.json';path.write_text(json.dumps(status));(folder/'execution/result.json').write_text(json.dumps(evidence))
        return path
    def test_last_protected_failure_can_survive_disabled_boots(self):
        with tempfile.TemporaryDirectory() as tmp:
            state=Path(tmp);path=self.failure_report(state,'boot-previous')
            selected,status=u.last_failure(state,Path('/package'))
            self.assertEqual(selected,path);self.assertEqual(status['boot_session_uuid'],'boot-previous')
    def test_never_skip_a_newer_unsafe_attempt(self):
        with tempfile.TemporaryDirectory() as tmp:
            state=Path(tmp);old=self.failure_report(state,'boot-old');new=self.failure_report(state,'boot-new',True)
            os.utime(old,ns=(1,1));os.utime(new,ns=(2,2))
            with self.assertRaises(ValueError):u.last_failure(state,Path('/package'))
    def test_no_protected_history_cannot_clear_markers(self):
        with tempfile.TemporaryDirectory() as tmp,self.assertRaises(ValueError):u.last_failure(Path(tmp),Path('/package'))
    def test_concurrent_collection_edit_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);old=root/'old.kc';new=root/'new.kc';old.write_bytes(b'edited');new.write_bytes(b'new')
            with self.assertRaises(ValueError):u.publish(new,old,root,u.hashlib.sha256(b'old').hexdigest())
            self.assertEqual(old.read_bytes(),b'edited')

if __name__=='__main__':unittest.main()
