#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Capture selected HP PCI/display facts without loading drivers or reading/writing registers.

Run on the HP: python3 collect_macos_evidence.py --output <new-directory>
No root access is needed. This cannot supply PSP/SMU/GC IP discovery or prove acceleration.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import plistlib
import subprocess

EXPECTED = {'vendor-id':0x1002, 'device-id':0x1900, 'revision-id':0xca,
            'subsystem-vendor-id':0x103c, 'subsystem-id':0x8c6a}
FIELDS = tuple(EXPECTED) + ('class-code', 'model', 'assigned-addresses', 'reg', 'IODeviceMemory',
    'phx-build', 'phx-stage', 'phx-profile', 'phx-failure', 'phx-bringup-blocker')


def safe(value):
    if isinstance(value, bytes): return {'hex':value.hex(), 'bytes':len(value)}
    if isinstance(value, dict): return {str(k):safe(v) for k,v in value.items()}
    if isinstance(value, list): return [safe(v) for v in value]
    return value


def walk(nodes):
    for node in nodes:
        yield node
        yield from walk(node.get('IORegistryEntryChildren', []))


def pci_number(value):
    return int.from_bytes(value, 'little') if isinstance(value, bytes) else value


def capture(nodes):
    matching = [n for n in walk(nodes) if all(pci_number(n.get(k)) == v for k,v in EXPECTED.items())]
    devices = []
    for n in matching:
        d = {'properties':safe({k:n[k] for k in FIELDS if k in n}), 'services':[], 'edid':[]}
        for child in walk([n]):
            cls = child.get('IOObjectClass')
            if cls and cls not in d['services']: d['services'].append(cls)
            if 'phx-stage' in child:
                d['bringup'] = safe({k:child[k] for k in FIELDS if k in child})
            edid = child.get('IODisplayEDID')
            if isinstance(edid,bytes):
                d['edid'].append({'length':len(edid),'sha256':hashlib.sha256(edid).hexdigest(),
                    'checksums_valid':bool(edid) and len(edid)%128==0 and all(sum(edid[i:i+128])%256==0 for i in range(0,len(edid),128))})
        devices.append(d)
    return devices


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output', type=Path, required=True)
    a = ap.parse_args()
    a.output.mkdir(parents=True, exist_ok=False)
    p = subprocess.run(['ioreg','-a','-r','-c','IOPCIDevice'], capture_output=True)
    devices = capture(plistlib.loads(p.stdout)) if p.returncode == 0 else []
    report = {'format':1,'captured_at':datetime.now(timezone.utc).isoformat(),
              'os':subprocess.check_output(['sw_vers'],text=True).strip(),
              'target_found':bool(devices),'devices':devices,'register_access':False,
              'driver_loaded_by_collector':False,
              'remaining':['IP discovery','firmware versions/hashes and load layout','memory-controller/GOP reservations','verified GPU command execution']}
    (a.output/'macos-evidence.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'output':str(a.output),'target_found':bool(devices),'read_only':True}))
    raise SystemExit(0 if devices else 1)
