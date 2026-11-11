"""Config transformations only; no signing-policy or GPU runtime is simulated."""
import copy
import importlib.util
from pathlib import Path
import unittest

SPEC=importlib.util.spec_from_file_location('configure_hp_amfi',Path(__file__).resolve().parents[1]/'install/configure_hp_amfi.py')
a=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(a)

class PolicyTests(unittest.TestCase):
    def config(self):
        return {'NVRAM':{'Add':{a.GUID:{'boot-args':'-v keepsyms=1 alcid=12 xhcinudge=1','csr-active-config':bytes.fromhex('7f0a0000')}},'Delete':{a.GUID:['boot-args','unrelated']}},
                'Misc':{'Security':{'SecureBootModel':'Disabled','Vault':'Optional'}},'Kernel':{'Patch':[{'Enabled':True,'Comment':'unrelated'}]}}

    def test_changes_only_boot_args_and_preserves_extra_sip_bits(self):
        c=self.config();original=copy.deepcopy(c);out=a.derive(c)
        self.assertEqual(c,original)
        self.assertEqual(out['NVRAM']['Add'][a.GUID]['boot-args'],c['NVRAM']['Add'][a.GUID]['boot-args']+' '+' '.join(a.FLAGS))
        out['NVRAM']['Add'][a.GUID]['boot-args']=c['NVRAM']['Add'][a.GUID]['boot-args'];self.assertEqual(out,c)

    def test_idempotent_and_preserves_quoted_existing_options(self):
        c=self.config();c['NVRAM']['Add'][a.GUID]['boot-args']+=' label="two words" amfi=0x80'
        out=a.derive(c);self.assertEqual(a.derive(out),out)
        self.assertIn('label="two words"',out['NVRAM']['Add'][a.GUID]['boot-args'])

    def test_conflicting_or_duplicate_options_require_review(self):
        for value in ('amfi=0','amfi=0x80 amfi=0x80','amfi_get_out_of_my_way=0','phxdebug=0'):
            c=self.config();c['NVRAM']['Add'][a.GUID]['boot-args']+=' '+value
            with self.subTest(value=value),self.assertRaises(ValueError):a.derive(c)

    def test_does_not_silently_change_other_security_requirements(self):
        for key in ('sip','secureboot','delete','vault'):
            c=self.config()
            if key=='sip':c['NVRAM']['Add'][a.GUID]['csr-active-config']=bytes(4)
            elif key=='secureboot':c['Misc']['Security']['SecureBootModel']='Default'
            elif key=='delete':c['NVRAM']['Delete'][a.GUID]=[]
            else:c['Misc']['Security']['Vault']='Secure'
            with self.subTest(key=key),self.assertRaises(ValueError):a.derive(c)

if __name__=='__main__':unittest.main()
