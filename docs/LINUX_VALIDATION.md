# HP Linux hardware validation — 2026-11-08

Linux Mint 22.3, kernel 6.14.0-37-generic, stock Mesa RADV 25.0.7. Exact PCI
`1002:1900` rev `ca`, subsystem `103c:8c6a`. The live topology equals the supplied
profile, including physical CU indexing and sparse RB mask. The companion capture
completed without errors and records 39 IP instances and 512 MiB UMA VRAM.
Linux reports the MC range `0x8000000000..0x801fffffff` and a 64 MiB PSP TMR at
`0x8018000000`. These are Linux-managed allocations, **not macOS reservations**.

Verified with normal Vulkan command submission, bounded fences, explicit host
barriers, coherent readback and `VK_LAYER_KHRONOS_validation`:

| Test | Result |
|---|---|
| GLSL compute, compute-only queue | 256/256 exact uint values |
| GLSL compute, graphics-capable queue | 256/256 exact uint values |
| Translated authored Metal `store_value` | 7 returned; local size specialized to 1 |
| Translated Metal vertex + fragment draw | 16×16 pixels correct; first RGBA 64,128,191,255 |

No Vulkan validation errors were reported. The Metal shaders came from this fork's
built package: Apple MSL compiler → metallib → plugin's LLVM AIR reader → pinned
NullMoth translator → independently validated SPIR-V → stock Linux RADV/ACO → HP.
The render probe uses optimal-tiled RGBA8 image allocation, dynamic rendering,
image-layout transitions, image-to-buffer copy and a fence. It never owns a display.
Software-only enumeration and invalid/non-compute queue selection are refused.

This is **not** execution through PhxBringup, the Darwin winsys, an instantiated
macOS Metal device, WindowServer or PhxAccel. It does not establish macOS firmware
bring-up, interrupts, recovery, scanout, suspend/resume or Tahoe compatibility.
Only the authored shaders listed above were executed; general translator coverage
and complex rendering remain unverified.

## Reproduce

On the build Mac, run `tools/test_metal_stack.py` as documented in BUILD_STACK.md.
It preserves `build/metal-stack-test/{store,triangle_vertex,solid_fragment}.spv`.
Transfer those authored artifacts and this checkout to the HP Linux session.
With `libdrm-dev`, `libvulkan-dev`, `glslang-tools`, `spirv-tools` and
`vulkan-validationlayers` installed:

```sh
cc -std=c11 -Wall -Wextra -Werror $(pkg-config --cflags libdrm) tools/linux-profile/collect.c -o collect
sudo python3 tools/linux-profile/collect_evidence.py --device /dev/dri/renderD128 \
  --collector ./collect --output /tmp/hp-capture-NEW
python3 tools/test_linux_gpu.py --translated-dir /path/to/translated-shaders \
  --output /tmp/hp-gpu-test-NEW
```

The second command collects selected sysfs/debugfs information without resetting
the device or accessing registers. The last command **executes GPU commands** via
the existing Linux driver and records hashes, return codes and validation output.
It checks the exact HP identity and does not inherit mock/ICD override variables.
Neither command installs a macOS driver or changes firmware/EFI.

Checked-in evidence: `hardware/dumps/hp_envy_760m/linux-2026-11-08.json`,
`linux-*-readback.txt`, `linux-compute-graphics-queue.txt`, `linux-firmware-plan.tsv`
and the hardware-test receipt. No VBIOS, system serial, private SSH key or firmware
binary is committed. Firmware hashes identify local decompressed files; the
debugfs loaded-version report is separate and does not prove file provenance.

## Firmware delta and remaining bring-up work

The live image's MEC payload is 268384 bytes (old script: 267008), scheduler MES
code is 112688 (old: 135648), KIQ MES code is 100112 (old: 104272), and several RLC
offsets differ. `phxfw` derives every payload range before the reference bring-up
script arms a watchdog or stages bytes. MES code/data use their explicit header
offsets, mandatory non-overlapping bounds and distinct scheduler/KIQ PSP types.
The ABI and offsets follow Linux v6.14's
[firmware headers](https://github.com/torvalds/linux/blob/v6.14/drivers/gpu/drm/amd/amdgpu/amdgpu_ucode.h)
and [MES implementation](https://github.com/torvalds/linux/blob/v6.14/drivers/gpu/drm/amd/amdgpu/mes_v11_0.c).
The whole set must fit the existing reference staging slots; unsupported layouts
fail before partial output. This validates structure/ranges, not cryptographic
authenticity or successful PSP/MES startup.

HP runtime memory/scanout ownership, PSP/TMR command addresses and MES queue
configuration still require a macOS-specific implementation and staged validation.
The diagnostic gates remain in place. Do not transplant Linux physical addresses
or reference-machine raw PSP/GART values into the HP configuration.
