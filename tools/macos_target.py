#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Validate actual x86_64 Mach-O deployment commands, including copied dependencies."""
from pathlib import Path
import struct

def version(text):
    values=text.split('.')
    if not 2<=len(values)<=3 or any(not p.isdecimal() for p in values):
        raise ValueError('expected a numeric macOS major.minor[.patch]')
    parts=tuple(int(p) for p in values)
    return parts+(0,)*(3-len(parts))

def inspect(data):
    if len(data)<4 or data[:4] not in (b'\xcf\xfa\xed\xfe',b'\xca\xfe\xba\xbe',b'\xbe\xba\xfe\xca'):
        return None
    if data[:4]!=b'\xcf\xfa\xed\xfe':
        endian='>' if data[:4]==b'\xca\xfe\xba\xbe' else '<'
        if len(data)<8:raise ValueError('truncated universal Mach-O')
        count=struct.unpack_from(endian+'I',data,4)[0]
        if count>32 or len(data)<8+20*count:raise ValueError('invalid universal architecture table')
        for i in range(count):
            cpu,sub,off,size,align=struct.unpack_from(endian+'5I',data,8+20*i)
            if cpu==0x01000007:
                if off>len(data) or size>len(data)-off:raise ValueError('truncated x86_64 slice')
                return inspect(data[off:off+size])
        raise ValueError('no x86_64 Mach-O slice')
    if len(data)<32:raise ValueError('truncated Mach-O header')
    magic,cpu,sub,kind,ncmds,nbytes,flags,reserved=struct.unpack_from('<8I',data)
    if cpu!=0x01000007:raise ValueError('expected x86_64 Mach-O')
    if nbytes>len(data)-32 or ncmds>nbytes//8:raise ValueError('truncated Mach-O commands')
    offset=32;minimum=None
    for _ in range(ncmds):
        if offset+8>32+nbytes:raise ValueError('truncated load command')
        cmd,size=struct.unpack_from('<II',data,offset)
        if size<8 or size>32+nbytes-offset:raise ValueError('invalid load command size')
        if cmd in (0x24,0x32):
            if size<(24 if cmd==0x32 else 16):raise ValueError('short deployment command')
            if minimum is not None:raise ValueError('ambiguous deployment commands')
            if cmd==0x32:
                platform,encoded=struct.unpack_from('<II',data,offset+8)
                if platform!=1:raise ValueError('expected macOS platform')
            else:encoded=struct.unpack_from('<I',data,offset+8)[0]
            minimum=(encoded>>16,(encoded>>8)&255,encoded&255)
        offset+=size
    if kind!=11 and minimum is None:raise ValueError('missing macOS deployment command')
    return {'kind':kind,'minimum_macos':minimum}

def verify_tree(root,minimum):
    target=version(minimum);found={}
    for p in sorted(Path(root).rglob('*')):
        if not p.is_file():continue
        with p.open('rb') as f:magic=f.read(4)
        if magic not in (b'\xcf\xfa\xed\xfe',b'\xca\xfe\xba\xbe',b'\xbe\xba\xfe\xca'):continue
        info=inspect(p.read_bytes());v=info['minimum_macos']
        if v is not None and v>target:raise ValueError(f'{p}: requires macOS {v}, package target is {minimum}')
        found[str(p.relative_to(root))]=info
    if not found:raise ValueError('package contains no native binaries')
    return found
