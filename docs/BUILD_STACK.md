# Build and validate the development stack

This workflow builds the fork's kexts, Metal plugin, pinned AIR translator and
patched RADV. It assembles the binaries actually built, without copying installed
reference-machine driver binaries. **The HP remains diagnostic-only.** A successful
build/package/offline translation test does not establish GPU execution.

## Inputs

- macOS Tahoe, Xcode/CLT with SDK 26+, Python 3, Clang, Cargo/Rust >=1.87 and Ninja.
- MacKernelSDK path; Vulkan-Headers checkout; configured Mesa at the documented
  pinned commit with Cobalt64 0001..0009 and Phoenix 0001..0009.
- Clean NullMoth source checkout at `76df0f6af5c64c2af9a22090da8b3fe14616023e`
  (v2.4.1). Only its LGPL `translator/` is compiled/archived.
- Compatible LLVM/Zstd AIR-reader runtime bundle, including
  `Contents/MacOS/air-runtime/{libLLVM.dylib,libzstd.1.dylib}` and their license files
  under `Contents/Resources/air-runtime`. These remain supplied binary dependencies;
  building LLVM itself is outside this script.
- A directory of licenses/corresponding source for extra native dylib dependencies
  found by `otool` (for this host's Mesa: libelf 0.8.13_6 and zlib 1.3.2).

For MSL compilation tests, install Apple's optional Metal Toolchain if absent:
`xcodebuild -downloadComponent MetalToolchain`. Supply SPIRV-Tools `spirv-val`.
No Apple binaries are included in the resulting development package.

```sh
python3 tools/build_stack.py \
  --sdk /path/to/MacKernelSDK \
  --vulkan-headers /path/to/Vulkan-Headers \
  --translator-source /path/to/NullMoth-v2.4.1 \
  --mesa /path/to/patched-mesa \
  --air-runtime /path/to/compatible/NVMTLDriver.bundle \
  --dependency-notices /path/to/native-dependency-notices \
  --output build/stack
python3 tools/package_manifest.py build/stack
python3 tools/test_metal_stack.py --package build/stack --mesa /path/to/patched-mesa \
  --spirv-val /path/to/spirv-val
```

The output directory must be new. Failed assembly never publishes a partial
package. `--assemble-only` reuses a successful build receipt and rejects changed
source inputs or binaries. Dependencies are copied recursively and relocated only
inside staging; external host library paths must not remain. Package hashes cover
all resulting files. The direct RADV ICD path does not require a Vulkan loader.

The Metal test compiles authored storage-buffer compute, vertex and fragment MSL shaders, opens the actual
plugin, indexes its metallib, reads AIR bitcode with LLVM, translates with the
pinned library, independently validates SPIR-V, and compiles compute and graphics ACO pipelines using
8-CU HP and 12-CU legacy mocks. It constructs no Metal device and dispatches no GPU
commands. Metal API coverage, WindowServer, rendering and display behavior still
require target runtime tests. Upstream plugin protocol warnings remain visible.

## Diagnostic installation and rollback

The package contains no firmware or automatic acceleration activation. Its
`install_diagnostics.py` edits only PhxBringup and its Kernel/Add entry in the
OpenCore directory explicitly selected by the user. Security settings and boot
arguments are preserved. Default mode checks only:

```sh
python3 build/stack/install_diagnostics.py --oc /Volumes/EFI/EFI/OC --check
sudo python3 build/stack/install_diagnostics.py --oc /Volumes/EFI/EFI/OC --install
```

Installation validates package hashes, stages the kext and config, retains a
backup, and rolls back a failed transaction. It neither mounts EFI nor reboots.
The entry admits Darwin 24+ for diagnostic collection on Sequoia as well as Tahoe;
actual load compatibility on the HP remains to be tested. The acceleration
components are built for Tahoe and are not installed by this command.

Removal takes the backup directory printed by installation:

```sh
sudo python3 build/stack/install_diagnostics.py --oc /Volumes/EFI/EFI/OC \
  --remove /Volumes/EFI/EFI/OC/.nullarc-diagnostic-backup-EXAMPLE
```

If the user edited the config/kext afterward, automatic removal refuses to
replace those subsequent changes. The backup remains available for manual recovery.
The previous automatic accelerator installer now refuses an HP diagnostic-only
service. No diagnostic gate bypass or unverified hardware reset is provided.

## Hardware collection

On the HP under macOS, `tools/collect_macos_evidence.py --output NEW_DIRECTORY`
collects selected PCI, service and EDID facts without loading a driver, accessing
registers, altering boot settings, or recording system serial numbers. This is
useful on Sequoia; it cannot substitute for Linux IP discovery/firmware evidence.
The live Linux capture is now recorded in `hardware/dumps/hp_envy_760m`;
see [Linux validation](LINUX_VALIDATION.md) for verified execution scope and reproduction. Historical HP BAR and panel evidence is stored separately from runtime
configuration; never reuse its physical addresses as live values.

For the Linux live session, build the existing C collector with installed libdrm
headers, then run the companion capture (root enables available debugfs reports):

```sh
cc -std=c11 -Wall -Wextra -Werror $(pkg-config --cflags libdrm) tools/linux-profile/collect.c -o collect
sudo python3 tools/linux-profile/collect_evidence.py --device /dev/dri/renderD128   --collector ./collect --output /tmp/hp-760m-linux-capture
```

The exact PCI identity is checked before capture. Candidate firmware files are
inventoried as present, not asserted to be loaded. Missing/privileged files are
recorded explicitly. No registers, module state or firmware are changed.

The package also includes `gpu/phxctl/phxfw`. Its offline `--phoenix-plan DIR`
checks the complete known Phoenix firmware layout and emits tab-separated payload
ranges; no firmware binary is shipped or loaded by this operation. `bringup5.sh`
requires this preflight before watchdog/PSP access. Unsupported payload sets fail
closed. Staging/PSP/TMR addresses remain reference-machine values, and HP stays gated.

## Build the downloadable installer release

The source-built stack now includes executable root `install.sh`/`uninstall.sh`,
`INSTALL.md`, the diagnostic installer and read-only collector. The base stack
contains no firmware. After committing the validated sources and assembling a
stack whose source commit matches the checkout, create the release assets:

```sh
python3 tools/release/build_release.py --version 0.1.0-alpha \
  --stack build/stack --firmware /path/to/measured-unmodified-firmware \
  --mesa /path/to/patched-mesa --output build/release-NEW
```

This requires a clean driver/Mesa tree, verifies the stack inventory and source
commits, checks the nine firmware hashes against the live HP capture, and runs
`phxfw` before producing output. It includes the matching driver source archive,
translator source, Mesa patchset and license notices. No installed driver or
personal EFI is read. ZIP executable modes and CRCs are preserved/verified, and
old dependency timestamps are clamped to the ZIP epoch. The output directory
appears atomically and contains the installer ZIP, a standalone diagnostic-kext
ZIP, translator source, SHA256SUMS and release notes. Publishing does not retag
`alpha`, merge main or install anything locally. Release notes distinguish the
binary source commit from the existing tag's automatic source archives.

## Sequoia deployment profile

Build headers still require SDK 26 because the source implements newer protocol
surfaces. `--min-macos 15.0` selects the Sequoia deployment target, compiles with
availability checking, sets the plugin Info.plist, and isolates the translator's
Rust cache by target OS. The default remains 26.0. Never edit deployment load
commands to make an incompatible binary appear older.

Rebuild libelf from the pinned source archive and the supplied MacPorts patch:

```sh
python3 tools/build_macos_libelf.py --archive /path/to/libelf-0.8.13.tar.gz \
  --elf-patch /path/to/elf_repl.diff --output /path/to/NEW-libelf-build --min-macos 15.0
```

Use that prefix's `lib/pkgconfig` first in `PKG_CONFIG_PATH` when configuring a
separate Mesa `build-sequoia`. Keep the Vulkan options above and set `c_args`,
`cpp_args`, `objc_args`, `c_link_args`, `cpp_link_args`, and `objc_link_args` each to
`-mmacosx-version-min=15.0`. The helper supplies a system-zlib `.pc` derived from
the SDK header; no Apple library is copied. Then use the normal stack command with
`--min-macos 15.0 --mesa-build /path/to/mesa/build-sequoia`.

The assembler checks every packaged native dependency's actual Mach-O minimum
version. It rejects a newer transitive dependency or a mismatched build receipt.
Run the compiler test with `--min-macos 15.0` as well. The source-built package
passed loader, AIR translation and mock ACO pipeline tests on the HP's actual
Sequoia 15.8.2; native kernel/Metal-device/GPU rendering remain separate tests.
