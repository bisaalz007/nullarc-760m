import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]

def module(name,path):
    spec=importlib.util.spec_from_file_location(name,REPO/path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

mac=module('mac_capture','tools/collect_macos_evidence.py')
linux=module('linux_capture','tools/linux-profile/collect_evidence.py')


class EvidenceCollectorTests(unittest.TestCase):
    def test_exact_pci_and_selected_properties(self):
        pci={k:v.to_bytes(4,'little') for k,v in mac.EXPECTED.items()}
        pci.update({'IOObjectClass':'IOPCIDevice','IOPlatformSerialNumber':'not recorded',
          'IORegistryEntryChildren':[{'IOObjectClass':'IONDRVFramebuffer','PrivateData':'not recorded'}]})
        result=mac.capture([pci])
        self.assertEqual(result[0]['services'],['IOPCIDevice','IONDRVFramebuffer'])
        self.assertNotIn('not recorded',str(result))
        pci['device-id']=(0x731f).to_bytes(4,'little')
        self.assertEqual(mac.capture([pci]),[])

    def test_linux_sysfs_attributes_and_missing_data(self):
        with tempfile.TemporaryDirectory() as root:
            root=Path(root);dev=root/'device';dev.mkdir();out=root/'capture'
            (dev/'vendor').write_text('0x1002\n')
            ip=dev/'ip_discovery/die/0/GC/0';ip.mkdir(parents=True)
            (ip/'major').write_text('11\n');(ip/'base_addr').write_text('0x1260\n0xa000\n')
            # A symlink outside IP discovery must not be copied into the report.
            (ip/'outside').symlink_to(dev/'vendor')
            errors=[];linux.copy_sysfs(dev,out,errors)
            self.assertEqual((out/'ip_discovery/die/0/GC/0/major').read_text(),'11\n')
            self.assertFalse((out/'ip_discovery/die/0/GC/0/outside').exists())
            self.assertTrue(errors) # absent attributes are explicit, never fabricated


if __name__=='__main__':unittest.main()
