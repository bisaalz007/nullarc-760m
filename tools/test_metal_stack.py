#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compile authored MSL, translate through the real plugin, validate SPIR-V and compile ACO in explicit mocks."""
import argparse
import os
from pathlib import Path
import subprocess
import json
import hashlib

REPO = Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--package', type=Path, required=True)
    ap.add_argument('--mesa', type=Path, required=True)
    ap.add_argument('--spirv-val', required=True)
    ap.add_argument('--min-macos',choices=('15.0','26.0'),default='26.0')
    a = ap.parse_args()
    a.package = a.package.resolve(); a.mesa = a.mesa.resolve()
    out = REPO / 'build/metal-stack-test'; out.mkdir(parents=True, exist_ok=True)
    receipt=out/'fixture-receipt.json'
    if receipt.exists():receipt.unlink()
    (out / 'cache/aircache').mkdir(parents=True, exist_ok=True)
    def run(args, **kw): subprocess.run([str(x) for x in args], check=True, timeout=90, **kw)
    run(['xcrun','metal','-mmacosx-version-min='+a.min_macos,'-c',REPO / 'tests/shaders/store.metal','-o',out/'store.air'])
    run(['xcrun','metallib',out/'store.air','-o',out/'store.metallib'])
    run(['clang','-arch','x86_64','-mmacosx-version-min='+a.min_macos,'-fobjc-arc','-framework','Foundation',
         '-framework','Metal',REPO/'tests/test_metallib_translation.m','-o',out/'metallib-test'])
    env = dict(os.environ, NVMTL_AIRCACHE=str(out/'cache/aircache'), NVMTL_LOG_PATH=str(out/'plugin.log'),
               NVMTL_SPVCACHE_OFF='1', NVMTL_NO_LIBMEMO='1', NVMTL_NO_LAZYAIR='1')
    run([out/'metallib-test',a.package/'PhxGPU/NVMTLDriver.bundle/Contents/MacOS/NVMTLDriver',
         out/'store.metallib',out/'store.spv'], env=env)
    for name in ('store.spv','triangle_vertex.spv','solid_fragment.spv'):
        run([a.spirv_val,'--target-env','vulkan1.2',out/name])
    run(['clang','-arch','x86_64','-mmacosx-version-min='+a.min_macos,'-std=c11','-Wall','-Wextra','-Werror','-I'+str(a.mesa/'include'),
         REPO/'tests/test_mesa_vulkan_profile.c','-o',out/'radv-test'])
    for profile, count in [('hp-760m',8),('',12)]:
        env = dict(os.environ, RADV_DARWIN_MOCK='1', RADV_DARWIN_MOCK_PROFILE=profile,
                   RADV_DARWIN_CANNED='phoenix', MESA_SHADER_CACHE_DISABLE='true')
        run([out/'radv-test',a.package/'PhxGPU/nvmtl/libvulkan_radeon.dylib',str(count),out/'store.spv','main',out/'triangle_vertex.spv',out/'solid_fragment.spv'],env=env)
    digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    inputs=['PhxGPU/NVMTLDriver.bundle/Contents/MacOS/NVMTLDriver',
            'PhxGPU/NVMTLDriver.bundle/Contents/MacOS/libnvmtl_translate.dylib','PhxGPU/nvmtl/libvulkan_radeon.dylib']
    receipt.write_text(json.dumps({'inputs':{n:digest(a.package/n) for n in inputs},
        'shaders':{n:digest(out/n) for n in ('store.spv','triangle_vertex.spv','solid_fragment.spv')},
        'independent_spirv_validation':True,'aco_mock_cu_profiles':[8,12],'gpu_commands_submitted':0},indent=2)+'\n')
    print('[PASS] packaged source Metal -> AIR reader -> translator -> SPIR-V validation -> RADV/ACO (8/12-CU mocks); no GPU execution')


if __name__ == '__main__': main()
