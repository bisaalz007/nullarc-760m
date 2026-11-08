#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Apply measured HP device properties after Phoenix Mesa patches 0001..0008."""
import argparse
from pathlib import Path
from phx_device_profile import CAPTURE, HEADER, render
import json

def apply(root):
    if HEADER.read_text()!=render(json.loads(CAPTURE.read_text())):
        raise ValueError('stale measured device properties')
    base=root/'src/amd/common/darwin'
    path=base/'ac_darwin_drm.c'; text=path.read_text()
    old='#include "phx_hp_760m.h"'
    anchor='''         memcpy(di->cu_bitmap, p->cu_bitmap, sizeof(di->cu_bitmap));
      }
      return 0;
   }
   case AMDGPU_INFO_MEMORY:'''
    if text.count(old)!=1 or text.count(anchor)!=1 or 'native queues are not ready' not in text:
        raise ValueError('expected Mesa patch 0008 baseline, or patch 0009 already applied')
    text=text.replace(old,old+'\n#include "phx_hp_760m_device.h"').replace(anchor,'''         memcpy(di->cu_bitmap, p->cu_bitmap, sizeof(di->cu_bitmap));
         if (phx_topology_matches(p, phx_hp_760m.vendor, phx_hp_760m.device, phx_hp_760m.revision,
                                  phx_hp_760m.subvendor, phx_hp_760m.subdevice))
            phx_hp_760m_apply_device_info(di);
      }
      return 0;
   }
   case AMDGPU_INFO_MEMORY:''')
    if (base/HEADER.name).exists(): raise ValueError('measured header already exists')
    path.write_text(text); (base/HEADER.name).write_bytes(HEADER.read_bytes())

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('mesa',type=Path);a=ap.parse_args()
    try:apply(a.mesa)
    except (ValueError,OSError) as e:ap.exit(1,f'Mesa device properties: {e}\n')
