"""Synthetic decoder/command-boundary tests; not HP timing evidence."""
import importlib.util
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('display_capture',ROOT/'tools/phxctl/hp_display_capture.py')
d=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(d)
PROFILE=json.loads((ROOT/'hardware/profiles/hp-760m-display-registers.json').read_text())

class TimingTests(unittest.TestCase):
    def samples(self):
        first={r['name']:0 for r in PROFILE['registers']}
        def set_value(suffix,value):first['regOTG0_OTG_'+suffix]=value
        set_value('CONTROL',1)
        set_value('H_TOTAL',19);set_value('H_BLANK_START_END',18|(8<<16));set_value('H_SYNC_A',3<<16)
        set_value('V_TOTAL',11);set_value('V_BLANK_START_END',11|(5<<16));set_value('V_SYNC_A',2<<16)
        second=dict(first);second['regOTG0_OTG_STATUS_FRAME_COUNT']=60
        return first,second

    def test_coordinates_follow_linux_inverse_not_cvt_defaults(self):
        first,second=self.samples();t=d.decode_timing(PROFILE,first,second,10**9)
        self.assertEqual(t['h']['active'],10);self.assertEqual(t['h']['sync_start'],12);self.assertEqual(t['h']['sync_end'],15)
        self.assertEqual(t['v']['active'],6);self.assertEqual(t['v']['front_porch'],1)
        self.assertEqual(t['estimated_refresh_millihz'],60000)
        self.assertFalse(t['pixel_clock_measured_directly'])

    def test_dynamic_timing_or_interlace_is_not_silently_accepted(self):
        first,second=self.samples();second['regOTG0_OTG_H_TOTAL']+=1
        with self.assertRaises(ValueError):d.decode_timing(PROFILE,first,second,10**9)
        first,second=self.samples()
        for s in (first,second):s['regOTG0_OTG_INTERLACE_CONTROL']=1
        with self.assertRaisesRegex(ValueError,'interlaced'):d.decode_timing(PROFILE,first,second,10**9)

    def test_counter_wrap_and_zero_progress(self):
        first,second=self.samples();first['regOTG0_OTG_STATUS_FRAME_COUNT']=0xfffff0;second['regOTG0_OTG_STATUS_FRAME_COUNT']=44
        self.assertEqual(d.decode_timing(PROFILE,first,second,10**9)['frame_count_delta'],60)
        second['regOTG0_OTG_STATUS_FRAME_COUNT']=first['regOTG0_OTG_STATUS_FRAME_COUNT']
        with self.assertRaises(ValueError):d.decode_timing(PROFILE,first,second,10**9)

    def test_collector_only_invokes_existing_read_register_command(self):
        output=''.join('0x%05x: 0x%08x\n'%(r['dword'],0) for r in PROFILE['registers'])
        with patch.object(d.subprocess,'check_output',return_value=output) as read:
            result=d.read_registers(Path('/fixture/phxctl'),PROFILE)
        self.assertEqual(read.call_args.args[0][:2],['/fixture/phxctl','regs'])
        self.assertEqual(len(result['registers']),14)

    def test_short_or_error_response_is_refused(self):
        with patch.object(d.subprocess,'check_output',return_value='0x05000: (error) 0x00000000\n'),self.assertRaises(ValueError):
            d.read_registers(Path('/fixture/phxctl'),PROFILE)

if __name__=='__main__':unittest.main()
