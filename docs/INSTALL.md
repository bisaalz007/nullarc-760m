# Installing the Radeon 760M development prerelease

Download the ZIP asset from this fork's
[Releases](https://github.com/yt42c2mvn2-cmd/nullarc-760m/releases), verify its
SHA-256 using `SHA256SUMS-sequoia` for the Sequoia asset (`SHA256SUMS` for the
older Tahoe asset), and extract it. Open Terminal in the
extracted `nullarc-...` directory containing `install.sh`.

This guide uses the upstream installation stages as a reference, with commands
and limits specific to this fork. The original instructions are preserved in
[INSTALL_REFERENCE.md](INSTALL_REFERENCE.md). Their Firebat acceleration results
do not establish HP compatibility.

## What this prerelease can install

| Target | Available operation |
|---|---|
| HP Envy x360 16-ad0013dx, Radeon 760M | Diagnostic PhxBringup kext in an explicitly selected OpenCore directory |
| HP with Sequoia 15 | Diagnostic kext boot and installed plugin translation verified; backed-up `--components` replacement available; acceleration unverified |
| HP with Tahoe | Same diagnostic gate; GPU acceleration is not enabled |
| Reference 780M on Tahoe | Existing acceleration installer is included; this source build has not been runtime-validated there |

Linux tests executed translated compute and graphics shaders on the HP. The
diagnostic macOS kext boots, but native queues, Metal device and WindowServer remain unverified.
Running `sudo ./install.sh --windowserver` on the HP returns an error **before
installing acceleration or changing boot settings**. There is no bypass option.

Choose the Sequoia-labelled ZIP for macOS 15. Its native deployment target is 15.0;
the older Tahoe-only ZIP remains a different build. CPU loading/translation is
verified on Sequoia 15.8.2, not full Metal-device or WindowServer operation.

You need Python 3, a working OpenCore configuration and a backup of your EFI.
Keep a separate way to boot if a diagnostic kext cannot load. These commands
do not mount EFI, change SIP/AMFI, install OpenCore dependencies or reboot.

## HP: check and install diagnostics

Mount the correct EFI using your existing disk-management workflow. Substitute
its actual `EFI/OC` directory; do not use another disk's EFI by accident.

```sh
./install.sh --diagnostics --oc /Volumes/EFI/EFI/OC --check
sudo ./install.sh --diagnostics --oc /Volumes/EFI/EFI/OC
```

The first command verifies package hashes, the native kext and the selected
OpenCore configuration without writing. The second backs up the original files,
copies `EFI/OC/Kexts/PhxBringup.kext`, and updates its `Kernel/Add` entry. Save the
printed backup directory. It restores the previous state if the transaction fails.
Boot arguments and security settings are preserved; no accelerator, LaunchDaemon
or WindowServer driver is installed by this mode.

After your next manual reboot, inspect:

```sh
ioreg -rc PhxBringup -l
python3 collect_macos_evidence.py --output "$HOME/Desktop/hp-760m-diagnostics"
```

The expected HP stage is `profile-diagnostic-only`. A loaded service, successful
copy or firmware framebuffer does not prove GPU acceleration. If the kext is
absent, keep the boot log and collector report for the next engineering stage.

## What `--windowserver` does

The acceleration installer retains the reference flow:

```sh
sudo ./install.sh --check --windowserver
sudo ./install.sh --windowserver
```

The checks require an OS matching the package deployment target, a loaded
non-diagnostic PhxBringup, the reference
boot/security prerequisites, every package component and a valid header-derived
firmware plan. On a diagnostic HP, both commands refuse acceleration. Use the Sequoia-target binaries on Sequoia; changing the installer check or
lowering a binary header alone is insufficient. Hardware readiness is still required.

For the reference path, installation copies boot tools and AMD firmware to
`/Users/Shared/gpu`, PhxAccel into `/Library/Extensions`, and the Metal/RADV
stack into `PhxGPU` with `/Library/GPUBundles` links. It registers the boot daemon,
rebuilds the auxiliary kernel collection and creates `phxboot-m2`. The boot daemon
attempts bring-up and arms framebuffer takeover only after its checks; the second
boot is part of that reference sequence. Installer success alone proves none of
those runtime stages. The [archived reference guide](INSTALL_REFERENCE.md) describes
its security prerequisites and boot behavior; those changes are not required or
made by the HP diagnostic installer.

The release includes nine unmodified AMD firmware files and their license. Their
headers/ranges are checked during packaging and reference installation. Their
presence does not authorize HP firmware loading or prove PSP/MES compatibility.
No Apple toolchain, AppleHDA, OpenCore configuration or personal EFI is bundled.
See `LICENSE`, `LICENSES` and `sources` for source archives and third-party terms.

## Remove or update

Remove the diagnostic installation using the backup printed at installation:

```sh
sudo ./uninstall.sh --diagnostics --oc /Volumes/EFI/EFI/OC \
  --backup /Volumes/EFI/EFI/OC/.nullarc-diagnostic-backup-EXAMPLE
```

Removal refuses to overwrite a config or kext edited after installation. Reboot
manually to stop using the injected kext. If macOS fails to boot, first disable
PhxBringup in your recovery EFI, then restore the saved files.

For a reference acceleration installation, `sudo ./uninstall.sh` removes its
system components; OpenCore entries and security settings need separate review.
Do not use that mode to remove an HP diagnostic-only installation.

For updates, extract a new release and repeat the appropriate check/install mode.
Do not combine assets from different releases. Current engineering progress and
remaining hardware tests are in [760M_STATUS.md](760M_STATUS.md).

## Sequoia component replacement test

Once the diagnostic service is loaded, the Sequoia package can replace the other
files for a controlled test. This requires administrator access:

```sh
./install.sh --components --check
sudo ./install.sh --components
```

It backs up existing PhxAccel, Metal/RADV and GPU files, copies the replacements,
and keeps `phxboot-off`. No LaunchDaemon is installed, kernel cache rebuilt, module
loaded, reboot performed or WindowServer armed. An already loaded accelerator
continues to use its old code; replacing the file does not prove the new kext loaded.
Successful user-space loading/compiler tests also do not prove GPU acceleration.
Use the printed backup for rollback (substitute its actual path):

```sh
sudo python3 -B install_components.py --restore /Users/Shared/nullarc-component-backups/backup-EXAMPLE
```

Rollback refuses to overwrite later edits. Keep the Sequoia and Tahoe kernel
build profiles separate; their private accelerator interfaces differ.

## Developer firmware snapshot (build 37+)

With the diagnostic kext loaded, capture the selected cached VFCT image using
the matching development tool:

```sh
sudo ./phxprofile --dump-vbios /Users/Shared/hp-vbios.rom
```

Use a new filename. The root-only read copies cached firmware bytes; it does not
execute VBIOS or initialize the GPU. The capture stays mode 0600 and is assigned
to the invoking sudo user where available. Keep the raw image private and inspect
it before sharing decoded facts. Older kexts refuse this operation. Capturing the
image does not enable acceleration or validate memory ownership.


## Build 39 explicit engine experiment

Build-39 development packets support an experimental, local-administrator HP
bootstrap. Cold boot still performs diagnostics only. The experiment checks the
running kext UUID, exclusive PCI ownership, live reservations, firmware, queues
and actual native shader readbacks. Unknown configurations and existing owners
are refused. Do not use an older packet's tools with this kext.

With the matching packet and build 39 loaded, preflight is:
`python3 gpu/phxctl/hp_bringup.py --package . --output NEW_REPORT_DIRECTORY`.
Adding `--execute` under sudo performs GPU initialization and native compute/
render tests; it can expose a kernel/firmware fault. It does not arm WindowServer,
set NVRAM, install a daemon or reboot. `--claim` additionally requires the matching
PhxAccel UUID and requests accelerator attachment only after shader readbacks.
Do not use `--claim` to infer Metal or display success. Keep the installer backup.
