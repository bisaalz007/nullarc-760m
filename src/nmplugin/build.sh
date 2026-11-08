#!/bin/bash
# SPDX-License-Identifier: MIT
# Compile the fork's entire one-translation-unit Metal plugin; no system installation.
# Usage: build.sh <Vulkan-Headers checkout/include directory>
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
HDR=$(cd "${1:?provide Vulkan-Headers}" && pwd)
[ ! -d "$HDR/include/vulkan" ] || HDR="$HDR/include"
[ -f "$HDR/vulkan/vulkan_core.h" ] || { echo 'missing Vulkan headers' >&2; exit 1; }
SDK_VERSION=$(xcrun --sdk macosx --show-sdk-version)
[ "${SDK_VERSION%%.*}" -ge 26 ] || { echo 'Tahoe SDK 26 or newer required' >&2; exit 1; }
MIN_MACOS=${NULLARC_MIN_MACOS:-26.0}
case "$MIN_MACOS" in 15.0|26.0) ;; *) echo 'Supported deployment targets: 15.0 or 26.0' >&2; exit 1;; esac
OUT="$HERE/build/NVMTLDriver.bundle"
mkdir -p "$OUT/Contents/MacOS"
xcrun clang -arch x86_64 -mmacosx-version-min="$MIN_MACOS" -bundle -fobjc-arc -O1 -Werror=unguarded-availability-new \
  -Wno-protocol -Wno-incomplete-implementation -I"$HDR" \
  "$HERE/NVMTLDevice.m" -o "$OUT/Contents/MacOS/NVMTLDriver.new" \
  -framework Foundation -framework Metal -framework IOSurface -framework MetalFX -framework IOKit
mv "$OUT/Contents/MacOS/NVMTLDriver.new" "$OUT/Contents/MacOS/NVMTLDriver"
cp "$HERE/Info.plist" "$OUT/Contents/Info.plist"
/usr/libexec/PlistBuddy -c "Set :LSMinimumSystemVersion $MIN_MACOS" "$OUT/Contents/Info.plist"
codesign --force --sign - "$OUT"
echo "Built source Metal plugin: $OUT (runtime dependencies assembled separately)"
