# Radeon 760M development status

Updated 2026-11-08. Fork: `yt42c2mvn2-cmd/nullarc-760m`.
Branch: `codex/radeon-760m-driver-completion`. Continuation baseline: merged `main` at `f08b898` (PR #1).

**HP acceleration is not functional or hardware-tested. This branch intentionally
allows only diagnostics on the captured HP PCI identity. Do not install an upstream
780M release expecting these source changes.** No system drivers were installed,
loaded, or replaced during this session.

## Continuation after PR #1

- **Kernel execution/memory:** `PhxExecutionPolicy.h` is used directly by the
  production kext and failure-injection tests. Mapping failures clear the installed
  prefix; canonical-span/BO-range overflow is rejected; unmap/free waits for client
  retirement and removes PTEs. Graphics/compute batches require their actual engine;
  mixed-engine batches are refused. The old immediate-retirement fallback was removed.
- **Fences and faults:** sixteen user-fence slots prevent overwriting earlier pending
  completions. TLB/ring/VMID timeouts enter an atomic device-lost state. New GPU
  work is refused and affected wired BO/page-table memory is deliberately retained
  until reboot. This is a bounded diagnostic failure policy, **not verified GPU
  reset/recovery**. The actual hardware fault/timeout path still needs runtime tests.
- **Bring-up tools:** `phxctl` returns failures for transport/reply-shape errors,
  failed SMU/PSP operations and short firmware reads. File ranges are checked before
  staging; unsigned overflow is refused. Scripts stop before watchdog/hardware access
  when the service is missing, diagnostic-only or lost, and stop on command failures.
  No HP firmware sequence was enabled or executed.
- **Metal/translation:** source build scripts now compile the full plugin and pinned
  NullMoth v2.4.1 translator (`76df0f6...`) and preserve corresponding LGPL source.
  The Metal `hasUnifiedMemory` property follows Vulkan's integrated-device type.
  Authored MSL compute/vertex/fragment shaders traverse the real metallib reader,
  LLVM AIR decoder and translator, pass independent `spirv-val`, and compile into
  compute and graphics pipelines with the HP/legacy mocks. No Metal device is
  constructed and no GPU dispatch/draw is issued by this test.
- **RADV:** Phoenix patch 0008 refuses native initialization without positive queue
  readiness. Explicit mocks remain separate. Patches 0007/0008 and their generators
  are checked for byte-identical output from the documented baseline.
- **Build/package/install:** `build_stack.py` builds components from explicit inputs,
  checks build receipts, relocates native dylib dependencies in staging, signs the
  bundle and writes a complete hashed package inventory. It never copies an installed
  driver executable or automatically installs it. LLVM/Zstd runtime binaries remain
  separately supplied dependencies with their notices. The transactional diagnostic
  installer has dry-run, backup, failure rollback, removal and later-edit protection.
  Installation/removal tests operate on temporary EFI fixtures; no HP EFI was modified.
- **Hardware evidence:** live SSH capture on the HP confirmed PCI `1002:1900` rev `ca`,
  subsystem `103c:8c6a`, Sequoia 15.8.2, IONDRVFramebuffer and 1920×1200 output. System
  Information reports the firmware framebuffer's 8 MB, **not functional acceleration**.
  BAR sizes are 256 MiB/2 MiB/512 KiB; addresses differ from historical Linux, reinforcing
  the need for runtime address discovery. Saved reports omit system serials. The
  supplied Windows report independently corroborates CPU, identity and 60 Hz panel;
  it does not provide IP/firmware/controller data.

Validation completed for this continuation: 7 host C++ binaries, 14 Python test
methods, existing firmware/discovery fuzz cases, ASan/UBSan execution-policy tests,
134 Mesa marshaller checks plus topology tests, native kext/plugin/translator/RADV
builds, package hashes and signature checks, and real MSL-to-ACO compute/graphics
compilation under both mocks. Three existing kext field-shadow warnings and the
plugin's upstream protocol/deprecation warnings remain. KXLD/AuxKC compatibility,
HP execution, hardware rendering, display takeover, suspend/resume and reset remain
unverified. The HP currently runs Sequoia; Tahoe driver runtime testing is outstanding.

The Linux collector can now capture topology, full available IP sysfs attributes,
firmware-version/debugfs reports, memory inventory, relevant kernel messages and
candidate firmware hashes without reloading drivers or accessing registers. Its
sysfs/file handling is fixture-tested; actual Linux capture/compilation awaits the
HP live session.

## PR #1 baseline stages and changed components

| Stage | Result | Files/components changed | Validation |
|---|---|---|---|
| 1: inspect | Completed architecture audit; old R3N path is a simulation | `docs/760M_ARCHITECTURE.md` | README and linked notes cross-checked against active sources |
| 2: profile | Exact HP identity; physical masks retained; strict JSON/bitmap validation | `hardware/profiles/hp-760m.json`, `src/amd/phx_{topology,hp_760m}.h`, `tools/phx_profile.py`, profile tests | Header reproduction; malformed/count/range/sparse-mask/4-CU/12-CU tests |
| 3: bring-up | Diagnostic-only attachment; selector 30 exports captured topology; no HP DMA enable, writes, BOs, submit, queue adoption or accelerator claim | `src/phxbringup/{PhxBringup.cpp,PhxNativeABI.h}`, `tools/phxctl/{bringup5,full,phxboot}.sh` | Native x86_64 kext build; ABI size assertions; selector policy tests; shell syntax; only new kernel import is standard IOPCIDevice byte-config read |
| 4: translation/backend | Runtime topology reaches RADV DEV_INFO, CU mapping, enabled RBs and PCI identity; old fallback retained | `mesa-patches-phoenix/0007-*`, `tools/mesa_phoenix_topology.py`, Mesa tests/runners | Complete x86_64 RADV build; mock Vulkan reports 8 CUs; gfx1103 ACO pipeline compiled |
| 5: accelerator | HP framebuffer and NMXAccel decline before takeover, independent of service start order | `src/phxaccel/accel/{phxfb,nvrm-accel}.cpp` | Native x86_64 PhxAccel build; no runtime loading |
| 6: integration | Read-only macOS profile inspector; Linux DRM/IP collector; host tests and Linux collector CI build | `tools/phxctl/phxprofile.c`, `tools/linux-profile/collect.c`, `Makefile`, `.github/workflows/ci.yml` | macOS inspector compiles with warnings as errors; Linux collector awaits Linux CI/hardware |
| 7: tests | Host and mock coverage passes; no hardware result | `tests/test_phx_*`, `tests/test_mesa_*`, `tools/test_mesa_*` | 5 host C++ test binaries, 4 Python test methods; firmware fixtures incl. 5000 mutations; Mesa marshaller 134 checks plus new topology tests; ASan/UBSan for topology and transport; byte-identical patch/generator roundtrip; 8-CU and unchanged 12-CU Vulkan mock + ACO |
| 8: docs | Usage, evidence requirements and source dependency map | README, install caveat, Mesa patch instructions, status/architecture docs | Commands checked where this Mac provides dependencies |

Native builds use the documented `src/phxbringup/build.sh` and
`src/phxaccel/build.sh` with MacKernelSDK. Three pre-existing field-shadow warnings
remain in PhxBringup. PhxAccel builds cleanly. Standard unresolved kernel imports
are expected in linked kexts; KXLD/AuxKC load compatibility is untested.

## Authoritative supplied capture

`hp-760m.json` was supplied by the user and copied unchanged. Its original collection
method/date were not supplied. Validation establishes internal consistency, not
independent measurement of this machine:

- PCI `1002:1900`, revision `ca`, subsystem `103c:8c6a`.
- 1 shader engine; 2 shader arrays; 6 physical CU slots per array.
- 8 active CUs: masks `[0x0f, 0x0f]`; do not derive masks from CU count.
- 4 physical RB pipes, enabled mask `0x0a`; preserve physical indexing.
- No IP-discovery versions, GB_ADDR_CONFIG, firmware hashes/addresses, memory
  aperture/reservation map, panel configuration, or validated initialization trace.

The private 128-byte topology query is separate from the existing 192-byte N48N
QueryInfo. Its `CAPTURED` flag never implies `RUNTIME_READY`; this branch never sets
that readiness bit for HP. Unavailable legacy query uses the original canned path;
malformed topology is rejected. A nonempty invalid mock-profile name is refused.

## Reproduce

```sh
make fixtures
REQUIRE_FIXTURES=1 make test
sh src/phxbringup/build.sh /path/to/MacKernelSDK
sh src/phxaccel/build.sh /path/to/MacKernelSDK
```

Apply Cobalt64 0001..0009, then this repository's Phoenix 0001..0008 to Mesa
`f5cb8ee032adabef599ae892ec4e42d796b84da9`. Each generator is an alternative to its corresponding patch, not an additional patch. Build per `mesa-patches-phoenix/README.txt`, then:

```sh
sh tools/test_mesa_topology.sh /path/to/mesa
python3 tools/test_mesa_vulkan_profile.py /path/to/mesa --glslang /path/to/glslangValidator
```

The Mesa-only tests are mocks. They verify topology transport/compiler integration, not GPU
execution, Metal, textures, scanout, interrupts or scheduler behavior on HP.
PR #1 used an external prebuilt AIR translator and did not build the full Metal
bundle. The continuation above adds the pinned source build and real translation
checks; source archives accompany development packages.

## Next required hardware evidence

On Linux booted on the HP, build/run `tools/linux-profile/collect.c` as documented
at its top. Validate the resulting JSON with `python3 tools/phx_profile.py captured.json`.
Keep stderr's IP query results. Also collect the target's PCI `resource` file,
full `device/ip_discovery/` sysfs tree if available, amdgpu initialization log and
matching firmware filenames/hashes. The generic DRM HW_IP query alone does not
identify PSP, SMU, MMHUB or DCN sufficiently.

Next, compare the HP IP/base-address table and firmware layout with the reference,
validate memory reservations against the live GOP scanout, then replace the Firebat
constants with checked per-device data. Only then implement staged HP firmware,
VM, MES/CP, fence and recovery tests. Require a verified GPU write/fence, compute
readback, offscreen rendering/readback, and only subsequently Metal/panel tests
before removing the diagnostic gates. No boot argument bypass is provided.

The existing 780M fallback is preserved and passes mock regression checks. The
baseline has no verified dedicated 740M implementation; synthetic 4-CU validation
must not be described as 740M hardware support. Upstream README performance claims
remain upstream reports about Firebat, not results from this session.
