# Radeon 760M development status

Updated 2026-11-08. Fork: `yt42c2mvn2-cmd/nullarc-760m`.
Branch: `codex/radeon-760m-driver-completion`. Continuation baseline: merged `main` at `f08b898` (PR #1).

**Current verified state:** HP Sequoia 15.8.2, build 39: exclusive VRAM/PSP/MES
bring-up, native fenced compute/render, public Metal compute/render and app access
all pass. Automatic cold-boot initialization and app activation passed in boot
`49800A69-CF26-4E40-91FC-F09883D6268F`. WindowServer/display acceleration, reset
and suspend/resume remain unverified. The current task is WindowServer support;
its framebuffer boot ordering, measured timing and Sequoia ABI must be validated.
Historical implementation notes below describe earlier states.

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

## Postboot installed-translator verification

SSH access resumed. On the HP running Sequoia 15.8.2, the installed plugin,
translator and LLVM/Zstd dependencies exactly match the 0.1.1 Sequoia package.
Fresh compute, vertex and fragment metallib translation passed with empty test
caches and cache reuse disabled. All three HP-produced SPIR-V files passed
independent Vulkan 1.2 validation. Installed RADV/ACO compute/graphics compilation
passed under explicit 8/12-CU mocks with zero GPU submissions.

The loaded accelerator UUID is now independently verified as
A672A59E-9077-35D7-840D-360640764497, matching the rebuilt Sequoia binary. This
confirms module loading, not GPU execution or IOAccelerator service operation.
PhxBringup remains build 34, profile-diagnostic-only and decoded-not-initialized;
development build 35 was not installed. Evidence:
`hardware/dumps/hp_envy_760m/sequoia-translator-postboot-2026-11-08.json`.

## Firmware reservation acquisition continuation

Live HP still has build 34 in diagnostic mode and no NMXAccel/PhxAMDFB service.
IORegistry does not expose its VBIOS or VFCT to the existing user-space collector;
the exported memory-map node is not an EFI reservation map. The GPU's actual
IOService ancestry includes IOACPIPlatformDevice, and IOACPIFamily 1.4 is loaded.

Build 36 adds `src/amd/phx_vbios.h`, production cached-VFCT acquisition in
`PhxBringup.cpp`, its explicit IOACPIFamily dependency and selected collector
fields. It validates the full ACPI checksum, image bounds and exact BDF/device
selection before parsing supported ATOM formats. No VBIOS command execution,
register write, firmware submission, readiness change or fallback mask was added.
Extra, protected and usage memory claims stay distinct and incomplete.

Validation: native PhxBringup compiles with the same three pre-existing shadow
warnings. Nine C++ binaries and 33 Python methods pass. The production parser
passes ASan/UBSan, all truncations of the synthetic image, duplicate/wrong-device
cases and 10,000 mutations. These fixtures are not an HP VBIOS capture. A build-36
diagnostic update is now staged on the already-authorized USB EFI, using the
existing backup/rollback installer. Independent verification confirms the new
binary matches the packet and every parsed configuration value is unchanged.
The new backup is separate from the earlier one. Expected build-36 module UUID:
7B8E4713-0C01-39FB-948B-2CADB5FC8F26. A manual boot/capture is needed before this
metadata can inform a safe HP memory plan. Acceleration remains unimplemented.

## Build 36 boot result and protected firmware capture

The HP booted build 36, UUID 7B8E4713-0C01-39FB-948B-2CADB5FC8F26. Selector 31
returned the expected decoded 512 MiB layout, but firmware parsing returned
`unsupported-atom-format`. No firmware reservations were established. Evidence:
`hardware/dumps/hp_envy_760m/sequoia-build36-postboot.json`. The reader failed to
expose which header version was unsupported; treating the reboot as completed
hardware bring-up would be incorrect.

Build 37 corrects that diagnostic gap. The selected VFCT image is cached before
format-specific decoding, actual validated common-header revisions are reported,
and new root-only selector 32 supports private snapshot capture. `phxprofile
--dump-vbios NEW_FILE` creates a private new file with strict reply checks and
failure cleanup. This allows user-space inspection/parser development against
actual bytes without a kernel reboot for each parser iteration. Unknown ROM and
master formats still do not inherit existing layouts.

Native PhxBringup and the Sequoia capture CLI compile. Nine C++ binaries and 34
Python methods pass; parser ASan/UBSan and 10,000-mutation cases pass. Mock capture
transport tests verify cleanup, no-overwrite and exact lengths, not kernel
authorization. On actual HP build 36 the new CLI's existing topology query still
passes, and snapshot capture refuses before creating a file. Build-37 root
authorization/snapshot operation remains a runtime test. No HP PSP/MES command,
GPU memory initialization or GPU submission was enabled or executed.

Build 37 is now staged on the confirmed USB EFI with a separate rollback backup.
Independent comparison verified the staged binary and unchanged parsed config.
Expected module UUID: 389AD4FD-0B13-3162-AD0E-DFC7443A9CC2. The matching tool and
source packet are on the HP under the existing Shared test directory. Manual
reboot followed by the root-only private VBIOS capture is pending. Build 36 was
the last independently verified running kernel. Staging is not GPU initialization.


## Build 37 capture result and build 38 integration

The HP successfully booted build 37 and its protected VFCT snapshot worked.
The private 16,896-byte image has SHA-256
`e94afef0bb72e8fd2d3e1695dfb55b9a201a8eff1891be0f06a531ceed6ac40a`.
It contains ROM 2.3/master 2.1, firmware-info 3.4 and usage 2.1. The decoded
extra firmware field is 2 MiB; usage start and both usage sizes are zero.
Zero-valued usage fields do not prove ownership or a complete reservation map.
The full ROM remains private. A sparse hexadecimal, non-executable metadata
fixture and `hardware/dumps/hp_envy_760m/vbios-metadata.json` make the parser result
reproducible. Build 38 adds the measured ROM prefix, preserving unknown-version
rejection and original 2.2 handling.

The new read-only scanout CLI ran with local administrator authentication on
running build 37. Evidence is
`hardware/dumps/hp_envy_760m/sequoia-build37-scanout.json`. All 48 documented DCN
3.1.4 reads succeeded; two consecutive samples match. HUBP0 primary/secondary
raw address low/high are 0/0x80; pitch is 0x77f and viewport 0x04b00780. The other
three captured viewports are zero. No ownership conclusion follows from these
raw samples; cursor, firmware and DMCUB reservations are not fully captured.
No new reboot or HP hardware writes were needed for this read.

PSP fixes in build 38:
- Reject TMR requests above the existing capacity, instead of silently clamping.
- Record confirmed TMR bytes only after transport success and zero PSP status.
- Preserve/quarantine buffers after failed command fences or unacknowledged ring
  creation/destruction. Require acknowledged destruction before reuse.
- Serialize staging-state validation with the PSP lock and reject staging while
  quarantined. Validate producer indices before command-buffer changes and skip
  the cleared zero fence value on wrap.
- Add selector-106 LOAD_TOC operation and `phxctl toc BYTES`; return required TMR
  bytes from the documented response offset +16. Existing raw response ABI stays.

These controller fixes do not remove HP diagnostic restrictions. No PSP/MES
command or native GPU command has been executed on the HP by this work.

Validation: the complete macOS-15 stack builds (both kexts, plugin, translator,
RADV and four tools). Nine C++ binaries and 36 Python methods pass. The measured
metadata parser passes ASan/UBSan and the existing 10,000 mutation cases. Actual
CLI transport tests cover scanout failure/short replies/wrong GPU and TOC status,
size/shape/error handling with explicit host mocks. PSP quarantine state tests
cover failed completion and failed/successful destruction; they are not hardware
DMA/recovery tests. Build 38 is not installed on the HP. The running build remains
37; previously installed translation/compiler tests remain CPU-only evidence.

Still required: establish exclusive GPU memory reservations, implement the HP
PSP/SMU/GART/MES initialization using those allocations, and verify native fences
and readbacks before accelerator/Metal/display activation. Full acceleration has
not been achieved. A successful full binary build does not change that status.


## Build 39 — coupled reservation and engine experiment

Implemented, not yet runtime-tested on HP:
- `phx_vram_arena.h`: exclusive interval leases, exclusions, stale-handle checks,
  pinning and quarantine. PSP/TMR/staging/MES regions cannot overlap.
- `phx_hp_memory.h`, reservation register profile and Sequoia capture: exact live
  configuration gate, with only documented status bits ignored. The measured
  9,216,000-byte console is conservatively protected through 16 MiB; active DMCUB
  windows lie in firmware's top 2 MiB. Captured hardware cursors are disabled.
- PhxBringup selector 115: administrator-only explicit start; exclusive PCI open,
  live reservation checks and allocations precede DMA enable. No boot auto-start.
- PSP: dynamic LOAD_TOC-sized TMR, separate MC/physical address calculation,
  all 17 successful engine-firmware acknowledgements before RLC autoload.
- MES/GART: owned scratch/default page, 64-bit fences, bounded ring-space checks,
  wrapping packet writes, real firmware-header PCs and abort-on-failure handling.
- Queue adoption: leases, cross-queue overlap/doorbell checks and actual kernel
  RELEASE_MEM acknowledgement before ready flags. Native GB_ADDR_CONFIG is read
  after engine power-up; HP BO budgets use its decoded sizes.
- PhxAccel/framebuffer: HP requires positive native claim and cleared diagnostic
  property; boot arming remains separate. Source build includes native compute
  and offscreen translated graphics probes plus explicit `hp_bringup.py` harness.
- Build/release: probe source receipts, glslang input, validated shader fixtures
  and an explicit administrator-only experimental package policy.

Fresh Linux capture confirmed a 64 MiB PSP TMR at Linux MC address 0x8018000000;
that address is not imported into macOS. Linux and Sequoia firmware/cursor/window
captures are separately labelled under `hardware/dumps/hp_envy_760m`. The
Sequoia samples differ only in HUBP0 status, not allocation configuration.

Host tests cover exact capture mismatch rejection, firmware sequencing, allocator
fragmentation/stale handles/quarantine and MES counter rollover. Hardware driver
initialization, native shader readbacks, Metal, display and runtime recovery
remain unverified until the explicit experiment succeeds. Retaining DMA-exposed
memory and requiring reboot is the current failure policy; no GPU reset or
suspend/resume implementation is claimed. Build-38 release assets are unchanged.

Build-39 static validation completed: full Sequoia stack (both kexts, plugin,
translator, RADV and six native tools), ten C++ binaries and 37 Python methods
passed. Captured-profile/arena tests passed ASan/UBSan. Metal/AIR/SPIR-V and ACO
offline validation passed for explicit 8/12-CU mocks with zero submissions.
The native probe correctly rejects mock transport. No HP engine command has
yet been issued; the running HP kext is still build 37.

### HP build-39 installation check

The HP preparation report confirms component backup/copy and USB EFI backup/copy
completed. Backups are `/Users/Shared/nullarc-component-backups/backup-oz84ev5b`
and `/Volumes/EFI/EFI/OC/.nullarc-diagnostic-backup-xt4k7k6k`. Independent SSH reads
verified both installed binaries against the package: PhxBringup UUID
`014F7217-A726-3497-A963-604079AADD1F`, PhxAccel UUID
`535B5212-AD0C-34E1-9F0F-489176793105`. The parsed OpenCore configuration is
unchanged. The currently running kext is actually build 38 (UUID
`17848C8F-1493-39EB-AD2A-0A99FDFBF572`), not build 37; the old accelerator UUID
`A672A59E-9077-35D7-840D-360640764497` remains loaded.

Preparation stopped at the update request: Sequoia rejected `--start-only`.
Its live `kmutil help load` documents `--load-style start-only`. The source
installer now uses that syntax and checks capabilities before copying files.
Three command-boundary regression tests pass without loading any extension.
The original experimental39 ZIP contains the faulty preparation helper; do not
rerun it to request the update. For this already-staged HP, the pending local
administrator command is:

```
sudo /usr/bin/kmutil load --bundle-path /Library/Extensions/PhxAccel.kext --load-style start-only
```

No OS update approval, new loaded UUID, reboot, GPU initialization, native shader
execution or acceleration success is inferred from the installation report.

### Build-39 modules now loaded

SSH verification after the user update confirmed both matching build-39 UUIDs
listed above are actually loaded. The live registry reports `phx-build=39` and
`phx-stage=profile-diagnostic-only`; installed binary hashes match the package.
The read-only hardware harness preflight passed package hashes, firmware plan,
firmware entry points and the running kernel UUID. No GPU command was issued.
The explicit local administrator experiment is prepared as
`/Users/Shared/nullarc-760m-sequoia-test/hp39-test.sh`, writing its report to
`/Users/Shared/nullarc-760m-sequoia-test/hp39-execution/result.json`. Native shader
readbacks, accelerator claim, Metal and display acceleration remain unverified.

## Native GPU and public Metal execution confirmed on HP

The actual build-39 hardware experiment completed all 40 stages successfully on
Sequoia 15.8.2. Evidence is committed under
`hardware/dumps/hp_envy_760m/sequoia-build39-native-execution.json`; the full loaded
module list was removed to avoid publishing unrelated kernel addresses.

Confirmed: exclusive HP VRAM bootstrap, PSP ring, TOC-reported 64 MiB TMR and
successful TMR setup, all 17 engine firmware acknowledgements, RLC autoload, SMU
responses, GART acknowledgement, MES resource/status/queue commands, real compute
and graphics packet readbacks, kernel queue adoption, native Darwin RADV GLSL
compute (256/256), translated Metal store (7), translated offscreen rendering
(256/256 pixels), and accelerator claim. Live registry reports
`native-queues-ready` and an active NMXAccel. This is native macOS hardware
execution, not Linux RADV, compiler simulation or immediate software retirement.

Public Metal tests also passed twice, including the new strict HP probe:
4096/4096 computed values; command-buffer status Completed with no error; a
256x256 offscreen render with 32,640 red pixels, 32,896 blue pixels and zero
other pixels. `sequoia-build39-metal-execution.json` records the strict run.
`mtlprobe --hp` verifies the actual accelerator PCI ancestry and all five HP
identity fields, rejects mocks, and permits no default-device fallback. The
probe refused the development Mac's RX 5700 XT without GPU submissions.

Changed components this stage: `mtlprobe.m` now requires completed/error-free
command buffers and checked allocations; build receipts fingerprint/package the
probe; `hp_bringup.py --claim` verifies installed runtime hashes and performs
public Metal tests after the native probes. `hp_boot.py` and
`install_hp_boot.py` add an explicit `install.sh --hp-native` service that keeps
WindowServer denied, repeats hardware/Metal checks each boot, and disables retries
after interrupted/failed initialization. The installer checks matching installed
binaries/loaded UUIDs and makes no kext, EFI, security or NVRAM changes.

Validation: full Sequoia stack build passed, ten C++ binaries and 45 Python methods
passed during that build; the added stale-boot-status test brings boot tests to
six. The prior offline shader receipt still matches all rebuilt plugin,
translator and RADV binaries. Both rebuilt kext binary hashes exactly match the
HP's running tested binaries; no kernel reinstall is needed for this stage.

Still pending: first cold-boot test of the new app service, real application
coverage, WindowServer/panel acceleration, reset/recovery and suspend/resume.
The old reference WindowServer script cannot simply be enabled: it exits on the
HP diagnostic boot, while PhxAMDFB's HP gate requires a native claim that occurs
later in user space. Correct framebuffer/boot ordering and a dedicated display
experiment remain necessary. Current successful tests are compute/offscreen
rendering; the firmware framebuffer still drives the panel. No new display gate
was removed or NVRAM arming performed.

### HP app-only boot service installed

The user ran the native boot installer. Independent SSH verification confirmed
`/Library/LaunchDaemons/local.nullarc.hp-native.plist`, its exact launch arguments,
and all 82 package files under
`/Library/Application Support/NullArc760M/package-3d1c70d5e9d3e6d6`. The service
and entire package are root-owned and not writable by group/others. No pending
or disabled marker exists; the boot-status file is absent, consistent with no
service execution yet. Current manually initialized queues remain ready. The
next required step is a manual reboot with the same USB, followed by fresh boot
status, running UUID and real Metal verification. Cold-boot success and
WindowServer acceleration are not yet claimed.

### First automatic boot: native execution passed, Metal publication check failed

Boot session `1E5E00C3-38CE-4D4F-86A7-8D09557D3F2C` differs from the previous
manual test. Its protected report confirms all PSP/MES/queue stages, native
compute, translated compute/render and accelerator claim passed. The immediate
`metal-hp-device` check exited 1 after 9.65 ms with `devices: 0`, `no Metal device`
and empty stderr. NMXAccel was published by the later SSH inspection. The
harness conservatively marked the driver lost; the boot service retained pending/
disabled markers and did not enable app access. No GPU command was retried.
The redacted cold-boot report is committed beside the successful manual reports.

`claimAccel` requests asynchronous IOKit matching. The fix candidate therefore
waits for Metal publication using fresh enumeration-only processes, bounded by
a 30-second budget and individual command timeouts. Only an empty catalogue
has the new explicit temporary exit 75; a wrong device, probe error or lost
kernel stops immediately. Four publication tests and eight boot-control tests
pass. Public boot status now includes exact stage/verification results without
raw module lists, and timed-out stages are retained in the detailed report.

`recover_hp_boot.py` stages a future-boot-only update after independently
validating this precise failure and identical kernel, driver, native execution,
firmware and shader-fixture bytes. It backs up the old daemon and markers, checks
configuration readback and rolls back on failure. Four recovery tests cover
success, changed native code refusal, unrelated failure refusal and rollback.
No kext, EFI, NVRAM or security change is needed. The current boot remains lost;
the corrected publication sequence requires a new boot and is not yet confirmed.
Only the Metal diagnostic executable was recompiled; all other compiled inputs
and artifacts matched the prior full-build receipt before updating that receipt.

### Second automatic boot: system-context Metal enumeration remained empty

Boot `D33E3ACC-D5BD-44FD-8F43-74CB6CF40F55` again confirmed native compute and
translated graphics, but Metal enumeration timed out after the bounded wait.
The public stage report is committed as `sequoia-build39-system-metal-timeout.json`.
The original race-only hypothesis was insufficient. Current queues were marked
lost by the old all-stages abort policy; no GPU commands were retried in this boot.

The HP currently has console UID 501 and a GUI launchd domain. Its installed
`launchctl(1)` manual confirms `asuser` adopts the target bootstrap namespace,
exception server and audit session, but does not change credentials or user
environment. The new boot path uses `launchctl asuser` together with `sudo -n -H
-u` for the actual console user. This is a context correction candidate, not a
claim that the second failure's underlying framework cause is fully established.

`hp_bringup.py --execute --claim --defer-metal` now returns verified native
execution and accelerator claim to the boot supervisor. The supervisor waits
for a real console GUI session, then runs strict HP Metal device/compute/render
checks with that user's credentials, bootstrap and private shader caches. Only
successful readbacks enable app access. A missing GUI session or empty Metal
catalogue keeps app access restricted and retains healthy native queues; actual
shader-test failures still request conservative abort. No GPU register values,
firmware, kernel, translator or RADV binaries change.

Fifteen boot/supervisor tests, four publication tests and five recovery tests
pass. They cover session credential/bootstrap selection, missing session/device
without GPU abort, shader failure with abort, exact native-proof requirements,
public report filtering, reviewed timeout recovery and rollback. These host
fixtures do not claim GPU execution. The GUI-session startup path requires a
fresh HP boot because the current boot was already marked lost by the old code.

### Third boot: automatic native initialization plus post-boot Metal confirmed

Boot `3D411909-7D79-4A0F-9ABC-04366A28A0AE` completed automatic native
initialization and retained `native-queues-ready`. The console-user enumeration
command hit its five-second deadline; no Metal shader was submitted by the boot
supervisor, which correctly retained healthy queues rather than marking them
lost. Subsequent SSH tests, without reinitialization or reboot, verified exact HP
PCI ancestry, Metal compute 4096/4096, completed/error-free command buffers and
all 65,536 render pixels (32,640 red, 32,896 blue, zero other). The report is
`sequoia-build39-automatic-native-postboot-metal.json`.

A concrete publication prerequisite was found in PhxAccel: it removes
`MetalPluginName` while awaiting PhxAMDFB and restores it through the existing
60-second headless callback. Live NMXAccel now exposes the property and
`NVAccelHeadless=true`, matching that path. The previous waits did not account
for this deliberate driver policy. The helper now waits for that exact property
under the exact claimed HP PCI device, within a 90-second software budget, before
entering Metal. It does not bypass the display gate or shorten the kernel timer.
The ioreg command must include `-l` to obtain descendant properties; that was
verified against actual HP output and corrected in the evidence collector too.

A verification-only continuation validates healthy queues, both loaded module
UUIDs and installed runtime hashes, then repeats user-session Metal tests. It
never calls PCI/PSP/SMU/GART/MES initialization. The reviewed updater can stage
the new immutable service and invoke this continuation on the existing healthy
GPU, avoiding another reboot. Shader-test failure still aborts; an absent Metal
catalogue does not. App access remains restricted until real readbacks pass.
Thirty targeted publication/boot/recovery tests and four collector tests pass.
All compiled inputs and artifacts remain unchanged; only Python/control/docs
assembly is needed. Future cold-boot publication handling and current-session
app activation still require their actual runtime results.


## Automatic apps verified; WindowServer integration in progress

Fresh boot `49800A69-CF26-4E40-91FC-F09883D6268F` passed automatic native
initialization, console-user Metal compute/render and app activation. Saved report:
`hardware/dumps/hp_envy_760m/sequoia-build39-automatic-app-activation.json`.
This supersedes the earlier pending-publication notes above.

The administrator's read-only build-39 display capture measured stable 1920×1200
active timing, 2260×1240 totals, H porch/sync 48/32, V porch/sync 3/6, H+/V−,
and approximately 60 Hz. PLL clock was not read; 168144000 Hz is the derived
nominal clock at 60 Hz. CoreDisplay's four current shader entries translated,
passed independent SPIR-V validation, and three PSOs compiled through the plugin's
real pipeline-layout model using the explicit mock. No GPU execution is claimed
for that preflight; Apple shader binaries are private and not redistributed.

Modified components: shared `phx_hp_display.h`, PhxAMDFB, AGDC timing replies,
NMXAccel runtime size/plan diagnostics and HP pipe guards; staged display installer,
boot supervisor, packaging and tests. PhxBringup build 39 and the translator/RADV
runtime are preserved. The early CPU console path resolves the previous circular
ordering (framebuffer needed native claim, while WindowServer needs an early
framebuffer). The new installer requires an app-mode validation reboot before it
can arm one display boot. It does not modify USB EFI or security settings.

Sequoia PhxAccel compilation and the complete host `make test` suite pass, including
captured-plan bit mutation tests, display arm ordering/failure tests and installer
backup/rollback/concurrent-edit tests. Current HP display module is still the
previous app-tested UUID. Next required hardware step: install this display module
with NVRAM unchanged, reboot and validate its ABI/console diagnostics and app tests;
then authorize the one-shot display boot. WindowServer, reset and suspend/resume
remain unverified. Do not report accelerated desktop support from these host tests.

HP-side strict signature validation caught an assembly bug that omitted the
accelerator's `_CodeSignature/CodeResources`. Kext copying now preserves seals,
assembly verifies PhxAccel strictly, and a regression test covers resource copying.
The unchanged OpenCore PhxBringup build is unsigned; no signature or USB change
is introduced there. Unexpected kmutil failures now stop the display installer
with the staged files and backup retained for review.


### Display module cache mismatch after app-mode reboot

Boot `A268D201-2389-4FF2-9E4D-388C08F5E56B` loaded the old PhxAccel UUID
535B5212-AD0C-34E1-9F0F-489176793105, although the installed module and immutable
`package-display-eylbejlw` contain 633BB085-1049-336E-B87E-C1626D9B5417. The
wrapper stopped at its UUID comparison before hardware execution; PhxBringup is
diagnostic, NMXAccel/PhxAMDFB absent, framebuffer NVRAM arming absent. USB OpenCore
injects only unchanged PhxBringup. Actual auxiliary-collection inspection confirms
that collection still contains the old UUID, alongside three unrelated extensions.

`update_hp_aux.py` repairs only this reviewed pre-GPU failure. It builds an aux-only
candidate against the existing exact-system boot/system collections, using the
documented missing-KDK option already used by reference `kinst.sh` (HP has no KDK),
without that script's `-z` authorization bypass. Before backed-up atomic publication
it requires exactly the previous extension set, all other entries unchanged, and
the new accelerator UUID. It preserves/moves failure markers only for this exact
failure to enable the next app-mode boot; it submits no GPU work and never arms
WindowServer or reboots. Seven host tests and parsing of the actual four-entry HP
collection pass. Candidate build/publication and new module runtime remain pending
local administrator authentication. Do not blindly remove failure markers.

The first preparation wrapper also pinned the pre-firmware assembly manifest;
its guard correctly aborted without installing. The wrapper was corrected against
the final ZIP, whose manifest and all 86 payload files were verified on the HP.


2026-11-09 continuation: boot 244C6F83-6643-4738-972F-AFD31C541945 still loads
535B5212 and is diagnostic-only. The auxiliary updater stopped before building
because it required a protected report from the same boot; a disabled boot creates
only a fresh public status. The updater now validates the latest protected
initialization attempt across disabled boots, never skips a newer unsafe attempt,
and independently verifies this boot's idle hardware, zero module references,
stale collection identity and failure markers. Ten targeted tests pass. The root
wrapper now saves filtered protected-report/candidate diagnostics on failures and
independently verifies the published UUID before printing READY TO REBOOT. No new
kernel build, GPU initialization, cache publication or WindowServer arming is yet
verified for this continuation; the corrected root operation is pending.


### Actual auxiliary link error: missing ACPI dependency

The corrected updater reached kmutil create and returned KMErrorDomain 31:
`IOACPIPlatformDevice::metaClass` could not bind. No collection was published.
PhxAccel's new read-only VFCT path imported that class but its OSBundleLibraries
omitted IOACPIFamily; PhxBringup already declares the same dependency. The HP
loads IOACPIFamily 1.4, compatible with minimum 1.0. PhxAccel now declares
`com.apple.iokit.IOACPIFamily = 1.0`. This is a linkage correction, not an AMFI
rejection; the HP already loads AMFIPass 1.3.1. No security changes are requested.

The signed metadata fix preserves every compiled program byte outside the trailing
signature (including UUID 633BB085). `fix_hp_acpi_dependency.py` clones the immutable
package, verifies this exact dependency-only change, backs up disk/daemon state,
and invokes the guarded aux updater bound to the original protected failure.
Failed linking restores metadata when the collection is unchanged. Four added
metadata/rollback tests and ten aux tests pass. Candidate linking, new module load
and WindowServer remain pending actual HP root/runtime tests.
