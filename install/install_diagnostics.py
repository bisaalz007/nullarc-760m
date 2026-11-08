#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Check/install a diagnostic-only PhxBringup in an explicitly selected OpenCore.

Default is --check. Does not mount disks, change boot arguments/security, install
an accelerator, start a daemon, reboot, or enable hardware writes. Changes take
effect only at the user's next boot. Keep the printed backup path for removal.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import plistlib
import shutil
import struct
import sys
import tempfile

# Works in the repository and at the root of an assembled package.
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'tools'))
from package_manifest import verify, inventory, digest


def atomic_write(path, data):
    fd, name = tempfile.mkstemp(prefix='.' + path.name + '-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(data); f.flush(); os.fsync(f.fileno())
        if path.exists(): os.chmod(name, path.stat().st_mode & 0o777)
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def configuration(oc):
    path = oc / 'config.plist'
    if path.is_symlink(): raise ValueError('config.plist must not be a symlink')
    raw = path.read_bytes()
    config = plistlib.loads(raw)
    entries = config.get('Kernel', {}).get('Add')
    if not isinstance(entries, list) or not all(isinstance(e, dict) for e in entries):
        raise ValueError('expected Kernel/Add array of dictionaries')
    return raw, config, entries


def validate_kext(source):
    info = plistlib.loads((source / 'Contents/Info.plist').read_bytes())
    if info.get('CFBundleExecutable') != 'PhxBringup' or info.get('CFBundleIdentifier') != 'org.drip.PhxBringup':
        raise ValueError('unexpected diagnostic kext identity')
    binary = source / 'Contents/MacOS/PhxBringup'
    with binary.open('rb') as f: header = f.read(32)
    if len(header) != 32: raise ValueError('truncated kext Mach-O header')
    magic, cpu, subtype, kind, commands, command_bytes, flags, reserved = struct.unpack('<8I', header)
    if magic != 0xfeedfacf or cpu != 0x01000007 or kind != 11 or not commands:
        raise ValueError('expected a native x86_64 Mach-O kext bundle')
    if binary.stat().st_size < 32 + command_bytes:
        raise ValueError('truncated kext load commands')
    return binary


def install(package, oc, check=True):
    document = verify(package)
    if not oc.is_dir() or oc.is_symlink(): raise ValueError('provide the actual EFI/OC directory')
    raw, config, entries = configuration(oc)
    source = package / 'EFI/OC/Kexts/PhxBringup.kext'
    validate_kext(source)
    target = oc / 'Kexts/PhxBringup.kext'
    if (oc / 'Kexts').is_symlink() or target.is_symlink(): raise ValueError('symlinked kext paths are not supported')
    matching = [e for e in entries if e.get('BundlePath') == 'PhxBringup.kext']
    if len(matching) > 1: raise ValueError('duplicate PhxBringup OpenCore entries')
    entry = matching[0] if matching else {}
    if not matching: entries.append(entry)
    entry.update(BundlePath='PhxBringup.kext', ExecutablePath='Contents/MacOS/PhxBringup',
                 PlistPath='Contents/Info.plist', Enabled=True, MinKernel='24.0.0', MaxKernel='')
    updated = plistlib.dumps(config, sort_keys=False)
    if check: return {'mode':'check', 'policy':document['policy'], 'changes_written':False}
    (oc / 'Kexts').mkdir(exist_ok=True)
    backup = Path(tempfile.mkdtemp(prefix='.nullarc-diagnostic-backup-', dir=oc))
    (backup / 'config.plist').write_bytes(raw)
    had_kext = target.exists()
    if had_kext: shutil.copytree(target, backup / 'PhxBringup.kext', symlinks=False)
    staged = backup / 'new.kext'
    shutil.copytree(source, staged)
    swapped = False
    try:
        if had_kext: target.rename(backup / 'original.kext')
        staged.rename(target); swapped = True
        atomic_write(oc / 'config.plist', updated)
        receipt = {'format':1, 'oc':str(oc), 'original_config_sha256':hashlib.sha256(raw).hexdigest(),
                   'installed_config_sha256':digest(oc / 'config.plist'), 'had_kext':had_kext,
                   'original_kext':inventory(backup / 'PhxBringup.kext') if had_kext else {},
                   'installed_kext':inventory(target), 'package_manifest_sha256':digest(package / 'package-manifest.json')}
        atomic_write(backup / 'receipt.json', (json.dumps(receipt, indent=2)+'\n').encode())
    except BaseException:
        if swapped and target.exists(): shutil.rmtree(target)
        if (backup / 'original.kext').exists(): (backup / 'original.kext').rename(target)
        if (oc / 'config.plist').read_bytes() != raw: atomic_write(oc / 'config.plist', raw)
        raise
    if (backup / 'original.kext').exists(): shutil.rmtree(backup / 'original.kext')
    return {'mode':'installed', 'policy':'hp-diagnostic-only', 'backup':str(backup), 'reboot_performed':False}


def remove(oc, backup, check=True):
    receipt = json.loads((backup / 'receipt.json').read_text())
    target = oc / 'Kexts/PhxBringup.kext'
    if receipt.get('format') != 1 or receipt['oc'] != str(oc): raise ValueError('backup belongs to another OpenCore')
    if digest(oc / 'config.plist') != receipt['installed_config_sha256'] or inventory(target) != receipt['installed_kext']:
        raise ValueError('OpenCore or kext changed since installation; refusing to overwrite subsequent edits')
    original = backup / 'config.plist'
    if digest(original) != receipt['original_config_sha256']: raise ValueError('backup configuration differs')
    if receipt['had_kext'] and inventory(backup / 'PhxBringup.kext') != receipt['original_kext']:
        raise ValueError('backup kext differs')
    if check: return {'mode':'removal-check', 'changes_written':False}
    # Retain installed state until both restoration steps succeed.
    with tempfile.TemporaryDirectory(prefix='.nullarc-remove-', dir=oc) as tmp:
        tmp = Path(tmp)
        target.rename(tmp / 'installed.kext')
        try:
            if receipt['had_kext']: shutil.copytree(backup / 'PhxBringup.kext', target)
            atomic_write(oc / 'config.plist', original.read_bytes())
        except BaseException:
            if target.exists(): shutil.rmtree(target)
            (tmp / 'installed.kext').rename(target)
            raise
    return {'mode':'removed', 'backup_retained':str(backup), 'reboot_performed':False}


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--package', type=Path, default=HERE)
    ap.add_argument('--oc', type=Path, required=True)
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument('--check', action='store_true')
    mode.add_argument('--install', action='store_true')
    mode.add_argument('--remove', type=Path, metavar='BACKUP')
    a = ap.parse_args()
    try:
        result = remove(a.oc.resolve(), a.remove.resolve(), check=False) if a.remove else install(a.package.resolve(), a.oc.resolve(), check=not a.install)
        print(json.dumps(result, indent=2))
    except (ValueError, OSError, KeyError) as e:
        ap.exit(1, f'{e}\n')
