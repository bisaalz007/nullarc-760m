from pathlib import Path
import copy
import json
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import phx_device_profile as profile

class DeviceProfileTests(unittest.TestCase):
    def test_measured_header_and_excluded_runtime_state(self):
        capture=json.loads(profile.CAPTURE.read_text())
        self.assertEqual(profile.render(capture),profile.HEADER.read_text())
        changed=copy.deepcopy(capture)
        for key in ('ids_flags','virtual_address_max','high_va_max'):
            changed['device_info'][key]=0
        changed['memory_bytes']['vram_total']=1
        self.assertEqual(profile.render(changed),profile.render(capture))

    def test_identity_topology_and_invalid_scalar_refused(self):
        capture=json.loads(profile.CAPTURE.read_text())
        for section,key,value in [('pci','subdevice',0),('device_info','device_id',0),
                                  ('device_info','gpu_counter_freq',False),('device_info','max_engine_clock',0)]:
            changed=copy.deepcopy(capture);changed[section][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):profile.render(changed)
        changed=copy.deepcopy(capture);changed['profile']['cu_bitmap'][0][0]=0x33
        with self.assertRaises(ValueError):profile.render(changed)
        changed=copy.deepcopy(capture);changed['profile']['num_shader_engines']=True
        with self.assertRaises(ValueError):profile.render(changed)

if __name__=='__main__':unittest.main()
