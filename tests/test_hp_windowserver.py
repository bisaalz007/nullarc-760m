"""Failure/order checks only; synthetic IORegistry data is not display evidence."""
import importlib.util
import json
from pathlib import Path
import plistlib
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/phxctl'))
import hp_windowserver as d

class DisplayTests(unittest.TestCase):
    def test_empty_ioreg_is_not_misparsed_as_plist(self):
        with patch.object(d.subprocess,'check_output',return_value=b''):self.assertEqual(d.nodes('PhxAMDFB'),[])

    def test_no_request_never_arms(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(d,'nodes',return_value=[]),patch.object(d,'sysctl') as write:
            self.assertFalse(d.begin(Path(tmp),Path(tmp),Path(tmp)))
            write.assert_not_called()

    def test_unrequested_framebuffer_requires_fallback(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(d,'nodes',return_value=[{}]),self.assertRaises(d.DisplayOwnershipError):
            d.begin(Path(tmp),Path(tmp),Path(tmp))

    def test_runtime_plan_requires_exact_version_geometry_and_family(self):
        plan=struct.pack('<14I6Q',1,3,1920,1200,7680,60000,2260,1968,2000,1240,1203,1209,1,0,
                         0x2b0000000,0x260000000,0x8000000000,0,9216000,168144000)
        a={'IOObjectClass':'NMXAccel','PhxHPDisplayABICompatible':True,'PhxHPDisplayPlanValid':True,'PhxHPDisplayPlan':plan}
        loaded='\n'.join(k+' ('+v+')' for k,v in [('com.apple.iokit.IOGraphicsFamily','599'),('com.apple.iokit.IOAcceleratorFamily2','485.2'),('com.apple.AppleGraphicsDeviceControl','8.1.10')])
        with patch.object(d,'nodes',return_value=[]),patch.object(d,'claimed_hp',return_value={'IORegistryEntryChildren':[a]}),patch.object(d.subprocess,'check_output',return_value=loaded):
            self.assertIs(d.validated_accelerator(),a)
            a['PhxHPDisplayABICompatible']=False
            with self.assertRaisesRegex(ValueError,'ABI'):d.validated_accelerator()
            a['PhxHPDisplayABICompatible']=True;a['PhxHPDisplayPlan']=plan[:-1]
            with self.assertRaisesRegex(ValueError,'plan data'):d.validated_accelerator()
            a['PhxHPDisplayPlan']=plan
            with patch.object(d.subprocess,'check_output',return_value=loaded.replace('485.2','486')):
                with self.assertRaisesRegex(ValueError,'family'):d.validated_accelerator()

    def test_arm_order_releases_only_after_positive_checks(self):
        events=[];values={'debug.nvaccelfb':1,'debug.nvaccel_heads_piped':1,'debug.nvaccel_iop':1,'debug.phxagdc':1,'debug.phxfb_hold':0}
        def control(name,value=None):
            events.append((name,value));return values.get(name,0) if value is None else ''
        with patch.object(d,'validated_accelerator'),patch.object(d,'unopened_held_framebuffer'),patch.object(d,'sysctl',side_effect=control),patch.object(d.time,'sleep'):
            report={};d.arm(report,lambda:None,Path('fixture'),lambda *args:events.append(('allow',None)))
        self.assertTrue(report['desktop_armed'])
        self.assertLess(events.index(('debug.phxagdc',1)),events.index(('allow',None)))
        self.assertLess(events.index(('allow',None)),events.index(('debug.phxfb_hold',0)))

    def test_failed_pipe_registration_does_not_allow_or_release(self):
        events=[]
        def control(name,value=None):events.append((name,value));return 0
        with patch.object(d,'validated_accelerator'),patch.object(d,'unopened_held_framebuffer'),patch.object(d,'sysctl',side_effect=control),patch.object(d.time,'sleep'),self.assertRaises(ValueError):
            d.arm({},lambda:None,Path('fixture'),lambda *args:self.fail('must not allow WindowServer'))
        self.assertNotIn(('debug.phxfb_hold',0),events)

    def test_hold_and_existing_framebuffer_client_are_hard_failures(self):
        with patch.object(d,'framebuffer',return_value={'IORegistryEntryChildren':[{'IOObjectClass':'IOFramebufferUserClient'}]}),patch.object(d,'sysctl') as control,self.assertRaisesRegex(ValueError,'before arming'):
            d.unopened_held_framebuffer()
        control.assert_not_called()
        with patch.object(d,'framebuffer',return_value={}),patch.object(d,'sysctl',return_value=0),self.assertRaisesRegex(ValueError,'expired'):
            d.unopened_held_framebuffer()

    def test_present_counter_alone_is_not_success(self):
        with patch.object(d,'sysctl',return_value=10),patch.object(d,'framebuffer',return_value={}),patch.object(d.time,'monotonic',side_effect=[0,121]),self.assertRaisesRegex(ValueError,'no verified'):
            d.verify_present({},lambda:None)

    def test_failed_display_boot_reboots_only_if_custom_framebuffer_owns_panel(self):
        for nodes,expected in (([],0),([{}],1)):
            with patch.object(d,'nodes',return_value=nodes),patch.object(d.subprocess,'run') as run:
                d.fallback({},lambda:None);self.assertEqual(run.call_count,expected)
                if expected:self.assertEqual(run.call_args.args[0],['/sbin/shutdown','-r','now'])

if __name__=='__main__':unittest.main()
