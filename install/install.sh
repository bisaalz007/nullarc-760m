#!/bin/bash
# nullarc installer. Run from the unpacked release folder with sudo, once the Mac boots with PhxBringup.kext in
# OpenCore (see INSTALL.md):
#
#   sudo ./install.sh                  Metal for apps on the Radeon 780M
#   sudo ./install.sh --windowserver   the same, and from the second boot on WindowServer composites on the GPU too
#   sudo ./install.sh --check          only the checks, nothing is changed
#
# It puts the boot-time GPU bring-up into /Users/Shared/gpu (run by the LaunchDaemon local.phxboot), PhxAccel.kext into
# the Auxiliary kernel collection and the Metal plugin with Mesa RADV into PhxGPU, linked from /Library/GPUBundles.
# Running it again upgrades in place. Takes effect at the next boot.
set -euo pipefail
SRC=$(cd "$(dirname "$0")" && pwd)
G=/Users/Shared/gpu
H=/System/Library/CoreServices/CoreTypes.bundle/Contents/Library/PhxGPU
L=/Library/GPUBundles
TS=$(date +%Y%m%d-%H%M%S)

WS=0; CHECK=0; DIAG=0; COMPONENTS=0; HP_NATIVE=0; FRESH=0; OC=""
while [ "$#" -gt 0 ]; do
    case "$1" in
        --windowserver) WS=1 ;;
        --check) CHECK=1 ;;
        --diagnostics) DIAG=1 ;;
        --components) COMPONENTS=1 ;;
        --fresh-files) COMPONENTS=1; FRESH=1 ;;
        --hp-native) HP_NATIVE=1 ;;
        --oc) [ "$#" -ge 2 ] || { echo "--oc needs an EFI/OC directory" >&2; exit 2; }; OC=$2; shift ;;
        -h|--help)
            echo 'Usage: ./install.sh --check [--windowserver]'
            echo '       sudo ./install.sh --windowserver  (HP staged one-shot display experiment)'
            echo '       sudo ./install.sh --diagnostics --oc /Volumes/EFI/EFI/OC [--check]'
            echo '       sudo ./install.sh --components  (HP files only; no automatic activation)'
            echo '       sudo ./install.sh --fresh-files [--check]  (back up prior HP service and install ZIP files; no activation)'
            echo '       sudo ./install.sh --hp-native [--check] (verified HP app-only boot service)'
            exit 0 ;;
        *) echo "unknown option $1 (see --help)"; exit 2 ;;
    esac
    shift
done
if [ "$HP_NATIVE" = 1 ] && { [ "$COMPONENTS" = 1 ] || [ "$DIAG" = 1 ] || [ "$WS" = 1 ] || [ -n "$OC" ]; }; then
    echo '--hp-native cannot be combined with component, diagnostic or WindowServer modes' >&2; exit 2
fi
if [ "$COMPONENTS" = 1 ] && { [ "$DIAG" = 1 ] || [ "$WS" = 1 ] || [ -n "$OC" ]; }; then
    echo '--components cannot be combined with --diagnostics, --oc or --windowserver' >&2; exit 2
fi
if [ "$DIAG" = 1 ] && { [ "$WS" = 1 ] || [ -z "$OC" ]; }; then
    echo "--diagnostics requires --oc and cannot be combined with --windowserver" >&2; exit 2
fi
if [ "$DIAG" = 0 ] && [ "$WS" = 0 ] && [ -n "$OC" ]; then echo "--oc requires --diagnostics or --windowserver" >&2; exit 2; fi
command -v python3 >/dev/null || { echo "Python 3 is required; see INSTALL.md" >&2; exit 1; }
python3 -B "$SRC/package_manifest.py" "$SRC"
if [ "$HP_NATIVE" = 1 ]; then
    if [ "$CHECK" = 1 ]; then exec python3 -B "$SRC/install_hp_boot.py" --package "$SRC"; fi
    exec python3 -B "$SRC/install_hp_boot.py" --package "$SRC" --install
fi
if [ "$COMPONENTS" = 1 ]; then
    MODE=--install; [ "$CHECK" = 0 ] || MODE=--check
    COMPONENT_ARGS=(--package "$SRC" "$MODE")
    [ "$FRESH" = 0 ] || COMPONENT_ARGS+=(--fresh-files)
    exec python3 -B "$SRC/install_components.py" "${COMPONENT_ARGS[@]}"
fi
if [ "$DIAG" = 1 ]; then
    MODE=--check
    if [ "$CHECK" = 0 ]; then
        [ "$(id -u)" = 0 ] || { echo "Use sudo for diagnostic installation" >&2; exit 1; }
        MODE=--install
    fi
    exec python3 -B "$SRC/install_diagnostics.py" --package "$SRC" --oc "$OC" "$MODE"
fi
POLICY=$(python3 -B "$SRC/collect_macos_evidence.py" --target-policy)
if [ "$POLICY" = hp-diagnostic-only ]; then
    if [ "$WS" = 1 ] && [ -f "$SRC/install_hp_windowserver.py" ]; then
        MODE=--install; [ "$CHECK" = 0 ] || MODE=--check
        HP_ARGS=(--package "$SRC")
        [ -z "$OC" ] || HP_ARGS+=(--oc "$OC")
        [ "$MODE" = --check ] || HP_ARGS+=(--install)
        exec python3 -B "$SRC/install_hp_windowserver.py" "${HP_ARGS[@]}"
    fi
    echo 'HP Radeon 760M: WindowServer acceleration is not verified; the reference boot path is unavailable.' >&2
    echo 'After native bootstrap and Metal tests, use --hp-native for app-only automatic initialization.' >&2
    echo 'Use sudo ./install.sh --diagnostics --oc /Volumes/EFI/EFI/OC instead.' >&2
    exit 1
fi

say() { printf '%s\n' "$*"; }
fail() { say "  ✗ $*"; FAILED=1; }
FAILED=0

say "== checks"
[ "$(id -u)" = 0 ] || { say "  ✗ run it with sudo"; exit 1; }
ver=$(sw_vers -productVersion)
MIN_MACOS=$(python3 -B -c 'import json,sys; print(json.load(open(sys.argv[1])).get("minimum_macos","26.0"))' "$SRC/package-manifest.json")
case "$MIN_MACOS:$ver" in
    15.0:15.*|26.0:26.*) say "  ✓ macOS $ver (package deployment target $MIN_MACOS)" ;;
    *) fail "macOS $ver does not match this package's deployment target $MIN_MACOS" ;;
esac
args=$(nvram boot-args 2>/dev/null | cut -f2- || true)
for a in amfi=0x80 amfi_get_out_of_my_way=0x1 phxdebug=1; do
    case " $args " in *" $a "*) say "  ✓ boot-arg $a" ;; *) fail "boot-arg $a is missing (OpenCore NVRAM -> boot-args)" ;; esac
done
if grep -q "status: enabled" <<<"$(csrutil status)"; then fail "System Integrity Protection is on (OpenCore csr-active-config 7F080000)"
else say "  ✓ System Integrity Protection relaxed"; fi
# read the registry once: grep -q on a pipe would stop ioreg early, and pipefail counts that as a failure
IOR=$(ioreg -l -w0)
if grep -q '"phx-stage" = "profile-diagnostic-only"' <<<"$IOR"; then
    say "HP is diagnostic-only: acceleration installation and WindowServer arming are unavailable."
    say "Use sudo ./install.sh --diagnostics --oc /Volumes/EFI/EFI/OC for the diagnostic kext."
    exit 1
fi

build=$(grep -m1 '"phx-build"' <<<"$IOR" | grep -oE '[0-9]+$' || true)
if [ -n "$build" ]; then say "  ✓ PhxBringup.kext is loaded (build $build)"
else fail "PhxBringup.kext is not loaded: add EFI/OC/Kexts/PhxBringup.kext to OpenCore and reboot first"; fi
if grep -qE '"compatible" = <[^>]*"pci1002,(15bf|15c8|1900|1901)"' <<<"$IOR"; then say "  ✓ Radeon 780M/760M found"
else say "  ! no Radeon 780M/760M (1002:15bf/15c8/1900/1901) found: other GPUs are not supported"; fi
for f in EFI/OC/Kexts/PhxBringup.kext Library/Extensions/PhxAccel.kext PhxGPU/NVMTLDriver.bundle PhxGPU/nvmtl/libvulkan_radeon.dylib \
         gpu/phxboot.sh gpu/full.sh gpu/bringup5.sh gpu/kinst.sh gpu/phxctl/phxctl gpu/phxctl/mesboot gpu/phxctl/phxfw gpu/phxctl/phxprofile gpu/local.phxboot.plist; do
    [ -e "$SRC/$f" ] || fail "package file $f is missing"
done
if [ -x "$SRC/gpu/phxctl/phxfw" ]; then
    "$SRC/gpu/phxctl/phxfw" --phoenix-plan "$SRC/gpu/fw" >/dev/null || fail "firmware header/range/staging preflight failed"
else fail "firmware planner is missing or not executable"; fi
[ $FAILED = 0 ] || { say "Fix the items marked ✗ and run it again."; exit 1; }
[ $CHECK = 1 ] && { say "All checks passed; nothing was changed (--check)."; exit 0; }

say "== GPU bring-up -> $G"
mkdir -p "$G/phxctl" "$G/fw" "$G/backup"
for f in phxboot.sh full.sh bringup5.sh kinst.sh; do install -m 755 "$SRC/gpu/$f" "$G/$f"; done
install -m 755 "$SRC/gpu/phxctl/phxctl" "$SRC/gpu/phxctl/mesboot" "$SRC/gpu/phxctl/phxfw" "$SRC/gpu/phxctl/phxprofile" "$G/phxctl/"
install -m 644 "$SRC"/gpu/fw/*.bin "$G/fw/"
chown -R root:wheel "$G"
rm -f "$G/phxboot-off" /var/db/phxboot.pending

say "== PhxAccel.kext -> Auxiliary kernel collection"
rm -rf /Library/Extensions/PhxAccel.kext
ditto "$SRC/Library/Extensions/PhxAccel.kext" /Library/Extensions/PhxAccel.kext
chown -R root:wheel /Library/Extensions/PhxAccel.kext; chmod -R go-w /Library/Extensions/PhxAccel.kext
BK="$G/backup" "$G/kinst.sh"

say "== Metal plugin -> $H"
mkdir -p "$H"
for n in NVMTLDriver.bundle nvmtl; do
    rm -rf "$H/.$n.new"; ditto "$SRC/PhxGPU/$n" "$H/.$n.new"
    # caches the plugin keeps next to the driver survive an upgrade
    if [ "$n" = nvmtl ]; then
        for c in aircache spvcache; do if [ -d "$H/nvmtl/$c" ]; then mv "$H/nvmtl/$c" "$H/.$n.new/"; fi; done
    fi
    # running processes keep the copy they mapped: move the old one aside instead of writing over it
    [ -e "$H/$n" ] && mv "$H/$n" "$H/.$n.old.$TS"
    mv "$H/.$n.new" "$H/$n"
    rm -rf "$H/.$n.old.$TS"
done
chown -R root:wheel "$H"
codesign --force --sign - "$H/NVMTLDriver.bundle" >/dev/null 2>&1
codesign --verify --strict "$H/NVMTLDriver.bundle" && say "  plugin signature ok"
mkdir -p "$L"
for n in NVMTLDriver.bundle nvmtl; do
    if [ -e "$L/$n" ] && [ ! -L "$L/$n" ]; then mkdir -p "/Library/GPUBundles-backup/$TS"; mv "$L/$n" "/Library/GPUBundles-backup/$TS/"; fi
    ln -sfn "$H/$n" "$L/$n"
done
# phxboot writes the real list at every boot; until then only the built-in test tools get the device
printf '# phxboot: Metal for the built-in test tools only\n' > "$L/nvmtl-allow.txt"; chmod 644 "$L/nvmtl-allow.txt"

say "== LaunchDaemon local.phxboot"
install -m 644 -o root -g wheel "$SRC/gpu/local.phxboot.plist" /Library/LaunchDaemons/local.phxboot.plist

if [ $WS = 1 ]; then
    touch "$G/phxboot-m2"
    say "== WindowServer on the GPU: on from the second boot (the first one checks the GPU comes up)"
else
    rm -f "$G/phxboot-m2"; nvram -d phxfb-boot 2>/dev/null || true
fi

say ""
say "Installed. Reboot now; /var/log/phxboot.log ends with \"done\" once the GPU is up."
say "Turn on automatic login (System Settings -> Users & Groups) if you used --windowserver."
