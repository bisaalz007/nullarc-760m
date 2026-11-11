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
| HP with Sequoia 15 | Build-39 native RADV and public Metal compute/render verified; manual bootstrap and opt-in app boot service |
| HP with Tahoe | Same diagnostic gate; GPU acceleration is not enabled |
| Reference 780M on Tahoe | Existing acceleration installer is included; this source build has not been runtime-validated there |

Linux tests executed translated compute and graphics shaders on the HP. Build 39 now also passes native macOS GPU and public Metal compute/render readbacks. WindowServer remains unverified.
The new Sequoia display-development package provides a staged one-shot
`sudo ./install.sh --windowserver` experiment, described below. Older packages
still refuse this mode on HP. Display acceleration is not yet verified.

Choose the Sequoia-labelled ZIP for macOS 15. Its native deployment target is 15.0;
the older Tahoe-only ZIP remains a different build. CPU loading/translation is
verified on Sequoia 15.8.2. Basic native Metal compute/render are also verified; full application compatibility and WindowServer are not.

You need Python 3, a working OpenCore configuration and a backup of your EFI.
Keep a separate way to boot if a diagnostic kext cannot load. These commands
do not mount EFI, change SIP/AMFI, install OpenCore dependencies or reboot.

## HP: experimental WindowServer stages

This path currently supports the measured HP console on Sequoia 15 with
IOGraphicsFamily 599, IOAcceleratorFamily2 485.2 and AGDC 8.1.10. It requires the
working app-only boot service and matching native runtime. Class-size checks are
necessary guards, not proof that every private display API is compatible.

```sh
./install.sh --windowserver --check
sudo ./install.sh --windowserver
```

First installation backs up PhxAccel and the daemon, stages the new PhxAccel and
an immutable service package, then requests standard start-only kext loading.
It does not unload the current accelerator, change EFI/security/NVRAM, arm the
framebuffer or initialize GPU queues. Follow any specific macOS approval message,
then reboot using the same USB and log in. Confirm the new loaded UUID and fresh
`/Users/Shared/nullarc-hp-native-status.json` app/Metal results before continuing.

After those checks pass, run the same command again. It verifies the measured
1920×1200 console, 2260×1240 timing totals, firmware reservations and display ABI,
then writes a root-only next-boot request and `phxfb-boot=1`. Reboot with the same
USB. The kext consumes/commits removal of that NVRAM flag before attachment. This
is one display boot, never automatically rearmed. The console presenter changes
no display registers; the existing GPU display pipe copies completed frames into
the firmware scanout surface. Its 60 Hz clock is nominal, derived from captured
totals and corroborated panel mode, not a measured/programmed PLL clock.

The daemon initializes/test-checks native queues, registers exactly one display
pipe and AGDC, and releases the panel hold before waiting for a GUI session.
It then requires Metal readbacks and live framebuffer-client/present evidence.
Failure disables retries; if the custom framebuffer owns the panel, it requests
one reboot into the firmware framebuffer. A kernel/GPU fault can still require
a manual power cycle. The consumed flag and failure markers prevent a repeated
accelerated-display boot. No WindowServer compatibility is claimed until the HP
runtime results and visible desktop have been checked.

To cancel a staged display request before reboot (local administrator):

```sh
sudo nvram -d phxfb-boot
sudo rm -f /var/db/nullarc-760m/windowserver-next-boot.json
```

Keep the printed `/var/db/nullarc-760m/display-update-*` backup. Do not remove
pending/disabled markers or retry initialization after a failure without first
reviewing its protected report. App-mode support remains independently verified
on the previous build; the updated display module requires its own runtime test.

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

## HP: opt-in app acceleration after reboot

Build 39 passed actual PSP/MES/queue, native shader and public Metal readbacks on
the HP. New packages include `gpu/phxctl/mtlprobe --hp`, which requires the exact
HP PCI ancestry, refuses mocks and allows no device fallback. The explicit
`hp_bringup.py --execute --claim` sequence now requires these Metal checks too.
Never repeat initialization in an already initialized or failed boot.

After a successful manual bootstrap, with the matching kexts installed and the
confirmed USB EFI mounted at `/Volumes/EFI`, the app-only boot service can be
checked and installed:

```sh
./install.sh --hp-native --check
sudo ./install.sh --hp-native
```

This mode verifies the actual installed binaries and running kernel UUIDs,
repeats public Metal readbacks before making persistent changes, copies this
package into a root-owned directory under `/Library/Application Support/NullArc760M`,
and installs `local.nullarc.hp-native.plist`. It replaces no kext, plugin or EFI
file, starts no service immediately and changes no security or NVRAM setting.
Do not install it alongside the reference `local.phxboot` service.

At the next manual reboot, the system service runs the guarded native bootstrap,
then waits for the logged-in console GUI session and runs Metal tests under that
user’s bootstrap and credentials. Only complete success enables app access; WindowServer is
explicitly denied. Interrupted or failed initialization disables subsequent
automatic attempts and retains evidence under `/var/db/nullarc-760m`. A compact
status is readable at `/Users/Shared/nullarc-hp-native-status.json`; raw root-only
reports retain the detailed diagnostics. Automatic reboot, reset and resume are
not implemented. The first HP cold boot passed native GPU tests but checked Metal before any
device appeared. The corrected publication wait has host tests and requires
another boot; the existing manual Metal initialization is the verified path.

Disable future automatic initialization with:

```sh
sudo mkdir -p /var/db/nullarc-760m
sudo touch /var/db/nullarc-760m/disabled
```

This does not reset an active or lost GPU. After a failure, preserve reports and
use a fresh reboot; do not clear markers and retry hardware initialization in the
same boot. The panel remains on the firmware framebuffer throughout this mode.

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

## Updating the reviewed empty-catalogue boot failure

For the exact captured failure (all native tests passed, then Metal enumeration
returned zero devices without stderr), `recover_hp_boot.py --package PACKAGE`
is an administrator-only next-boot updater. It compares native execution binaries,
firmware and shader fixtures, backs up the daemon and failure markers, copies a
new immutable package, and verifies the new service configuration. It refuses
other failure classes or changed native components and rolls back if marker
migration fails. It submits no GPU commands, starts no service and changes no
kext, EFI or NVRAM setting. Only after successful staging, reboot manually with
the same USB. A failed/lost boot is never used for another initialization attempt.

The bounded system-context enumeration wait also failed on the second boot,
while native GPU tests passed. The latest boot service therefore separates the
privileged native stage from public Metal verification in the real console-user
GUI session. `launchctl asuser` supplies its Mach/audit context and `sudo -n -H -u`
supplies the user credentials/home. Private user-owned caches avoid root-owned
shader caches in the login user's home. This path still needs HP runtime proof.
A missing session/catalogue does not itself mark healthy native queues lost;
app access remains disabled. GPU shader-test failures retain the abort policy.
The recovery tool also accepts the captured all-empty-catalogue timeout when
native tests passed; it still refuses unrelated errors or changed native bytes.

## Publication prerequisite and verification-only continuation

PhxAccel's existing display fallback withholds `MetalPluginName` for 60 seconds
when no custom framebuffer publishes. The latest helper waits explicitly for
that property on the exact claimed HP PCI device before entering Metal; it does
not arm or bypass a framebuffer. ioreg uses `-l` so child properties are present.

For a reviewed enumeration-only failure with healthy queues,
`recover_hp_boot.py --package PACKAGE --resume-metal` backs up and updates the
future boot service, then validates the running module UUIDs/runtime hashes and
repeats Metal device/compute/render tests on existing queues. This optional mode
submits test shaders but never reinitializes PCI, firmware, GART or MES. No reboot
is required. A lost driver or shader-failure class is refused. Only successful
readbacks enable app access; WindowServer stays denied. The third HP boot already
passed post-boot SSH Metal tests without repeating native initialization.
