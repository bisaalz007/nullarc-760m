#!/usr/bin/env python3
"""Exercise the pinned translator's C ABI on authored IR; no GPU execution.

Use an x86_64 Python process on macOS (arch -x86_64 on Apple Silicon).
Pass --spirv-val /path/to/spirv-val for independent Vulkan 1.2 validation.
"""
import argparse
import ctypes as c
from pathlib import Path
import struct
import subprocess
import tempfile


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("library", type=Path)
    cli.add_argument("--spirv-val")
    cli.add_argument("--output-spv", type=Path)
    args = cli.parse_args()
    lib = c.CDLL(str(args.library.resolve()))
    # Core symbols used by NVMTLLibraryLoad.m, including buffer-address lowering.
    for name in ("nvmtl_translate", "nvmtl_translate_free", "nvmtl_reflect",
                 "nvmtl_translate_fc", "nvmtl_reflect_fc", "nvmtl_translate_set_caps",
                 "nvmtl_lower_buffer_addresses", "nvmtl_lower_buffer_addresses_ex",
                 "nvmtl_translate_samplers", "nvmtl_translate_set_threadgroup_lengths"):
        getattr(lib, name)
    pointer = c.POINTER(c.c_uint8)
    lib.nvmtl_translate.argtypes = [c.c_char_p, c.c_char_p, c.POINTER(pointer),
                                    c.POINTER(c.c_size_t), c.c_char_p, c.c_size_t]
    lib.nvmtl_translate.restype = c.c_int
    lib.nvmtl_translate_free.argtypes = [pointer, c.c_size_t]
    lib.nvmtl_translate_free.restype = None
    source = (Path(__file__).resolve().parents[1] / "tests/shaders/store.ll").read_bytes()
    out, length, error = pointer(), c.c_size_t(), c.create_string_buffer(4096)
    rc = lib.nvmtl_translate(source, b"kernel", c.byref(out), c.byref(length), error, len(error))
    if rc or not out or length.value < 20:
        raise RuntimeError(f"translation failed ({rc}): {error.value.decode(errors='replace')}")
    try:
        binary = c.string_at(out, length.value)
    finally:
        lib.nvmtl_translate_free(out, length)
    if len(binary) % 4:
        raise RuntimeError("SPIR-V output is not word aligned")
    words = struct.unpack(f"<{len(binary) // 4}I", binary)
    if words[0] != 0x07230203:
        raise RuntimeError("missing SPIR-V magic")
    i, compute, store = 5, False, False
    while i < len(words):
        count, opcode = words[i] >> 16, words[i] & 0xffff
        if not count or i + count > len(words):
            raise RuntimeError("malformed SPIR-V instruction")
        compute |= opcode == 15 and count >= 4 and words[i + 1] == 5
        store |= opcode == 62
        i += count
    if not compute or not store:
        raise RuntimeError("kernel entry point or output write lost in translation")
    out, length = pointer(), c.c_size_t()
    rc = lib.nvmtl_translate(source, b"invalid-stage", c.byref(out), c.byref(length), error, len(error))
    if rc == 0 or out or length.value:
        raise RuntimeError("invalid stage did not fail cleanly")
    if args.output_spv:
        args.output_spv.write_bytes(binary)
    if args.spirv_val:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "store.spv"
            path.write_bytes(binary)
            subprocess.run([args.spirv_val, "--target-env", "vulkan1.2", str(path)], check=True)
        print("PASS: spirv-val Vulkan 1.2")
    else:
        print("Independent spirv-val validation not run (supply --spirv-val).")
    print(f"PASS: C ABI, kernel translation ({len(binary)} bytes), output store, invalid-stage rejection.")
    print("No Radeon execution or Metal application tested.")


if __name__ == "__main__":
    main()
