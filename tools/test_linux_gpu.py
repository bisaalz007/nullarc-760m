#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Run bounded offscreen HP hardware tests through stock Linux RADV.

No macOS driver is loaded or tested. Requires libvulkan-dev, glslang-tools,
spirv-tools, vulkan-validationlayers and translated fixtures from test_metal_stack.py.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[1]

def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--translated-dir',type=Path,required=True)
    ap.add_argument('--device',type=Path,default=Path('/dev/dri/renderD128'))
    ap.add_argument('--output',type=Path,required=True)
    a=ap.parse_args()
    if sys.platform!='linux': ap.error('run on the HP Linux session')
    st=a.device.stat()
    if not stat.S_ISCHR(st.st_mode): ap.error('expected DRM character device')
    pci=(Path('/sys/dev/char')/f'{os.major(st.st_rdev)}:{os.minor(st.st_rdev)}'/'device').resolve(strict=True)
    expected={'vendor':0x1002,'device':0x1900,'revision':0xca,'subsystem_vendor':0x103c,'subsystem_device':0x8c6a}
    if {k:int((pci/k).read_text(),16) for k in expected}!=expected: ap.error('exact HP identity required')
    a.output=a.output.resolve();a.output.mkdir(parents=True,exist_ok=False)
    shaders=[a.translated_dir/n for n in ('store.spv','triangle_vertex.spv','solid_fragment.spv')]
    sources=[ROOT/'tools/vkprobe'/n for n in ('vkprobe.c','translated_render.c','fill.comp')]
    report={'format':1,'captured_at':datetime.now(timezone.utc).isoformat(),'kernel':os.uname().release,
            'pci':expected,'backend':'stock Linux Vulkan loader/RADV, not Darwin winsys or NullArc kext',
            'shader_sha256':{p.name:digest(p) for p in shaders},'source_sha256':{p.name:digest(p) for p in sources},'steps':[],
            'validation_layer':'VK_LAYER_KHRONOS_validation','passed':False}
    # Do not inherit injected layers/ICDs, mock modes or diagnostic overrides.
    env={k:v for k,v in os.environ.items() if not k.startswith(('VK_','RADV_','MESA_','AMD_','NVMTL_'))}
    env['VK_INSTANCE_LAYERS']='VK_LAYER_KHRONOS_validation'
    def run(name,args):
        result=subprocess.run([str(x) for x in args],env=env,capture_output=True,text=True,timeout=45)
        log=result.stdout+result.stderr
        (a.output/(name+'.log')).write_text(log)
        validation_error=bool(re.search(r'Validation Error|VUID-|ERROR.*Validation',log))
        report['steps'].append({'name':name,'returncode':result.returncode,'validation_error':validation_error})
        if result.returncode or validation_error: raise RuntimeError(f'{name} failed; see {a.output/name}.log')
    try:
        for p in shaders:run('validate-'+p.stem,['spirv-val','--target-env','vulkan1.2',p])
        run('compile-glsl',['glslangValidator','-V','--vn','fill_spv',sources[2],'-o',a.output/'fill_spv.h'])
        for p in sources[:2]:
            run('build-'+p.stem,['cc','-std=c11','-Wall','-Wextra','-Werror','-I'+str(a.output),p,'-lvulkan','-o',a.output/p.stem])
        run('compute-queue',[a.output/'vkprobe','--hp'])
        env['VKPROBE_QFAM']='0'
        run('graphics-queue-compute',[a.output/'vkprobe','--hp'])
        del env['VKPROBE_QFAM']
        run('translated-compute',[a.output/'vkprobe','--hp','--translated-store',shaders[0]])
        run('translated-render',[a.output/'translated_render',shaders[1],shaders[2]])
        report['passed']=True
    finally:
        (a.output/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PASS: Linux hardware readbacks, including translated MSL compute/graphics; macOS execution remains unverified')

if __name__=='__main__': main()
