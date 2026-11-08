#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Apply Phoenix 0008 after 0007: native RADV requires ready queues."""
import argparse
from pathlib import Path

OLD = '   /* GB_ADDR_CONFIG: the tiling layout'
INSERT = '''   /* A real kernel must have adopted graphics and compute queues before
    * RADV advertises their canned capabilities. Mocks remain explicit. */
   if (!env_is_1("RADV_DARWIN_MOCK") &&
       (info.flags & (N48N_INFO_S1B_POSITIVE | N48N_INFO_NATIVE_BOOT)) !=
       (N48N_INFO_S1B_POSITIVE | N48N_INFO_NATIVE_BOOT)) {
      fprintf(stderr, "radv-darwin: native queues are not ready (flags 0x%x)\\n", info.flags);
      return -ENODEV;
   }

'''


def apply(root):
    path = root / 'src/amd/common/darwin/ac_darwin_drm.c'
    text = path.read_text()
    if text.count(OLD) != 1 or 'native queues are not ready' in text or 'acd_kext_query_topology(kext, topology)' not in text:
        raise ValueError('expected Mesa after Phoenix patch 0007, without 0008')
    path.write_text(text.replace(OLD, INSERT + OLD))


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('mesa', type=Path)
    a = ap.parse_args()
    apply(a.mesa)
