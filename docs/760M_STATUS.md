# Radeon 760M development status

Updated 2026-11-08. Fork: `yt42c2mvn2-cmd/nullarc-760m`.
Branch: `codex/radeon-760m-driver-completion`. Continuation baseline: merged `main` at `f08b898` (PR #1).

**HP macOS acceleration is not functional or hardware-tested. This branch intentionally
allows only diagnostics on the captured HP PCI identity. Do not install an upstream
780M release expecting these source changes.** A diagnostic kext is now staged in the user-confirmed USB EFI with a backup;
its diagnostic load is now verified on Sequoia. Older acceleration files were
already present on the HP; replacement tests are being prepared.

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

## Live Linux continuation (2026-11-08)

- **Measured evidence:** `hardware/dumps/hp_envy_760m/linux-2026-11-08.json`
  records Linux Mint 22.3, kernel 6.14.0-37, all 39 IP instances, device-info
  fields, 512 MiB UMA VRAM, firmware versions and decompressed-file hashes.
  No capture errors. The live topology exactly equals the supplied JSON.
  Critical GC 11.0.1 / MP0+MP1 13.0.4 / SDMA 6.0.1 / MMHUB 3.0.1 / DCN 3.1.4
  versions and segment bases match the reference. Linux memory state does not
  reserve any corresponding region under macOS.
- **Real hardware execution:** hardened `vkprobe` refuses CPU fallback, invalid
  queue selection and incorrect readback. The HP passed 256/256 compute values on
  compute-only and graphics-capable queues. Actual authored MSL passed through the
  packaged Metal plugin/AIR reader/translator and executed on stock Linux RADV:
  compute returned 7; vertex+fragment draw returned 256/256 correct RGBA pixels.
  Fences and host barriers were used. Vulkan validation reported no errors.
  `tools/test_linux_gpu.py` reproduces these offscreen tests and records hashes.
  **This does not test the macOS kernel, Darwin winsys, Metal API device or panel.**
- **Firmware integration:** `rdna3_ucode_extract.*` now supports MES scheduler and
  KIQ v1.0 code/data offsets with atomic rejection of incomplete/overlapping ranges.
  `phxfw` validates the complete Phoenix firmware set and staging capacities before
  `bringup5.sh` arms a watchdog or stages bytes. The live image differs from old
  constants in MEC, MES and RLC payloads; header-derived offsets avoid truncation
  and loading the wrong bytes. RLC_G remains last. The reference staging/PSP/TMR
  addresses remain unchanged and are not enabled for HP. Bounds/header checks are
  not cryptographic authenticity or firmware runtime compatibility verification.
- **Measured RADV properties:** generated `phx_hp_760m_device.h`, generator and
  Phoenix patch 0009 apply only to the exact HP topology identity. Chip revisions
  12/13, 100000 kHz counter, 2600000/800000 kHz clock caps and cache geometry replace
  the 780M capture's assumptions. Timestamp period is 10 ns in the HP mock; the
  legacy mock remains unchanged. No Linux VA ranges, heap budgets, flags, firmware
  versions or readiness bits are imported. Runtime clock telemetry is still absent.
- **Validation:** new firmware-plan/pre-watchdog and measured-profile tests; both
  firmware generations pass complete preflight; ASan/UBSan includes MES malformed
  and truncation cases; Mesa patch/generator 0007..0009 roundtrip, 8/12-CU compiler
  regressions, native source builds and final package checks are recorded below.
  See `docs/LINUX_VALIDATION.md` for exact runtime scope and reproduction.

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
- Original profile contains no IP-discovery versions or runtime configuration.
  The later Linux capture above independently confirms its topology and adds
  IP/firmware/device properties; macOS reservations and initialization remain unverified.

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

Apply Cobalt64 0001..0009, then this repository's Phoenix 0001..0009 to Mesa
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

## Next required hardware integration

The Linux evidence gap is closed for topology, IP/base tables, memory inventory
and firmware identification. Keep the HP diagnostic gate until macOS-specific
memory/scanout reservations and PSP/TMR addresses are derived and verified. The
remaining Firebat literals in `mesboot.c` and raw PSP requests are not an HP plan.
Next collect the new PhxBringup diagnostic properties on Sequoia, verify actual
MC/physical mapping and firmware-framebuffer ownership, then implement bounded
PSP/SMU, VM and MES/CP stages. Require a real NullArc write/fence, compute readback,
offscreen rendering and only subsequently Metal-device/panel tests before enabling
acceleration. Tahoe runtime validation, suspend/resume and hardware reset/recovery
are still outstanding. Linux success cannot remove these gates.

The existing 780M fallback is preserved and passes mock regression checks. The
baseline has no verified dedicated 740M implementation; synthetic 4-CU validation
must not be described as 740M hardware support. Upstream README performance claims
remain upstream reports about Firebat, not results from this session.

### Final validation for the Linux-evidence stage

Both kexts, the full Metal plugin, pinned translator, patched RADV and all four
CLI tools built successfully. Seven host C++ binaries and 20 Python test methods
passed with firmware fixtures; the actual firmware extractor also passed ASan/UBSan.
Mesa transport tests passed 134 legacy checks plus topology cases; patches 0007..0009
match their generators byte-for-byte. The packaged MSL-to-AIR-to-SPIR-V-to-ACO
compute/graphics tests passed under both 8-CU and 12-CU mocks, including the new
10 ns HP timestamp-property check. Ten Linux hardware-test/build/validation steps
passed; the current translated shader hashes match the HP-tested receipt.
Existing kernel field-shadow and plugin protocol/deprecation warnings remain.
No macOS device was activated, no target EFI was changed, and no firmware/register
write or driver reload was performed outside normal Linux Vulkan submissions.

The final review also hardened the actual `mesboot.c`: every IOKit transport and
reply size is checked; MES completion timeouts and failed compute/graphics
readback stop the process before queue adoption. Unknown/incomplete commands fail
before opening IOKit. An injected-transport build of the real source tests Hello,
register reads, staging writes, claims, short replies and scheduler timeout paths.
These host cases do not execute GPU commands. Other experimental VM/SDMA branches
still need runtime work; no hardware reset or HP initialization was added.

## Installer release engineering (2026-11-08)

The release pipeline now assembles source-built artifacts instead of snapshotting
installed drivers or mounting EFI. Root installer/uninstaller scripts and a
fork-specific guide are included. The archived upstream guide is preserved as
`docs/INSTALL_REFERENCE.md`. HP diagnostics have shell entrypoints with explicit
EFI/OC selection, backup and removal. Exact PCI detection refuses `--windowserver`
even if an older loaded kext lacks a diagnostic marker. Reference installation
copies the newly required `phxfw` and checks the entire header-derived firmware plan.
Python bytecode writes are disabled before importing package helpers, preventing
checks from modifying the hashed package.

New shell-level tests exercise diagnostic install/remove, HP WindowServer refusal,
unreadable PCI inventory, package tampering and ZIP executable/timestamp handling.
These use temporary EFI fixtures and injected PCI facts; they are not kext-load or
GPU tests. The prerelease includes measured unmodified AMD firmware under its
redistribution license, matching source archives, checksums and explicit HP limits.
The existing `alpha` tag is retained; binary provenance is recorded separately.

Release validation: both kexts, the full Metal plugin, pinned translator, patched
RADV and four tools rebuilt successfully. Seven host binaries and 25 Python test
methods passed. Shell-level checks preserve temporary EFI state on refusal; no
macOS driver was installed or loaded on the build host or HP. Existing native
compile warnings remain. The release's WindowServer path is present but still
refuses the diagnostic HP identity.

## WindowServer continuation: runtime access required

The installer command is present, but HP firmware/MES/VM/display bring-up is not
implemented and verified sufficiently to enable it. Both known SSH endpoints
(Linux `192.168.1.68`, macOS `192.168.1.148`) timed out during this continuation;
no current HP OS or driver state was inferred. Last verified installed macOS was
Sequoia 15.8.2; the acceleration/plugin binaries target Tahoe 26.

`tools/collect_macos_evidence.py` now preserves the existing PhxBringup memory
status, MC base, size, physical offset, BAR aperture and HDP properties. Previously
these were dropped from the report despite being exported by the kernel. A new
fixture test verifies exact property transport, omission of unavailable values
and preservation of diagnostic-only state. Eight targeted collector/installer
tests passed. No native source changed, so a native rebuild was not required.
This is a diagnostic collection fix, not completion of the WindowServer path.
No new raw register values, reservations, firmware interface or readiness claims
were added; no target EFI or released binary asset was changed. The next step
requires the HP back in macOS with SSH, then actual memory/scanout ownership and
staged firmware/queue/fence validation.

## Sequoia compatibility continuation

The user requires Sequoia because another required kext does not support Tahoe.
Live SSH reconfirmed HP Sequoia 15.8.2 (24H232), x86_64. The old package actually
contained macOS-26 deployment commands in the plugin, translator, RADV, four tools,
libelf and zlib. `--min-macos 15.0` now rebuilds/selects compatible artifacts, writes
the plugin minimum OS and records the selected Mesa build/OS in the receipt.
`macos_target.py` inspects all packaged x86_64 Mach-O deployment commands, including
copied dependencies; it caught a cached macOS-26 translator and refused assembly.
Rust target caches are now separated by deployment target; a clean 15.0 build passed.
A pinned-source libelf builder provides macOS-15 libelf and pkg-config metadata for
SDK system zlib, so no macOS-26 MacPorts zlib binary is copied into the port.

The plugin built with unguarded newer-API availability treated as an error. On
the actual HP/Sequoia, RTLD_NOW loading, compute/vertex/fragment metallib translation
and RADV/ACO compute+graphics pipeline compilation with explicit 8/12-CU mocks
passed. Zero GPU submissions, no Metal device construction, and no native GPU
acceleration proof. Evidence is in `hardware/dumps/hp_envy_760m/sequoia-runtime-2026-11-08.json`
and `sequoia-translation-test.log`. The translated compute shader is byte-identical
to the earlier Linux hardware-tested fixture; this is not macOS GPU execution.

With explicit user approval, the current diagnostic PhxBringup was installed into
the confirmed USB EFI. The installer made a restorable backup; an independent
comparison verified all unrelated config/security values and kext bytes. No reboot
was performed by the agent. PhxBringup was absent before reboot. Native bring-up,
scanout ownership, firmware/MES and macOS readback remain blocked pending that test.

The user rebooted with the confirmed USB EFI. Live SSH/IORegistry now verifies
PhxBringup build 34 active on Sequoia, selector/profile diagnostic state and decoded
memory: MC base 0x8000000000, physical base 0x260000000, 512 MiB total and 256 MiB
CPU aperture. This is a loaded diagnostic service, not initialized GPU queues.
The physical base differs from Firebat's 0x6a0000000 and cannot be substituted by
assuming the 780M layout. Firmware/TMR/scanout reservation validation is still needed.

PhxAccel and older Metal bundles were already installed on the HP; the module is
loaded but NMXAccel/PhxAMDFB services are absent. The new Sequoia accelerator build
selects the existing Sequoia base-class headers without NM_TAHOE forwarding code;
the default Tahoe build retains it. Its native load is not yet tested.
A transactional `--components` installer provides a separately backed-up file
replacement test. It keeps phxboot-off, refuses an existing boot daemon, does not
rebuild the kernel cache or load a module, and never arms WindowServer. A password
is required locally for protected paths; the SSH session has no noninteractive
sudo access. Copy/restore and failure-injection tests cover this mode.

Final Sequoia host checks passed: seven C++ binaries and 32 Python methods,
including deployment-command dependency rejection, target-specific receipt checks
and component-copy failure rollback. Native source builds and the actual HP
user-space compiler/load tests above passed. This does not validate the new
accelerator's runtime load or the native GPU command path.

## Installed Sequoia components (2026-11-08)

The user ran the protected `--components` installation on the HP. Independent
SSH hashing verifies the installed PhxAccel (2 files), NVMTLDriver bundle (9),
RADV directory (3) and disabled bring-up directory (20) against the published
0.1.1-sequoia-alpha package. The backup directory exists; its root-only receipt
requires administrator access to verify. `phxboot-off` exists and no boot daemon
is installed. The old accelerator UUID AA33BEDC-8AC7-3EE4-87BE-A45D328C46A1 remains
loaded, while the rebuilt binary on disk is A672A59E-9077-35D7-840D-360640764497.
File installation does not establish a successful new-module load.

The actual installed plugin passes RTLD_NOW and compute/vertex/fragment AIR
translation. Installed RADV/ACO passes compute and graphics pipeline compilation
under explicit 8/12-CU mocks with zero submissions. This verifies installed
user-space dependencies, not native GPU execution. The existing `alpha` prerelease
now includes the Sequoia ZIP, diagnostic kext ZIP, matching checksum file and
build-time validation receipt. Its tag is unchanged; each binary package embeds
its matching source commit, and older Tahoe assets remain separate.

A target-local administrator command completed package/backup verification and
idle-service checks, then unloaded the old module. The new start-only load was
refused with KMErrorDomain 28 (reboot required); restoring the old module was
refused with code 27 (approval required). Neither accelerator UUID remained
loaded. This is a failed live-load test, not a successful kernel link/start.
No device matching or GPU initialization was requested. Normal Sequoia extension
approval and a user-controlled reboot are the next test; no security bypass was
attempted. PSP/TMR/GPUVM/scanout ownership, native queues, command
completion and Metal/display acceleration remain unimplemented or unverified.

## Runtime memory integration continuation

The user reports both kexts loaded after the load/reboot discussion. Exact loaded
accelerator UUID and new postboot state remain independently unverified because
SSH is unreachable. Work proceeds without treating that report as GPU readiness.

Build 35 adds the shared `phx_memory_layout.h` wire contract/decoder and kernel
selector 31. `PhxBringup.cpp` exports the attach-time raw/decoded memory snapshot;
`PhxExecutionPolicy.h` shares its decoder and adds production queue/aperture span
checks. `mesboot.c` reads and validates this contract, supports a read-only `layout`
step, derives address bases from it and stops mismatched/diagnostic/lost plans
before mutations. Remaining Firebat register/default-page constants are explicitly
restricted to the reference memory geometry. No HP initialization was enabled.

Queue adoption now rejects integer wrap, uint32 offset truncation and overlap of
ring, writeback and fence spans. VRAM accesses are bounded by both decoded VRAM
and BAR extent; PSP staging includes rounded final-dword bounds. Doorbell and
system-debug offsets use overflow-safe subtraction checks.

Validation: eight C++ host binaries and 32 Python methods passed, including
malformed/short memory replies, HP/reference layouts, diagnostic/lost/mismatched
pre-mutation refusal and queue overflow/overlap cases. ASan/UBSan memory and
execution-policy cases passed. PhxBringup and Sequoia PhxAccel native builds and
Sequoia mesboot compilation passed; three existing PhxBringup shadow warnings
remain. Neither build 35 nor native GPU execution was runtime tested. Existing
0.1.1 release assets remain unchanged; their matching source is the older commit.
Next required hardware evidence remains macOS memory/scanout/firmware reservation
ownership before PSP/TMR/GPUVM/MES initialization can be implemented safely.
