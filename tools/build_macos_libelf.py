#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build the pinned libelf dependency and SDK-zlib pkg-config metadata without root."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

SHA256='591a9b4ec81c1f2042a97aa60564e0cb79d041c52faa7416acb38bc95bd2c76d'

def run(args,**kw):subprocess.run([str(x) for x in args],check=True,**kw)

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--archive',type=Path,required=True)
    ap.add_argument('--elf-patch',type=Path,required=True,help='MacPorts elf_repl.diff from native dependency notices')
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--min-macos',choices=('15.0','26.0'),default='15.0')
    a=ap.parse_args()
    if hashlib.sha256(a.archive.read_bytes()).hexdigest()!=SHA256:ap.error('libelf source checksum differs')
    out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    source=out/'source';source.mkdir();prefix=out/'prefix'
    run(['tar','-xzf',a.archive.resolve(),'-C',source])
    src=source/'libelf-0.8.13'
    with a.elf_patch.open('rb') as patch:run(['patch','-p0'],cwd=src,stdin=patch)
    env=os.environ.copy()
    env.update(CC='clang -arch x86_64 -mmacosx-version-min='+a.min_macos,
               CFLAGS='-O2 -Wno-error=implicit-int -Wno-error=implicit-function-declaration')
    run(['./configure','--disable-shared','--enable-static','--disable-compat','--prefix='+str(prefix)],cwd=src,env=env)
    run(['make','-j4'],cwd=src);run(['make','install'],cwd=src)
    lib=prefix/'lib/libelf.0.8.13.dylib'
    run(['clang','-arch','x86_64','-mmacosx-version-min='+a.min_macos,'-dynamiclib','-Wl,-all_load',
         src/'lib/libelf.a','-Wl,-install_name,'+str(prefix/'lib/libelf.0.dylib'),'-o',lib])
    for name in ('libelf.0.dylib','libelf.dylib'):(prefix/'lib'/name).symlink_to(lib.name)
    pc=prefix/'lib/pkgconfig';pc.mkdir(exist_ok=True)
    (pc/'libelf.pc').write_bytes((src/'libelf.pc').read_bytes())
    sdk=Path(subprocess.check_output(['xcrun','--show-sdk-path'],text=True).strip())
    match=re.search(r'^#define ZLIB_VERSION "([0-9.]+)"',(sdk/'usr/include/zlib.h').read_text(),re.M)
    if not match:raise ValueError('cannot identify SDK zlib version')
    (pc/'zlib.pc').write_text('Name: zlib\nDescription: macOS SDK system zlib; no Apple binary bundled\n'
                            'Version: '+match[1]+'\nLibs: -lz\nCflags:\n')
    (out/'build.json').write_text(json.dumps({'libelf_source_sha256':SHA256,'minimum_macos':a.min_macos,
        'patch_sha256':hashlib.sha256(a.elf_patch.read_bytes()).hexdigest(),'system_zlib':match[1],
        'library_sha256':hashlib.sha256(lib.read_bytes()).hexdigest()},indent=2)+'\n')
    print('Built '+str(prefix)+'; use its lib/pkgconfig first in PKG_CONFIG_PATH')

if __name__=='__main__':main()
