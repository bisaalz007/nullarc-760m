# NullArc-760M — Radeon 760M graphics for macOS Sequoia

**Experimental HP Envy x360 16-ad0013dx build.** This repository targets the **AMD Radeon 760M (gfx1103)** in the measured HP laptop. It is not a general Radeon 7xxM installer and is **not verified on macOS Tahoe**.

The implementation provides native GPU queues, a Metal-facing plugin implemented over Vulkan/Mesa RADV, and an opt-in accelerated WindowServer framebuffer. It incorporates derivative components from the original NullArc/NullMoth work; see [Licenses and attribution](#licenses-and-attribution).

## Download — one current Sequoia installer

**[Release v0.2.0 — Sequoia beta](https://github.com/yt42c2mvn2-cmd/nullarc-760m/releases/tag/v0.2.0-sequoia-beta)**

Download these **release assets**, rather than GitHub's automatically generated source-code ZIP:

- `nullarc-760m-0.2.0-sequoia-beta-startup-readiness.zip` — the complete current compiled package, with the verified startup-readiness fix, fresh-file installer and guarded WindowServer persistence
- `SHA256SUMS-startup-readiness` — checksum for that ZIP

The release pipeline assembles and checksum-verifies this package from the previously pinned compiled Sequoia stack plus reviewed startup-script changes. The native GPU binaries are unchanged from the underlying 0.2.0 build. **Do not mix files from old ZIPs or replace an already working installation with unrelated build outputs.**

### Verify and extract

After downloading both files to `~/Downloads`, run:

```bash
cd ~/Downloads
shasum -a 256 -c SHA256SUMS-startup-readiness
unzip nullarc-760m-0.2.0-sequoia-beta-startup-readiness.zip
cd nullarc-760m-0.2.0-sequoia-beta
python3 -B package_manifest.py .
```

Require the checksum to report `OK` and the package inventory to verify before installing. The line `acceleration unverified` in the static package-manifest check is an intentional packaging policy flag, **not** a claim that the runtime tests below failed.

## Hardware and results — verified on the actual HP

| Item | Measured or observed result |
| --- | --- |
| Machine | HP Envy x360 16-ad0013dx |
| System | macOS Sequoia 15.8.2, Darwin 24 |
| GPU | AMD Radeon 760M, 8 active CUs, gfx1103 |
| PCI identity | `1002:1900`, revision `ca`, subsystem `103c:8c6a` |
| Bring-up | PhxBringup build 39, native queues ready |
| Automatic initialization | `native_initialization_verified: true`, return code 0 |
| Metal API | Radeon 760M / `NVMTLDevice` discovered, no device fallback |
| Metal compute | **4,096 / 4,096 correct**, command buffer completed |
| Metal render | Completed without error; 32,640 red, 32,896 blue, 0 other pixels |
| Automatic app enablement | `metal_verified: true`, `metal_readbacks_verified: true`, `apps_enabled: true` |
| Accelerated desktop | WindowServer compositing visibly working on the HP; guarded persistence enabled |
| Typing/display counters | In one 15-second typing sample: 292 successful display transactions; 0 failed, skipped, blank or late transactions |

This is **one-machine experimental validation**, not certification of general compatibility, indefinite stability, or repeated reboot recovery. Source evidence is in [HP hardware reports](hardware/dumps/hp_envy_760m/); the latest app verification also comes from the live `/Users/Shared/nullarc-hp-native-status.json` on this HP.

**Known issues:** Safari's address bar, Spotlight and login-screen text fields can temporarily display only the first few typed characters, then show later characters with flickering. TextEdit's document area did not reproduce that behavior. Boot progress-bar flicker has also been reported. Video performance, sleep/wake, brightness, external displays and hardware video codecs are not fully verified. These issues remain open; this release does **not** claim to fix them.

## Installation — choose the correct starting point

**Before anything:** Use the exact HP hardware and Sequoia version above; have Python 3, a working OpenCore setup, a **backup of your EFI**, an alternate boot/recovery path, and the full verified ZIP. The installer does **not** set SIP/AMFI policy or repair OpenCore dependencies. Display-mode validation on this HP required an explicitly reviewed AMFIPass 1.4.1 service and security-relaxing AMFI boot arguments. Those changes have system-wide security implications; see [advanced installation and recovery](docs/INSTALL.md) and do not copy settings blindly.

### A. Already running this exact, healthy accelerated HP build

**Do not run `--fresh-files`, manual GPU bootstrap, or reinstall kexts on the working boot.** Only check whether the reviewed package can stage its WindowServer startup configuration:

```bash
./install.sh --windowserver --check
```

If it reports matching runtime components and you intentionally want guarded persistent display boots:

```bash
sudo ./install.sh --windowserver
```

Follow the installer's output. A successful display boot checks native queues, public Metal readbacks and live WindowServer presents before rearming the **next** accelerated boot. The framebuffer consumes a one-shot NVRAM request; failures cancel rearming. This is **guarded persistence**, not unconditional forced acceleration.

After a successful boot, inspect:

```bash
cat /Users/Shared/nullarc-hp-native-status.json
sysctl debug.nvaccel_iop_ok debug.nvaccel_iop_fail
```

Check `native_initialization_verified`, `metal_verified` and `apps_enabled`; in display mode also check `desktop_armed` and `desktop_present_verified`. A successful preflight by itself is not proof of accelerated display.

### B. Fresh HP / no initialized GPU (staged development installation)

**There is no verified one-command clean install.** The stages deliberately refuse to activate or reinitialize unsafe GPU state. Use the **same extracted ZIP** throughout; do not install the driver while native queues or WindowServer are already armed.

1. **Diagnostic OpenCore kext**, while idle: mount the EFI that actually boots the HP, then run:

   ```bash
   ./install.sh --diagnostics --oc /Volumes/EFI/EFI/OC --check
   sudo ./install.sh --diagnostics --oc /Volumes/EFI/EFI/OC
   ```

   Replace `/Volumes/EFI/EFI/OC` if your real OpenCore path differs. Save the printed backup; reboot with that same EFI. Verify `ioreg -rc PhxBringup -l` shows the expected HP diagnostic profile.

2. **Stage the compiled drivers from this ZIP**, still in a safe, idle **diagnostic-only** boot:

   ```bash
   ./install.sh --fresh-files --check
   sudo ./install.sh --fresh-files
   ```

   This backs up existing recognized components and stages PhxAccel, NVMTL, RADV, firmware and tools, but **does not** install the EFI kext, build/load the auxiliary kernel collection, initialize GPU queues, enable app access or arm WindowServer. It intentionally does not erase failure markers.

3. **Finish and validate the engineering stages before activation.** Confirm the matching PhxAccel auxiliary collection and loaded binary UUID, use the explicit **one-time native bootstrap** from [the advanced HP guide](docs/INSTALL.md#build-39-explicit-engine-experiment), and prove Metal device, compute and render success. A native bootstrap can cause a GPU hang or kernel panic. Never rerun it when queues are already initialized or after a failed boot.

4. **Stage app-only automatic startup**, only after that successful same-boot native/Metal validation and matching package binaries:

   ```bash
   ./install.sh --hp-native --check
   sudo ./install.sh --hp-native
   ```

   Reboot, log in and verify `metal_verified: true` and `apps_enabled: true` in the public status JSON. Only then run the `--windowserver --check` and `sudo ./install.sh --windowserver` steps from section A; depending on the module state, the display installer may require an intermediate **app-only reboot** before it will arm the first display boot.

For the precise recovery, auxiliary-collection, AMFI and rollback prerequisites, read [docs/INSTALL.md](docs/INSTALL.md). An installed file is **not** proof that its kext loaded, its GPU queue is safe, or WindowServer can present.

## Recovery and safety

If an accelerated display boot fails, use the working recovery OpenCore/firmware-framebuffer path. Keep the saved EFI and component backups and the protected boot report under `/var/db/nullarc-760m/`. **Do not** delete `pending` / `disabled` markers or manually reinitialize firmware/GPU queues in the same boot.

To stop *future* persistent WindowServer arming from a healthy system, see [the cancellation procedure](docs/INSTALL.md#hp-experimental-windowserver-stages). The separate startup-readiness recovery tool is only for its specifically reviewed boot-registry failure signature; it is not a general repair command.

## Source and development

- [Bring-up and GPU memory](src/phxbringup)
- [Accelerator, display pipe and framebuffer](src/phxaccel)
- [Metal plugin and IOSurface code](src/nmplugin)
- [Darwin Mesa/RADV patches](mesa-patches-phoenix)
- [Developer build instructions](docs/BUILD_STACK.md)
- [HP measurement and validation data](hardware/dumps/hp_envy_760m)

**Tahoe is not yet verified on this 760M.** Do not apply Sequoia display or auxiliary-collection instructions to Tahoe without a separate build and validation.

## Licenses and attribution

This is a 760M-specific fork, **not a claim of exclusive authorship** of the underlying driver. Components derived from NullMoth/NullArc are subject to their existing **PolyForm Noncommercial 1.0.0** terms; other components include MIT/GPL, LGPL, Mesa and AMD firmware terms. Preserve the original copyright and third-party notices. See [LICENSE](LICENSE), [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) and [LICENSES](LICENSES).

Thanks to the original NullArc/NullMoth contributors, Mesa/RADV, the Linux amdgpu project, Cobalt64, Acidanthera and AMD-OSX contributors.
