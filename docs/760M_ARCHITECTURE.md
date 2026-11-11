# Actual source dependencies and HP 760M gaps

The root README was read before modification. Its production stack matches the
current source; several older notes describe earlier experiments and a separate
mock driver, so their success labels do not apply to HP hardware.

Current runtime evidence: build 39 successfully initializes the HP PSP/TMR,
firmware, GART and MES, validates kernel queue fences, executes native Darwin
RADV compute/render and passes public Metal compute/render readbacks. The older
inventory/gap notes below describe the starting state; the build-39 continuation
and captured execution reports supersede their execution blockers. WindowServer,
cold-boot service execution, reset and suspend/resume still require work.

The current display audit follows the Sequoia `hp_boot.py` service through
native initialization, `hp_windowserver.py` display release and GUI validation.
The separate reference `phxboot.sh` did not perform the HP's failed retest.
Texture44 reached WindowServer, enabled framebuffer fetch and recorded 314
presents before its console-session check requested firmware fallback.
Resource46 reproduces native BO allocation/handle-reuse failures and an OOM
cleanup crash in RADV. Phoenix patches 0011..0013 address those resource paths.
The corrected backend passes bounded native IOSurface, churn and shader
readbacks. Its guarded HP boot now reaches the desktop and passes the live
framebuffer-client/present check. CPU frame-copy durations around 100 ms remain
the next measured bottleneck. Longer-session desktop stability needs validation.

```text
App / WindowServer
  Metal -> src/nmplugin/NVMTLDevice.m (includes other plugin .m files)
    NVMTLLibraryLoad.m -> dlopen(libnvmtl_translate): AIR -> SPIR-V
    NVMTLObjects.m / NVMTLEventSync.m -> nvmtl_vk.c -> Vulkan resources/submit
  RADV/ACO (external Mesa f5cb8ee0 + Cobalt64 + Phoenix patches)
    ac_gpu_info.c <- AMDGPU_INFO_DEV_INFO <- ac_darwin_drm.c
      <- ac_darwin_kext.c <- IOKit (direct PhxBringup or NMXAccel proxy)
    topology selector 30 <- PhxBringup <- captured HP profile + exact PCI match
  PhxBringup.cpp: BO pages/imports -> GPUVM -> MES rings -> CP -> fences
    phxctl/bringup5.sh: PSP/firmware/SMU
    phxctl/full.sh + mesboot.c: memory hub/CP/MES queues -> adoptQueue
    claimAccel -> PCI nmxgpu-claimed -> NMXAccel
  PhxAccel:
    nvrm-accel.cpp: IOAccelerator object and native-client proxy
    phxfb.cpp: GOP framebuffer, contiguous host pool, IOSurface frame copy
    phxagdc.cpp: display control, arming and fallback
```

## Subsystem inventory

| Concern | Actual implementation | HP implications |
|---|---|---|
| PCI/attachment | `src/phxbringup/Info.plist`, `PhxBringup::start`; accelerator personalities | Device 1900 already matches HP; distinguish revision and subsystem rather than relabel all devices |
| CU/RB topology | Mesa canned `amdgpu_devices.c` originally feeds RADV; new private topology query overlays captured fields | Physical CU bitmap + RB mask needed, not only active CU count; counts feed ACO/register resource decisions through Mesa |
| Shader translation | `NVMTLLibraryLoad.m`, `NVMTLVendorCompiler.m`, `NVMTLSass*.m`; AIR library external | AIR->SPIR-V is not CU dispatch; native AMD ISA generation lives in ACO; no xlat11 subsystem exists here |
| Pipeline/resources | `nvmtl_vk.c`, `NVMTLObjects.m` -> RADV | Shared Vulkan implementation; compiler mock succeeds with captured HP topology; no evidence of HP execution |
| Power/firmware | `tools/phxctl/bringup5.sh` -> PhxBringup PSP/SMU debug selectors | Exact file offsets/sizes and raw TMR address words are Firebat-specific; HP profile cannot validate them |
| GPUVM/memory | `PhxBringup.cpp` BO allocation, imports, multi-process page tables/VMID reuse; `mesboot.c` hub setup | `VRAM_MC=0x8000000000`, `FB_PA=0x6a0000000`, aperture/default-page settings and scratch regions in tools require target evidence |
| Scheduling/commands | MES API `mes_v11_api_def.h`, `mesboot.c` MQDs/rings/CSB -> adoptQueue -> gpuSubmit/gpuRetired | Existing hardware path, not simulated completion after queue adoption; HP is deliberately prevented from using it |
| Interrupts/recovery | Submission/wait polling; boot watchdogs and WindowServer crash/hang monitoring | No demonstrated HP interrupt-driven completion/reset or suspend/resume path; no claims of complete interrupt support |
| Framebuffer/display | `src/phxaccel/accel/phxfb.cpp` reads GOP, measures OTG0, provides vblank timer; `phxagdc.cpp` controls arming | GOP geometry is not wholly fixed at 2560x1600 here; OTG0/DCN314 assumptions still need HP validation |
| Installation/build | native kext build scripts; `install/`; `tools/release/build_release.sh` packages reference machine binaries | Source builds are not automatically installed; release script copies installed assets and is not a reproducible HP build pipeline |
| Hardware evidence | `hardware/dumps/firebat_u6c` vs new `hardware/profiles/hp-760m.json` | Reference PCI/IP/trace data describe Firebat only; supplied HP capture contains topology and identity only |
| Diagnostics | `src/phxprobe`, `tools/parse_discovery.py`, `tools/linux-trace/trace.sh`, phxctl/mesboot, vkprobe/mtlprobe/iosurf | Probe/trace procedures may change power/driver state; new Linux profile collector uses read-only DRM/sysfs queries |

## Earlier experimental path

`src/kext/RDNA3Driver*` -> `src/amd/rdna3_ip_blocks*` is a separate scaffold with
placeholder initialization. `src/uapi/r3n_user_client*` and `src/winsys/radv_r3n_winsys*`
are host-side simulations, including immediate retirement. Their hardcoded
12-CU/11.0.3/2560x1600 values and passing mock tests are not the production N48N
interface or hardware evidence. `src/amd/rdna3_ip_discovery*`, firmware extractors,
and UMA planners have useful independent tests but are not all wired into
PhxBringup. The old `tools/build_kext.py` is not the README's native production build.

## Data contract and scope

`phx_topology.h` defines a versioned, fixed-width 128-byte extension (selector 30,
outside existing N48N 0..26 and debug 100..113). The kernel reports captured data only
after matching all five PCI identity fields. A ready flag is reserved for a future
validated native implementation; it is never set by the capture generator.

The Mesa patch transports that structure, validates dimensions and populations,
then copies physical CU and RB fields into `drm_amdgpu_info_device`; Mesa's existing
GFX11 mapping in `ac_gpu_info.c` derives enabled CUs and ACO constraints. PCI identity
and marketing name follow the same profile. Existing canned paths remain available
when the extension is unsupported. An explicit mock profile exercises the HP path
without changing the default 780M mock. Neither a mock nor a captured profile
validates inherited tiling/memory/firmware properties.

Header semantics were checked against the Linux UAPI `drm_amdgpu_info_device` and
GFX11 CU mapping; no hardware register/fuse encoding was inferred from these masks:
[Linux AMDGPU UAPI](https://github.com/torvalds/linux/blob/master/include/uapi/drm/amdgpu_drm.h),
[Linux GFX11 implementation](https://github.com/torvalds/linux/blob/master/drivers/gpu/drm/amd/amdgpu/gfx_v11_0.c),
Mesa source at the build's pinned commit. Runtime proof remains required.

## Continuation implementation

`PhxExecutionPolicy.h` now supplies canonical/BO range checks, transactional page
mapping, engine-selection policy and pending-fence storage to the actual kext.
PhxBringup build 34 removes immediate software retirement, checks TLB completion,
unmaps BO PTEs before release and quarantines wired resources after device loss.
It advertises native readiness to RADV only with graphics and compute queues ready;
Mesa patch 0008 enforces that handshake for native transport. HP diagnostic gates
remain in force independently of those shared execution improvements.

The source Metal build is now `src/nmplugin/build.sh`; translator source is built
by `tools/build_translator.sh`. `tools/test_metal_stack.py` exercises the actual
plugin's lazy metallib indexing followed by `nvmtl_compile_library_entry`, not a
separate translator stand-in. It tests three authored shader stages and the
packaged RADV library with mock transport. `hasUnifiedMemory` now reflects the
queried Vulkan integrated-device type, preserving discrete-device behavior.

`tools/build_stack.py` assembles these components with LLVM/Zstd runtime inputs,
corresponding source/notices and relocatable native dependencies. Package manifests
and compiled-input receipts prevent accidental stale/missing-file assembly.
`install/install_diagnostics.py` provides explicit OpenCore staging and rollback;
it does not activate acceleration. Reference bring-up scripts now propagate errors,
validate firmware file ranges, and refuse missing/diagnostic/lost services before
arming watchdogs. Their Firebat memory/firmware constants are still not an HP recipe.

Live Sequoia capture and historical HP evidence are in `hardware/dumps/hp_envy_760m`.
The current CPU aperture addresses differ from the earlier Linux snapshot; neither
snapshot is compiled into initialization. Linux IP and memory-controller evidence
remain prerequisites to replacing the remaining board-specific bootstrap constants.

## Live-evidence integration

`tools/linux-profile/collect.c --device-info` preserves selected AMDGPU_INFO fields
alongside the original topology format. `phx_device_profile.py` validates the live
capture against the supplied exact HP topology and generates a separate RADV-only
property header. Phoenix patch 0009 calls it after the topology override; other GPU
profiles retain their canned values. Linux-managed VA ranges/heap budgets and
readiness flags never cross this boundary. Runtime clock telemetry remains absent.

`phxfw` shares the freestanding firmware extractor with host tests and the legacy
RDNA3 scaffold. The production `bringup5.sh` now consumes its complete validated
plan, including MES/KIQ code/data, before any watchdog/hardware action. The new
extractor does not start MES. `mesboot.c`, fixed PSP/TMR addresses and HP memory
reservation discovery still need integration before diagnostic restrictions can go.
Stock Linux hardware tests establish shader translator behavior independently of
these unfinished macOS paths; see [Linux validation](LINUX_VALIDATION.md).

## Runtime memory contract (build 35)

`src/amd/phx_memory_layout.h` defines selector 31 and an 80-byte snapshot. It
exports the raw attach-time MMHUB registers, decoded MC/physical/size fields and
the mapped BAR0 extent. The shared decoder/validator checks internal consistency,
reserved/version/flag fields and address overflow. The kernel requires the exact
method shape and a successful Hello; diagnostic/lost devices can still report
their snapshot. No readiness, reservation or CPU-window-offset assertion is made.

`mesboot layout` reads this snapshot without a mutating selector. Other mesboot
steps require a valid reply and reject diagnostic/lost hardware before register,
VRAM or doorbell operations. Address calculations use the query, but remaining
Firebat default-page/register sequences require the original matching memory
layout. A different physical base cannot silently reuse those sequences. New
mesboot requires build 35+; older kernels fail before hardware operations.

The production queue adoption policy checks both VRAM and CPU aperture bounds,
32-bit offset storage, doorbell span and ring/writeback/fence overlap. The same
overflow-safe bounds protect VRAM reads/writes, PSP ring/staging and system-memory
debug accesses. This does not prove ownership of any of those regions. HP PSP/TMR,
GOP scanout reservations and actual queue initialization remain separate work.

## Firmware reservation evidence (build 36)

`PhxBringup::readFirmwareLayout` obtains the cached VFCT through the public
IOACPIPlatformDevice ancestor API. It does not evaluate ACPI methods or read a ROM
BAR. `phx_vbios.h` selects the exact PCI BDF/vendor/device image and decodes ATOM
ROM 2.2/master data 2.1. Known VRAM usage 2.1/2.2 and firmware-info 3.4/3.5 fields
are exported as selected `phx-vbios-*` properties. Other table revisions do not
inherit their layouts. Raw start fields retain operation flags and KiB units;
they are not interpreted as allocation permissions. Firmware-info extra/protected
sizes and VRAM usage claims are distinct; they are never summed or treated as a
complete reservation map. The collector preserves absence versus measured zero.

Field layouts and offsets were checked against
[Linux v6.14 atomfirmware.h](https://github.com/torvalds/linux/blob/v6.14/drivers/gpu/drm/amd/include/atomfirmware.h)
and [the Linux VFCT acquisition path](https://github.com/torvalds/linux/blob/v6.14/drivers/gpu/drm/amd/amdgpu/amdgpu_bios.c).
VFCT checksum, truncation, duplicate images, version rejection and 10,000 mutated
inputs are covered by the same parser used in the kext. Missing VFCT has no
speculative VRAM fallback. IOACPIFamily is an explicit dependency. This only
collects evidence needed for a later ownership/initialization implementation.

Build 37 preserves the selected cached ACPI image independently of the decoder's
supported formats, and reports common ROM/master header revisions when validated.
Private selector 32 reads bounded (1..4096-byte) chunks after Hello and requires
administrator privilege even on diagnostic/lost devices. It reads immutable
kernel-owned OSData, not a caller-selected address or ROM BAR; the cache is
released at service free. No unknown layout is accepted to establish readiness.
The capture CLI creates a new mode-0600 file, refuses overwrite, checks reply
lengths, removes failed captures and returns ownership to a valid sudo caller.
The binary stays private; only selected decoded facts belong in public evidence.


## Captured HP firmware and scanout (build 38)

The build-37 private snapshot succeeded. The measured ROM 2.3 header is 44 bytes;
its master-data pointer at +32 references master 2.1. Build 38 accepts that
specific prefix alongside ROM 2.2, checks the complete declared bounds and still
rejects future revisions. Firmware-info 3.4 reports 2048 KiB extra firmware
memory. Usage 2.1 reports zero start/firmware/driver fields; those zeros do not
prove unreserved VRAM. `vbios-metadata.json` records the source hash and redacted
fixture regions. The executable ROM is neither committed nor packaged.

`phxprofile --scanout` verifies the exact captured PCI profile, validates selector
31 on the same connection, and reads 48 DCN 3.1.4 register addresses from the
pinned Linux register header and measured segment bases. It collects two samples
before emitting JSON and refuses failed/short replies. The capture is not atomic
and does not cover all cursor/DMCUB/firmware allocations. Running HP build 37
returned matching samples without another diagnostic kext installation. No
register writes or GPU commands occurred.

The PSP controller now distinguishes successful IOKit delivery from a zero PSP
status before recording TMR setup. Oversized TMR requests fail rather than
silently shrinking. A failed command fence or ring creation/destruction leaves
buffers quarantined; command submission and firmware staging cannot reuse them
until ring destruction is acknowledged. Producer indices are validated before
command-buffer writes; zero fence values are skipped on counter wrap.

Selector 106 op 3 uses an explicitly staged TOC at firmware-buffer offset zero
and returns `psp_gfx_resp.tmr_size` (+16), independently of the old firmware-address
outputs (+8/+12). The legacy raw-command ABI is unchanged. This is a prerequisite
for a later allocator, not an HP firmware bootstrap implementation. The fixed
reference TMR capacity remains explicit and rejects larger requirements. Sources:
[Linux v6.14 PSP wire layout](https://github.com/torvalds/linux/blob/v6.14/drivers/gpu/drm/amd/amdgpu/psp_gfx_if.h)
and [TOC/TMR setup](https://github.com/torvalds/linux/blob/v6.14/drivers/gpu/drm/amd/amdgpu/amdgpu_psp.c).

No complete HP VRAM reservation allocator, PSP/MES bootstrap, native command
execution, Metal device, accelerated framebuffer, or validated recovery exists.
The collected evidence does not authorize substituting Firebat physical addresses
or removing the diagnostic execution gate.


## Build 39 bootstrap ownership and readiness

`beginHpBootstrap` is an administrator-only operation, separate from cold boot.
It opens the IOPCIDevice, checks actual configuration twice through the pinned
DCN register list and validates cached ATOM metadata. Unknown configurations or
an existing PCI owner stop before hardware initialization; the owner's service
class is reported when available. IOPCIDevice's public implementation delegates
open ownership to IOService: https://github.com/apple-oss-distributions/IOPCIFamily/blob/main/IOPCIDevice.cpp.
The exact profile gate protects the measured console prefix and confirms every
captured active DMCUB window remains in the firmware exclusion. A PCI-assigned CPU
BAR may relocate; the MC backing and capacity must match the captured profile.

The serialized arena owns bootstrap intervals. TMR is allocated only after PSP
reports its required size, naturally aligned where possible and at least 1 MiB
aligned otherwise (Linux PSP_TMR_ALIGNMENT). PSP MC and system physical fields
come from the running kernel's decoder and lease offset. The existing reference
scratch policy is retained explicitly; HP does not inherit reference addresses.
User BOs retain the existing system-backed UMA/GPUVM design; their VRAM-domain
budgets do not mean they occupy the resident PSP/MES carve-out.

MES writes are restricted to its lease. Queue adoption checks both queues and
emits the same RELEASE_MEM packet as actual IB submission; only the GPU can
replace the cleared/old fence with the new sequence. Both queues must pass before
native readiness/topology flags become positive. Claiming the accelerator is a
later operation. Failed bootstrap cannot silently reset leases, free DMA-exposed
pages or pretend commands retired. A reboot remains necessary after loss.

`hp_bringup.py` validates package, firmware plan, shader fixtures and running
kernel UUID before opting into hardware operations. It stages firmware, boots
PSP/SMU/GART/MES, runs native compute and translated offscreen rendering, and can
claim PhxAccel only after readbacks pass and the expected accelerator UUID is
loaded. It changes no NVRAM/boot/security settings and starts no daemon. The
native probes load the selected RADV ICD directly and reject mock environments.

The opt-in app boot path is separate from the reference WindowServer daemon:
`install --hp-native` -> immutable root-owned package -> `hp_boot.py` -> guarded
`hp_bringup.py --execute --claim` -> native RADV and strict HP Metal probes -> app
allow list with an explicit WindowServer denial. Pending/disabled markers prevent
retry after an interrupted or failed initialization. It does not change the
framebuffer matching gates, display timing or NVRAM.


## HP one-shot display integration (implemented; runtime validation pending)

`phx_hp_display.h` validates the exact captured firmware console against two
read-only timing/reservation snapshots and decoded VFCT/ATOM memory metadata.
`PhxAMDFB` may present that CPU console early, before native GPU initialization,
only with explicit consumed NVRAM arming. It refuses late matching beside an
existing framebuffer. It neither opens PCI exclusively nor programs display
registers. `NMXAccel` retains its independent native-readiness gate and publishes
base-class sizes plus the validated console plan; HP pipe registration is refused
when sizes differ. The AGDC timing reply uses captured porches/polarity instead of
reference-machine CVT defaults. Nominal pixel clock is labelled accordingly.

`install_hp_windowserver.py` -> app-only module-validation reboot -> same installer
verifies actual ABI/plan/current-boot Metal -> root-owned one-shot request/NVRAM ->
`hp_boot.py` privileged native tests -> `hp_windowserver.py` exact pipe and AGDC
registration -> release hold -> GUI Metal and present checks. GUI waiting cannot
precede releasing the panel. The request is consumed, not automatically renewed.
A failed display boot disables GPU retries and requests a firmware-fallback reboot
only when the custom framebuffer actually owns the panel. This preserves the
existing reference-machine display path. Private method/offset compatibility,
WindowServer shader execution and visible panel output still require HP testing.

The first actual display boot passed attachment/native checks but failed at
WindowServer's platform-process library validation, before loading NVMTLDriver.
App Metal tests do not exercise that boundary. The supervisor and arming installer
now require the reviewed Sequoia-compatible AMFIPass 1.4.1 and an active service;
neither version presence nor service attachment is a claim that every signature
check was relaxed. A second boot with 1.4.1 active still failed library validation;
the guards now additionally require both explicitly authorized upstream AMFI
arguments in the actual boot. An authored hardened/validation-required host loads
the actual plugin under that policy without GPU commands. Actual WindowServer loading/presents remain separate runtime
requirements. The supervisor/display installer never edits AMFI arguments; only
the separate explicitly invoked configuration helper does so, with backup.
Crash-report monitoring
is armed before panel release and checked during console waiting and presentation,
so a fresh same-boot WindowServer crash requests fallback without waiting the full
login deadline. Existing app-only startup does not inspect display crash reports.

Source checks used Apple IOGraphics-599's IOFramebuffer::start/header and Linux
v6.14 `dcn10_optc.c`/DCN 3.1.4 register definitions. The framebuffer base does not
open its provider in those Apple sources; this matters because PhxBringup must
still acquire exclusive PCI ownership later. Timing decode/capture provenance is
in `hardware/profiles/hp-760m-display-registers.json`.
