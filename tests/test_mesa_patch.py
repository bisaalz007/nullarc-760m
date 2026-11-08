#!/usr/bin/env python3
"""Check patch 0007 and the generator produce identical files from the supplied Mesa baseline.

Usage: python3 tests/test_mesa_patch.py /path/to/mesa <ref-after-Phoenix-0006>
"""
from pathlib import Path
import subprocess
import sys
import tempfile

repo = Path(__file__).resolve().parents[1]
mesa = Path(sys.argv[1]).resolve()
base_ref = sys.argv[2]
patch = repo / 'mesa-patches-phoenix/0007-radv-darwin-captured-phoenix-topology.patch'
paths = [line.split('\t')[2] for line in subprocess.check_output(
    ['git', 'apply', '--numstat', str(patch)], text=True).splitlines()]
sys.path.insert(0, str(repo / 'tools'))
from mesa_phoenix_topology import apply
from mesa_phoenix_readiness import apply as apply_readiness
from mesa_phoenix_device_info import apply as apply_device_info


def materialize(root):
    for path in paths:
        r = subprocess.run(['git', '-C', str(mesa), 'show', f'{base_ref}:{path}'], capture_output=True)
        if r.returncode:
            assert path.endswith(('/phx_topology.h', '/phx_hp_760m.h')), r.stderr
            continue
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(r.stdout)


with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
    generated, patched = Path(a), Path(b)
    materialize(generated)
    materialize(patched)
    subprocess.run(['git', 'init', '-q', str(patched)], check=True)
    subprocess.run(['git', '-C', str(patched), 'apply', '--check', str(patch)], check=True)
    subprocess.run(['git', '-C', str(patched), 'apply', str(patch)], check=True)
    apply(generated)
    for path in paths:
        assert (generated / path).read_bytes() == (patched / path).read_bytes(), path
    readiness = repo / 'mesa-patches-phoenix/0008-radv-darwin-require-native-queue-readiness.patch'
    subprocess.run(['git', '-C', str(patched), 'apply', '--check', str(readiness)], check=True)
    subprocess.run(['git', '-C', str(patched), 'apply', str(readiness)], check=True)
    apply_readiness(generated)
    for path in paths:
        assert (generated / path).read_bytes() == (patched / path).read_bytes(), path
    measured = repo / 'mesa-patches-phoenix/0009-radv-darwin-measured-hp-device-properties.patch'
    subprocess.run(['git', '-C', str(patched), 'apply', '--check', str(measured)], check=True)
    subprocess.run(['git', '-C', str(patched), 'apply', str(measured)], check=True)
    apply_device_info(generated)
    paths.append('src/amd/common/darwin/phx_hp_760m_device.h')
    for path in paths:
        assert (generated / path).read_bytes() == (patched / path).read_bytes(), path
    before = {path: (generated / path).read_bytes() for path in paths}
    try:
        apply(generated)
        raise AssertionError('reapplying the generator must fail')
    except ValueError:
        pass
    assert before == {path: (generated / path).read_bytes() for path in paths}
    try:
        apply_device_info(generated)
        raise AssertionError('reapplying measured device properties must fail')
    except ValueError:
        pass
    assert before == {path: (generated / path).read_bytes() for path in paths}
print('[PASS] patches 0007/0008/0009 apply; generators match byte-for-byte; reapplication leaves files unchanged')
