#!/usr/bin/env python3
"""Overlay verified WindowServer startup scripts onto the existing compiled release.

This does not rebuild kexts, RADV, or the translator. The original release ZIP
and its SHA256SUMS remain untouched; this creates a separately named add-on ZIP.
"""
import argparse
import json
from pathlib import Path, PurePosixPath
import stat
import subprocess
import sys
import tarfile
import tempfile
import zipfile

RELEASE = 'nullarc-760m-0.2.0-sequoia-beta'
PATCH_COMMIT = '5de9ab4221a5af7af20723b9c2bc1faf5ffa4b64'
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'tools'))
from package_manifest import digest, inventory, verify, write

OVERLAY = {
    'tools/phxctl/hp_windowserver.py': 'gpu/phxctl/hp_windowserver.py',
    'tools/phxctl/hp_boot.py': 'gpu/phxctl/hp_boot.py',
    'install/install_hp_windowserver.py': 'install_hp_windowserver.py',
    'docs/INSTALL.md': 'docs/INSTALL.md',
}


def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args])


def current_patch_contents(path):
    return git('show', f'{PATCH_COMMIT}:{path}')


def verify_original_archive(archive, checksum_file):
    records = dict(line.strip().split('  ', 1) for line in checksum_file.read_text().splitlines() if '  ' in line)
    if records.get(archive.name) != digest(archive):
        raise ValueError('original release ZIP checksum does not match the published SHA256SUMS')


def extract_trusted_zip(archive, destination):
    with zipfile.ZipFile(archive) as z:
        if z.testzip() is not None:
            raise ValueError('original ZIP failed CRC validation')
        for info in z.infolist():
            p = PurePosixPath(info.filename)
            if (not p.parts or p.parts[0] != RELEASE or p.is_absolute()
                    or '..' in p.parts or stat.S_ISLNK(info.external_attr >> 16)):
                raise ValueError('unexpected ZIP member: ' + info.filename)
        z.extractall(destination)
        # Python's ZipFile.extractall does not restore Unix permissions.
        for info in z.infolist():
            mode = (info.external_attr >> 16) & 0o777
            file = destination / info.filename
            if mode and file.exists():
                file.chmod(mode)
    return destination / RELEASE


def make_patch_archive(package):
    # Original sources/nullarc-source.tar.gz continues to describe the binary build.
    source = package/'sources/windowserver-persistence-source.tar.gz'
    with tarfile.open(source, 'w:gz') as tar:
        for path in sorted(OVERLAY):
            payload = current_patch_contents(path)
            import io
            info = tarfile.TarInfo(f'nullarc-windowserver-persistence/{path}')
            info.mode = 0o644
            info.size = len(payload)
            info.mtime = 0
            tar.addfile(info, io.BytesIO(payload))
    return source


def assemble(original, sums, output):
    output.mkdir(parents=True, exist_ok=False)
    verify_original_archive(original, sums)
    with tempfile.TemporaryDirectory(prefix='nullarc-persist-') as work:
        package = extract_trusted_zip(original, Path(work))
        before = verify(package)
        if before.get('release_version') != '0.2.0-sequoia-beta':
            raise ValueError('unexpected source release version')
        if before.get('source_commit') != '776fd94491946e6a15162b58f4f95adcf8d0add9':
            raise ValueError('original binary provenance differs from published release')
        old_files = inventory(package)
        modified = set()
        for source, target in OVERLAY.items():
            dst = package/target
            if not dst.is_file():
                raise ValueError('release is missing expected startup file ' + target)
            dst.write_bytes(current_patch_contents(source))
            modified.add(target)
        guide = current_patch_contents('docs/INSTALL.md').decode().replace(
            '](INSTALL_REFERENCE.md)', '](docs/INSTALL_REFERENCE.md)')
        (package/'INSTALL.md').write_text(guide)
        modified.add('INSTALL.md')
        patch_source = make_patch_archive(package)
        modified.add(patch_source.relative_to(package).as_posix())
        new_files = inventory(package)
        for filename, value in old_files.items():
            if filename not in modified and new_files.get(filename) != value:
                raise ValueError('unexpected compiled release change: ' + filename)
        metadata = {key: value for key, value in before.items()
                    if key not in ('files', 'format', 'policy', 'acceleration_verified')}
        metadata['startup_patch_commit'] = PATCH_COMMIT
        metadata['startup_patch_type'] = 'persistent-windowserver-script-overlay; compiled drivers unchanged'
        write(package, metadata)
        verify(package)
        output_zip = output/f'{RELEASE}-persistent-windowserver.zip'
        with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED,
                             compresslevel=6, strict_timestamps=False) as z:
            for file in sorted(package.rglob('*')):
                if file.is_symlink():
                    raise ValueError('unexpected release symlink: '+str(file))
                if file.is_file():
                    z.write(file, Path(RELEASE)/file.relative_to(package))
        with zipfile.ZipFile(output_zip) as z:
            if z.testzip() is not None:
                raise ValueError('new ZIP CRC verification failed')
        (output/'SHA256SUMS-persistent-windowserver').write_text(
            f'{digest(output_zip)}  {output_zip.name}\n')
        (output/'RELEASE_NOTES-persistent-windowserver.md').write_text(
            '# WindowServer persistent arming — addition to 0.2.0 Sequoia beta\n\n'
            f'Startup-script patch: {PATCH_COMMIT}. Compiled driver source remains '
            f'{before["source_commit"]}. The original ZIP is retained as-is.\n\n'
            'This add-on ZIP contains the original compiled kexts, translator, RADV and '
            'firmware, with updated HP startup supervisor, installer, and instructions. '
            'No graphics binary was rebuilt or replaced.\n\n'
            'After the existing staged installer validation, '
            'sudo ./install.sh --windowserver opts in once. Only a boot with '
            'validated native GPU queues, console-user Metal tests, and live '
            'WindowServer presents will rearm its successor. The NVRAM flag remains '
            'one-shot inside the framebuffer kext; failed boots cancel persistence '
            'and retain the firmware fallback path.\n\n'
            '**This patch has not been runtime-validated on the HP since commit '
            f'{PATCH_COMMIT[:12]}.** Earlier accelerated-display results pertain '
            'to the original compiled stack. All previous limitations remain.\n\n'
            'Verify SHA256SUMS-persistent-windowserver; unzip and read '
            'INSTALL.md. This is an alternate install ZIP within the original '
            'release; do not confuse it with GitHub automatic source archives.\n')
    return output_zip


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--original', type=Path, required=True)
    ap.add_argument('--checksums', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    result = assemble(args.original, args.checksums, args.output)
    print(json.dumps({'zip': str(result), 'sha256': digest(result)}))


if __name__ == '__main__':
    main()
