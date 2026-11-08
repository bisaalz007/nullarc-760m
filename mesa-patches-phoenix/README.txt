Phoenix (Radeon 780M, gfx1103) patches on top of Cobalt64's RADV Darwin port.

Base: Mesa f5cb8ee032adabef599ae892ec4e42d796b84da9 + reference/Cobalt64/mesa-patches/0001..0009.
Apply these after them (git am, 0001..0009).  0001..0003 are what tools/mesa_phoenix_canned.py,
tools/mesa_phoenix_identity.py and tools/mesa_phoenix_service.py produce (0003: open the PhxBringup service).
0004 answers AMDGPU_INFO_TIMESTAMP from SMUIO GOLDEN_TSC (needs PhxBringup build 31): Metal GPUStartTime/GPUEndTime.
0005 opens PhxBringup through NMXAccel when sandboxed (needs the PhxAccel proxy): Metal in WebKit's GPU process.
0006 unrolls nested loops without a full optimization round per level: a new CoreAnimation compositor shader
     variant compiles in ~1 s instead of ~2 s (same code), so WindowServer stalls less on first use.

Build on the Mac (Tahoe 26.6.2, CLT 16.2, Python 3.14 venv with meson/ninja/mako/pyyaml/packaging,
glslangValidator built from source into ~/gpu/prefix):
  meson setup build --buildtype=release -Dvulkan-drivers=amd -Dgallium-drivers= -Dplatforms= \
    -Dllvm=disabled -Dglx=disabled -Degl=disabled -Dgbm=disabled -Dopengl=false -Dgles1=disabled \
    -Dgles2=disabled -Dxmlconfig=disabled -Dvalgrind=disabled -Dlibunwind=disabled -Dzstd=disabled \
    -Dbuild-tests=false -Dvulkan-layers= -Dtools=
  ninja -C build

Check (no GPU, in-process mock kext):
  python3 tools/test_mesa_vulkan_profile.py /path/to/mesa --glslang /path/to/glslangValidator
  -> 8/12-CU properties and ACO compilation, zero submissions.
The vkprobe tool performs actual submission/readback and must not be used as a
compile-only mock success check.

0007 adds NullArc topology selector 30 and an explicit HP mock profile. DEV_INFO's
     physical CU masks, active counts, shader-array dimensions and enabled RB mask
     come from the captured kernel profile; PCI identity follows the same data.
     Legacy kexts keep their existing fallback. Captured-only HP native use fails.
     No GB_ADDR_CONFIG, memory layout or firmware values are inferred from topology.

Alternative to applying 0007 (do not do both):
  python3 /path/to/nullarc-760m/tools/mesa_phoenix_topology.py /path/to/mesa
This generator verifies all source anchors before writing. Regenerate it and the
patch together when changing the wire header/profile. Check the shared HP header:
  python3 tools/phx_profile.py --check

Host transport tests (from the NullArc checkout):
  sh tools/test_mesa_topology.sh /path/to/mesa
Mock Vulkan properties plus gfx1103 ACO pipeline compilation (macOS, x86_64):
  python3 tools/test_mesa_vulkan_profile.py /path/to/mesa --glslang /path/to/glslangValidator
The latter explicitly checks 8-CU HP and the unchanged 12-CU legacy default, with
zero command submissions. It is not hardware execution or Metal testing.

0008 requires the native kernel's positive readiness flags before a Vulkan device
     is exposed. PhxBringup build 34 reports these only with both queue types ready;
     it no longer retires submissions in software when queues are absent.
Alternative to 0008, after 0007:
  python3 /path/to/nullarc-760m/tools/mesa_phoenix_readiness.py /path/to/mesa
Roundtrip test from the ref after 0006:
  python3 tests/test_mesa_patch.py /path/to/mesa <ref-after-0006>
Packaged real Metal/AIR/SPIR-V + ACO compute/graphics compiler integration:
  python3 tools/test_metal_stack.py --package build/stack --mesa /path/to/mesa --spirv-val /path/to/spirv-val
This compiles authored MSL and runs no GPU command execution.

0009 applies measured HP chip/counter/clock-cap/cache properties only when the exact
     captured HP topology identity matches. The 100000 kHz counter yields 10 ns
     timestamp periods. No Linux VA layout, budgets, flags or firmware state is
     copied, and native readiness checks remain intact. Other profiles unchanged.
Alternative to 0009, after 0008:
  python3 /path/to/nullarc-760m/tools/mesa_phoenix_device_info.py /path/to/mesa
Generated header check:
  python3 tools/phx_device_profile.py
The roundtrip test above now covers 0007..0009. The separate Linux validation
executes translated shaders on the HP with stock RADV, not this Darwin backend;
see docs/LINUX_VALIDATION.md. Earlier vkprobe mock text describes compilation only;
vkprobe now explicitly rejects software devices and returns failure on bad readback.
