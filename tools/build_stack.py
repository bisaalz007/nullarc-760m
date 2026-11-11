#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build and assemble a relocatable macOS development stack from explicit inputs.

The kernel enforces HP diagnostic-only operation. This tool never installs or
loads a kext, edits OpenCore, arms WindowServer, or changes system security.
External LLVM/Zstd runtime binaries remain separately supplied dependencies.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from package_manifest import write, verify, digest
from macos_target import verify_tree

REPO = Path(__file__).resolve().parents[1]


def run(args, **kwargs):
    subprocess.run([str(x) for x in args], check=True, **kwargs)


def output(args):
    return subprocess.check_output([str(x) for x in args], text=True).strip()


def copy(src, dst):
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        # Kexts are copied without subsequent mutation; preserve their sealed
        # resources. The plugin is relocated and explicitly re-signed below.
        ignored=('*.new',) if src.suffix=='.kext' else ('_CodeSignature','*.new')
        shutil.copytree(src, dst, ignore=shutil.ignore_patterns(*ignored))
    else:
        shutil.copy2(src, dst)


def dependencies(path):
    return [line.strip().split(' (compatibility version')[0]
            for line in output(['otool', '-L', path]).splitlines()[1:]]


def relocate(path, pending, dest, origins):
    """Copy actual transitive dylibs; change paths only in this package's copies."""
    run(['lipo', path, '-verify_arch', 'x86_64'])
    if path.suffix == '.dylib':
        run(['install_name_tool', '-id', '@loader_path/' + path.name, path])
    for dep in dependencies(path):
        if dep.startswith(('/System/Library/', '/usr/lib/')) or dep.rsplit('/', 1)[-1] == path.name:
            continue
        if dep.startswith('@loader_path/'):
            local = path.parent / dep[len('@loader_path/'):]
            if not local.is_file():
                raise ValueError(f'missing sibling dependency {local}')
            continue
        if dep.startswith('@'):
            raise ValueError(f'unresolved dependency {dep} in {path}')
        source = Path(dep).resolve(strict=True)
        target = dest / source.name
        if target.exists() and origins.get(target) != digest(source):
            raise ValueError(f'conflicting dylib basename {source.name}')
        if not target.exists():
            copy(source, target)
            origins[target] = digest(source)
            pending.append(target)
        run(['install_name_tool', '-change', dep, '@loader_path/' + target.name, path])
    run(['codesign', '--force', '--sign', '-', path])


def source_inputs():
    native = [f for f in (REPO / 'src').rglob('*')
              if f.is_file() and 'build' not in f.relative_to(REPO).parts]
    native += [f for f in (REPO / 'tools/phxctl').rglob('*')
               if f.is_file() and f.suffix in ('.c','.cpp','.h')]
    native += [f for f in (REPO / 'tools/vkprobe').rglob('*')
               if f.is_file() and f.suffix in ('.c','.h','.comp')]
    native.append(REPO/'tools/mtlprobe/mtlprobe.m')
    return {str(f.relative_to(REPO)):digest(f) for f in native}


def required_artifacts(mesa, mesa_build=None):
    files = [REPO / 'src/phxbringup/build/PhxBringup.kext/Contents/MacOS/PhxBringup',
        REPO / 'src/phxaccel/build/PhxAccel.kext/Contents/MacOS/PhxAccel',
        REPO / 'src/nmplugin/build/NVMTLDriver.bundle/Contents/MacOS/NVMTLDriver',
        REPO / 'build/translator/libnvmtl_translate.dylib',
        REPO / 'build/translator/nvmtl-translator-source.tar.gz',
        REPO / 'build/translator/SOURCE_COMMIT',
        (mesa_build or mesa / 'build') / 'src/amd/vulkan/libvulkan_radeon.dylib']
    files += [REPO / 'build/tools' / name for name in ('phxctl','mesboot','phxprofile','phxfw','vkprobe-native','render-native','mtlprobe')]
    return files


def build_receipt(a):
    record = {'source_inputs':source_inputs(), 'artifacts':{str(p):digest(p) for p in required_artifacts(a.mesa, a.mesa_build)},
              'sdk':output(['xcrun','--sdk','macosx','--show-sdk-version']),
              'target':'x86_64 macOS '+a.min_macos, 'minimum_macos':a.min_macos, 'runtime_validated':False}
    (REPO / 'build/stack-build.json').write_text(json.dumps(record, indent=2)+'\n')


def verify_build_receipt(mesa, min_macos=None, mesa_build=None):
    receipt = json.loads((REPO / 'build/stack-build.json').read_text())
    if min_macos is not None and receipt.get('minimum_macos') != min_macos:
        raise ValueError('build deployment target differs; rebuild for this macOS target')
    if receipt['source_inputs'] != source_inputs(): raise ValueError('compiled source inputs are stale; rebuild first')
    if any(str(path) not in receipt['artifacts'] for path in required_artifacts(mesa, mesa_build)):
        raise ValueError('selected build inputs differ from the recorded build; rebuild with these inputs')
    for path, sha in receipt['artifacts'].items():
        if digest(Path(path)) != sha: raise ValueError(f'compiled artifact differs: {path}')
    return receipt


def assemble(a):
    for name in ('phx_topology.h', 'phx_hp_760m.h', 'phx_hp_760m_device.h'):
        if (a.mesa / 'src/amd/common/darwin' / name).read_bytes() != (REPO / 'src/amd' / name).read_bytes():
            raise ValueError('Mesa topology headers differ; apply the documented patches')
    if 'native queues are not ready' not in (a.mesa / 'src/amd/common/darwin/ac_darwin_drm.c').read_text():
        raise ValueError('Mesa readiness patch 0008 is required')
    if 'phx_hp_760m_apply_device_info(di)' not in (a.mesa / 'src/amd/common/darwin/ac_darwin_drm.c').read_text():
        raise ValueError('Mesa measured device properties patch 0009 is required')
    receipt_path = REPO / 'build/stack-build.json'
    verify_build_receipt(a.mesa, a.min_macos, a.mesa_build)
    dest = a.output.resolve()
    if dest.exists():
        raise ValueError(f'output already exists: {dest}; choose a new output directory')
    dest.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.nullarc-stage-', dir=dest.parent) as temp:
        p = Path(temp) / 'package'; p.mkdir()
        copy(REPO / 'src/phxbringup/build/PhxBringup.kext', p / 'EFI/OC/Kexts/PhxBringup.kext')
        copy(REPO / 'src/phxaccel/build/PhxAccel.kext', p / 'Library/Extensions/PhxAccel.kext')
        run(['codesign','--verify','--strict',p/'Library/Extensions/PhxAccel.kext'])
        bundle = p / 'PhxGPU/NVMTLDriver.bundle'
        copy(REPO / 'src/nmplugin/build/NVMTLDriver.bundle', bundle)
        native = bundle / 'Contents/MacOS'
        translator = REPO / 'build/translator'
        copy(translator / 'libnvmtl_translate.dylib', native / 'libnvmtl_translate.dylib')
        copy(translator / 'nvmtl-translator-source.tar.gz', p / 'sources/nvmtl-translator-source.tar.gz')
        copy(a.air_runtime / 'Contents/MacOS/air-runtime', native / 'air-runtime')
        copy(a.air_runtime / 'Contents/Resources/air-runtime', bundle / 'Contents/Resources/air-runtime')
        copy(a.dependency_notices, p / 'sources/native-dependencies')
        radv = p / 'PhxGPU/nvmtl/libvulkan_radeon.dylib'
        copy(a.mesa_build / 'src/amd/vulkan/libvulkan_radeon.dylib', radv)
        # The plugin opens the ICD directly. The JSON is also usable by a
        # separately installed Vulkan loader; no loader binary is required here.
        (radv.parent / 'radeon_icd.json').write_text(json.dumps({'file_format_version':'1.0.0',
            'ICD':{'library_path':'libvulkan_radeon.dylib','api_version':'1.3.0'}}, indent=2)+'\n')
        pending = [radv, native / 'NVMTLDriver', native / 'libnvmtl_translate.dylib']
        pending += list((native / 'air-runtime').glob('*.dylib'))
        origins = {x:digest(x) for x in pending}
        while pending:
            binary = pending.pop(0)
            relocate(binary, pending, binary.parent, origins)
        run(['codesign', '--force', '--sign', '-', bundle])
        run(['codesign', '--verify', '--deep', '--strict', bundle])
        for name in ('phxctl', 'mesboot', 'phxprofile', 'phxfw','vkprobe-native','render-native','mtlprobe'):
            copy(REPO / 'build/tools' / name, p / 'gpu/phxctl' / name)
        for name in ('hp_bringup.py','hp_boot.py','hp_windowserver.py'):
            copy(REPO/'tools/phxctl'/name,p/'gpu/phxctl'/name)
        for name in ('phxboot.sh', 'full.sh', 'bringup5.sh', 'kinst.sh', 'local.phxboot.plist'):
            copy(REPO / 'tools/phxctl' / name, p / 'gpu' / name)
        # No firmware or automatic activation: these remain blocked on HP.
        copy(REPO / 'hardware/profiles/hp-760m.json', p / 'hardware/hp-760m.json')
        for name in ('LICENSE', 'THIRD_PARTY_NOTICES.md', 'LICENSES'):
            copy(REPO / name, p / name)
        for name in ('760M_STATUS.md', '760M_ARCHITECTURE.md', 'BUILD_STACK.md', 'LINUX_VALIDATION.md',
                     'INSTALL.md','INSTALL_REFERENCE.md'):
            copy(REPO / 'docs' / name, p / 'docs' / name)
        for name in ('install_diagnostics.py','install_components.py','prepare_experiment.py','install_hp_boot.py','recover_hp_boot.py','install_hp_windowserver.py'):
            copy(REPO / 'install' / name, p / name)
        for name in ('install.sh','uninstall.sh'):
            copy(REPO / 'install' / name, p / name)
            (p / name).chmod(0o755)
        guide=(REPO / 'docs/INSTALL.md').read_text().replace('](INSTALL_REFERENCE.md)','](docs/INSTALL_REFERENCE.md)')
        guide=guide.replace('](760M_STATUS.md)','](docs/760M_STATUS.md)')
        (p / 'INSTALL.md').write_text(guide)
        copy(REPO / 'tools/collect_macos_evidence.py', p / 'collect_macos_evidence.py')
        copy(REPO / 'tools/package_manifest.py', p / 'package_manifest.py')
        (p / 'README.txt').write_text('NullArc 760M development stack, macOS '+a.min_macos+'+\n'
            'HP boots diagnostic-only; explicit local-admin bootstrap experiment available.\n'
            'GPU execution and acceleration are not verified by compilation.\n'
            'No firmware or automatic activation is included. See docs/BUILD_STACK.md.\n')
        src = {str(f.relative_to(REPO)):digest(f) for folder in ('src', 'tools', 'install')
               for f in (REPO / folder).rglob('*') if f.is_file() and 'build' not in f.relative_to(REPO).parts and '__pycache__' not in f.parts}
        copy(receipt_path, p / 'stack-build.json')
        native_targets=verify_tree(p,a.min_macos)
        metadata = {'source_commit':output(['git', '-C', REPO, 'rev-parse', 'HEAD']),
                    'source_inputs':src, 'mesa_commit':output(['git', '-C', a.mesa, 'rev-parse', 'HEAD']),
                    'translator_commit':(translator / 'SOURCE_COMMIT').read_text().strip(),
                    'minimum_macos':a.min_macos, 'native_targets':native_targets,
                    'experimental_hp_bootstrap':True,'bootstrap_requires_local_admin':True,
                    'validation':'build-39 HP native/Metal/apps verified; updated display module compiled/host-tested, runtime pending'}
        write(p, metadata); verify(p)
        p.rename(dest)
    print(f'Assembled {dest}; HP diagnostic boot, explicit experimental bootstrap')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--sdk', type=Path)
    ap.add_argument('--vulkan-headers', type=Path)
    ap.add_argument('--translator-source', type=Path)
    ap.add_argument('--glslang',type=Path,help='glslang executable for the authored native compute probe')
    ap.add_argument('--mesa', type=Path, required=True)
    ap.add_argument('--mesa-build', type=Path, help='configured Mesa build directory; defaults to MESA/build')
    ap.add_argument('--min-macos', choices=('15.0','26.0'), default='26.0')
    ap.add_argument('--air-runtime', type=Path, required=True, help='compatible bundle containing LLVM, Zstd and their license files')
    ap.add_argument('--dependency-notices', type=Path, required=True, help='licenses and corresponding source for non-system dylib dependencies')
    ap.add_argument('--output', type=Path, default=REPO / 'build/stack')
    ap.add_argument('--assemble-only', action='store_true', help='use components already built in this checkout')
    a = ap.parse_args()
    a.mesa = a.mesa.resolve()
    a.mesa_build=(a.mesa_build or a.mesa/'build').resolve()
    build_env=dict(os.environ,NULLARC_MIN_MACOS=a.min_macos)
    if not a.assemble_only:
        if not all((a.sdk, a.vulkan_headers, a.translator_source,a.glslang)):
            ap.error('--sdk, --vulkan-headers, --translator-source and --glslang are required for building')
        run(['python3', REPO / 'tools/phx_profile.py', '--check'])
        run(['python3', REPO / 'tools/phx_device_profile.py'])
        run(['make', 'test'], cwd=REPO)
        for component in ('phxbringup', 'phxaccel'):
            run(['sh', REPO / 'src' / component / 'build.sh', a.sdk],env=build_env)
        run(['bash', REPO / 'src/nmplugin/build.sh', a.vulkan_headers],env=build_env)
        run(['bash', REPO / 'tools/build_translator.sh', a.translator_source],env=build_env)
        run(['ninja', '-C', a.mesa_build])
        tools = REPO / 'build/tools'; tools.mkdir(parents=True, exist_ok=True)
        for name in ('phxctl', 'mesboot', 'phxprofile'):
            run(['clang', '-arch', 'x86_64', '-mmacosx-version-min='+a.min_macos, '-O2', REPO / 'tools/phxctl' / (name+'.c'),
                 '-framework', 'IOKit', '-framework', 'CoreFoundation', '-o', tools / name])
        run(['clang++', '-arch', 'x86_64', '-mmacosx-version-min='+a.min_macos, '-std=c++17', '-O2',
             REPO / 'tools/phxctl/phxfw.cpp', REPO / 'src/amd/rdna3_ucode_extract.cpp', '-o', tools / 'phxfw'])
        includes=REPO/'build/probe-include';includes.mkdir(exist_ok=True)
        run([a.glslang,'-V','--vn','fill_spv',REPO/'tools/vkprobe/fill.comp','-o',includes/'fill_spv.h'])
        for source,name in [('vkprobe.c','vkprobe-native'),('translated_render.c','render-native')]:
            run(['clang','-arch','x86_64','-mmacosx-version-min='+a.min_macos,'-std=gnu11','-O2',
                 '-DPHX_DIRECT_RADV','-I',a.vulkan_headers/'include','-I',includes,
                 REPO/'tools/vkprobe'/source,'-o',tools/name])
        run(['clang','-arch','x86_64','-mmacosx-version-min='+a.min_macos,'-fobjc-arc',
             '-Wall','-Wextra','-Werror','-framework','Foundation','-framework','Metal','-framework','IOKit',
             REPO/'tools/mtlprobe/mtlprobe.m','-o',tools/'mtlprobe'])
        build_receipt(a)
    assemble(a)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as e:
        raise SystemExit(str(e))
