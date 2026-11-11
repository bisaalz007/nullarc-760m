#!/usr/bin/env python3
"""Check the actual streaming-copy routine's pixels and allocation guards."""
from pathlib import Path
import platform
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if platform.machine().lower() not in ('x86_64', 'amd64'):
    print('SKIP: scanout streaming copy requires x86_64')
    raise SystemExit(0)
compiler = shutil.which('clang++') or shutil.which('g++')
if not compiler:
    raise SystemExit('C++ compiler required for scanout-copy regression')
source = (ROOT / 'src/phxaccel/accel/nvrm-accel.cpp').read_text()
start = source.index('static void nvIopRowSSE(')
end = source.index('\n// A copied frame completes', start)
harness = r"""
#include <stdint.h>
#include <string.h>
#include <stdio.h>
COPY_FUNCTION
int main(void) {
    if (!__builtin_cpu_supports("sse4.1")) return 77;
    alignas(16) uint8_t source[8192 + 64], destination[8192 + 64];
    uint8_t expected[8192 + 64], original[8192 + 64];
    uint32_t state = 42;
    unsigned checks = 0;
    for (unsigned convert = 0; convert < 2; convert++) {
        for (unsigned bytes = 64; bytes <= 8192; bytes += 64) {
            for (unsigned offset = 16; offset <= 32; offset += 16) {
                for (unsigned i = 0; i < sizeof(source); i++) {
                    state = state * 1664525u + 1013904223u;
                    source[i] = (uint8_t)(state >> 24);
                }
                memcpy(original, source, sizeof(source));
                memset(destination, 0xa5, sizeof(destination));
                memset(expected, 0xa5, sizeof(expected));
                for (unsigned i = 0; i < bytes; i += 4) {
                    uint32_t pixel;
                    memcpy(&pixel, source + offset + i, 4);
                    if (convert) {
                        pixel = 0xff000000u | ((pixel >> 6) & 0x00ff0000u)
                              | ((pixel >> 4) & 0x0000ff00u) | ((pixel >> 2) & 0xffu);
                    }
                    memcpy(expected + offset + i, &pixel, 4);
                }
                nvIopRowSSE(source + offset, destination + offset, bytes, convert);
                __asm__ __volatile__("sfence" ::: "memory");
                if (memcmp(expected, destination, sizeof(destination)) ||
                    memcmp(original, source, sizeof(source))) return 1;
                checks++;
            }
        }
    }
    printf("PASS: %u scanout streaming copies, format conversion and allocation guards\n", checks);
}
"""
with tempfile.TemporaryDirectory(prefix='nullarc-copy-test-') as directory:
    folder = Path(directory)
    code = folder / 'copy.cpp'
    executable = folder / 'copy'
    code.write_text(harness.replace('COPY_FUNCTION', source[start:end]))
    subprocess.run([compiler, '-std=c++17', '-O2', '-mno-sse', '-mno-mmx', '-msoft-float',
                    str(code), '-o', str(executable)], check=True, timeout=30)
    result = subprocess.run([str(executable)], timeout=30)
    if result.returncode == 77:
        print('SKIP: CPU lacks SSE4.1')
    elif result.returncode:
        raise SystemExit(result.returncode)
